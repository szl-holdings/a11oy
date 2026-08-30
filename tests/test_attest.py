"""L6 chain-of-title attestation organ — honesty + policy gate (Wave 32 Dev E).

Guards the invariants that make szl_attest worth signing:

  * the in-toto v1 Statement builds with the SZL predicateType and a subject
    that binds the locked-8 kernel gitCommit;
  * an absent sovereign-weights artifact yields an HONEST NULL, never an
    invented digest, and never a subject entry with an empty digest set;
  * ``energy_measured`` is EMPTY with no live joule meter — no fabricated joule;
  * the Statement DSSE-signs through szl_dsse (and reports UNSIGNED-NO-KEY
    honestly when no runtime cosign secret is present — never a fake signature);
  * verify() returns PASSED on a valid Statement, FAILED on a tampered one, and
    UNKNOWN when a REQUIRED Rekor inclusion proof cannot be obtained;
  * no code path fabricates a Rekor entry, log index, or inclusion proof;
  * the in-process policy stays in lockstep with ops/szl_chain_of_title.rego;
  * both endpoints answer 200 through the REAL app (TestClient, no mocks) and
    resolve ahead of the pre-existing parametrized /attest/{receipt_hash} route.

Doctrine v11: never fabricate PASSED / MEASURED / a Rekor entry; UNKNOWN when
unreachable; Λ = Conjecture 1, never a theorem; locked-8 immutable.
"""
import json
import re
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")

import szl_attest as A  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REGO = ROOT / "ops" / "szl_chain_of_title.rego"


# --------------------------------------------------------------------------- #
# Statement construction
# --------------------------------------------------------------------------- #
def test_statement_builds_as_intoto_v1_with_szl_predicate_type():
    stmt = A.build_statement()
    assert stmt["_type"] == "https://in-toto.io/Statement/v1"
    assert stmt["predicateType"] == "https://szl.dev/chain-of-title/v1"
    assert stmt["predicate"]["doctrine"] == "v11"


def test_subject_binds_non_empty_locked8_kernel_commit():
    stmt = A.build_statement()
    kernels = [s for s in stmt["subject"] if s["name"] == "locked8_kernel"]
    assert len(kernels) == 1
    commit = kernels[0]["digest"]["gitCommit"]
    assert isinstance(commit, str) and commit.strip()
    assert commit == A.KERNEL_PIN == "c7c0ba17"
    # the locked-8 is attested, never extended
    assert kernels[0]["annotations"]["locked_proven"] == list(A.LOCKED_8)
    assert len(A.LOCKED_8) == 8


def test_every_subject_carries_at_least_one_digest():
    """in-toto requires a non-empty digest set; an absent subject is OMITTED,
    never emitted with an empty digest."""
    stmt = A.build_statement()
    for s in stmt["subject"]:
        assert isinstance(s["digest"], dict) and s["digest"]
        for value in s["digest"].values():
            assert isinstance(value, str) and value.strip()


def test_absent_sovereign_weights_is_honest_null_not_a_fabricated_digest(monkeypatch):
    monkeypatch.delenv(A.WEIGHTS_PATH_ENV, raising=False)
    weights = A.sovereign_weights_digest()
    if weights["present"]:
        pytest.skip("a real weights artifact is readable in this checkout")
    assert weights["sha256"] is None
    assert weights["path"] is None
    assert "honest null" in weights["note"]
    stmt = A.build_statement()
    assert stmt["predicate"]["provenance"]["sovereign_weights"]["sha256"] is None
    assert [s for s in stmt["subject"] if s["name"] == "sovereign_weights"] == []


def test_weights_digest_is_real_when_a_weights_artifact_exists(tmp_path, monkeypatch):
    """With a readable artifact the digest is the REAL sha256 of its bytes."""
    import hashlib

    blob = ROOT / "_attest_test_weights.bin"
    payload = b"szl-attest-test-weights"
    blob.write_bytes(payload)
    try:
        monkeypatch.setenv(A.WEIGHTS_PATH_ENV, blob.name)
        weights = A.sovereign_weights_digest()
        assert weights["present"] is True
        assert weights["sha256"] == hashlib.sha256(payload).hexdigest()
        stmt = A.build_statement()
        subs = [s for s in stmt["subject"] if s["name"] == "sovereign_weights"]
        assert len(subs) == 1
        assert subs[0]["digest"]["sha256"] == weights["sha256"]
    finally:
        blob.unlink(missing_ok=True)


