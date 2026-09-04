#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One-shot materializer for the bounded energy-ledger read projection.

This script is intentionally removed by its controller after it has applied and
verified the durable source diff. It never touches the ledger write path.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "szl_energy_ledger.py"
TEST_PATH = ROOT / "test_energy_ledger.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


ledger = LEDGER_PATH.read_text(encoding="utf-8")

ledger = replace_once(
    ledger,
    'DEFAULT_PRICE_PER_KWH_CENTS = int(os.getenv("STRIPE_PRICE_PER_KWH_CENTS", "45"))\n',
    'DEFAULT_PRICE_PER_KWH_CENTS = int(os.getenv("STRIPE_PRICE_PER_KWH_CENTS", "45"))\n'
    '\n'
    '# The public GET is a bounded operational projection, not an unbounded dump.\n'
    '# The durable store, full-chain verifier, and aggregate totals still cover every\n'
    '# retained entry. The response window stays below the investor probe\'s 512 KiB\n'
    '# body cap so an edge/client never receives JSON truncated in the middle.\n'
    'DEFAULT_LEDGER_PAGE_LIMIT = 50\n'
    'MAX_LEDGER_PAGE_LIMIT = 200\n'
    'MAX_LEDGER_RESPONSE_BYTES = 448_000\n',
    "ledger transport constants",
)

old_summary = '''    def summary(self) -> dict:
        """Full ledger view for the GET /energy/ledger endpoint."""
        return {
            "ok": True,
            "receipts": self.entries(),
            "chain": self.verify(),
            "totals": self.totals(),
            "persistence": self.persistence_info(),
            "storage": self.storage_health(),
            "price_per_kwh_cents": self.price_per_kwh_cents,
            "stripe_mode": "live" if os.getenv("STRIPE_API_KEY") else "dry-run",
            "doctrine": DOCTRINE_NOTE,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
'''
new_summary = '''    def summary(
        self,
        limit: int = DEFAULT_LEDGER_PAGE_LIMIT,
        offset_from_latest: int = 0,
    ) -> dict:
        """Bounded public view of the complete durable energy ledger.

        Verification and totals cover the full retained chain. Only ``receipts`` is
        windowed, newest window by default and chronological inside the window.
        ``offset_from_latest`` skips that many newest entries, allowing callers to
        page backward without changing or minting any receipt.
        """
        try:
            requested_limit = int(limit)
        except (TypeError, ValueError):
            requested_limit = DEFAULT_LEDGER_PAGE_LIMIT
        page_limit = max(1, min(MAX_LEDGER_PAGE_LIMIT, requested_limit))
        try:
            offset = max(0, int(offset_from_latest))
        except (TypeError, ValueError):
            offset = 0

        all_entries = self.entries()
        total = len(all_entries)
        end = max(0, total - offset)
        start = max(0, end - page_limit)
        receipts = all_entries[start:end]
        transport_truncated = False

        def page_metadata() -> dict:
            returned = len(receipts)
            return {
                "order": "ascending-within-window",
                "window": "latest",
                "requested_limit": requested_limit,
                "limit": page_limit,
                "max_limit": MAX_LEDGER_PAGE_LIMIT,
                "offset_from_latest": offset,
                "returned": returned,
                "total": total,
                "first_seq": receipts[0].get("seq") if receipts else None,
                "last_seq": receipts[-1].get("seq") if receipts else None,
                "has_older": start > 0,
                "has_newer": end < total,
                "next_offset_from_latest": (
                    offset + returned if start > 0 else None
                ),
                "transport_truncated": transport_truncated,
                "max_response_bytes": MAX_LEDGER_RESPONSE_BYTES,
                "full_chain_in_response": returned == total,
            }

        response = {
            "ok": True,
            "receipts": receipts,
            "page": page_metadata(),
            "chain": self.verify(),
            "totals": self.totals(),
            "persistence": self.persistence_info(),
            "storage": self.storage_health(),
            "price_per_kwh_cents": self.price_per_kwh_cents,
            "stripe_mode": "live" if os.getenv("STRIPE_API_KEY") else "dry-run",
            "doctrine": DOCTRINE_NOTE,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

        # Item limits are normally sufficient, but a valid metadata field can still
        # be unexpectedly large. Enforce a whole-response byte ceiling as a second
        # transport invariant, dropping only the oldest entry in this returned window.
        while receipts:
            encoded = json.dumps(
                response, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
            if len(encoded) <= MAX_LEDGER_RESPONSE_BYTES:
                break
            receipts.pop(0)
            start += 1
            transport_truncated = True
            response["page"] = page_metadata()

        return response
'''
ledger = replace_once(ledger, old_summary, new_summary, "summary method")

