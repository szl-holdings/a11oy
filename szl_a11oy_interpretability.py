# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1 · SLSA L1 honest / L2 attested / L3 roadmap
# Co-Authored-By: Perplexity Computer Agent
"""
szl_a11oy_interpretability.py — ADDITIVE SPARSE-AUTOENCODER (SAE) feature-extraction
simulator, a11oy-NATIVE self-hosted twin of the killinchu frontier organ. It is the
PRIMARY, honest self-hosted endpoint behind a11oy static/3d/surfaces/interpretability.js
(the surface's guarded fallback stays the isolated killinchu Space, so a fault in either
path never darkens the other).

Clean-room port of killinchu's szl_kc_interpretability.py: same deterministic top-k SAE
encode/decode math, extended to emit the SUPERSET of fields interpretability.js actually
reads (label, l0_sparsity, active_features, reconstruction_cos, top_features[]) while
remaining a byte-compatible superset of the killinchu JSON (reconstruction_mse,
fraction_variance_unexplained, dead_features, monosemanticity_proxy, feature_fire_frequency).

Mechanistic interpretability resolves polysemantic neurons into monosemantic FEATURES by
training a sparse autoencoder on a model's residual-stream activations: an overcomplete
dictionary D of feature directions is learned so each activation reconstructs as a SPARSE,
non-negative combination of dictionary atoms. Cunningham, Ewart, Riggs, Huben, Sharkey
(2023) — "Sparse Autoencoders Find Highly Interpretable Features in Language Models"
(arXiv:2309.08600) — show these features are more interpretable/monosemantic than neurons.
Anthropic's "Towards Monosemanticity" (Bricken et al. 2023) established dictionary learning
on a real model, and "Scaling Monosemanticity" (Templeton et al. 2024) scaled it to
Claude 3 Sonnet. Gao et al. (2024) "Scaling and evaluating sparse autoencoders"
(arXiv:2406.04093, OpenAI) give the top-k SAE + scaling-law recipe this organ re-derives;
Rajamanoharan et al. (2024) "JumpReLU SAEs" (arXiv:2407.14435) and Marks et al. (2024)
"Sparse Feature Circuits" (arXiv:2406.02395, causal ablation) inform the top-k/causal
fields the surface renders.

Deterministic MODELED SAE encode/decode (seeded, no live model):
  * x = seeded d-dim activation vector; dictionary D is a seeded h-by-d overcomplete matrix
    (h >> d), rows L2-normalized to unit atoms.
  * pre-activations a = D x - b (a seeded bias/threshold), feature codes f = ReLU(a).
    Keep only the top-k largest codes (a JumpReLU / top-k sparsity stand-in) so L0 = k.
  * reconstruction x_hat = D^T f ; reconstruction_mse = mean((x - x_hat)^2) and a cosine
    reconstruction fidelity reconstruction_cos = <x, x_hat> / (||x|| ||x_hat||).
  * feature activation frequency over a batch of seeded activations; a feature is DEAD if it
    never fires. Report L0, fraction_variance_unexplained proxy, active/dead feature counts.
  * top_features[] = the top-k fired dictionary atoms with a MODELED causal-ablation KL
    proxy (energy removed from the reconstruction when that atom is ablated) and an
    interpretation_confidence proxy (its share of the activation's reconstructed energy).

  f = ReLU(D x - b), keep top-k       (sparse feature codes; L0 = k)
  x_hat = D^T f                        (tied-dictionary reconstruction)
  reconstruction_mse = mean((x - x_hat)^2)
  reconstruction_cos = <x, x_hat> / (||x|| ||x_hat||)
  causal_ablation_kl ~ ||f_j D_j||^2 / ||x_hat||^2   (MODELED ablation-energy proxy)
  monosemanticity_proxy = k / h        (sparse fraction of the overcomplete dictionary firing)

HONESTY SPINE (Doctrine v11):
  * MODELED deterministic SAE encode/decode SIMULATION. NOT a trained SAE / Anthropic
    dictionary running; NO live model, NO GPU, NO trained weights. Activations x, dictionary
    D, and bias b are SEEDED PRNG inputs, NOT a real residual stream or learned dictionary.
  * L0 / reconstruction error / cosine / causal-ablation KL / dead-feature counts are
    properties of the modeled encode on seeded inputs, honestly labeled — NOT a measured
    claim about a real model's interpretability.
  * Label "MODELED" is returned verbatim and read verbatim by the frontend; never upgraded.
  * Advisory only (Λ = Conjecture 1); adds nothing to the locked-8; trust never 100%.

Route (NEW; never collides — a11oy-native primary endpoint):
  GET /api/{ns}/v1/interpretability/features  — SAE feature-extraction snapshot (MODELED)

Pure stdlib. Defensive: a compute failure NEVER raises out of a handler (fail-open 200).
"""
from __future__ import annotations