def test_energy_measured_is_empty_with_no_live_meter(monkeypatch):
    monkeypatch.delenv(A.JOULE_METER_ENV, raising=False)
    readings, disclosure = A.energy_measured()
    assert readings == []
    assert disclosure["meters_configured"] == 0
    assert disclosure["label"] == "STRUCTURAL-ONLY"
    assert "no joule fabricated" in disclosure["note"]
    stmt = A.build_statement()
    assert stmt["predicate"]["energy_measured"] == []


def test_configured_but_unreachable_meter_still_yields_no_joule(monkeypatch):
    monkeypatch.setenv(A.JOULE_METER_ENV, "http://127.0.0.1:1/meter")

    def _boom(url, timeout):
        raise OSError("unreachable")

    readings, disclosure = A.energy_measured(opener=_boom)
    assert readings == []
    assert disclosure["label"] == "STRUCTURAL-ONLY"
    assert "no joule fabricated" in disclosure["note"]


def test_provenance_is_fully_disclosed_and_kernel_verification_is_real():
    prov = A.build_statement()["predicate"]["provenance"]
    assert prov["provenance_coverage"] == 1.0
    assert prov["kernel_pin"] == "c7c0ba17"
    # kernel_verified must come from an actual registry check, not a constant
    checks = prov["kernel_verification"]["checks"]
    assert set(checks) == {"registry_digest_verified", "locked8_covered",
                           "locked_set_not_inflated", "lambda_is_conjecture"}
    assert prov["kernel_verified"] is all(checks.values())
    # training config is READ from the committed trainer, not hard-coded here
    assert prov["training"]["source"] == "sovereign-weights/train_lora.py"
    assert prov["training"]["config"]["base_model"]


def test_honesty_invariants_and_lambda_are_bound_into_the_predicate():
    pred = A.build_statement()["predicate"]
    inv = pred["honesty_invariants"]
    assert inv["no_fabricated_measured"] is True
    assert inv["lambda_is_conjecture_not_theorem"] is True
    assert inv["locked8_immutable"] is True
    assert inv["provenance_coverage"] == 1.0
    assert pred["lambda"]["status"] == "Conjecture 1"
    assert pred["lambda"]["is_theorem"] is False
    assert pred["lambda"]["trust_ceiling"] == 0.97
    # the seal formula is never presented as validated
    assert pred["seal"]["tier"] == "PROPOSED"
    assert pred["seal"]["formula"] == "A=[Σ wₖ·SEALₖ/4]×(1−DCI)×100"
    assert any("EU Cloud Sovereignty" in c for c in pred["seal"]["cites"])
    assert any("Herfindahl" in c for c in pred["seal"]["cites"])


# --------------------------------------------------------------------------- #
# DSSE signing
# --------------------------------------------------------------------------- #
def test_statement_dsse_signs_or_reports_unsigned_honestly():
    import base64

    stmt = A.build_statement()
    env = A.sign_statement(stmt)
    assert env["payloadType"] == "application/vnd.in-toto+json"
    # the envelope payload round-trips to the exact Statement
    assert json.loads(base64.b64decode(env["payload"]).decode("utf-8")) == stmt
    assert env["_statement_digest_sha256"] == A.digest_hex(stmt)
    sig = A.signature_status(env)
    if env.get("signed"):
        assert env["signatures"] and sig["status"] == "VERIFIED"
        assert sig["verified"] is True
    else:
        # no runtime cosign secret: explicitly unsigned, never a fake signature
        assert env["signatures"] == []
        assert sig["status"] == "UNSIGNED-NO-KEY"
        assert sig["verified"] is None


# --------------------------------------------------------------------------- #
# verify() — PASSED / FAILED / UNKNOWN
# --------------------------------------------------------------------------- #
def test_verify_passed_on_a_valid_statement():
    stmt = A.build_statement()
    out = A.verify(stmt, require_transparency=False)
    assert out["verdict"] == "PASSED"
    assert out["policy"]["policy"] == "PASSED"
    assert out["policy"]["failed"] == []
    # a policy-only PASSED must SAY it is policy-only
    assert "policy-only" in out["verdict_scope"]
    assert out["label"] == "MODELED"


