from fractions import Fraction

import torch
from szl_gdw.lambda_attnres import LambdaAttnRes, egyptian_project


def _sources(dtype=torch.float32):
    torch.manual_seed(0)
    return torch.randn(2, 4, 5, 8, dtype=dtype)


def test_lambda_zero_matches_arithmetic_exactly():
    module = LambdaAttnRes(
        d_model=8,
        n_sources_max=5,
        lam_init=0.0,
        egyptian=False,
    )
    sources = _sources()
    baseline = (module._weights(sources).unsqueeze(-1) * sources).sum(-2)
    output = module(sources)
    assert torch.equal(output, baseline)


def test_egyptian_projection_closes_exactly_in_rationals():
    torch.manual_seed(4)
    alpha = torch.softmax(torch.randn(2, 3, 5), dim=-1)
    projected, rows = egyptian_project(alpha, depth=4)
    assert projected.shape == alpha.shape
    for _, row in rows:
        assert sum(Fraction(n, d) for n, d in row) == Fraction(1)


def test_certificate_hash_is_input_dtype_invariant():
    module = LambdaAttnRes(d_model=8, n_sources_max=5, lam_init=0.25)
    sources = _sources()
    _, certificate32 = module(sources.to(torch.float32), return_cert=True)
    _, certificate16 = module(sources.to(torch.float16), return_cert=True)
    assert certificate32["cert_sha256"] == certificate16["cert_sha256"]
    assert certificate32["label"] == "MODELED"


def test_epsilon_floor_prevents_single_zero_from_collapsing_positive_row():
    module = LambdaAttnRes(
        d_model=1,
        n_sources_max=2,
        lam_init=1.0,
        egyptian=False,
    )
    with torch.no_grad():
        module.pseudo_query.zero_()
    sources = torch.tensor([[[[0.0], [4.0]]]])
    output = module(sources)
    assert output.item() > 0.0
