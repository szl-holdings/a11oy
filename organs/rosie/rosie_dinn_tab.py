"""
rosie_dinn_tab.py — Rosie Tab 12 "DINN Lab" (ADDITIVE)
======================================================

Interactive DINN Lab for the Rosie operator console. Lets an operator pick one
of the three DINNs (Knot / Doctrine / Bekenstein), train it live, and see the
loss curve + (for Doctrine) the 13-axis monitor against Λ_FLOOR=0.90.

Self-contained: a tiny numpy autograd is inlined so the Space needs no extra
dependency beyond numpy (already present via gradio). Mirrors the szl-cookbook
recipes knot-calculus-v2 / doctrine-dinn-v1 / bekenstein-dinn-v1.

Honesty: every DINN claim is labelled "Lean obligation pending (sorry
placeholder)" — none is claimed proven.

© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
from __future__ import annotations

import base64
import io
import math

import numpy as np

LAMBDA_FLOOR = 0.90      # Doctrine v9 canonical
N_AXES = 13
S_MAX = math.pi * 0.6 * 0.6   # Bekenstein simplified bound for the demo

AXIS_NAMES = [
    "honesty", "calibration", "corrigibility", "non-deception", "harm-avoid",
    "transparency", "consent", "reversibility", "scope", "evidence",
    "uncertainty", "doctrine-adh", "provenance",
]


# --- tiny numpy MLP with manual gradients (no torch needed) ------------------
class _MLP:
    def __init__(self, sizes, seed=0, out_act="tanh"):
        rng = np.random.default_rng(seed)
        self.W, self.b = [], []
        for i in range(len(sizes) - 1):
            s = math.sqrt(2.0 / sizes[i])
            self.W.append(rng.normal(0, s, (sizes[i], sizes[i + 1])))
            self.b.append(np.zeros((1, sizes[i + 1])))
        self.out_act = out_act

    def forward(self, x):
        self.cache = [x]
        h = x
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            z = h @ W + b
            if i < len(self.W) - 1:
                h = np.tanh(z)
            else:
                if self.out_act == "tanh":
                    h = np.tanh(z)
                elif self.out_act == "sigmoid":
                    h = np.where(z >= 0, 1.0 / (1.0 + np.exp(-np.clip(z, -60, 60))),
                                 np.exp(np.clip(z, -60, 60)) / (1.0 + np.exp(np.clip(z, -60, 60))))
                elif self.out_act == "softmax":
                    e = np.exp(z - z.max(axis=1, keepdims=True))
                    h = e / e.sum(axis=1, keepdims=True)
                else:
                    h = z
            self.cache.append((z, h))
        return h


def _b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode()


# --- numerical-gradient training (robust, framework-free) --------------------
def _train_numgrad(loss_fn, params, epochs, lr):
    """Tiny SPSA-style optimiser: works for any scalar loss over a param list."""
    hist = []
    for _ in range(epochs):
        loss0 = loss_fn()
        hist.append(loss0)
        for p in params:
            g = np.zeros_like(p)
            # finite-difference along a random direction (fast, stochastic)
            d = np.random.default_rng().normal(0, 1, p.shape)
            eps = 1e-3
            p += eps * d
            lp = loss_fn()
            p -= eps * d
            g = ((lp - loss0) / eps) * d
            p -= lr * g
    return hist


def run_dinn(model_name: str, lam: float, epochs: int = 60):
    """Train the chosen DINN and return (markdown, image_data_uri)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rng = np.random.default_rng(0)
    epochs = int(max(10, min(120, epochs)))

    if model_name.startswith("DOCTRINE"):
        net = _MLP([8, 24, N_AXES], seed=0, out_act="sigmoid")
        X = rng.normal(0, 1, (96, 8))
        base = rng.uniform(0.78, 0.97, (96, N_AXES))
        base[:, [2, 6, 11]] -= rng.uniform(0.05, 0.18, (96, 3))
        Y = np.clip(base, 0, 1)

        def loss():
            p = net.forward(X)
            task = ((p - Y) ** 2).mean()
            viol = np.maximum(0, (LAMBDA_FLOOR + 0.03) - p)
            doc = (viol ** 2).mean(axis=0).sum()
            return task + lam * doc

        params = net.W + net.b
        hist = _train_numgrad(loss, params, epochs, lr=0.05)
        p = net.forward(X)
        per_axis_min = p.min(axis=0)
        fig, ax = plt.subplots(figsize=(6.6, 3.4))
        ax.bar(range(N_AXES), per_axis_min, color="#3b82f6")
        ax.axhline(LAMBDA_FLOOR, color="#dc2626", ls="--", lw=2, label=f"Λ_FLOOR={LAMBDA_FLOOR}")
        ax.set_xticks(range(N_AXES)); ax.set_xticklabels([n[:4] for n in AXIS_NAMES], rotation=60, fontsize=7)
        ax.set_ylim(0.7, 1.0); ax.set_title("DOCTRINE-DINN — 13-axis monitor"); ax.legend(fontsize=8)
        img = _b64(fig); plt.close(fig)
        md = (f"### DOCTRINE-DINN (doctrine-dinn-v1)\n"
              f"13-axis reasoner · Λ_FLOOR={LAMBDA_FLOOR} · λ_doctrine={lam:g} · {epochs} epochs\n\n"
              f"- min axis at convergence: **{per_axis_min.min():.3f}**\n"
              f"- doctrine residual: **{hist[-1]:.4f}**\n\n"
              f"> Governance becomes a learning signal, not a wall. "
              f"*Lean obligation pending (sorry placeholder) — not proven.*")
        return md, img

    if model_name.startswith("BEKENSTEIN"):
        net = _MLP([8, 24, 8], seed=0, out_act="softmax")
        X = rng.normal(0, 1, (96, 8))
        W = rng.normal(0, 1, (8, 8))
        soft = np.exp(X @ W - (X @ W).max(1, keepdims=True)); soft /= soft.sum(1, keepdims=True)
        Y = 0.5 * soft + 0.5 / 8.0

        def loss():
            p = net.forward(X)
            task = ((p - Y) ** 2).mean()
            h = -(p * np.log(p + 1e-12)).sum(1)
            bek = (np.maximum(0, h - S_MAX) ** 2).mean()
            return task + lam * bek

        params = net.W + net.b
        hist = _train_numgrad(loss, params, epochs, lr=0.05)
        p = net.forward(X)
        meanH = float((-(p * np.log(p + 1e-12)).sum(1)).mean())
        fig, ax = plt.subplots(figsize=(6.6, 3.4))
        ax.plot(hist, color="#8b5cf6", lw=2, label="loss (task + λ_B·Bekenstein)")
        ax.axhline(S_MAX, color="#dc2626", ls="--", lw=1.5, label=f"S_max=π·R·E={S_MAX:.3f}")
        ax.set_xlabel("epoch"); ax.set_title("BEKENSTEIN-DINN — entropy cap"); ax.legend(fontsize=8)
        img = _b64(fig); plt.close(fig)
        md = (f"### BEKENSTEIN-DINN (bekenstein-dinn-v1)\n"
              f"S_max = π·R·E = **{S_MAX:.3f} nats** · λ_B={lam:g} · {epochs} epochs\n\n"
              f"- mean output entropy: **{meanH:.3f} nats** "
              f"({'UNDER' if meanH < S_MAX else 'OVER'} cap)\n\n"
              f"> *Lean obligation pending (sorry placeholder) — not proven.*")
        return md, img

    # KNOT-DINN (default)
    net = _MLP([3, 12, 1], seed=0, out_act="tanh")
    nb = 80
    X = rng.normal(0, 1, (nb, 3))
    Y = np.tanh(X.sum(1, keepdims=True))
    Xm = X + rng.normal(0, 0.05, X.shape)   # "moved" braids (R1-like perturbation)

    def loss():
        f0 = net.forward(X)
        f1 = net.forward(Xm)
        task = ((f0 - Y) ** 2).mean()
        res = ((f0 - f1) ** 2).mean()
        return task + lam * res

    params = net.W + net.b
    hist = _train_numgrad(loss, params, epochs, lr=0.05)
    gap = float(np.abs(net.forward(X) - net.forward(Xm)).mean())
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    ax.plot(hist, color="#ef4444", lw=2, label="loss (task + λ_R·Reidemeister)")
    ax.set_xlabel("epoch"); ax.set_yscale("log"); ax.set_title("KNOT-DINN — invariance residual"); ax.legend(fontsize=8)
    img = _b64(fig); plt.close(fig)
    md = (f"### KNOT-DINN (knot-calculus-v2)\n"
          f"f_θ(braid)→invariant · λ_R={lam:g} · {epochs} epochs\n\n"
          f"- mean invariance gap |f(K)−f(R(K))|: **{gap:.4f}**\n\n"
          f"> The Reidemeister law becomes a learning signal. "
          f"*Lean obligation pending (sorry placeholder) — not proven.*")
    return md, img


