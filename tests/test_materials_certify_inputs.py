#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""PAC-Bayes certification input contract — szl_materials.register_certify.

Doctrine v11: RECEIPT-ON-WRITE, NOT ON-READ, and no receipt for a request that
then fails. These tests drive the /materials/certify surface on a fresh FastAPI
app with counting test doubles installed in sys.modules for szl_khipu, szl_dsse
and szl_lake_ingest. The doubles never sign, never write and never touch the
network; every rejection and every read path must leave all counters at zero.

Pinned behaviour (fails on origin/main — szl_materials.py blob 78c38450 — and
passes with the fix):
  - n is a JSON integer: 1000.9, true, "1000", 1000.0 and 10**400 are rejected
    (main truncated 1000.9 -> 1000 and coerced true -> 1); n >= 8 (Maurer 2004).
  - empirical_risk in [0,1], kl finite and >= 0, delta in (0,1); NaN/Infinity are
    rejected (main minted a receipt for kl=NaN and THEN answered 400).
  - delta small enough that 2*sqrt(n)/delta overflows a double (below about
    3.1e-308 for n=8, 3.5e-307 for n=1000, 1.1e-300 for n=2**53) is a 400 with no
    receipt (main receipted the +inf bound and then failed to serialize).
  - risk_units must equal the module's normalized dimensionless-loss label; a
    caller label such as "eV/atom" never reaches the signed certificate_text.
  - model is a short printable string label and family/preset must name a
    preset; a body carries either explicit inputs or a preset, never both (main
    receipted a dict / 200 kB string / nested array as `model`, "eV/atom" as
    `family`, and silently ignored invalid explicit keys beside a preset).
  - GET /materials/certify is 405 + Allow: POST and mints nothing (main resolved
    ?query inputs and emitted a receipt on that read path).
  - certificate_text names the Maurer (2004) form and never says "exact".

