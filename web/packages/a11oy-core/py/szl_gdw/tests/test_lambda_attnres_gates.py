#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173

from fractions import Fraction

import pytest

torch = pytest.importorskip("torch")

from szl_gdw.lambda_attnres import LambdaAttnRes, egyptian_project


def _sources(dtype=torch.float32):
    torch.manual_seed(0)
    return torch.randn(2, 4, 5, 8, dtype=dtype)


def test_lambda_zero_is_exact_arithmetic_endpoint():
    module = LambdaAttnRes(
        d_model=8,
        n_sources_max=5,
        lam_init=0.0,
        egyptian=False,
    )
    sources = _sources()
    weights = module._weights(sources).unsqueeze(-1)
    baseline = (weights * sources).sum(-2)
    assert module.lam.item() == 0.0
    assert torch.allclose(module(sources), baseline, atol=1e-7, rtol=0.0)


def test_lambda_one_is_exact_geometric_endpoint():
    module = LambdaAttnRes(
        d_model=8,
        n_sources_max=5,
        lam_init=1.0,
        egyptian=False,
    )
    sources = _sources().abs().add(0.1)
    weights = module._weights(sources).unsqueeze(-1)
    arithmetic = (weights * sources).sum(-2)
    expected = torch.sign(arithmetic) * (
        weights * sources.clamp_min(module.eps).log()
    ).sum(-2).exp()
    assert module.lam.item() == 1.0
    assert torch.allclose(module(sources), expected, atol=1e-6, rtol=0.0)


def test_egyptian_closure_is_exact():
    torch.manual_seed(2)
    alpha = torch.softmax(torch.randn(2, 3, 5), dim=-1)
    _, rows = egyptian_project(alpha, depth=4)
    for _, row in rows:
        assert sum(
            (Fraction(numerator, denominator) for numerator, denominator in row),
            Fraction(0),
        ) == Fraction(1)


def test_certificate_hash_is_dtype_invariant():
    module = LambdaAttnRes(d_model=8, n_sources_max=5, lam_init=0.25)
    sources = _sources()
    _, cert32 = module(sources.float(), return_cert=True)
    _, cert16 = module(sources.half(), return_cert=True)
    assert cert32["cert_sha256"] == cert16["cert_sha256"]


def test_non_finite_and_oversized_sources_fail_closed():
    module = LambdaAttnRes(d_model=8, n_sources_max=2)
    with pytest.raises(ValueError):
        module(torch.zeros(1, 1, 3, 8))
    bad = torch.zeros(1, 1, 2, 8)
    bad[..., 0] = torch.nan
    with pytest.raises(ValueError):
        module(bad)
