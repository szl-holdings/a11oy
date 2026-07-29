"""Async GDW burst runner with JSON evidence output."""

import argparse
import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx


async def fire(client, index, token, shared_session, retries):
    request_id = "burst-" + uuid.uuid4().hex
    session_id = shared_session or "burst-" + uuid.uuid4().hex
    payload = {
        "session_id": session_id,
        "request": f"burst request {index}",
        "allowed_experts": ["planner", "retriever", "auditor"],
        "risk_budget": 0.35,
        "mode_hint": "auto",
        "dry_run": False,
    }
    started = time.perf_counter()
    for attempt in range(retries + 1):
        try:
            response = await client.post(
                "/api/a11oy/v1/gdw/step",
                json=payload,
                headers={
                    "Authorization": "Bearer " + token,
                    "X-Request-Id": request_id,
                },
                timeout=30.0,
            )
            latency_ms = (time.perf_counter() - started) * 1000.0
            try:
                body = response.json()
            except Exception:
                body = {}
            return {
                "i": index,
                "request_id": request_id,
                "session_id": session_id,
                "status": response.status_code,
                "latency_ms": latency_ms,
                "decision": body.get("decision"),
                "receipt_hash": body.get("receipt_hash"),
                "state_hash": body.get("state_hash"),
                "step": body.get("step"),
                "scheduler_mode": body.get("scheduler_mode"),
                "json_valid": bool(body),
                "attempts": attempt + 1,
                "error": None if response.status_code == 200 else str(body)[:500],
            }
        except Exception as exc:
            if attempt < retries:
                await asyncio.sleep(0.05 * (2**attempt))
                continue
            return {
                "i": index,
                "request_id": request_id,
                "session_id": session_id,
                "status": 0,
                "latency_ms": (time.perf_counter() - started) * 1000.0,
                "decision": "ERROR",
                "receipt_hash": None,
                "state_hash": None,
                "step": None,
                "scheduler_mode": None,
                "json_valid": False,
                "attempts": attempt + 1,
                "error": type(exc).__name__,
            }


async def run(args):
    token = args.token or os.environ.get("GDW_BENCH_TOKEN", "")
    if not token:
        raise SystemExit("GDW_BENCH_TOKEN or --token is required")
    limits = httpx.Limits(
        max_keepalive_connections=args.concurrency,
        max_connections=args.concurrency,
    )
    async with httpx.AsyncClient(base_url=args.base_url, limits=limits) as client:
        semaphore = asyncio.Semaphore(args.concurrency)

        async def bounded(index):
            async with semaphore:
                return await fire(
                    client, index, token, args.shared_session, args.retries
                )

        started = time.perf_counter()
        rows = await asyncio.gather(*(bounded(i) for i in range(args.total)))
        elapsed = time.perf_counter() - started
        integrity = {}
        try:
            response = await client.get(
                "/api/a11oy/v1/gdw/integrity",
                headers={"Authorization": "Bearer " + token},
                timeout=30.0,
            )
            integrity = response.json()
        except Exception as exc:
            integrity = {"ok": False, "error": type(exc).__name__}

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema": "szl.gdw.burst-results/v1",
        "label": "MEASURED",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "total": args.total,
        "concurrency": args.concurrency,
        "shared_session": bool(args.shared_session),
        "elapsed_seconds": elapsed,
        "requests_per_second": args.total / elapsed if elapsed else 0.0,
        "persistence_integrity": integrity,
        "rows": rows,
    }
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(str(output.resolve()))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--total", type=int, default=10000)
    parser.add_argument("--concurrency", type=int, default=250)
    parser.add_argument("--shared-session", default="")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--token", default="")
    parser.add_argument(
        "--output", default="output/bench_results/gdw_burst_results.json"
    )
    args = parser.parse_args()
    if args.total <= 0 or args.concurrency <= 0 or args.retries < 0:
        parser.error("--total and --concurrency must be positive; --retries nonnegative")
    return args


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