Unchanged behaviour (also holds on main): preset bound values equal the shared
formula evaluated in-process on the pinned preset inputs and agree with the
floats observed at origin/main to within a few ulp (see the lane log), each
valid POST emits exactly one receipt, GET /materials/certify/presets is 200
with zero emits.
"""
import importlib
import json
import math
import os
import sys
import types

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import fastapi  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

PREFIXES = ["/api/a11oy/v1/materials", "/v1/materials"]
RISK_UNITS = "normalized risk (dimensionless, [0,1])"
DBL_MAX = sys.float_info.max
# Bit-exactness is asserted against the shared formula evaluated in this process
# (same libm); the literals observed on the wire at origin/main (lane log
# a11oy-certify-inputs-repro-head.log, Windows UCRT) are checked to a few ulp so
# a correctly-rounded-vs-not math.log on another platform cannot flip the test.
ULP_TOL = 4 * sys.float_info.epsilon

PRESET_BOUNDS_AT_HEAD = {
    "oxides": 0.050769757934289464,
    "intermetallics": 0.07720510333475361,
    "refractory_hea": 0.11793891851419469,
}
PRESET_INPUTS_AT_HEAD = {
    "oxides": {"empirical_risk": 0.04, "kl": 2.5, "n": 50000, "delta": 0.05},
    "intermetallics": {"empirical_risk": 0.06, "kl": 3.2, "n": 20000, "delta": 0.05},
    "refractory_hea": {"empirical_risk": 0.09, "kl": 5.0, "n": 8000, "delta": 0.1},
}
EXPLICIT_VALID = {"empirical_risk": 0.1, "kl": 1.0, "n": 1000, "delta": 0.05}
EXPLICIT_VALID_BOUND_AT_HEAD = 0.1638073549585195
RECEIPT_INPUT_KEYS = {"empirical_risk", "kl", "n", "delta", "source", "family",
                      "model", "risk_units", "input_label"}

FAKE_MODULES = ("szl_khipu", "szl_dsse", "szl_lake_ingest")


def _real_bound(**inputs):
    import szl_formulas
    return szl_formulas.pac_bayes_mcallester(
        inputs["empirical_risk"], inputs["kl"], inputs["n"], inputs["delta"])


# --------------------------------------------------------------------------- #
# Counting test doubles. The khipu double mirrors the real KhipuDAG surface the
# module uses (get_dag / emit / head / depth / verify_chain) but only counts and
# keeps the payloads it was handed. The signer and ledger doubles count AND
# raise: a stray call must be loud.
# --------------------------------------------------------------------------- #
class _FakeDAG:
    def __init__(self, calls, organ, ns):
        self._calls, self.organ, self.ns, self._chain = calls, organ, ns, []

    def emit(self, action, payload=None):
        self._calls["khipu_emit"] += 1
        self._calls["emit_actions"].append(action)
        self._calls["payloads"].append(payload)
        r = {"organ": self.organ, "ns": self.ns, "seq": len(self._chain),
             "action": action, "payload_digest": f"fake-payload-{len(self._chain)}",
             "prev": self._chain[-1]["digest"] if self._chain else "0" * 64,
             "digest": f"fake-digest-{len(self._chain)}",
             "signature": "FAKE_NEVER_SIGNED", "chain_verified": True}
        self._chain.append(r)
        return r

    def head(self):
        return self._chain[-1]["digest"] if self._chain else "0" * 64

    def depth(self):
        return len(self._chain)

    def verify_chain(self):
        return {"ok": True, "depth": len(self._chain), "broken_at": None}


def _install_fakes():
    calls = {"khipu_emit": 0, "get_dag": 0, "dsse_sign": 0, "lake_write": 0,
             "emit_actions": [], "payloads": []}
    dags = {}

    def _get_dag(organ, ns="a11oy"):
        calls["get_dag"] += 1
        return dags.setdefault(f"{ns}/{organ}", _FakeDAG(calls, organ, ns))

    khipu = types.ModuleType("szl_khipu")
    khipu.get_dag = _get_dag
    khipu.KhipuDAG = _FakeDAG

    def _sign(*_a, **_k):
        calls["dsse_sign"] += 1
        raise AssertionError("szl_dsse must never be called by the certify surface")

    dsse = types.ModuleType("szl_dsse")
    for name in ("sign", "sign_statement", "sign_envelope", "sign_receipt"):
        setattr(dsse, name, _sign)

    def _write(*_a, **_k):
        calls["lake_write"] += 1
        raise AssertionError("szl_lake_ingest must never be called by the certify surface")

    lake = types.ModuleType("szl_lake_ingest")
    for name in ("record_receipt", "ingest", "append", "write"):
        setattr(lake, name, _write)

    sys.modules["szl_khipu"] = khipu
    sys.modules["szl_dsse"] = dsse
    sys.modules["szl_lake_ingest"] = lake
    return calls


@pytest.fixture
def surface():
    """Fresh module state + fresh app + counting doubles for one test."""
    saved = {name: sys.modules.get(name) for name in FAKE_MODULES}
    calls = _install_fakes()
    import szl_materials
    mat = importlib.reload(szl_materials)
    app = fastapi.FastAPI()
    mat.register(app, ns="a11oy")
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client, calls, mat
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


def _post(client, prefix, body):
    # json.dumps with allow_nan=True puts the NaN / Infinity literals on the wire
    # exactly as a permissive client would; Starlette's request.json() accepts them.
    return client.post(f"{prefix}/certify", content=json.dumps(body, allow_nan=True),
                       headers={"content-type": "application/json"})


def _assert_nothing_emitted(calls):
    assert calls["khipu_emit"] == 0, calls
    assert calls["dsse_sign"] == 0, calls
    assert calls["lake_write"] == 0, calls


def _assert_bound_unchanged(observed, expected_in_process, literal_at_head):
    assert observed == expected_in_process, (observed, expected_in_process)
    assert math.isclose(observed, literal_at_head, rel_tol=ULP_TOL, abs_tol=0.0), (
        observed, literal_at_head)


# --------------------------------------------------------------------------- #
# Rejections: HTTP 400, ok=false, zero emits, and the error names the field.
# --------------------------------------------------------------------------- #
REJECTED_N = [
    pytest.param(1000.9, id="n-fractional-1000.9"),
    pytest.param(1000.0, id="n-float-1000.0"),
    pytest.param(True, id="n-bool-true"),
    pytest.param("1000", id="n-numeric-string"),
    pytest.param(7, id="n-below-maurer-minimum-7"),
    pytest.param(0, id="n-zero"),
    pytest.param(10 ** 400, id="n-10e400-overflow"),
]


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("n", REJECTED_N)
def test_rejects_non_integer_or_out_of_range_n(surface, prefix, n):
    client, calls, _ = surface
    r = _post(client, prefix, {**EXPLICIT_VALID, "n": n})
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["ok"] is False
    assert "n must" in body["error"], body["error"]
    _assert_nothing_emitted(calls)


REJECTED_FIELDS = [
    pytest.param("kl", float("nan"), id="kl-nan"),
    pytest.param("kl", float("inf"), id="kl-inf"),
    pytest.param("kl", -1.0, id="kl-negative"),
    pytest.param("kl", True, id="kl-bool"),
    pytest.param("kl", "1.0", id="kl-string"),
    pytest.param("empirical_risk", float("nan"), id="risk-nan"),
    pytest.param("empirical_risk", float("inf"), id="risk-inf"),
    pytest.param("empirical_risk", -0.5, id="risk-negative"),
    pytest.param("empirical_risk", 1.5, id="risk-above-one"),
    pytest.param("empirical_risk", True, id="risk-bool"),
    pytest.param("delta", 0.0, id="delta-zero"),
    pytest.param("delta", 1.0, id="delta-one"),
    pytest.param("delta", float("nan"), id="delta-nan"),
    pytest.param("delta", False, id="delta-bool"),
]


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("field,value", REJECTED_FIELDS)
def test_rejects_non_finite_or_out_of_range_numbers(surface, prefix, field, value):
    client, calls, _ = surface
    r = _post(client, prefix, {**EXPLICIT_VALID, field: value})
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["ok"] is False
    assert field in body["error"], body["error"]
    _assert_nothing_emitted(calls)


# delta values that pass the (0,1) check but make 2*sqrt(n)/delta overflow a
# double inside the shared formula: ln(+inf) = +inf, bound = +inf. On main the
# +inf bound was receipted and then failed to serialize; before this fix round
# it was a 500 with no receipt; now it is a 400 with no receipt.
OVERFLOWING_DELTA = [
    pytest.param(1000, 1e-320, id="n1000-delta1e-320-subnormal"),
    pytest.param(1000, 5e-324, id="n1000-delta-smallest-subnormal"),
    pytest.param(8, 1e-308, id="n8-delta1e-308"),
    pytest.param(1000, 3.5e-307, id="n1000-delta3.5e-307"),
    pytest.param(2 ** 53, 1e-300, id="n2e53-delta1e-300"),
]


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("n,delta", OVERFLOWING_DELTA)
def test_rejects_delta_that_overflows_the_complexity_term(surface, prefix, n, delta):
    client, calls, _ = surface
    assert 0.0 < delta < 1.0 and math.isfinite(delta)  # it IS inside (0,1)
    assert not math.isfinite(2.0 * math.sqrt(n) / delta)  # ... and still overflows
    r = _post(client, prefix, {**EXPLICIT_VALID, "n": n, "delta": delta})
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["ok"] is False
    assert "delta is too small" in body["error"], body["error"]
    assert "2*sqrt(n)/delta" in body["error"]
    _assert_nothing_emitted(calls)
    assert calls["get_dag"] == 0


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("n,delta", [
    pytest.param(8, 1e-307, id="n8-delta1e-307"),
    pytest.param(1000, 3.6e-307, id="n1000-delta3.6e-307"),
    pytest.param(2 ** 53, 1.1e-300, id="n2e53-delta1.1e-300"),
])
def test_delta_just_above_the_overflow_threshold_is_certified_once(surface, prefix, n, delta):
    client, calls, _ = surface
    r = _post(client, prefix, {**EXPLICIT_VALID, "n": n, "delta": delta})
    assert r.status_code == 200, r.text
    body = r.json()
    assert math.isfinite(body["bound"])
    assert body["bound"] == _real_bound(**{**EXPLICIT_VALID, "n": n, "delta": delta})
    assert calls["khipu_emit"] == 1


def test_validated_inputs_never_yield_a_non_finite_bound_with_the_real_formula(surface):
    """Supports the defence-in-depth comment in _do_certify: once the validator
    has accepted (er, kl, n, delta), the shared formula's intermediates are all
    finite — including kl = DBL_MAX at the smallest admissible delta."""
    _, _, mat = surface
    for n in (8, 1000, 2 ** 53):
        threshold = 2.0 * math.sqrt(n) / DBL_MAX
        smallest_ok = math.nextafter(threshold, 1.0)
        just_below = math.nextafter(threshold, 0.0)
        with pytest.raises(ValueError, match="delta is too small"):
            mat._validate_pacbayes_inputs(0.1, 1.0, n, just_below)
        for er in (0.0, 1.0):
            for kl in (0.0, 1.0, DBL_MAX):
                for delta in (smallest_ok, 0.5, math.nextafter(1.0, 0.0)):
                    v_er, v_kl, v_n, v_delta = mat._validate_pacbayes_inputs(er, kl, n, delta)
                    bound = _real_bound(empirical_risk=v_er, kl=v_kl, n=v_n, delta=v_delta)
                    assert math.isfinite(bound), (er, kl, n, delta, bound)


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("units", ["eV/atom", "meV/atom", "", "NORMALIZED RISK",
                                   "normalized risk (dimensionless, [0,1]) unless "
                                   "otherwise specified by caller"])
def test_rejects_any_risk_units_other_than_the_bounded_loss_label(surface, prefix, units):
    client, calls, _ = surface
    r = _post(client, prefix, {**EXPLICIT_VALID, "risk_units": units})
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["ok"] is False
    assert "risk_units" in body["error"]
    assert "[0,1]" in body["error"]
    _assert_nothing_emitted(calls)


@pytest.mark.parametrize("prefix", PREFIXES)
def test_rejects_caller_units_on_a_preset_too(surface, prefix):
    client, calls, _ = surface
    r = _post(client, prefix, {"family": "oxides", "risk_units": "eV/atom"})
    assert r.status_code == 400, r.text
    assert "risk_units" in r.json()["error"]
    _assert_nothing_emitted(calls)


@pytest.mark.parametrize("prefix", PREFIXES)
def test_kl_nan_never_reaches_the_formula_or_the_chain(surface, prefix):
    """On main the shared pac_bayes_mcallester swallowed NaN (max(0.0, nan) == 0.0),
    the bound collapsed to empirical_risk, a receipt was emitted and only THEN did
    the response fail to serialize -> 400. Now: 400 first, nothing emitted."""
    client, calls, _ = surface
    r = _post(client, prefix, {**EXPLICIT_VALID, "kl": float("nan")})
    assert r.status_code == 400
    assert "kl" in r.json()["error"]
    assert "not JSON compliant" not in r.json()["error"]
    _assert_nothing_emitted(calls)
    assert calls["get_dag"] == 0


# `model` and `family`/`preset` are copied into the signed receipt, so they are
# validated like everything else: model is a short printable string label,
# family/preset must name a preset. On main all of these were receipted verbatim.
_NESTED = []
for _ in range(200):
    _NESTED = [_NESTED]

REJECTED_LABELS = [
    pytest.param("model", {"claim": "Lambda uniqueness THEOREM", "locked": 12}, id="model-dict"),
    pytest.param("model", "x" * 200000, id="model-200k-chars"),
    pytest.param("model", "x" * 129, id="model-129-chars"),
    pytest.param("model", _NESTED, id="model-200-deep-nested-list"),
    pytest.param("model", True, id="model-bool"),
    pytest.param("model", 12345, id="model-int"),
    pytest.param("model", float("nan"), id="model-nan"),
    pytest.param("model", "surrogate\x00v2", id="model-control-char"),
    pytest.param("model", "", id="model-empty"),
    pytest.param("model", "   ", id="model-blank"),
    pytest.param("family", {"eV/atom": True}, id="family-dict"),
    pytest.param("family", "eV/atom", id="family-eV-per-atom"),
    pytest.param("family", ["oxides"], id="family-list"),
    pytest.param("preset", 123, id="preset-int"),
    pytest.param("preset", "unknown", id="preset-unknown"),
]


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("field,value", REJECTED_LABELS)
def test_rejects_labels_that_are_not_short_printable_strings_or_preset_names(
        surface, prefix, field, value):
    client, calls, _ = surface
    r = _post(client, prefix, {**EXPLICIT_VALID, field: value})
    assert r.status_code == 400, r.text
    body = r.json()
    assert body["ok"] is False
    assert field in body["error"], body["error"]
    _assert_nothing_emitted(calls)
    assert calls["get_dag"] == 0


MIXED_BODIES = [
    pytest.param({"family": "oxides", "n": "junk"}, id="preset-plus-stray-n"),
    pytest.param({"family": "oxides", "empirical_risk": 0.1, "kl": 1.0, "n": 1000.9},
                 id="preset-plus-partial-explicit"),
    pytest.param({"family": "oxides", **EXPLICIT_VALID}, id="preset-plus-full-explicit"),
    pytest.param({"preset": "oxides", **EXPLICIT_VALID}, id="preset-key-plus-full-explicit"),
    pytest.param({"family": "oxides", "preset": "intermetallics"}, id="family-preset-disagree"),
]


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("body", MIXED_BODIES)
def test_rejects_bodies_that_mix_a_preset_with_explicit_keys(surface, prefix, body):
    """On main a preset silently won over stray or invalid explicit keys, and
    explicit values were receipted under a preset's name. Either/or now."""
    client, calls, _ = surface
    r = _post(client, prefix, body)
    assert r.status_code == 400, r.text
    assert r.json()["ok"] is False
    _assert_nothing_emitted(calls)
    assert calls["get_dag"] == 0


