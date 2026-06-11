# tests/test_chaski_dsse_cosign.py
# Proves that the Chaski orchestrator's khipu_emit co-signs receipts through the
# REAL host DSSE signer (app.state.szl_emit_signed_receipt) when one is wired,
# and stays honest (sha256 hash-chain only, NO fabricated signature) when it is
# not. No network, no real cosign key.
import importlib
import types

aco = importlib.import_module("a11oy_code_orchestrator")


def test_no_signer_means_hash_chain_only(monkeypatch):
    # CLI/test runtime: no host app captured -> receipt is the sha256 chain only.
    monkeypatch.setattr(aco, "_app", None, raising=False)
    rec = aco.khipu_emit("test.action", {"k": "v"})
    assert rec["chain_verified"] is True
    assert len(rec["hash"]) == 64
    assert "dsse_signed" not in rec  # honest: never claims a signature it doesn't have


def test_signer_present_attaches_real_dsse_fields(monkeypatch):
    # Simulate szl_provenance having wired app.state.szl_emit_signed_receipt.
    calls = {}

    def fake_emit(receipt, request=None):
        calls["receipt"] = receipt
        # Mimic szl_dsse: real digest; signed True only if a cosign key exists.
        return {"digest": "deadbeef" * 8, "signed": True, "index": 7}

    fake_app = types.SimpleNamespace(state=types.SimpleNamespace(
        szl_emit_signed_receipt=fake_emit))
    monkeypatch.setattr(aco, "_app", fake_app, raising=False)

    rec = aco.khipu_emit("chat.completion", {"model": "Qwen/Qwen2.5-Coder-32B-Instruct"})
    assert rec["chain_verified"] is True          # sha256 chain still the backbone
    assert rec["dsse_digest"] == "deadbeef" * 8   # real digest from the signer
    assert rec["dsse_signed"] is True             # co-signed
    assert rec["dsse_index"] == 7
    # The signer was handed the khipu hash + receipt id (cross-linked, no fabrication).
    assert calls["receipt"]["khipu_hash"] == rec["hash"]


def test_unsigned_signer_is_honest(monkeypatch):
    # Signer present but NO cosign key -> szl_dsse returns signed=False (UNSIGNED).
    def fake_emit_unsigned(receipt, request=None):
        return {"digest": "cafe" * 16, "signed": False, "index": 1}

    fake_app = types.SimpleNamespace(state=types.SimpleNamespace(
        szl_emit_signed_receipt=fake_emit_unsigned))
    monkeypatch.setattr(aco, "_app", fake_app, raising=False)

    rec = aco.khipu_emit("test.action", {"k": "v"})
    assert rec["dsse_signed"] is False  # honest UNSIGNED label, never faked


def test_signer_exception_never_breaks_the_turn(monkeypatch):
    def boom(receipt, request=None):
        raise RuntimeError("signer hiccup")

    fake_app = types.SimpleNamespace(state=types.SimpleNamespace(
        szl_emit_signed_receipt=boom))
    monkeypatch.setattr(aco, "_app", fake_app, raising=False)

    rec = aco.khipu_emit("test.action", {"k": "v"})  # must not raise
    assert rec["chain_verified"] is True
    assert "dsse_signed" not in rec  # signing failed -> no claim, chain stands