@pytest.mark.parametrize("mutate,rule", [
    (lambda s: s.__setitem__("predicateType", "https://example.test/other/v1"),
     "predicate_type_matches"),
    (lambda s: s["predicate"].__setitem__("doctrine", "v10"), "doctrine_is_v11"),
    (lambda s: s["predicate"]["provenance"].__setitem__("kernel_verified", False),
     "kernel_verified"),
    (lambda s: s["predicate"]["honesty_invariants"].__setitem__("locked8_immutable", False),
     "honesty_invariants_all_true"),
    (lambda s: s["predicate"]["honesty_invariants"].__setitem__(
        "lambda_is_conjecture_not_theorem", False), "honesty_invariants_all_true"),
    (lambda s: s["predicate"]["provenance"].__setitem__("provenance_coverage", 0.8),
     "provenance_coverage_is_one"),
    (lambda s: s["subject"][0]["digest"].__setitem__("gitCommit", "   "),
     "subject_binds_kernel_commit"),
    (lambda s: s.__setitem__("subject", []), "subject_binds_kernel_commit"),
])
def test_verify_failed_on_a_tampered_statement(mutate, rule):
    stmt = json.loads(json.dumps(A.build_statement()))
    mutate(stmt)
    out = A.verify(stmt, require_transparency=False)
    assert out["verdict"] == "FAILED", out["verdict_scope"]
    assert rule in out["policy"]["failed"]


def test_verify_unknown_when_rekor_unreachable():
    """A REQUIRED transparency anchor that cannot be obtained is UNKNOWN — never
    a fabricated PASSED, and never silently downgraded to FAILED."""
    stmt = A.build_statement()
    env = A.sign_statement(stmt)
    unreachable = {
        "status": "UNREACHABLE", "attempted": True, "reachable": False,
        "log_index": None, "inclusion_proof": None, "label": "STRUCTURAL-ONLY",
        "note": "Rekor unreachable (URLError)",
    }
    out = A.verify(stmt, envelope=env, rekor=unreachable, require_transparency=True)
    assert out["verdict"] == "UNKNOWN"
    assert out["transparency"]["status"] == "UNREACHABLE"
    assert out["transparency"]["inclusion_proof"] is None
    assert out["transparency"]["log_index"] is None
    assert out["label"] == "MODELED"
    assert "never a fabricated PASSED" in " ".join(out["reasons"])


def test_failed_beats_unknown_so_a_tamper_cannot_hide_behind_an_offline_log():
    stmt = json.loads(json.dumps(A.build_statement()))
    stmt["predicate"]["provenance"]["kernel_verified"] = False
    out = A.verify(stmt, rekor={"status": "UNREACHABLE", "inclusion_proof": None,
                                "log_index": None},
                   require_transparency=True)
    assert out["verdict"] == "FAILED"


def test_verify_passed_with_transparency_only_from_a_real_inclusion_proof():
    stmt = A.build_statement()
    env = A.sign_statement(stmt)
    recorded = {
        "status": "RECORDED", "attempted": True, "reachable": True,
        "log_index": 123456, "entry_uuid": "abc", "label": "MEASURED",
        "inclusion_proof": {"logIndex": 123456, "treeSize": 200000,
                            "rootHash": "0" * 64, "hashes": ["1" * 64]},
        "note": "real inclusion proof returned by the transparency log this request",
    }
    out = A.verify(stmt, envelope=env, rekor=recorded, require_transparency=True)
    assert out["verdict"] == "PASSED"
    assert "policy + transparency" in out["verdict_scope"]
    # MEASURED is reachable ONLY through a real inclusion proof
    assert out["label"] == "MEASURED"


def test_verify_unknown_when_log_answers_without_an_inclusion_proof():
    """A 200 from the log is not inclusion. Without a proof + index it stays UNKNOWN."""
    stmt = A.build_statement()
    env = dict(A.sign_statement(stmt))
    env["signatures"] = [{"sig": "AA==", "keyid": "test"}]

    def _answers_without_proof(url, body, timeout):
        return {"uuid-1": {"body": "x", "integratedTime": 1}}

    rk = A.rekor_submit(env, submitter=_answers_without_proof)
    assert rk["status"] in ("UNREACHABLE", "NOT_ATTEMPTED")
    assert rk["inclusion_proof"] is None and rk["log_index"] is None