@pytest.mark.parametrize("prefix", PREFIXES)
def test_rejection_errors_do_not_echo_huge_caller_values(surface, prefix):
    client, calls, _ = surface
    for body in ({**EXPLICIT_VALID, "risk_units": "u" * 100000},
                 {**EXPLICIT_VALID, "model": "m" * 100000},
                 {"family": "f" * 100000}):
        r = _post(client, prefix, body)
        assert r.status_code == 400, r.text
        assert len(r.json()["error"]) < 512, len(r.json()["error"])
    _assert_nothing_emitted(calls)


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("body", [{}, {"family": "unknown"}, {"n": 1000},
                                  {"empirical_risk": 0.1, "kl": 1.0, "n": 1000},
                                  {"family": ["oxides"]}, [1, 2, 3], "oxides"])
def test_missing_or_malformed_bodies_are_400_with_no_receipt(surface, prefix, body):
    client, calls, _ = surface
    r = _post(client, prefix, body)
    assert r.status_code == 400, r.text
    assert r.json()["ok"] is False
    _assert_nothing_emitted(calls)


def test_validator_contract_directly(surface):
    _, _, mat = surface
    ok = mat._validate_pacbayes_inputs(0.1, 1.0, 1000, 0.05)
    assert ok == (0.1, 1.0, 1000, 0.05)
    assert isinstance(ok[2], int)
    for bad in [(True, 1.0, 1000, 0.05), (0.1, 1.0, 1000.9, 0.05),
                (0.1, 1.0, True, 0.05), (0.1, 1.0, "1000", 0.05),
                (0.1, 1.0, 7, 0.05), (0.1, 1.0, 2 ** 53 + 1, 0.05),
                (0.1, math.nan, 1000, 0.05), (0.1, -1.0, 1000, 0.05),
                (1.5, 1.0, 1000, 0.05), (0.1, 1.0, 1000, 1.0),
                (0.1, 1.0, 1000, 1e-320), (0.1, 1.0, 8, 1e-308)]:
        with pytest.raises(ValueError):
            mat._validate_pacbayes_inputs(*bad)
    assert mat._validate_pacbayes_inputs(0.0, 0.0, 8, 0.5)[2] == 8
    assert mat._validate_pacbayes_inputs(1.0, 0.0, 2 ** 53, 0.5)[2] == 2 ** 53
    assert mat._validate_pacbayes_inputs(0.1, 1.0, 8, 1e-307)[3] == 1e-307
    with pytest.raises(ValueError):
        mat._pacbayes_risk_units("eV/atom")
    assert mat._pacbayes_risk_units(None) == RISK_UNITS == mat._PACBAYES_RISK_UNITS
    assert mat._pacbayes_model_label(None) is None
    assert mat._pacbayes_model_label("surrogate-v2") == "surrogate-v2"
    for bad_label in ({"a": 1}, ["x"], True, 1, "", " ", "a\x07b", "x" * 129):
        with pytest.raises(ValueError):
            mat._pacbayes_model_label(bad_label)
    assert mat._pacbayes_family(None) is None
    assert mat._pacbayes_family("oxides") == "oxides"
    for bad_family in ("eV/atom", {"oxides": 1}, ["oxides"], 1, True):
        with pytest.raises(ValueError):
            mat._pacbayes_family(bad_family)


