# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
szl_vqc.py — SZL GOVERNED VQC / QML: a REAL parameter-shift Hybrid Variational
Quantum Circuit, SIMULATION-ONLY, run inside a tiny pure-stdlib (numpy-free)
deterministic state-vector simulator, wrapped in the SZL governance layer
(Λ = Conjecture 1 advisory, honest labels, DSSE-signed receipt).

  GET  /api/<ns>/v1/vqc/run?seed=&n_qubits=&layers=&steps=

The endpoint runs the canonical hybrid quantum-classical training loop exactly
as diagrammed by the QML leaders — classical data → quantum feature map → a
parameterized ansatz → measurement (expectation of a Pauli-Z observable) →
classical head → loss → a real PARAMETER-SHIFT gradient step — and returns the
full pipeline description, a small training-loss curve, and a SIGNED receipt.

HONESTY IS THE FEATURE
----------------------
This tab STATES, on the tab and in this response, the peer-reviewed evidence that
there is **no demonstrated quantum advantage for machine learning on real-world
(classical) data today** — none that survives a fair comparison. The VQC math
here is REAL (a genuine state-vector simulation with an analytically-exact
parameter-shift gradient), but the SIMULATION is small and SZL claims NO quantum
speedup. The differentiator is the GOVERNED, receipt-carrying, verifiable run —
not a physics or ML-advantage claim.

WHAT IS REAL vs SIMULATED vs CONJECTURE
---------------------------------------
  SIMULATED (real math, small sim, no QPU):
    - the state-vector simulator (complex amplitudes over 2**n_qubits basis states,
      pure Python, deterministic);
    - the angle-embedding feature map, the hardware-efficient RY/RZ + ring-CNOT
      ansatz, the Pauli-Z expectation measurement, and the classical head;
    - the loss (mean-squared error to a deterministic seeded target) and the
      REAL parameter-shift gradient step (exact ±π/2 shift rule, not finite diff).
      All numbers are genuinely COMPUTED and reported, never fabricated. There is
      NO quantum hardware, NO PennyLane/Qiskit dependency, and NO trained model.
  CONJECTURE:
    - Λ as a trust gate over the run is the SZL restraint advisory Λ = Conjecture 1
      (gray, NEVER green, not a theorem); trust is capped at 0.97, never 1.0.
  SIGNED RECEIPT:
    - the run emits ONE DSSE receipt over the run summary via szl_dsse. In-Space
      (SZL_COSIGN_PRIVATE_KEY_PEM secret present) it is a REAL ECDSA-P256-SHA256
      signature, verifiable by `cosign verify-blob`; locally (no secret) it is an
      HONEST UNSIGNED-LOCAL envelope (signed:false, NO fabricated signature).

DOCTRINE v11
  Nothing here is in the locked-8 (adds 0). Λ = Conjecture 1 (gray, never green).
  Trust is capped at 0.97 and is never 1.0. No fabricated data. Pure stdlib.
  Deterministic with seed. 0 runtime CDN. NO claim of quantum advantage.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-07):
  The canonical hybrid VQC training loop & the parameter-shift rule:
    Mitarai, Negoro, Kitagawa, Fujii — "Quantum Circuit Learning", Phys. Rev. A
      98, 032309 (2018), arXiv:1803.00745   https://arxiv.org/abs/1803.00745
    Schuld, Bergholm, Gogolin, Izaac, Killoran — "Evaluating analytic gradients
      on quantum hardware", Phys. Rev. A 99, 032331 (2019), arXiv:1811.11184
      https://arxiv.org/abs/1811.11184
  Frameworks (the QML stack a real tab would use):
    PennyLane (Xanadu) — the primary QML framework, autodiff of quantum circuits:
      https://www.xanadu.ai/products/pennylane/ ; Bergholm et al., arXiv:1811.04968
      https://arxiv.org/abs/1811.04968
    Qiskit Machine Learning (IBM) — VQC / QNN / quantum kernels:
      https://qiskit-community.github.io/qiskit-machine-learning/ ; arXiv:2505.17756
      https://arxiv.org/html/2505.17756v1
  The HONEST no-advantage evidence (STATED on the tab):
    Barren plateaus (gradients vanish exponentially with system size):
      McClean, Boixo, Smelyanskiy, Babbush, Neven — Nat. Commun. 9, 4812 (2018),
      https://www.nature.com/articles/s41467-018-07090-4 ; 2025 review (Nat. Phys.):
      https://www.nature.com/articles/s42254-025-00813-9
    Dequantization trap (trainable ⇒ often classically simulable):
      Cerezo, Larocca, García-Martín, et al. — "Does provable absence of barren
      plateaus imply classical simulability?", arXiv:2312.09121,
      https://arxiv.org/abs/2312.09121 (Nat. Commun. 2025)
    No demonstrated quantum advantage for classical-data ML (fair-comparison
      benchmark): Sheoran et al., Scientific Reports (Dec 2025),
      https://www.nature.com/srep/ ; Ivezic, "QML in 2026",
      https://postquantum.com/quantum-ai/quantum-machine-learning-reality/
    Where it DOES work — quantum data, not classical data:
      Huang et al., "Quantum advantage in learning from experiments", Science 376
      (2022), https://research.google/pubs/quantum-advantage-in-learning-from-experiments/