def test_signature_invalid_is_failed_not_unknown():
    stmt = A.build_statement()
    env = dict(A.sign_statement(stmt))
    # a bogus signature on an otherwise valid statement must not pass
    env["signatures"] = [{"sig": "AAAA", "keyid": "szlholdings-cosign"}]
    out = A.verify(stmt, envelope=env, require_transparency=False)
    assert out["verdict"] == "FAILED"
    assert out["signature"]["status"] == "SIGNATURE-INVALID"


# --------------------------------------------------------------------------- #
# Rekor guard — no fabrication on any path
# --------------------------------------------------------------------------- #
def test_rekor_not_attempted_when_submission_is_not_enabled(monkeypatch):
    monkeypatch.delenv(A.REKOR_ENABLE_ENV, raising=False)
    stmt = A.build_statement()
    env = A.sign_statement(stmt)
    rk = A.rekor_submit(env)
    assert rk["status"] in ("NOT_ATTEMPTED",)
    assert rk["attempted"] is False
    assert rk["inclusion_proof"] is None
    assert rk["log_index"] is None
    assert rk["entry_uuid"] is None
    assert rk["label"] == "STRUCTURAL-ONLY"
    # the entry is only ever PROPOSED offline
    assert rk["proposed_entry"]["kind"] == "intoto"


def test_rekor_unreachable_records_unknown_never_an_entry(monkeypatch):
    monkeypatch.setenv(A.REKOR_ENABLE_ENV, "1")
    monkeypatch.setenv(A.REKOR_URL_ENV, "http://127.0.0.1:1")
    stmt = A.build_statement()
    env = dict(A.sign_statement(stmt))
    env["signatures"] = [{"sig": "AA==", "keyid": "test"}]

    def _boom(url, body, timeout):
        raise OSError("connection refused")

    rk = A.rekor_submit(env, submitter=_boom)
    assert rk["status"] == "UNREACHABLE"
    assert rk["reachable"] is False
    assert rk["inclusion_proof"] is None and rk["log_index"] is None
    assert rk["label"] == "STRUCTURAL-ONLY"
    assert "fabricated" in rk["note"]


def test_rekor_recorded_only_from_a_real_proof(monkeypatch):
    monkeypatch.setenv(A.REKOR_ENABLE_ENV, "1")
    stmt = A.build_statement()
    env = dict(A.sign_statement(stmt))
    env["signatures"] = [{"sig": "AA==", "keyid": "test"}]
    proof = {"logIndex": 42, "treeSize": 99, "rootHash": "a" * 64, "hashes": []}

    def _ok(url, body, timeout):
        return {"uuid-abc": {"logIndex": 42, "integratedTime": 1700000000,
                             "verification": {"inclusionProof": proof}}}

    rk = A.rekor_submit(env, submitter=_ok)
    assert rk["status"] == "RECORDED"
    assert rk["log_index"] == 42
    assert rk["inclusion_proof"] == proof
    assert rk["label"] == "MEASURED"


def test_unsigned_envelope_is_never_submitted(monkeypatch):
    monkeypatch.setenv(A.REKOR_ENABLE_ENV, "1")
    env = A.sign_statement(A.build_statement())
    if env.get("signed"):
        pytest.skip("a runtime cosign secret is present in this environment")
    rk = A.rekor_submit(env, submitter=lambda *a: pytest.fail("must not submit"))
    assert rk["status"] == "NOT_ATTEMPTED"
    assert rk["attempted"] is False


# --------------------------------------------------------------------------- #
# Rego policy lockstep
# --------------------------------------------------------------------------- #
def test_rego_policy_exists_and_declares_the_same_rules():
    text = REGO.read_text(encoding="utf-8")
    assert "package szl.attest.chain_of_title" in text
    assert 'expected_predicate_type := "https://szl.dev/chain-of-title/v1"' in text
    assert 'expected_doctrine := "v11"' in text
    assert "default passed := false" in text          # fail closed
    for rule in A.POLICY_RULES:
        assert re.search(r"^" + re.escape(rule) + r" if \{", text, re.M), rule
    # the tri-state verdict, with FAILED ahead of UNKNOWN
    assert 'verdict := "FAILED"' in text
    assert 'verdict := "UNKNOWN"' in text
    assert 'verdict := "PASSED"' in text
    assert text.index('verdict := "FAILED"') < text.index('verdict := "UNKNOWN"')
    assert A.POLICY_PATH == "ops/szl_chain_of_title.rego"
    assert A.POLICY_PACKAGE == "szl.attest.chain_of_title"