# --------------------------------------------------------------------------- #
# Valid writes: exactly one receipt, unchanged preset bounds, honest wording.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("family", sorted(PRESET_BOUNDS_AT_HEAD))
def test_valid_preset_post_emits_exactly_once_with_unchanged_bound(surface, prefix, family):
    client, calls, _ = surface
    r = _post(client, prefix, {"family": family})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert math.isfinite(body["bound"])
    _assert_bound_unchanged(body["bound"], _real_bound(**PRESET_INPUTS_AT_HEAD[family]),
                            PRESET_BOUNDS_AT_HEAD[family])
    for k, v in PRESET_INPUTS_AT_HEAD[family].items():
        assert body["inputs"][k] == v
    assert isinstance(body["inputs"]["n"], int)
    assert body["inputs"]["source"] == "preset"
    assert body["inputs"]["risk_units"] == RISK_UNITS
    assert body["receipt"]["receipt_type"] == "SZL.Materials.PACBayesCert.v1"
    assert r.headers["x-szl-receipt-digest"] == body["receipt"]["digest"]
    assert r.headers["x-szl-materials-bound"] == f"{body['bound']:.6g}"
    assert calls["khipu_emit"] == 1
    assert calls["emit_actions"] == ["materials.certify"]
    assert calls["dsse_sign"] == 0 and calls["lake_write"] == 0


