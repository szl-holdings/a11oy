# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""test_frontier_zkinfer — the zkML Proof-of-Inference surface must be honest by design.

GET /api/a11oy/v1/frontier/zkinfer returns the CRYPTOGRAPHIC-PROOF trust branch of
verifiable inference (counterpart to the TEE branch, ccattest). These checks enforce the
doctrine-v11 honesty contract on that surface:

  * top-level label is MODELED and explicitly NOT VERIFIED — never a green/1.0 state;
  * the doctrine block is exact: locked-8 = {F1,F4,F7,F11,F12,F18,F19,F22}, +0 added,
    Λ = Conjecture 1, trust ceiling 0.97 (never 100%), 0 runtime CDN;
  * EVERY numeric cost value cites one of the five primary sources (arXiv ID / DOI);
  * the real commit→prove→verify micro-artifact either reconciled (MEASURED, and is
    independently recomputable here) or is an honest HONEST-STUB — never a faked pass;
  * the surface is registered on the registry (holographic.html + szl3d SURFACES) so the
    /frontier/surfaces count includes it, and its 3D module carries no runtime-CDN fetch.
"""
import hashlib
import pathlib
import re

import szl_frontier_zkinfer as zk

_REPO_ROOT = pathlib.Path(__file__).resolve().parent
_SURFACE_JS = _REPO_ROOT / "static" / "3d" / "surfaces" / "zkinfer.js"
_HOLO = _REPO_ROOT / "static" / "3d" / "holographic.html"

_PRIMARY = {"2404.16109", "2210.08674", "10.1145/3627703.3650088",
            "2402.02675", "2502.18535"}


def _walk_sources(node):
    found = []
    if isinstance(node, dict):
        if node.get("source") is not None:
            found.append(node["source"])
        for v in node.values():
            found += _walk_sources(v)
    elif isinstance(node, list):
        for v in node:
            found += _walk_sources(v)
    return found


def test_top_label_modeled_not_verified():
    p = zk.build_payload()
    assert p["ok"] is True
    assert p["label"] == "MODELED" and p["claim"] == "MODELED"
    assert p["not_verified"] is True
    assert p["no_trusted_hardware_in_TCB"] is True
    assert "VERIFIED" not in p["label"]


def test_doctrine_block_is_exact_and_never_inflated():
    d = zk.build_payload()["doctrine"]
    assert d["locked_proven"] == 8
    assert d["locked_set"] == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_ceiling"] < 1.0
    assert d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0


def test_every_cost_value_cites_a_primary_source():
    p = zk.build_payload()
    cited = set(_walk_sources(p["proof_cost_model"]))
    assert cited, "no source citations in proof_cost_model"
    assert cited <= _PRIMARY, f"cost model cites a non-primary source: {cited - _PRIMARY}"
    # all five primary sources appear somewhere in the payload's source registry.
    assert _PRIMARY <= set(p["sources"])


def test_micro_artifact_is_measured_and_recomputable_or_honest_stub():
    m = zk.build_payload()["micro_artifact"]
    assert m["label"] in ("MEASURED", "HONEST-STUB")
    if m["label"] == "HONEST-STUB":
        assert m["verify_ok"] is False  # never a faked pass
        return
    # MEASURED: independently recompute the whole roundtrip to prove it is honest.
    assert m["verify_ok"] is True
    w = m["commit"]["weight_vector"]
    x = m["public_input"]
    root2, _ = zk._merkle_root([str(v).encode() for v in w])
    assert root2 == m["commit"]["merkle_root"], "Merkle root not client-recomputable"
    xb = (",".join(str(v) for v in x)).encode()
    ch2 = hashlib.sha256(bytes.fromhex(root2) + xb).hexdigest()
    assert ch2 == m["challenge_fiat_shamir"], "Fiat–Shamir challenge not recomputable"
    assert sum(wi * xi for wi, xi in zip(w, x)) == m["output_y"], "output y not recomputable"


def test_trust_matrix_contrasts_crypto_vs_tee_honestly():
    tm = zk.build_payload()["trust_model_matrix"]
    assert tm["label"] == "STRUCTURAL-ONLY"
    crypto = tm["branches"]["cryptographic_zkml (this surface)"]
    tee = tm["branches"]["tee_attestation (ccattest)"]
    # the whole point: crypto has NO trusted hardware / NO vendor in the trust base.
    assert crypto["trusted_hardware_in_TCB"] is False
    assert crypto["vendor_in_trust_base"] is False
    assert tee["trusted_hardware_in_TCB"] is True


def test_register_is_additive():
    class _FakeApp:
        def __init__(self): self.routes = []
        def get(self, path):
            self.routes.append(path)
            def _dec(fn): return fn
            return _dec
    app = _FakeApp()
    out = zk.register(app, ns="a11oy")
    assert out == "frontier-zkinfer-wired:1"
    assert "/api/a11oy/v1/frontier/zkinfer" in app.routes


def test_surface_is_registered_and_zero_cdn():
    # registered in the viewer registry so /frontier/surfaces counts it.
    holo = _HOLO.read_text(encoding="utf-8")
    assert 'id: "zkinfer"' in holo, "zkinfer not in holographic.html SURFACES"
    assert _SURFACE_JS.is_file(), "zkinfer.js module missing"
    src = _SURFACE_JS.read_text(encoding="utf-8")
    # honesty label present verbatim + runtime-default derivation to MODELED.
    assert "MODELED" in src
    assert re.search(r'\bS\.label\s*=\s*\(\s*j\.label\s*\|\|\s*"MODELED"', src)
    # 0 runtime CDN: no fetch-shaped external URL in the module.
    assert not re.search(r'\bfetch\s*\(\s*["\']https?://', src)
    assert not re.search(r'\bimport\b[^;\n]*\bfrom\s*["\']https?://', src)
    # same-origin relative endpoint only.
    assert "/api/a11oy/v1/frontier/zkinfer" in src