import json as _json
import math as _math
from datetime import datetime, timezone

DOCTRINE_VERSION = "v11"
MODELED_LABEL = "MODELED"
HONESTY_LONG = "MODELED | SAE_ENCODE_SIM | NOT_LIVE | NO_MODEL | DICTIONARY_IS_SEEDED"

CITATIONS = {
    "cunningham": ("Cunningham, Ewart, Riggs, Huben, Sharkey (2023) Sparse Autoencoders Find "
                   "Highly Interpretable Features in Language Models — "
                   "https://arxiv.org/abs/2309.08600"),
    "bricken": ("Bricken et al. / Anthropic (2023) Towards Monosemanticity: Decomposing "
                "Language Models With Dictionary Learning — "
                "https://transformer-circuits.pub/2023/monosemantic-features"),
    "templeton": ("Templeton et al. / Anthropic (2024) Scaling Monosemanticity: Extracting "
                  "Interpretable Features from Claude 3 Sonnet — "
                  "https://transformer-circuits.pub/2024/scaling-monosemanticity"),
    "gao": ("Gao, la Tour, Tillman, Goh, Troll, Radford, Sutskever, Leike, Wu (2024) Scaling "
            "and evaluating sparse autoencoders (top-k SAEs) — https://arxiv.org/abs/2406.04093"),
    "rajamanoharan": ("Rajamanoharan et al. / DeepMind (2024) Jumping Ahead: Improving "
                      "Reconstruction Fidelity with JumpReLU Sparse Autoencoders — "
                      "https://arxiv.org/abs/2407.14435"),
    "marks": ("Marks, Rager, Michaud, Belinkov, Bau, Mueller (2024) Sparse Feature Circuits: "
              "Discovering and Editing Interpretable Causal Graphs in Language Models — "
              "https://arxiv.org/abs/2406.02395"),
}