@pytest.mark.parametrize("prefix", PREFIXES)
def test_valid_explicit_post_emits_exactly_once_with_unchanged_bound(surface, prefix):
    client, calls, _ = surface
    r = _post(client, prefix, EXPLICIT_VALID)
    assert r.status_code == 200, r.text
    body = r.json()
    _assert_bound_unchanged(body["bound"], _real_bound(**EXPLICIT_VALID),
                            EXPLICIT_VALID_BOUND_AT_HEAD)
    assert body["inputs"]["n"] == 1000 and isinstance(body["inputs"]["n"], int)
    assert body["inputs"]["source"] == "explicit"
    assert body["inputs"]["risk_units"] == RISK_UNITS
    assert calls["khipu_emit"] == 1


@pytest.mark.parametrize("prefix", PREFIXES)
def test_explicit_post_with_the_bounded_loss_label_is_accepted(surface, prefix):
    client, calls, _ = surface
    r = _post(client, prefix, {**EXPLICIT_VALID, "risk_units": RISK_UNITS})
    assert r.status_code == 200, r.text
    assert r.json()["inputs"]["risk_units"] == RISK_UNITS
    assert calls["khipu_emit"] == 1


@pytest.mark.parametrize("prefix", PREFIXES)
def test_accepted_labels_are_receipted_verbatim_and_unknown_keys_are_not(surface, prefix):
    """A preset with a sane `model` label and provenance-shaped extra keys (the
    shape szl_provenance_receipt._compose_pac_bayes forwards) still certifies;
    the receipt carries exactly the validated fields and nothing else."""
    client, calls, _ = surface
    r = _post(client, prefix, {"family": "oxides", "model": "my-surrogate-v2",
                               "action": {"kind": "provenance"}, "request_id": "r-1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["inputs"]["family"] == "oxides"
    assert body["inputs"]["model"] == "my-surrogate-v2"
    assert set(body["inputs"]) == RECEIPT_INPUT_KEYS
    assert calls["khipu_emit"] == 1
    receipt_inputs = calls["payloads"][0]["inputs"]
    assert set(receipt_inputs) == RECEIPT_INPUT_KEYS
    assert receipt_inputs["model"] == "my-surrogate-v2"
    assert "action" not in json.dumps(calls["payloads"][0])
    assert "r-1" not in json.dumps(calls["payloads"][0])
    # Explicit inputs with a label: family is never a tag on the explicit path.
    r2 = _post(client, prefix, {**EXPLICIT_VALID, "model": "surrogate-v2"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["inputs"]["model"] == "surrogate-v2"
    assert r2.json()["inputs"]["family"] is None
    assert r2.json()["inputs"]["source"] == "explicit"
    assert calls["khipu_emit"] == 2


@pytest.mark.parametrize("prefix", PREFIXES)
def test_model_shorthand_and_preset_key_still_select_the_preset(surface, prefix):
    client, calls, _ = surface
    r = _post(client, prefix, {"model": "oxides"})
    assert r.status_code == 200, r.text
    assert r.json()["inputs"]["family"] == "oxides"
    assert r.json()["inputs"]["source"] == "preset"
    assert r.json()["bound"] == _real_bound(**PRESET_INPUTS_AT_HEAD["oxides"])
    r = _post(client, prefix, {"preset": "intermetallics"})
    assert r.status_code == 200, r.text
    assert r.json()["inputs"]["family"] == "intermetallics"
    assert r.json()["bound"] == _real_bound(**PRESET_INPUTS_AT_HEAD["intermetallics"])
    r = _post(client, prefix, {"family": "oxides", "preset": "oxides"})
    assert r.status_code == 200, r.text
    assert calls["khipu_emit"] == 3


@pytest.mark.parametrize("prefix", PREFIXES)
def test_maurer_minimum_n_is_the_boundary(surface, prefix):
    client, calls, _ = surface
    assert _post(client, prefix, {**EXPLICIT_VALID, "n": 7}).status_code == 400
    assert calls["khipu_emit"] == 0
    r = _post(client, prefix, {**EXPLICIT_VALID, "n": 8})
    assert r.status_code == 200, r.text
    assert r.json()["inputs"]["n"] == 8
    assert calls["khipu_emit"] == 1


@pytest.mark.parametrize("prefix", PREFIXES)
def test_certificate_text_names_the_maurer_form_and_never_claims_exactness(surface, prefix):
    client, _, _ = surface
    for body in ({"family": "oxides"}, EXPLICIT_VALID):
        r = _post(client, prefix, body)
        assert r.status_code == 200, r.text
        js = r.json()
        text = js["certificate_text"]
        assert "exact" not in text.lower()
        assert "Maurer (2004)" in text
        assert "McAllester" in text
        assert "IEEE-754 double precision" in text
        assert "fixed data-generating distribution" in text
        assert "eV/atom" not in text
        assert f"({RISK_UNITS})" in text
        # The whole wire payload is free of the retired exactness claim.
        assert "exact" not in json.dumps(js).lower()


def test_preset_vectors_are_bit_exact_in_source(surface):
    _, _, mat = surface
    for fam, want in PRESET_INPUTS_AT_HEAD.items():
        p = mat._PACBAYES_PRESETS[fam]
        for k, v in want.items():
            assert p[k] == v and type(p[k]) is type(v), (fam, k, p[k])
        assert p["risk_units"] == RISK_UNITS


# --------------------------------------------------------------------------- #
# Defence in depth: the non-finite-bound guard in _do_certify is not reached by
# validated inputs with the real formula (see
# test_validated_inputs_never_yield_a_non_finite_bound_with_the_real_formula),
# so it is exercised by faking the shared formula module. It must still never
# mint a receipt.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_bound_from_the_formula_never_mints_a_receipt(surface, bad):
    client, calls, _ = surface
    saved = sys.modules.get("szl_formulas")
    fake = types.ModuleType("szl_formulas")
    fake.pac_bayes_mcallester = lambda *_a, **_k: bad
    sys.modules["szl_formulas"] = fake
    try:
        r = _post(client, PREFIXES[0], EXPLICIT_VALID)
    finally:
        if saved is None:
            sys.modules.pop("szl_formulas", None)
        else:
            sys.modules["szl_formulas"] = saved
    assert r.status_code == 500, r.text
    assert r.json()["ok"] is False
    assert "no receipt minted" in r.json()["error"]
    _assert_nothing_emitted(calls)
    assert calls["get_dag"] == 0


# --------------------------------------------------------------------------- #
# Read paths: never a receipt.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("params", [None, {"family": "oxides"},
                                    {"empirical_risk": "0.1", "kl": "1.0",
                                     "n": "1000", "delta": "0.05"}])
def test_get_certify_is_405_with_usage_and_mints_nothing(surface, prefix, params):
    client, calls, _ = surface
    r = client.get(f"{prefix}/certify", params=params)
    assert r.status_code == 405, r.text
    assert r.headers["allow"] == "POST"
    body = r.json()
    assert body["ok"] is False
    assert body["usage"]["method"] == "POST"
    assert body["usage"]["read_only_presets"] == f"GET {prefix}/certify/presets"
    assert "bound" not in body
    _assert_nothing_emitted(calls)
    assert calls["get_dag"] == 0


@pytest.mark.parametrize("prefix", PREFIXES)
def test_get_presets_is_read_only_and_bit_exact(surface, prefix):
    client, calls, _ = surface
    r = client.get(f"{prefix}/certify/presets")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["count"] == 3
    for fam, want in PRESET_INPUTS_AT_HEAD.items():
        for k, v in want.items():
            assert body["presets"][fam][k] == v
        assert body["presets"][fam]["risk_units"] == RISK_UNITS
    assert "exact" not in json.dumps(body).lower()
    _assert_nothing_emitted(calls)
    assert calls["get_dag"] == 0
