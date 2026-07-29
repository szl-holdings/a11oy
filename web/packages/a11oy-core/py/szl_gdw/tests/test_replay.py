import json

import pytest
from szl_gdw.kernel_adapter import ReferenceImmutableKernel
from szl_gdw.models import Decision, WorkspaceState
from szl_gdw.persistence import JsonlReceiptStore
from szl_gdw.workspace import GovernedDeltaWorkspace

TIMESTAMP = "2026-07-29T00:00:00+00:00"


def test_workspace_step_is_immutable_and_receipt_replays(tmp_path):
    store = JsonlReceiptStore(tmp_path / "receipts.jsonl")
    kernel = ReferenceImmutableKernel()
    workspace = GovernedDeltaWorkspace(kernel, receipt_sink=store)
    initial = WorkspaceState("session", delta_memory=(0.0, 0.0))
    initial_hash = initial.canonical_hash()

    next_state, audit = workspace.step(
        initial,
        "route this request",
        (),
        ("expert-a",),
        0.5,
        created_at=TIMESTAMP,
    )

    assert initial.canonical_hash() == initial_hash
    assert next_state.step == 1
    assert audit["receipt"]["decision"] == Decision.ACCEPT.value
    assert store.replay(kernel, initial).canonical_hash() == next_state.canonical_hash()


def test_deterministic_inputs_produce_same_receipt():
    kernel = ReferenceImmutableKernel()
    state = WorkspaceState("session", delta_memory=(0.0,))
    workspace = GovernedDeltaWorkspace(kernel)
    first_state, first = workspace.step(
        state, "same", (), ("expert-a",), 0.25, created_at=TIMESTAMP
    )
    second_state, second = workspace.step(
        state, "same", (), ("expert-a",), 0.25, created_at=TIMESTAMP
    )
    assert first["receipt"]["receipt_hash"] == second["receipt"]["receipt_hash"]
    assert first_state.canonical_hash() == second_state.canonical_hash()


def test_tampered_replay_record_is_rejected(tmp_path):
    path = tmp_path / "receipts.jsonl"
    store = JsonlReceiptStore(path)
    kernel = ReferenceImmutableKernel()
    initial = WorkspaceState("session", delta_memory=(0.0,))
    GovernedDeltaWorkspace(kernel, receipt_sink=store).step(
        initial, "same", (), ("expert-a",), 0.25, created_at=TIMESTAMP
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    record["receipt"]["decision"] = "REJECT"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        store.load()
