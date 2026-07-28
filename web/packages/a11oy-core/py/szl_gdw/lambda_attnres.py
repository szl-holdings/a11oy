#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

"""Auditable Lambda-AttnRes aggregation (MODELED; no training claim)."""

from __future__ import annotations

from fractions import Fraction
from hashlib import sha256
import json
import math
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


EPS_FLOOR = math.exp(-5.0)
G_MIN = -5.0
MAX_DENOM = 1 << 20


def _inv_sigmoid(p: float) -> float:
    if not 0.0 < p < 1.0:
        raise ValueError("inverse sigmoid requires an interior probability")
    return math.log(p / (1.0 - p))


class LambdaAttnRes(nn.Module):
    """Blend arithmetic and sign-preserving geometric depth aggregation."""

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
        if d_model <= 0 or n_sources_max <= 0 or depth <= 0:
            raise ValueError("dimensions and Egyptian depth must be positive")
        if not 0.0 <= lam_init <= 1.0:
            raise ValueError("lam_init must be in [0, 1]")
        if not math.isfinite(eps) or eps <= 0.0:
            raise ValueError("eps must be finite and positive")
        self.d_model = d_model
        self.n_sources_max = n_sources_max
        self.egyptian = egyptian
        self.depth = depth
        self.eps = eps
        self._lam_endpoint = lam_init if lam_init in (0.0, 1.0) else None

        self.pseudo_query = nn.Parameter(torch.zeros(d_model))
        nn.init.normal_(self.pseudo_query, std=d_model**-0.5)
        raw = 0.0 if self._lam_endpoint is not None else _inv_sigmoid(lam_init)
        self._lam_raw = nn.Parameter(torch.tensor(raw, dtype=torch.float32))
        self.key_norm = (
            nn.RMSNorm(d_model) if hasattr(nn, "RMSNorm") else _RMSNorm(d_model)
        )

    @property
    def lam(self) -> torch.Tensor:
        if self._lam_endpoint is not None:
            return self._lam_raw.new_tensor(self._lam_endpoint)
        return torch.sigmoid(self._lam_raw)

    def _weights(self, sources: torch.Tensor) -> torch.Tensor:
        # FP32 makes certificate inputs stable across device/dtype presentation.
        normalized = self.key_norm(sources.float())
        logits = torch.einsum(
            "btsd,d->bts", normalized, self.pseudo_query.float()
        )
        return F.softmax(logits, dim=-1)

    def forward(self, sources: torch.Tensor, return_cert: bool = False):
        if sources.dim() != 4:
            raise ValueError("expected sources with shape (B,T,S,D)")
        _, _, source_count, dimension = sources.shape
        if not 1 <= source_count <= self.n_sources_max:
            raise ValueError("source count is outside the configured bound")
        if dimension != self.d_model:
            raise ValueError("source dimension does not match d_model")
        if not torch.isfinite(sources).all():
            raise ValueError("sources must be finite")

        alpha = self._weights(sources)
        if self.egyptian:
            alpha_q, rows = egyptian_project(alpha, depth=self.depth)
        else:
            alpha_q, rows = alpha, None
        weights = alpha_q.to(device=sources.device, dtype=sources.dtype).unsqueeze(-1)
        arithmetic = (weights * sources).sum(dim=-2)

        magnitude = sources.abs().clamp_min(self.eps)
        log_magnitude = (weights * magnitude.log()).sum(dim=-2)
        log_magnitude = log_magnitude.clamp(
            min=G_MIN * self.n_sources_max,
            max=80.0,
        )
        geometric = torch.sign(arithmetic) * log_magnitude.exp()
        lam = self.lam.to(device=sources.device, dtype=sources.dtype)
        output = (1.0 - lam) * arithmetic + lam * geometric
        if not return_cert:
            return output
        return output, build_certificate(
            rows=rows,
            lam=float(self.lam.detach().cpu()),
            eps=self.eps,
            n_sources=source_count,
            d_model=self.d_model,
            shape=tuple(int(value) for value in sources.shape),
            egyptian=self.egyptian,
        )


class _RMSNorm(nn.Module):
    def __init__(self, dimension: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.gain = nn.Parameter(torch.ones(dimension))
        self.eps = eps

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return (
            self.gain
            * value
            * value.pow(2).mean(-1, keepdim=True).add(self.eps).rsqrt()
        )


def _row_to_egyptian(row: List[float], depth: int) -> List[Fraction]:
    if not row or depth <= 0 or not all(math.isfinite(value) for value in row):
        raise ValueError("Egyptian projection requires a finite non-empty row")
    count = len(row)
    output = [Fraction(0)] * count
    remaining = Fraction(1)
    order = sorted(range(count), key=lambda index: (-row[index], index))
    for index in order[: min(depth, count)]:
        if remaining <= 0:
            break
        target = Fraction(max(0.0, row[index])).limit_denominator(MAX_DENOM)
        if target <= 0:
            continue
        cap = min(target, remaining)
        denominator = max(1, math.ceil(1.0 / float(cap)))
        unit = Fraction(1, denominator)
        while unit > remaining:
            denominator += 1
            unit = Fraction(1, denominator)
        output[index] += unit
        remaining -= unit
    output[order[0]] += remaining
    if sum(output, Fraction(0)) != Fraction(1):
        raise ArithmeticError("Egyptian projection did not close exactly")
    return output


def egyptian_project(
    alpha: torch.Tensor,
    depth: int = 4,
) -> Tuple[
    torch.Tensor,
    List[Tuple[Tuple[int, int], Tuple[Tuple[int, int], ...]]],
]:
    if alpha.dim() != 3:
        raise ValueError("expected attention weights with shape (B,T,S)")
    batch, tokens, source_count = alpha.shape
    flat = alpha.detach().float().reshape(-1, source_count).cpu().tolist()
    quantized = torch.empty(len(flat), source_count, dtype=torch.float64)
    rows = []
    for row_index, row in enumerate(flat):
        fractions = _row_to_egyptian(row, depth)
        for column, fraction in enumerate(fractions):
            quantized[row_index, column] = float(fraction)
        rows.append(
            (
                (row_index // tokens, row_index % tokens),
                tuple(
                    (fraction.numerator, fraction.denominator)
                    for fraction in fractions
                ),
            )
        )
    projected = quantized.reshape(batch, tokens, source_count).to(
        device=alpha.device,
        dtype=alpha.dtype,
    )
    return projected, rows


def build_certificate(
    *,
    rows,
    lam: float,
    eps: float,
    n_sources: int,
    d_model: int,
    shape: tuple[int, ...],
    egyptian: bool,
) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "doctrine": "Doctrine-v11",
        "label": "MODELED",
        "aggregator": "lambda-attnres/v1",
        "lam": round(lam, 12),
        "eps": round(eps, 15),
        "n_sources": n_sources,
        "d_model": d_model,
        "input_shape": list(shape),
        "weight_encoding": "exact-rational" if egyptian else "runtime-float32",
        "rational_rows_sample": rows[:256] if rows is not None else None,
    }
    blob = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload["cert_sha256"] = sha256(blob).hexdigest()
    return payload