def test_policy_rules_are_exactly_the_six_required_conditions():
    assert A.POLICY_RULES == (
        "predicate_type_matches",
        "doctrine_is_v11",
        "kernel_verified",
        "honesty_invariants_all_true",
        "provenance_coverage_is_one",
        "subject_binds_kernel_commit",
    )
    checks = A.evaluate_policy(A.build_statement())["checks"]
    assert set(checks) == set(A.POLICY_RULES)


def test_policy_fails_closed_on_junk_input():
    for junk in (None, [], "statement", 7, {}):
        out = A.evaluate_policy(junk)
        assert out["policy"] == "FAILED"


# --------------------------------------------------------------------------- #
# Manifest + ledger receipt
# --------------------------------------------------------------------------- #
def test_manifest_is_self_consistent_and_labels_honestly():
    man = A.build_manifest()
    assert man["ok"] is True
    assert man["statement_digest_sha256"] == A.digest_hex(man["statement"])
    assert man["verdict"] in ("PASSED", "FAILED", "UNKNOWN")
    assert man["policy_source"]["path"] == "ops/szl_chain_of_title.rego"
    if man["rekor"]["status"] != "RECORDED":
        assert man["label"] == "MODELED"
    assert any("in-toto" in c for c in man["cites"])
    assert any("slsa.dev" in c for c in man["cites"])
    assert any("sigstore" in c.lower() for c in man["cites"])


def test_lake_receipt_is_opt_in_and_never_writes_on_a_read_path(monkeypatch):
    monkeypatch.delenv(A.LAKE_DIR_ENV, raising=False)
    res = A.lake_receipt(A.build_manifest())
    assert res["appended"] is False
    assert res["status"] == "NOT_CONFIGURED"


# --------------------------------------------------------------------------- #
# Live endpoints through the REAL app (no mocks, no network)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def client():
    pytest.importorskip("starlette.testclient")
    from starlette.testclient import TestClient

    import serve

    with TestClient(serve.app) as c:
        yield c


def test_attest_routes_are_registered_ahead_of_the_parametrized_route():
    pytest.importorskip("starlette.testclient")
    import serve

    paths = [getattr(r, "path", "") for r in serve.app.router.routes]
    assert "/api/a11oy/v1/attest/manifest" in paths
    assert "/api/a11oy/v1/attest/verify" in paths
    # the pre-existing /attest/{receipt_hash} must not shadow the static routes
    param = [i for i, p in enumerate(paths)
             if p.startswith("/api/a11oy/v1/attest/") and "{" in p]
    if param:
        assert paths.index("/api/a11oy/v1/attest/manifest") < min(param)
        assert paths.index("/api/a11oy/v1/attest/verify") < min(param)


def test_manifest_endpoint_200_and_honest(client):
    r = client.get("/api/a11oy/v1/attest/manifest")
    assert r.status_code == 200
    j = r.json()
    assert j["statement"]["predicateType"] == "https://szl.dev/chain-of-title/v1"
    assert j["statement"]["predicate"]["doctrine"] == "v11"
    assert j["verdict"] in ("PASSED", "FAILED", "UNKNOWN")
    assert j["label"] in ("MODELED", "MEASURED")
    if j["rekor"]["status"] != "RECORDED":
        assert j["label"] == "MODELED"
        assert j["rekor"]["inclusion_proof"] is None
    assert j["lake"]["appended"] in (True, False)


def test_verify_endpoint_get_200(client):
    r = client.get("/api/a11oy/v1/attest/verify")
    assert r.status_code == 200
    j = r.json()
    assert j["verdict"] in ("PASSED", "FAILED", "UNKNOWN")
    assert j["lambda"]["is_theorem"] is False