old_handler = '''    # Annotated with the module-scope Request so FastAPI injects it (not a 422 query param).
    def _h_ledger(request: _Request):
        return JSONResponse(handle_ledger())
'''
new_handler = '''    # Annotated with the module-scope Request so FastAPI injects it (not a 422 query param).
    def _h_ledger(request: _Request):
        # These values shape only the read projection. This GET never appends,
        # signs, bills, executes, or mints a receipt.
        try:
            limit = int(request.query_params.get("limit", DEFAULT_LEDGER_PAGE_LIMIT))
        except (TypeError, ValueError):
            limit = DEFAULT_LEDGER_PAGE_LIMIT
        try:
            offset = int(request.query_params.get("offset_from_latest", 0))
        except (TypeError, ValueError):
            offset = 0
        response = JSONResponse(
            get_ledger().summary(limit=limit, offset_from_latest=offset)
        )
        response.headers["Cache-Control"] = "no-store"
        return response
'''
ledger = replace_once(ledger, old_handler, new_handler, "GET route handler")
LEDGER_PATH.write_text(ledger, encoding="utf-8", newline="\n")


tests = TEST_PATH.read_text(encoding="utf-8")
if "import json\n" not in tests:
    tests = replace_once(tests, "import os\n", "import json\nimport os\n", "test imports")

insert_anchor = '''# ---------------------------------------------------------------------------
# Persistence across redeploy — the demo risk this guard exists for. The receipt
'''
new_tests = '''def test_ledger_summary_defaults_to_bounded_latest_window():
    led, tmp = _ledger()
    try:
        for index in range(60):
            led.append_job(
                _fresh_measured_job(
                    joules=10_000.0 + index,
                    model=f"bounded-{index}",
                ),
                now=NOW,
            )
        summary = led.summary()
        assert [entry["seq"] for entry in summary["receipts"]] == list(range(10, 60))
        assert summary["page"]["returned"] == 50
        assert summary["page"]["total"] == 60
        assert summary["page"]["has_older"] is True
        assert summary["page"]["full_chain_in_response"] is False
        assert summary["chain"]["ok"] is True
        assert summary["chain"]["length"] == 60
        assert summary["totals"]["jobs"] == 60
    finally:
        _cleanup(tmp)


def test_ledger_summary_pages_backward_without_mutation():
    led, tmp = _ledger()
    try:
        for index in range(12):
            led.append_job(
                _fresh_measured_job(
                    joules=20_000.0 + index,
                    model=f"page-{index}",
                ),
                now=NOW,
            )
        before = led.verify()["length"]
        page = led.summary(limit=4, offset_from_latest=4)
        assert [entry["seq"] for entry in page["receipts"]] == [4, 5, 6, 7]
        assert page["page"]["has_older"] is True
        assert page["page"]["has_newer"] is True
        assert page["page"]["next_offset_from_latest"] == 8
        assert led.verify()["length"] == before
    finally:
        _cleanup(tmp)


def test_ledger_summary_enforces_whole_response_byte_budget():
    led, tmp = _ledger()
    try:
        for index in range(60):
            led.append_job(
                _fresh_measured_job(
                    joules=30_000.0 + index,
                    model=f"byte-budget-{index}",
                ),
                now=NOW,
            )
        for entry in led._entries:
            entry["transport_test_pad"] = "x" * 12_000
        summary = led.summary(limit=200)
        encoded = json.dumps(
            summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        assert len(encoded) <= L.MAX_LEDGER_RESPONSE_BYTES
        assert len(encoded) < 512 * 1024
        assert summary["page"]["transport_truncated"] is True
        assert summary["page"]["returned"] < summary["page"]["total"]
        assert summary["chain"]["length"] == 60
        assert summary["totals"]["jobs"] == 60
    finally:
        _cleanup(tmp)


def test_ledger_get_projection_is_no_store_and_read_only():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    led, tmp = _ledger()
    try:
        for index in range(6):
            led.append_job(
                _fresh_measured_job(
                    joules=40_000.0 + index,
                    model=f"http-{index}",
                ),
                now=NOW,
            )
        L._LEDGER = led
        before = led.verify()["length"]
        app = FastAPI()
        mounted = L.register(app)
        assert "/api/a11oy/v1/energy/ledger" in mounted
        response = TestClient(app).get(
            "/api/a11oy/v1/energy/ledger?limit=2&offset_from_latest=1"
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        body = response.json()
        assert [entry["seq"] for entry in body["receipts"]] == [3, 4]
        assert body["page"]["total"] == 6
        assert led.verify()["length"] == before
    finally:
        L._LEDGER = None
        _cleanup(tmp)


# ---------------------------------------------------------------------------
# Persistence across redeploy — the demo risk this guard exists for. The receipt
'''
tests = replace_once(tests, insert_anchor, new_tests, "test insertion")
TEST_PATH.write_text(tests, encoding="utf-8", newline="\n")

print("materialized bounded energy-ledger transport projection")