DINN_INTRO = (
    "## DINN Lab — Doctrine-Informed Neural Networks\n\n"
    "DINNs generalise physics-informed neural networks (PINNs): instead of a PDE "
    "residual, a DINN carries a **law residual** — a Reidemeister invariance "
    "(Knot), a doctrine Λ-floor (Doctrine), or a Bekenstein entropy cap "
    "(Bekenstein). **Governance becomes a learning signal, not a wall.**\n\n"
    "Pick a model, set the law-weight λ, and train it live. Recipes: "
    "[szl-cookbook](https://github.com/szl-holdings/szl-cookbook/tree/main/recipes).\n\n"
    "⚠ **Honesty:** every DINN ships a Lean obligation as a `sorry` placeholder "
    "— *Lean obligation pending*. None is claimed proven."
)


def build_dinn_tab(gr, demo):
    """Insert the DINN Lab tab. Call inside an open `with gr.Tabs():` block."""
    with gr.TabItem("DINN Lab"):
        gr.Markdown(DINN_INTRO)
        with gr.Row():
            dinn_model = gr.Dropdown(
                choices=["DOCTRINE-DINN", "KNOT-DINN", "BEKENSTEIN-DINN"],
                value="DOCTRINE-DINN", label="DINN model",
            )
            dinn_lam = gr.Slider(0.0, 20.0, value=10.0, step=0.5, label="law weight λ")
            dinn_epochs = gr.Slider(10, 120, value=60, step=10, label="epochs")
        dinn_btn = gr.Button("▶ Train DINN live", variant="primary")
        dinn_out = gr.Markdown()
        dinn_img = gr.Image(label="trained curve / axis monitor", type="filepath")

        def _go(model, lam, epochs):
            md, data_uri = run_dinn(model, float(lam), int(epochs))
            # write the data-uri PNG to a temp file for gr.Image
            import tempfile
            raw = base64.b64decode(data_uri.split(",", 1)[1])
            f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            f.write(raw); f.close()
            return md, f.name

        dinn_btn.click(_go, inputs=[dinn_model, dinn_lam, dinn_epochs],
                       outputs=[dinn_out, dinn_img])