def test_verify_endpoint_post_passed_then_failed(client):
    stmt = A.build_statement()
    ok = client.post("/api/a11oy/v1/attest/verify", json={"statement": stmt})
    assert ok.status_code == 200
    assert ok.json()["verdict"] == "PASSED"

    tampered = json.loads(json.dumps(stmt))
    tampered["predicate"]["honesty_invariants"]["no_fabricated_measured"] = False
    bad = client.post("/api/a11oy/v1/attest/verify", json={"statement": tampered})
    assert bad.status_code == 200
    assert bad.json()["verdict"] == "FAILED"
    assert "honesty_invariants_all_true" in bad.json()["policy"]["failed"]


def test_verify_endpoint_post_accepts_a_dsse_envelope(client):
    env = A.sign_statement(A.build_statement())
    r = client.post("/api/a11oy/v1/attest/verify", json={"envelope": env})
    assert r.status_code == 200
    j = r.json()
    assert j["verdict"] in ("PASSED", "FAILED", "UNKNOWN")
    assert j["source"] == "caller-supplied envelope"


def test_verify_endpoint_post_require_transparency_is_unknown(client):
    """No Rekor reachable from this runtime: a required anchor must read UNKNOWN."""
    stmt = A.build_statement()
    r = client.post("/api/a11oy/v1/attest/verify?require_transparency=1",
                    json={"statement": stmt})
    assert r.status_code == 200
    j = r.json()
    assert j["verdict"] == "UNKNOWN"
    assert j["transparency"]["required"] is True
    assert j["transparency"]["inclusion_proof"] is None


def test_verify_endpoint_rejects_junk_without_a_500(client):
    r = client.post("/api/a11oy/v1/attest/verify", json={"nope": 1})
    assert r.status_code == 200
    assert r.json()["verdict"] == "FAILED"


# --------------------------------------------------------------------------- #
# 3-place surface registry + doctrine lexicon
# --------------------------------------------------------------------------- #
def test_attest_surface_is_registered_last_in_all_three_places():
    import szl3d_holographic

    ids = [s["id"] for s in szl3d_holographic.SURFACES]
    assert ids[-1] == "attest", ids[-3:]
    assert ids.count("attest") == 1

    html = (ROOT / "static" / "3d" / "holographic.html").read_text(encoding="utf-8")
    html_ids = re.findall(r'\{\s*id:\s*"([A-Za-z0-9_-]+)"', html)
    assert html_ids[-1] == "attest"
    assert html_ids == ids

    js = ROOT / "static" / "3d" / "surfaces" / "attest.js"
    assert js.is_file()
    text = js.read_text(encoding="utf-8")
    assert '"/api/a11oy/v1/attest/manifest"' in text
    assert "export function mount" in text and "export function unmount" in text
    # honest labels only; no green success colour, no fabricated pass
    assert "MODELED" in text and "UNKNOWN" in text
    assert "Conjecture 1" in text


def test_new_files_carry_no_banned_superlative_and_no_bare_lambda_theorem():
    # assembled from fragments so this guard does not trip over its own source
    banned = tuple(a + b for a, b in (
        ("revolution", "ary"), ("world-", "class"), ("seam", "less"),
        ("industry-", "leading"), ("cutting-", "edge"), ("game-", "changing"),
        ("break", "through"), ("unpreced", "ented")))
    targets = [
        ROOT / "szl_attest.py",
        REGO,
        ROOT / "static" / "3d" / "surfaces" / "attest.js",
        ROOT / "tests" / "test_attest.py",
    ]
    for path in targets:
        text = path.read_text(encoding="utf-8")
        low = text.lower()
        for word in banned:
            assert word not in low, f"{path.name}: banned superlative {word!r}"
        # "Λ ... theorem" is only ever allowed alongside "Conjecture"
        for m in re.finditer(r"Λ[^.\n]{0,120}theorem", text):
            assert "Conjecture" in text[max(0, m.start() - 200):m.end() + 200], \
                f"{path.name}: Λ near 'theorem' without 'Conjecture'"
        # any mention of consciousness/sentience must be a DISCLAIMER, never a claim
        for m in re.finditer(r"conscious|sentien", low):
            window = low[max(0, m.start() - 60):m.end() + 60]
            assert re.search(r"\bno\b|\bnot\b|never", window), \
                f"{path.name}: mind-state wording must be a disclaimer, not a claim"
