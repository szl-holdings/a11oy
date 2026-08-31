"""Auditable, MODELED Lambda-AttnRes tensor aggregation."""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction

import torch
import torch.nn.functional as F
from torch import nn

EPS_FLOOR = math.exp(-5.0)
MAX_DENOMINATOR = 1 << 20

RationalRows = list[tuple[tuple[int, ...], tuple[tuple[int, int], ...]]]


def _inverse_sigmoid(probability: float) -> float:
    if not 0.0 < probability < 1.0:
        raise ValueError("trainable lambda must be strictly between zero and one")
    return math.log(probability / (1.0 - probability))


def _project_row(row: list[float], depth: int) -> list[Fraction]:
    """Project to an exact common-denominator simplex deterministically."""
    if not row or not all(math.isfinite(value) and value >= 0.0 for value in row):
        raise ValueError("attention rows must be finite and non-negative")
    total = sum(row)
    if total <= 0.0:
        raise ValueError("attention rows must have positive mass")
    denominator = min(MAX_DENOMINATOR, 1 << max(1, depth * 4))
    scaled = [value / total * denominator for value in row]
    numerators = [math.floor(value) for value in scaled]
    remainder = denominator - sum(numerators)
    order = sorted(
        range(len(row)),
        key=lambda index: (-(scaled[index] - numerators[index]), index),
    )
    for index in order[:remainder]:
        numerators[index] += 1
    projected = [Fraction(numerator, denominator) for numerator in numerators]
    if sum(projected, Fraction(0)) != Fraction(1):
        raise AssertionError("rational projection did not close exactly")
    return projected


def egyptian_project(
    alpha: torch.Tensor,
    depth: int = 4,
) -> tuple[torch.Tensor, RationalRows]:
    """Return a straight-through exact-rational simplex projection and audit rows."""
    if alpha.ndim != 3:
        raise ValueError("alpha must have shape (B,T,S)")
    if depth <= 0:
        raise ValueError("depth must be positive")
    if not torch.isfinite(alpha).all():
        raise ValueError("alpha must contain only finite values")

    batch, tokens, sources = alpha.shape
    flat = alpha.detach().to(torch.float64).reshape(-1, sources).cpu().tolist()
    exact = torch.empty((len(flat), sources), dtype=torch.float64)
    rows: RationalRows = []
    for row_index, row in enumerate(flat):
        fractions = _project_row(row, depth)
        for source_index, fraction in enumerate(fractions):
            exact[row_index, source_index] = float(fraction)
        rows.append(
            (
                (row_index,),
                tuple(
                    (fraction.numerator, fraction.denominator) for fraction in fractions
                ),
            )
        )
    exact = exact.reshape(batch, tokens, sources).to(
        device=alpha.device, dtype=alpha.dtype
    )
    straight_through = alpha + (exact - alpha).detach()
    return straight_through, rows


def build_certificate(
    rows: RationalRows | None,
    lam: float,
    eps: float,
    n_sources: int,
    d_model: int,
    scoring_dtype: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "doctrine": "Doctrine-v11",
        "label": "MODELED",
        "aggregator": "lambda-attnres/v1",
        "lambda": round(lam, 12),
        "epsilon_floor": round(eps, 12),
        "n_sources": n_sources,
        "d_model": d_model,
        "scoring_dtype": scoring_dtype,
        "rational_rows": rows,
        "claim_scope": "auditability-only",
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["cert_sha256"] = hashlib.sha256(blob).hexdigest()
    return payload


class LambdaAttnRes(nn.Module):
    """Blend arithmetic depth attention with epsilon-pinned geometric magnitude."""

    def __init__(
        self,
        d_model: int,
        n_sources_max: int,
        lam_init: float = 0.25,
        egyptian: bool = True,
        depth: int = 4,
        eps: float = EPS_FLOOR,
    ) -> None:
        super().__init__()
        if d_model <= 0 or n_sources_max <= 0:
            raise ValueError("d_model and n_sources_max must be positive")
        if not 0.0 <= lam_init <= 1.0:
            raise ValueError("lam_init must be in [0, 1]")
        if depth <= 0 or not math.isfinite(eps) or eps <= 0.0:
            raise ValueError("depth and epsilon floor must be positive")

        self.d_model = d_model
        self.n_sources_max = n_sources_max
        self.egyptian = egyptian
        self.depth = depth
        self.eps = eps
        self.scoring_dtype = "float16-canonicalized"

        self.pseudo_query = nn.Parameter(torch.zeros(d_model, dtype=torch.float32))
        nn.init.normal_(self.pseudo_query, std=d_model**-0.5)
        self.key_norm = (
            nn.RMSNorm(d_model) if hasattr(nn, "RMSNorm") else _RMSNorm(d_model)
        )
        if lam_init in (0.0, 1.0):
            self.register_parameter("_lam_raw", None)
            self.register_buffer(
                "_lam_fixed", torch.tensor(lam_init, dtype=torch.float32)
            )
        else:
            self._lam_raw = nn.Parameter(
                torch.tensor(_inverse_sigmoid(lam_init), dtype=torch.float32)
            )
            self.register_buffer("_lam_fixed", None)

    @property
    def lam(self) -> torch.Tensor:
        if self._lam_raw is None:
            return self._lam_fixed
        return torch.sigmoid(self._lam_raw)

    def _weights(self, sources: torch.Tensor) -> torch.Tensor:
        # Both float32 and float16 callers score the same float16-quantized values.
        # This makes the certificate about one explicit numerical surface.
        canonical = sources.to(torch.float16).to(torch.float32)
        if not torch.isfinite(canonical).all():
            raise ValueError("sources exceed the certificate scoring range")
        normalized = self.key_norm(canonical)
        logits = torch.einsum("btsd,d->bts", normalized, self.pseudo_query.float())
        return F.softmax(logits, dim=-1)

    def forward(self, sources: torch.Tensor, return_cert: bool = False):
        if sources.ndim != 4:
            raise ValueError("expected sources with shape (B,T,S,D)")
        _, _, source_count, model_width = sources.shape
        if source_count <= 0 or source_count > self.n_sources_max:
            raise ValueError("source count is outside configured bounds")
        if model_width != self.d_model:
            raise ValueError("source model width does not match d_model")
        if not torch.isfinite(sources).all():
            raise ValueError("sources must contain only finite values")

        alpha = self._weights(sources)
        if self.egyptian:
            projected, rows = egyptian_project(alpha, depth=self.depth)
        else:
            projected, rows = alpha, None

        weights = projected.unsqueeze(-1)
        source_values = sources.to(torch.float32)
        arithmetic = (weights * source_values).sum(dim=-2)
        magnitudes = source_values.abs().clamp_min(self.eps)
        log_magnitude = (weights * magnitudes.log()).sum(dim=-2)
        geometric = torch.sign(arithmetic) * log_magnitude.exp()
        lam = self.lam.float()
        output = ((1.0 - lam) * arithmetic + lam * geometric).to(sources.dtype)

        if not return_cert:
            return output
        certificate = build_certificate(
            rows=rows,
            lam=float(lam.detach().cpu()),
            eps=self.eps,
            n_sources=source_count,
            d_model=self.d_model,
            scoring_dtype=self.scoring_dtype,
        )
        return output, certificate


class _RMSNorm(nn.Module):
    def __init__(self, width: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.gain = nn.Parameter(torch.ones(width, dtype=torch.float32))
        self.eps = eps

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        scale = value.pow(2).mean(-1, keepdim=True).add(self.eps).rsqrt()
        return self.gain * value * scale
