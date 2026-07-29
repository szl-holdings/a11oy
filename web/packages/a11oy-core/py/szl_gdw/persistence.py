"""Append-only JSONL receipts and deterministic replay for the MODELED organ."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .kernel_adapter import ImmutableKernel, kernel_dispose
from .models import (
    KernelReceipt,
    Proposal,
    WorkspaceState,
    canonical_hash,
    proposal_from_mapping,
    to_primitive,
)


class JsonlReceiptStore:
    """Process-safe append sink; not a replacement for canonical GDW SQLite."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(
        self,
        proposal: Proposal,
        receipt: KernelReceipt,
        state_before: WorkspaceState,
        state_after: WorkspaceState,
    ) -> str:
        if receipt.proposal_id != proposal.proposal_id:
            raise ValueError("receipt and proposal identities differ")
        if receipt.state_before != state_before.canonical_hash():
            raise ValueError("receipt does not bind the supplied prior state")
        if receipt.state_after is not None:
            if receipt.state_after != state_after.canonical_hash():
                raise ValueError("receipt does not bind the supplied next state")
        elif state_after.canonical_hash() != state_before.canonical_hash():
            raise ValueError("rejected transition changed state")

        body: dict[str, Any] = {
            "schema": "szl.gdw.replay-record/v1",
            "proposal": to_primitive(proposal),
            "receipt": to_primitive(receipt),
            "state_before": to_primitive(state_before),
            "state_after": to_primitive(state_after),
        }
        body["record_hash"] = canonical_hash(body)
        encoded = (
            json.dumps(
                body,
                allow_nan=False,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("ab") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        return str(body["record_hash"])

    def load(self) -> list[Mapping[str, Any]]:
        if not self.path.exists():
            return []
        records: list[Mapping[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                expected = record.pop("record_hash", None)
                observed = canonical_hash(record)
                record["record_hash"] = expected
                if expected != observed:
                    raise ValueError(
                        f"replay record hash mismatch at line {line_number}"
                    )
                records.append(record)
        return records

    def replay(
        self, kernel: ImmutableKernel, initial_state: WorkspaceState
    ) -> WorkspaceState:
        state = initial_state
        for index, record in enumerate(self.load(), start=1):
            if canonical_hash(record["state_before"]) != state.canonical_hash():
                raise ValueError(f"replay state continuity failed at record {index}")
            proposal = proposal_from_mapping(record["proposal"])
            next_state, receipt = kernel_dispose(kernel, state, proposal)
            recorded_receipt = record["receipt"]
            if receipt.receipt_hash != recorded_receipt["receipt_hash"]:
                raise ValueError(f"receipt replay mismatch at record {index}")
            if canonical_hash(record["state_after"]) != next_state.canonical_hash():
                raise ValueError(f"next-state replay mismatch at record {index}")
            state = next_state
        return state
