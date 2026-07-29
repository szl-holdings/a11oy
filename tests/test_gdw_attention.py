import pytest

from gdw_attention import AttentionFeatures, choose_attention_mode


def features(**overrides):
    values = {
        "novelty": 0.1,
        "disagreement": 0.1,
        "risk": 0.1,
        "context_tokens": 256,
        "active_tool_count": 1,
        "memory_pressure": 0.1,
    }
    values.update(overrides)
    return AttentionFeatures(**values)


def test_policy_spans_local_hybrid_global_and_memory_guard():
    assert choose_attention_mode(features())["mode"] == "kda_local"
    assert choose_attention_mode(
        features(novelty=0.8, disagreement=0.8, risk=0.5, context_tokens=16000)
    )["mode"] == "laguna_hybrid"
    assert choose_attention_mode(
        features(
            novelty=1.0,
            disagreement=1.0,
            risk=1.0,
            context_tokens=32768,
            active_tool_count=16,
            memory_pressure=0.0,
        )
    )["mode"] == "mla_global"
    assert choose_attention_mode(
        features(novelty=1.0, disagreement=1.0, memory_pressure=0.9)
    )["mode"] == "kda_local"


def test_explicit_valid_hint_is_honored():
    route = choose_attention_mode(features(), "laguna_hybrid")
    assert route["mode"] == "laguna_hybrid"
    assert route["probabilities"]["laguna_hybrid"] == 1.0


def test_torch_router_and_grouped_dispatch_when_available():
    torch = pytest.importorskip("torch")
    from gdw_attention import HybridAttentionRouter, hybrid_attention_dispatch

    router = HybridAttentionRouter(4)
    x = torch.ones(3, 4)
    mode = torch.tensor([0, 2, 1])
    output = hybrid_attention_dispatch(
        mode,
        x,
        lambda batch: batch + 1,
        lambda batch: batch + 2,
        lambda batch: batch + 3,
    )
    assert torch.equal(output[0], torch.full((4,), 2.0))
    assert torch.equal(output[1], torch.full((4,), 3.0))
    assert torch.equal(output[2], torch.full((4,), 4.0))
    selected, probabilities = router(x)
    assert selected.shape == (3,)
    assert probabilities.shape == (3, 3)