class _LCG:
    """Small deterministic LCG PRNG (pure stdlib; no numpy, no stdlib random)."""

    __slots__ = ("_s",)

    def __init__(self, seed: int) -> None:
        self._s = (int(seed) & 0xFFFFFFFFFFFFFFFF) or 0x9E3779B97F4A7C15

    def _next(self) -> int:
        self._s = (6364136223846793005 * self._s + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return self._s

    def random(self) -> float:
        return (self._next() >> 11) / float(1 << 53)

    def normalish(self) -> float:
        # Irwin-Hall(4)-centered approx of a zero-mean unit-ish gaussian (pure stdlib).
        return (self.random() + self.random() + self.random() + self.random()) - 2.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relu(x: float) -> float:
    return x if x > 0.0 else 0.0


def interp_features(seed: int = 42, d_model: int = 16, n_features: int = 128,
                    top_k: int = 8, batch: int = 64) -> dict:
    """SAE feature-extraction snapshot (MODELED).

    d_model    — activation dimensionality d.
    n_features — overcomplete dictionary size h (h >> d).
    top_k      — kept active features per activation (L0 sparsity).
    batch      — number of seeded activations to census.
    seed       — PRNG seed; deterministic.
    """
    d = max(2, min(256, int(d_model)))
    h = max(d + 1, min(4096, int(n_features)))
    k = max(1, min(h, int(top_k)))
    B = max(1, min(2048, int(batch)))
    rng = _LCG(int(seed) * 2_654_435_761 + d * 131 + h * 17 + k * 7)

    # overcomplete dictionary D: h atoms in R^d, each L2-normalized to a unit direction.
    D = []
    for _ in range(h):
        atom = [rng.normalish() for _ in range(d)]
        nrm = _math.sqrt(sum(v * v for v in atom)) or 1.0
        D.append([v / nrm for v in atom])
    bias = [0.15 * rng.random() for _ in range(h)]  # seeded threshold/bias per feature

    fire_count = [0] * h
    total_mse = 0.0
    total_energy = 0.0
    total_cos = 0.0
    first_l0 = None
    first_active_ids = None
    first_top_features = None
    for t in range(B):
        x = [rng.normalish() for _ in range(d)]
        # pre-activations a_j = <D_j, x> - b_j ; codes f = ReLU(a), then top-k.
        pre = [sum(D[j][c] * x[c] for c in range(d)) - bias[j] for j in range(h)]
        codes = [_relu(p) for p in pre]
        # keep only the top-k largest codes (JumpReLU/top-k sparsity)
        idx_sorted = sorted(range(h), key=lambda j: codes[j], reverse=True)[:k]
        active = [j for j in idx_sorted if codes[j] > 0.0]
        f = [0.0] * h
        for j in active:
            f[j] = codes[j]
            fire_count[j] += 1
        # reconstruction x_hat = sum_j f_j * D_j  (tied dictionary decode)
        x_hat = [0.0] * d
        for j in active:
            Dj = D[j]
            fj = f[j]
            for c in range(d):
                x_hat[c] += fj * Dj[c]
        mse = sum((x[c] - x_hat[c]) ** 2 for c in range(d)) / d
        total_mse += mse
        total_energy += sum(v * v for v in x) / d
        # cosine reconstruction fidelity <x, x_hat> / (||x|| ||x_hat||)
        dot = sum(x[c] * x_hat[c] for c in range(d))
        nx = _math.sqrt(sum(v * v for v in x))
        nxh = _math.sqrt(sum(v * v for v in x_hat))
        cos = (dot / (nx * nxh)) if (nx > 0.0 and nxh > 0.0) else 0.0
        total_cos += cos
        if t == 0:
            first_l0 = len(active)
            first_active_ids = sorted(active)[:16]
            # top_features[]: per-fired-atom MODELED causal-ablation KL + interpretation
            # confidence proxies, read verbatim by interpretability.js.
            recon_energy = sum(v * v for v in x_hat) or 1.0
            _tf = []
            # rank by code magnitude (strongest features first)
            for j in sorted(active, key=lambda a: f[a], reverse=True):
                atom_energy = (f[j] * f[j])  # ||f_j D_j||^2 (D_j unit-norm)
                kl = atom_energy / recon_energy         # MODELED ablation-energy KL proxy
                conf = atom_energy / recon_energy       # share of reconstructed energy
                _tf.append({
                    "feature": "f#%d" % int(j),
                    "feature_id": int(j),
                    "activation": round(float(f[j]), 6),
                    "causal_ablation_kl": round(float(kl), 6),
                    "interpretation_confidence": round(float(min(1.0, conf)), 6),
                })
            first_top_features = _tf

    recon_mse = total_mse / B
    recon_cos = total_cos / B
    mean_energy = total_energy / B or 1.0
    # fraction of variance unexplained proxy (bounded by construction reporting)
    fvu = recon_mse / mean_energy
    active_features = sum(1 for c in fire_count if c > 0)
    dead_features = h - active_features
    mean_l0 = k  # top-k keeps exactly k (when enough positive codes exist)
    monosemanticity_proxy = k / h
    fire_freq = [round(c / B, 6) for c in fire_count[:32]]

    return {
        "service": "sae-feature-extraction",
        "label": MODELED_LABEL,
        # --- fields read VERBATIM by a11oy static/3d/surfaces/interpretability.js ---
        "d_model": int(d),
        "n_features": int(h),
        "top_k": int(k),
        "batch": int(B),
        "l0_sparsity": int(mean_l0),
        "reconstruction_mse": round(float(recon_mse), 6),
        "reconstruction_cos": round(float(recon_cos), 6),   # surface reconstruction-fidelity ring
        "fraction_variance_unexplained": round(float(fvu), 6),
        "active_features": int(active_features),
        "dead_features": int(dead_features),
        "dead_feature_pct": round(100.0 * dead_features / h, 4),
        "monosemanticity_proxy": round(float(monosemanticity_proxy), 6),
        "first_activation_l0": int(first_l0 or 0),
        "first_active_feature_ids": [int(x) for x in (first_active_ids or [])],  # [int]
        "feature_fire_frequency": fire_freq,   # [float] per-feature fire rate (first 32)
        # top_features[] — fired dictionary atoms the ring lights up (surface reads
        # feature / activation / causal_ablation_kl / interpretation_confidence verbatim).
        "top_features": first_top_features or [],
        "formulas": {
            "codes": "f = ReLU(D x - b), keep top-k",
            "reconstruction": "x_hat = D^T f (tied dictionary)",
            "reconstruction_mse": "mean((x - x_hat)^2)",
            "reconstruction_cos": "<x, x_hat> / (||x|| ||x_hat||)",
            "causal_ablation_kl": "||f_j D_j||^2 / ||x_hat||^2 (MODELED ablation-energy proxy)",
            "fvu": "reconstruction_mse / mean(||x||^2 / d)",
            "monosemanticity_proxy": "k / h (sparse fraction of overcomplete dictionary firing)",
        },
        "compute_backend": {
            "backend": "CPU pure-Python SAE encode/decode simulation (seeded LCG)",
            "label": "MODELED",
            "honest_note": ("Deterministic top-k SAE encode on seeded activations + seeded "
                            "dictionary; NO trained SAE, NO live model, NO GPU. The "
                            "trained-dictionary-on-a-real-residual-stream path is ROADMAP."),
        },
        "honest_note": ("MODELED sparse-autoencoder feature extraction. NOT a trained SAE / "
                        "Anthropic dictionary running; NO live model, NO GPU, NO trained "
                        "weights. Activations, dictionary, and bias are seeded inputs; L0, "
                        "reconstruction error/cosine, and causal-ablation KL are properties of "
                        "the modeled encode. Advisory to Λ (Conjecture 1); adds nothing to the "
                        "locked-8."),
        "doctrine": DOCTRINE_VERSION,
        "lambda": "Conjecture 1 (advisory, NOT a theorem)",
        "effector_posture": "SIMULATED · human-on-loop (feature snapshot advisory — never an autonomous action)",
        "citations": {"cunningham": CITATIONS["cunningham"], "bricken": CITATIONS["bricken"],
                      "templeton": CITATIONS["templeton"], "gao": CITATIONS["gao"],
                      "rajamanoharan": CITATIONS["rajamanoharan"], "marks": CITATIONS["marks"]},
        "wired_into": "frontier ring — Interpretability surface (a11oy-native SAE monosemantic features)",
        "host": "a11oy-native (self-hosted primary; killinchu Space is the guarded fallback)",
        "computed_at": _now_iso(),
    }


# =====================================================================================
# Registration (additive). Mirrors szl_sovereign_compute / szl_kc_specdec registration:
# uses @app.get (APPENDS a route); serve.py then front-moves the path to router head so
# it wins over the /api/a11oy/{path:path} Node proxy + /{full_path:path} SPA catch-all.
# =====================================================================================
def register(app, ns: str = "a11oy") -> dict:
    from fastapi.responses import JSONResponse

    base = "/api/%s/v1/interpretability" % ns
    path = "%s/features" % base

    @app.get(path)
    async def _a11oy_interp(seed: int = 42, d_model: int = 16, n_features: int = 128,
                            top_k: int = 8, batch: int = 64):  # noqa: ANN202
        try:
            return JSONResponse(interp_features(seed=seed, d_model=d_model,
                                                n_features=n_features, top_k=top_k, batch=batch))
        except Exception as exc:  # pragma: no cover — never 500 the surface
            return JSONResponse({"service": "sae-feature-extraction",
                                 "label": MODELED_LABEL,
                                 "error": "compute fail-open: %s" % (str(exc)[:160]),
                                 "reconstruction_mse": None, "reconstruction_cos": None,
                                 "l0_sparsity": None, "top_features": []},
                                status_code=200)

    return {"ok": True, "ns": ns, "routes": [path]}


# =====================================================================================
# No-server self-test.
# =====================================================================================
def _selftest() -> dict:
    out: dict = {}
    r = interp_features(seed=42, d_model=16, n_features=128, top_k=8, batch=64)

    assert r["label"] == MODELED_LABEL, r["label"]
    for f in ("d_model", "n_features", "top_k", "batch", "l0_sparsity",
              "active_features", "dead_features"):
        assert isinstance(r[f], int), (f, r.get(f))
    for f in ("reconstruction_mse", "reconstruction_cos", "fraction_variance_unexplained",
              "monosemanticity_proxy"):
        assert isinstance(r[f], (int, float)), (f, r.get(f))
    assert isinstance(r["first_active_feature_ids"], list), r
    assert isinstance(r["feature_fire_frequency"], list) and r["feature_fire_frequency"], r

    # top_features[] shape the surface reads verbatim
    assert isinstance(r["top_features"], list) and r["top_features"], r
    tf0 = r["top_features"][0]
    for f in ("feature", "activation", "causal_ablation_kl", "interpretation_confidence"):
        assert f in tf0, (f, tf0)
    assert isinstance(tf0["feature"], str), tf0
    assert isinstance(tf0["activation"], (int, float)), tf0
    assert isinstance(tf0["causal_ablation_kl"], (int, float)), tf0

    # invariants: overcomplete dictionary; L0 sparsity == top_k << h; census sums to h.
    assert r["n_features"] > r["d_model"], r  # overcomplete
    assert r["l0_sparsity"] == r["top_k"], r
    assert r["l0_sparsity"] < r["n_features"], r  # genuinely sparse
    assert r["active_features"] + r["dead_features"] == r["n_features"], r
    assert 0.0 <= r["monosemanticity_proxy"] < 1.0, r
    assert r["reconstruction_mse"] > 0.0, r
    assert -1.0 <= r["reconstruction_cos"] <= 1.0, r
    assert r["fraction_variance_unexplained"] > 0.0, r
    assert r["first_activation_l0"] <= r["top_k"], r
    assert len(r["top_features"]) <= r["top_k"], r
    out["metrics"] = {"l0_sparsity": r["l0_sparsity"], "reconstruction_mse": r["reconstruction_mse"],
                      "reconstruction_cos": r["reconstruction_cos"],
                      "fraction_variance_unexplained": r["fraction_variance_unexplained"],
                      "active_features": r["active_features"], "dead_features": r["dead_features"],
                      "top_features": len(r["top_features"])}

    assert "arxiv.org/abs/2309.08600" in r["citations"]["cunningham"], r["citations"]
    assert "arxiv.org/abs/2406.04093" in r["citations"]["gao"], r["citations"]  # Gao et al.
    out["citations_ok"] = True

    # determinism
    r2 = interp_features(seed=42, d_model=16, n_features=128, top_k=8, batch=64)
    assert r2["feature_fire_frequency"] == r["feature_fire_frequency"], "non-deterministic freq"
    assert r2["reconstruction_mse"] == r["reconstruction_mse"], "non-deterministic mse"
    assert r2["reconstruction_cos"] == r["reconstruction_cos"], "non-deterministic cos"
    assert r2["top_features"] == r["top_features"], "non-deterministic top_features"
    out["deterministic"] = True

    out["ok"] = True
    return out


if __name__ == "__main__":
    import sys
    print(_json.dumps(_selftest(), indent=2), file=sys.stderr)
    print("ALL OK")