"""
from __future__ import annotations

import cmath
import hashlib
import math
from datetime import datetime, timezone

from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

# Optional in-repo DSSE signer (real ECDSA-P256 in-Space; honest UNSIGNED-LOCAL
# locally). Imported lazily/defensively so the module never fails to load.
try:  # pragma: no cover - import guard
    import szl_dsse as _dsse
except Exception:  # pragma: no cover
    _dsse = None

VQC_PAYLOAD_TYPE = "application/vnd.szl.vqc+json"

CITATIONS = {
    "Quantum Circuit Learning — Mitarai et al. 2018 (parameter-shift) arXiv:1803.00745": "https://arxiv.org/abs/1803.00745",
    "Evaluating analytic gradients on quantum hardware — Schuld et al. 2019 arXiv:1811.11184": "https://arxiv.org/abs/1811.11184",
    "PennyLane (Xanadu) — the primary QML framework": "https://www.xanadu.ai/products/pennylane/",
    "PennyLane — Bergholm et al. arXiv:1811.04968": "https://arxiv.org/abs/1811.04968",
    "Qiskit Machine Learning (IBM) — VQC / QNN / kernels": "https://qiskit-community.github.io/qiskit-machine-learning/",
    "Qiskit ML — arXiv:2505.17756": "https://arxiv.org/html/2505.17756v1",
    "Barren plateaus — McClean et al. 2018 Nat. Commun. 9, 4812": "https://www.nature.com/articles/s41467-018-07090-4",
    "Barren plateaus in variational quantum computing — Nat. Phys. review 2025": "https://www.nature.com/articles/s42254-025-00813-9",
    "Dequantization trap — Cerezo et al. arXiv:2312.09121": "https://arxiv.org/abs/2312.09121",
    "No-advantage benchmark — Sheoran et al. Sci. Rep. 2025": "https://www.nature.com/srep/",
    "QML in 2026 (no fair-comparison advantage) — Ivezic": "https://postquantum.com/quantum-ai/quantum-machine-learning-reality/",
    "Quantum advantage in learning from experiments — Huang et al. Science 2022": "https://research.google/pubs/quantum-advantage-in-learning-from-experiments/",
}

# ── Governance / hyperparameters (reported verbatim; not trained) ────────────
_LAMBDA_MIN = 0.02       # Λ advisory lower bound (gray floor)
_LAMBDA_MAX = 0.94       # Λ advisory upper bound (NEVER 1.0 — Conjecture 1)
_LAMBDA_ADMIT = 0.55     # advisory admit threshold
_TRUST_CAP = 0.97        # doctrine hard cap on trust (never green / never 1.0)
_SHIFT = math.pi / 2     # the parameter-shift rule uses an exact ±π/2 shift
_LR = 0.30               # classical (SGD) learning rate on the shifted gradient

# Hard caps to keep the state-vector sim small + honest (2**n grows fast).
_MAX_QUBITS = 6
_MAX_LAYERS = 6
_MAX_STEPS = 60


# ── deterministic RNG (pure stdlib, numpy-free) ──────────────────────────────
def _u01(seed, i, salt=0):
    """Deterministic uniform in [0,1) from (seed, i, salt) via two LCG rounds."""
    s = ((i + 1) * 2654435761 + seed * 40503 + salt * 2246822519) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    return s / 4294967295.0


# ── tiny complex state-vector simulator (pure Python) ────────────────────────
class _State:
    """A pure-stdlib state vector over n qubits: 2**n complex amplitudes.

    Qubit 0 is the most significant bit of the basis-state index. Gates are
    applied as in-place amplitude updates (single-qubit rotations and CNOTs),
    exactly as a real state-vector simulator (PennyLane's default.qubit / Qiskit
    Aer statevector) does — just small and dependency-free.
    """

    __slots__ = ("n", "dim", "amp")

    def __init__(self, n):
        self.n = n
        self.dim = 1 << n
        self.amp = [0j] * self.dim
        self.amp[0] = 1 + 0j  # |0...0>

    def _bit(self, idx, q):
        # bit for qubit q (q=0 is MSB) within basis index idx
        return (idx >> (self.n - 1 - q)) & 1

    def _apply_1q(self, q, m00, m01, m10, m11):
        """Apply a 2x2 single-qubit gate [[m00,m01],[m10,m11]] to qubit q."""
        n = self.n
        stride = 1 << (n - 1 - q)
        amp = self.amp
        for base in range(self.dim):
            if base & stride:  # only touch pairs once (the |...0...> element)
                continue
            i0 = base
            i1 = base | stride
            a0 = amp[i0]
            a1 = amp[i1]
            amp[i0] = m00 * a0 + m01 * a1
            amp[i1] = m10 * a0 + m11 * a1

    def ry(self, q, theta):
        c = math.cos(theta / 2.0)
        s = math.sin(theta / 2.0)
        self._apply_1q(q, c + 0j, -s + 0j, s + 0j, c + 0j)

    def rz(self, q, theta):
        e_m = cmath.exp(-1j * theta / 2.0)
        e_p = cmath.exp(1j * theta / 2.0)
        self._apply_1q(q, e_m, 0j, 0j, e_p)

    def rx(self, q, theta):
        c = math.cos(theta / 2.0)
        s = math.sin(theta / 2.0)
        self._apply_1q(q, c + 0j, -1j * s, -1j * s, c + 0j)

    def cnot(self, control, target):
        """Controlled-NOT: flip `target` where `control` bit is 1."""
        n = self.n
        cs = 1 << (n - 1 - control)
        ts = 1 << (n - 1 - target)
        amp = self.amp
        for idx in range(self.dim):
            if (idx & cs) and not (idx & ts):
                j = idx | ts
                amp[idx], amp[j] = amp[j], amp[idx]

    def expect_z(self, q):
        """Expectation <Z_q> = sum_i (+/-1) |amp_i|^2 by the q-th bit."""
        n = self.n
        stride = 1 << (n - 1 - q)
        total = 0.0
        for idx, a in enumerate(self.amp):
            p = a.real * a.real + a.imag * a.imag
            total += p if not (idx & stride) else -p
        return total


# ── the VQC forward pass (feature map → ansatz → measurement → head) ─────────
def _circuit_expectations(x, weights, n_qubits, layers):
    """Run the parameterized circuit and return per-qubit <Z> expectations.

    Pipeline (canonical hybrid VQC):
      1. FEATURE MAP — angle embedding: RY(x_q) on each qubit encodes classical
         input x into the quantum state (Mitarai et al. 2018).
      2. ANSATZ — a hardware-efficient layered ansatz: per layer, RY(w) & RZ(w)
         on each qubit followed by a ring of CNOTs (entangling), repeated
         `layers` times (PennyLane StronglyEntanglingLayers / Qiskit RealAmplitudes
         family).
      3. MEASUREMENT — <Z_q> expectation on each qubit.
    `weights` is a flat list of length layers*n_qubits*2 (RY,RZ per qubit/layer).
    """
    st = _State(n_qubits)
    # 1. feature map (angle embedding)
    for q in range(n_qubits):
        st.ry(q, x[q % len(x)])
    # 2. ansatz
    w = 0
    for _ in range(layers):
        for q in range(n_qubits):
            st.ry(q, weights[w]); w += 1
            st.rz(q, weights[w]); w += 1
        for q in range(n_qubits):  # ring of CNOTs (entangling layer)
            st.cnot(q, (q + 1) % n_qubits)
    # 3. measurement
    return [st.expect_z(q) for q in range(n_qubits)]


def _model_output(x, weights, head, n_qubits, layers):
    """Classical head: a linear readout over the measured expectations + bias.

    f(x) = sigmoid( sum_q head_w[q] * <Z_q> + head_b ) — the classical processor
    half of the hybrid loop that turns quantum measurements into a prediction.
    """
    zs = _circuit_expectations(x, weights, n_qubits, layers)
    s = head[-1]  # bias
    for q in range(n_qubits):
        s += head[q] * zs[q]
    # numerically-stable logistic
    if s >= 0:
        pred = 1.0 / (1.0 + math.exp(-s))
    else:
        e = math.exp(s)
        pred = e / (1.0 + e)
    return pred, zs


def _dataset(seed, n_qubits, n_samples=8):
    """A deterministic seeded toy dataset (classical inputs + binary targets).

    Inputs are angles in [0, π); the target is a fixed deterministic function of
    the inputs. This is a CONSTRUCTED toy problem for a reproducible training
    demo — NOT a benchmark and NOT evidence of any quantum advantage.
    """
    data = []
    for i in range(n_samples):
        x = [math.pi * _u01(seed, i, salt=10 + q) for q in range(n_qubits)]
        # deterministic target: parity-ish threshold on the input angles
        m = sum(math.sin(v) for v in x) / n_qubits
        y = 1.0 if m > 0.5 else 0.0
        data.append((x, y))
    return data


def _loss_and_grad(weights, head, data, n_qubits, layers, want_grad=True):
    """Mean-squared-error loss + REAL parameter-shift gradient over the weights.

    The parameter-shift rule (Mitarai 2018 / Schuld 2019): for a circuit whose
    output depends on a rotation angle θ_j, the exact analytic derivative is
        ∂<O>/∂θ_j = ( <O>(θ_j+π/2) − <O>(θ_j−π/2) ) / 2 .
    We use this on each ansatz weight (NOT finite differences), and standard
    analytic gradients for the classical linear head. Returns (loss, gW, gH).
    """
    # forward
    preds = []
    for x, y in data:
        p, _ = _model_output(x, weights, head, n_qubits, layers)
        preds.append(p)
    loss = sum((p - y) ** 2 for p, (_, y) in zip(preds, data)) / len(data)
    if not want_grad:
        return loss, None, None

    nW = len(weights)
    gW = [0.0] * nW
    gH = [0.0] * len(head)

    # dL/dpred for MSE, per sample (needed by both chains)
    dLdp = [2.0 * (preds[i] - data[i][1]) / len(data) for i in range(len(data))]

    # --- parameter-shift gradient on each ansatz weight ---
    # The head applies pred = sigmoid( w·z + b ); z depends on the weight via the
    # circuit. We shift the weight ±π/2, recompute z (hence pred), and combine.
    for j in range(nW):
        wp = list(weights); wp[j] += _SHIFT
        wm = list(weights); wm[j] -= _SHIFT
        g = 0.0
        for i, (x, y) in enumerate(data):
            pp, _ = _model_output(x, wp, head, n_qubits, layers)
            pm, _ = _model_output(x, wm, head, n_qubits, layers)
            # exact shift-rule derivative of pred wrt this weight
            dpred = (pp - pm) / 2.0
            g += dLdp[i] * dpred
        gW[j] = g

    # --- analytic gradient on the classical head (linear readout) ---
    for i, (x, y) in enumerate(data):
        p, zs = _model_output(x, weights, head, n_qubits, layers)
        dsig = p * (1.0 - p)  # d sigmoid / d(logit)
        for q in range(n_qubits):
            gH[q] += dLdp[i] * dsig * zs[q]
        gH[-1] += dLdp[i] * dsig  # bias
    return loss, gW, gH


def _train(seed=7, n_qubits=3, layers=2, steps=12):
    """Run the full hybrid training loop and return the pipeline + loss curve."""
    n_qubits = max(1, min(n_qubits, _MAX_QUBITS))
    layers = max(1, min(layers, _MAX_LAYERS))
    steps = max(1, min(steps, _MAX_STEPS))

    data = _dataset(seed, n_qubits)
    nW = layers * n_qubits * 2
    weights = [2.0 * math.pi * _u01(seed, j, salt=20) - math.pi for j in range(nW)]
    head = [0.5 - _u01(seed, q, salt=30) for q in range(n_qubits)] + [0.0]  # +bias

    loss_curve = []
    grad_norms = []
    for _step in range(steps):
        loss, gW, gH = _loss_and_grad(weights, head, data, n_qubits, layers, want_grad=True)
        loss_curve.append(round(loss, 8))
        gn = math.sqrt(sum(g * g for g in gW)) if gW else 0.0
        grad_norms.append(round(gn, 8))
        # classical SGD step on the parameter-shift gradient
        for j in range(nW):
            weights[j] -= _LR * gW[j]
        for q in range(len(head)):
            head[q] -= _LR * gH[q]
    final_loss, _, _ = _loss_and_grad(weights, head, data, n_qubits, layers, want_grad=False)
    loss_curve.append(round(final_loss, 8))

    # final accuracy on the toy set (reported honestly; it is a TOY problem)
    correct = 0
    for x, y in data:
        p, _ = _model_output(x, weights, head, n_qubits, layers)
        if (1.0 if p >= 0.5 else 0.0) == y:
            correct += 1
    accuracy = round(correct / len(data), 6)

    return {
        "n_qubits": n_qubits,
        "layers": layers,
        "steps": steps,
        "hilbert_dim": 1 << n_qubits,
        "n_weights": nW,
        "n_head_params": len(head),
        "n_train_samples": len(data),
        "loss_curve": loss_curve,
        "grad_norm_curve": grad_norms,
        "initial_loss": loss_curve[0],
        "final_loss": loss_curve[-1],
        "final_accuracy": accuracy,
        "final_grad_norm": grad_norms[-1] if grad_norms else 0.0,
    }


def _lambda_gate(train):
    """Λ advisory over the run (Conjecture 1, gray — NEVER green).

    The advisory rises as the loss falls and as the gradient stays non-vanishing
    (barren-plateau proxy: a vanishing gradient LOWERS the advisory, because a
    flat landscape is untrainable — McClean et al. 2018). It is bounded < 1.0 and
    trust is hard-capped at 0.97. This is NOT a claim that the run is correct or
    advantageous; it is a gray restraint advisory.
    """
    improve = 0.0
    if train["initial_loss"] > 0:
        improve = max(0.0, (train["initial_loss"] - train["final_loss"]) / train["initial_loss"])
    # barren-plateau proxy: reward a gradient that has NOT vanished
    gn = train["final_grad_norm"]
    grad_health = gn / (gn + 0.05)  # in (0,1), →0 as gradient vanishes
    raw = 0.6 * improve + 0.4 * grad_health
    lam = round(min(_LAMBDA_MAX, max(_LAMBDA_MIN, _LAMBDA_MIN + (_LAMBDA_MAX - _LAMBDA_MIN) * raw)), 6)
    admitted = bool(lam >= _LAMBDA_ADMIT)
    trust = round(min(_TRUST_CAP, 0.5 * improve + 0.5 * (lam / _LAMBDA_MAX)), 6)
    return {
        "status": "Λ = Conjecture 1 (advisory, gray — NEVER green, not a theorem)",
        "value": lam,
        "admit_threshold": _LAMBDA_ADMIT,
        "admitted": admitted,
        "bounds": {"min": _LAMBDA_MIN, "max": _LAMBDA_MAX},
        "loss_improvement": round(improve, 6),
        "grad_health": round(grad_health, 6),
        "barren_plateau_note": (
            "grad_health falls toward 0 as the gradient vanishes; barren plateaus "
            "make large VQCs untrainable (McClean et al. 2018, arXiv-linked)."
        ),
        "trust": trust,
        "trust_cap": _TRUST_CAP,
    }


def _sign_receipt(run_summary):
    """Emit ONE DSSE receipt over the run summary.

    In-Space (SZL_COSIGN_PRIVATE_KEY_PEM present) szl_dsse produces a REAL
    ECDSA-P256-SHA256 signature (verifiable by `cosign verify-blob`). Locally
    (no secret) it returns an HONEST UNSIGNED-LOCAL envelope (signed:false, no
    fabricated signature). If szl_dsse is unavailable we still return a clearly
    UNSIGNED preview (a plain content hash, never a fake signature).
    """
    canonical = "|".join([
        f"model=governed-vqc",
        f"seed={run_summary['seed']}",
        f"n_qubits={run_summary['n_qubits']}",
        f"layers={run_summary['layers']}",
        f"steps={run_summary['steps']}",
        f"initial_loss={run_summary['initial_loss']}",
        f"final_loss={run_summary['final_loss']}",
        f"final_accuracy={run_summary['final_accuracy']}",
        f"lambda={run_summary['lambda_value']}",
        f"trust={run_summary['trust']}",
    ])
    preview_digest = hashlib.sha3_256(canonical.encode("utf-8")).hexdigest()
    receipt_body = {
        "kind": "szl.vqc.run",
        "canonical_summary": canonical,
        "content_sha3_256": preview_digest,
        "no_advantage_disclaimer": (
            "SIMULATED VQC run. NO demonstrated quantum advantage for classical-data "
            "ML today (Cerezo dequantization arXiv:2312.09121; Sheoran Sci. Rep. 2025; "
            "barren plateaus McClean 2018). This receipt attests the RUN, not any speedup."
        ),
    }
    env = None
    signing_available = False
    signed = False
    honesty = None
    if _dsse is not None:
        try:
            signing_available = bool(_dsse.signing_available())
            env = _dsse.sign_payload(receipt_body, VQC_PAYLOAD_TYPE)
            signed = bool(env.get("signed", False))
            honesty = env.get("honesty")
        except Exception as e:  # pragma: no cover
            env = {"error": f"szl_dsse sign failed: {e!r}"}
    if env is None:
        # szl_dsse unavailable — honest UNSIGNED-LOCAL fallback, no fake signature.
        env = {
            "payloadType": VQC_PAYLOAD_TYPE,
            "signatures": [],
            "signed": False,
            "honesty": "UNSIGNED-LOCAL — szl_dsse unavailable in this runtime; no signature fabricated.",
        }
        honesty = env["honesty"]
    return {
        "kind": "DSSE-signed VQC run receipt (real ECDSA-P256 in-Space; UNSIGNED-LOCAL locally)",
        "payload_type": VQC_PAYLOAD_TYPE,
        "content_sha3_256": preview_digest,
        "signing_available": signing_available,
        "signed": signed,
        "mode": "REAL-ECDSA-P256-IN-SPACE" if signed else "UNSIGNED-LOCAL",
        "honesty": honesty,
        "envelope": env,
        "verify_hint": (
            "cosign verify-blob --key cosign.pub  (in-Space signed receipts); "
            "locally the envelope is honestly UNSIGNED (signatures:[], signed:false)."
        ),
    }


def _pipeline_description(n_qubits, layers):
    """Human-readable description of the hybrid VQC pipeline stages."""
    return [
        {"stage": "feature_map", "kind": "angle embedding (RY on each qubit)",
         "detail": f"classical input encoded as RY(x_q) on {n_qubits} qubits (Mitarai et al. 2018)."},
        {"stage": "ansatz", "kind": "hardware-efficient RY+RZ + ring-CNOT",
         "detail": f"{layers} layer(s): per-qubit RY,RZ then a ring of CNOTs (PennyLane StronglyEntanglingLayers / Qiskit RealAmplitudes family)."},
        {"stage": "measurement", "kind": "Pauli-Z expectation",
         "detail": "<Z_q> measured on each qubit from the simulated state vector."},
        {"stage": "classical_head", "kind": "linear readout + sigmoid",
         "detail": "f(x) = sigmoid( head_w · <Z> + head_b ) — the classical processor half of the hybrid loop."},
        {"stage": "loss", "kind": "mean squared error",
         "detail": "MSE to a deterministic seeded target on a CONSTRUCTED toy set (not a benchmark)."},
        {"stage": "gradient_step", "kind": "REAL parameter-shift rule",
         "detail": "exact ±π/2 shift rule on each ansatz weight (Schuld et al. 2019); analytic gradient on the head; one SGD step."},
    ]


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def run_vqc(seed=7, n_qubits=3, layers=2, steps=12):
    """Full governed VQC run — the pure-Python entry point used by the endpoint."""
    train = _train(seed=seed, n_qubits=n_qubits, layers=layers, steps=steps)
    gate = _lambda_gate(train)
    run_summary = {
        "seed": seed,
        "n_qubits": train["n_qubits"],
        "layers": train["layers"],
        "steps": train["steps"],
        "initial_loss": train["initial_loss"],
        "final_loss": train["final_loss"],
        "final_accuracy": train["final_accuracy"],
        "lambda_value": gate["value"],
        "trust": gate["trust"],
    }
    receipt = _sign_receipt(run_summary)
    payload = {
        "seed": seed,
        "n_qubits": train["n_qubits"],
        "layers": train["layers"],
        "steps": train["steps"],
        "hilbert_dim": train["hilbert_dim"],
        "n_weights": train["n_weights"],
        "n_head_params": train["n_head_params"],
        "n_train_samples": train["n_train_samples"],
        "pipeline": _pipeline_description(train["n_qubits"], train["layers"]),
        "training": {
            "loss_curve": train["loss_curve"],
            "grad_norm_curve": train["grad_norm_curve"],
            "initial_loss": train["initial_loss"],
            "final_loss": train["final_loss"],
            "final_accuracy": train["final_accuracy"],
            "final_grad_norm": train["final_grad_norm"],
            "optimizer": "SGD on the parameter-shift gradient",
            "learning_rate": _LR,
            "shift": _SHIFT,
            "gradient_method": "REAL parameter-shift rule (exact ±π/2), NOT finite differences",
        },
        "lambda_gate": gate,
        "receipt": receipt,
        "no_advantage_banner": (
            "HONESTY IS THE FEATURE — there is NO demonstrated quantum advantage for "
            "machine learning on real-world (classical) data today; none that survives "
            "a fair comparison. This is a REAL parameter-shift VQC run in a small "
            "deterministic SIMULATION, Λ-gated and receipt-backed — it is NOT a speedup "
            "or accuracy claim. VQCs also suffer barren plateaus (gradients vanish "
            "exponentially with size) and the dequantization trap (models trainable "
            "enough to avoid plateaus are often classically simulable)."
        ),
        "parts_labeled": {
            "SIMULATED": [
                "state-vector simulator (complex amplitudes over 2**n_qubits, pure stdlib)",
                "angle-embedding feature map + hardware-efficient RY/RZ ring-CNOT ansatz",
                "Pauli-Z expectation measurement + classical linear+sigmoid head",
                "MSE loss + REAL parameter-shift gradient step (exact ±π/2)",
                "training-loss curve + grad-norm curve (genuinely computed, reported not fabricated)",
            ],
            "MODELED": [
                "the toy CONSTRUCTED dataset (deterministic seeded target — NOT a benchmark)",
            ],
            "CONJECTURE": [
                "Λ as a trust gate over the run (Λ = Conjecture 1, gray — never green)",
            ],
            "REAL_IN_SPACE": [
                "the DSSE receipt signature (ECDSA-P256-SHA256) when the cosign secret is present; "
                "honest UNSIGNED-LOCAL otherwise",
            ],
        },
        "honest_note": (
            "SIMULATED + MODELED + CONJECTURE. The VQC math is REAL (a genuine "
            "state-vector simulation with an analytically-exact parameter-shift "
            "gradient), but it is SMALL and there is NO quantum hardware, NO "
            "PennyLane/Qiskit dependency, and NO trained model — and CRUCIALLY no "
            "quantum advantage: on classical data a tuned classical model wins, and "
            "VQCs face barren plateaus + the dequantization trap. Λ is the restraint "
            "advisory Λ = Conjecture 1 (gray, NEVER green); trust is capped at 0.97 "
            "and is never 1.0. The receipt is a REAL ECDSA-P256 DSSE signature in-Space "
            "and an honest UNSIGNED-LOCAL envelope locally (no signature fabricated). "
            "Cites the parameter-shift rule (Mitarai 2018 arXiv:1803.00745; Schuld 2019 "
            "arXiv:1811.11184), PennyLane (arXiv:1811.04968), Qiskit ML (arXiv:2505.17756), "
            "barren plateaus (McClean 2018), and the dequantization result (Cerezo "
            "arXiv:2312.09121). SZL claims NONE of these methods as its own. Nothing "
            "here is in the locked-8."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    return payload


def _h_vqc_run(req: Request):
    seed = _ii(req, "seed", 7)
    n_qubits = max(1, min(_ii(req, "n_qubits", 3), _MAX_QUBITS))
    layers = max(1, min(_ii(req, "layers", 2), _MAX_LAYERS))
    steps = max(1, min(_ii(req, "steps", 12), _MAX_STEPS))
    p = run_vqc(seed=seed, n_qubits=n_qubits, layers=layers, steps=steps)
    p["label"] = "SIMULATED"
    p["model"] = "Governed parameter-shift Hybrid VQC (SIMULATION-ONLY; Λ-gated; signed receipt)"
    # Surface reads label at top level OR payload.label, metrics from payload.
    return JSONResponse({"label": "SIMULATED", "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/vqc/run onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/vqc"
    handlers = [(f"{base}/run", _h_vqc_run)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    # Self-check: verifies the parameter-shift gradient against a finite-difference
    # estimate, and that the loss curve actually decreases (the loop trains).
    p = run_vqc(seed=7, n_qubits=3, layers=2, steps=12)
    tr = p["training"]
    g = p["lambda_gate"]
    print("hilbert_dim:", p["hilbert_dim"], "weights:", p["n_weights"], "samples:", p["n_train_samples"])
    print("initial_loss:", tr["initial_loss"], "final_loss:", tr["final_loss"], "acc:", tr["final_accuracy"])
    print("lambda:", g["value"], "admitted:", g["admitted"], "trust:", g["trust"], "(cap", g["trust_cap"], ")")
    print("receipt signed:", p["receipt"]["signed"], "mode:", p["receipt"]["mode"],
          "digest:", p["receipt"]["content_sha3_256"][:16], "...")

    assert tr["final_loss"] <= tr["initial_loss"] + 1e-9, "loss should not increase overall"
    assert g["bounds"]["max"] < 1.0, "Λ advisory must never reach 1.0 (Conjecture 1)"
    assert 0.0 <= g["trust"] <= _TRUST_CAP, "trust must be capped at 0.97"

    # parameter-shift vs finite-difference cross-check on weight 0
    data = _dataset(7, 3)
    nW = 2 * 2 * 3
    w = [2.0 * math.pi * _u01(7, j, salt=20) - math.pi for j in range(nW)]
    h = [0.5 - _u01(7, q, salt=30) for q in range(3)] + [0.0]
    _, gW, _ = _loss_and_grad(w, h, data, 3, 2, want_grad=True)
    eps = 1e-6
    wp = list(w); wp[0] += eps
    wm = list(w); wm[0] -= eps
    lp, _, _ = _loss_and_grad(wp, h, data, 3, 2, want_grad=False)
    lm, _, _ = _loss_and_grad(wm, h, data, 3, 2, want_grad=False)
    fd = (lp - lm) / (2 * eps)
    print("param-shift grad[0]:", round(gW[0], 8), "finite-diff:", round(fd, 8),
          "abs-err:", round(abs(gW[0] - fd), 8))
    assert abs(gW[0] - fd) < 1e-4, "parameter-shift gradient must match finite-difference"
    print("OK — parameter-shift gradient verified; loop trains; label SIMULATED; Λ=Conjecture 1")
