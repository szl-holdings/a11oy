"""Smoke tests for the Amaru FastAPI app."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Ensure the in-tree src/ is importable without installation.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi.testclient import TestClient  # noqa: E402


def _client() -> TestClient:
    # Re-import to start each test with a fresh receipt chain / scheduler.
    for name in list(sys.modules):
        if name == "amaru" or name.startswith("amaru."):
            del sys.modules[name]
    module = importlib.import_module("amaru.app")
    return TestClient(module.app)


def test_healthz_lists_all_chakras() -> None:
    client = _client()
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["chakras"] == ["root", "sacral", "solar", "heart", "throat", "third_eye", "crown"]
    # All 7 kernels are real (no stubs).
    assert body["stubbed"] == []


def test_root_evaluation_writes_receipt() -> None:
    client = _client()
    r = client.post(
        "/chakra/root/evaluate",
        json={"envelope": {"signals": {"grounded": 0.8, "integrity": 0.9}}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["chakra"] == "root"
    assert body["stubbed"] is False
    assert body["error"] is None
    assert body["proof_id"] == "amaru.root.v1"
    assert body["output"]["verdict"] == "ground"
    assert abs(body["output"]["stability"] - 0.85) < 1e-9
    assert body["receipt"]["seq"] == 1
    assert body["receipt"]["prevHash"] == "0" * 64


def test_every_chakra_returns_real_output() -> None:
    client = _client()
    envelope = {
        "signals": {
            "grounded": 0.9, "integrity": 0.9,
            "novelty": 0.5, "fluency": 0.8,
            "intent": 0.8, "agency": 0.9, "friction": 0.1,
            "care": 0.9, "harm": 0.1,
            "clarity": 0.81, "truth": 0.64,
            "pattern_strength": 0.7, "uncertainty": 0.2,
        },
        "upstream": {"stability": 0.9, "flow": 0.7, "coherence": 0.8, "fidelity": 0.72},
    }
    for name in ["root", "sacral", "solar", "heart", "throat", "third_eye", "crown"]:
        r = client.post(f"/chakra/{name}/evaluate", json={"envelope": envelope})
        assert r.status_code == 200, f"{name} → {r.status_code}"
        body = r.json()
        assert body["stubbed"] is False, f"{name} is unexpectedly stubbed"
        assert body["error"] is None, f"{name} surfaced error: {body['error']}"
        assert body["output"] and "verdict" in body["output"], f"{name} missing verdict"


def test_unknown_chakra_404() -> None:
    client = _client()
    r = client.post("/chakra/spleen/evaluate", json={"envelope": {}})
    assert r.status_code == 404


def test_leader_returns_real_proof_hash() -> None:
    client = _client()
    r = client.get("/chakra/heart/leader")
    assert r.status_code == 200
    body = r.json()
    assert body["chakra"] == "heart"
    assert body["proof_id"] == "amaru.heart.v1"
    # Proof sha is now the real sha256 of the kernel.py source bytes.
    assert len(body["proof_sha256"] or "") == 64
    assert body["proof_sha256"] != "0" * 64


def test_every_chakra_leader_has_real_kernel_source_sha() -> None:
    # Each chakra's proof.json sha256 must be the canonical sha256 of its
    # kernel.py source bytes (pinned by services/amaru/scripts/pin_proofs.py).
    import hashlib
    client = _client()
    chakras_root = _SRC / "amaru" / "chakras"
    for name in ["root", "sacral", "solar", "heart", "throat", "third_eye", "crown"]:
        r = client.get(f"/chakra/{name}/leader")
        assert r.status_code == 200, f"{name} → {r.status_code}"
        body = r.json()
        expected = hashlib.sha256((chakras_root / name / "kernel.py").read_bytes()).hexdigest()
        assert body["proof_sha256"] == expected, f"{name} proof sha drift — re-pin"
        assert body["proof_id"] == f"amaru.{name}.v1", f"{name} proof_id drift"


def test_scheduler_tick_chains_receipts() -> None:
    client = _client()
    r = client.post(
        "/scheduler/tick",
        json={"envelope": {"signals": {
            "grounded": 0.9, "integrity": 0.9,
            "novelty": 0.4, "fluency": 0.7,
            "intent": 0.8, "agency": 0.9, "friction": 0.1,
            "care": 0.8, "harm": 0.2,
            "clarity": 0.9, "truth": 0.9,
            "pattern_strength": 0.7, "uncertainty": 0.2,
        }}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tick_id"] == 1
    assert [s["chakra"] for s in body["steps"]] == ["root", "sacral", "solar", "heart", "throat", "third_eye", "crown"]
    # Per-step receipts (7) + one tick-level receipt = 8 total appends.
    seqs = [s["receipt_seq"] for s in body["steps"]]
    assert seqs == list(range(1, 8))
    assert body["tick_receipt"]["seq"] == 8
    assert all(s["stubbed"] is False for s in body["steps"])
    assert all(s["error"] is None for s in body["steps"])
    # Crown is real now → closure is a real bounded scalar in [0, 1].
    assert body["closure"] is not None
    assert 0.0 <= body["closure"] <= 1.0
    assert body["handoff"] == {"to": "root", "via": "ouroboros"}


def test_scheduler_tick_publishes_seven_chakra_plus_one_scheduler_event() -> None:
    # Replay-fidelity contract: one /scheduler/tick must publish exactly
    # 7 amaru.chakra events (one per kernel) + 1 amaru.scheduler event.
    # Consumers keyed to `amaru.chakra` (SSE / Brain panel / bus replay)
    # must observe every chakra evaluation, not just the scheduler summary.
    import asyncio
    import amaru.app as app_mod

    published: list[tuple[str, str]] = []

    class _Capture:
        async def publish(self, *, type_: str, source_id: str, payload: dict) -> dict:
            published.append((type_, source_id))
            return {"ok": True}

    app_mod._bus = _Capture()  # type: ignore[attr-defined]

    sse: list[dict] = []
    app_mod._sse_broadcast = lambda evt: sse.append(evt)  # type: ignore[attr-defined]

    async def drive() -> None:
        await app_mod.scheduler_tick(app_mod.SchedulerTickRequest(envelope={"signals": {
            "grounded": 0.9, "integrity": 0.9,
            "novelty": 0.4, "fluency": 0.7,
            "intent": 0.8, "agency": 0.9, "friction": 0.1,
            "care": 0.8, "harm": 0.2,
            "clarity": 0.9, "truth": 0.9,
            "pattern_strength": 0.7, "uncertainty": 0.2,
        }}))
        # Give the fire-and-forget publish tasks one loop turn to drain.
        for _ in range(20):
            await asyncio.sleep(0)

    # Fresh module so the global registry/state is clean.
    for name in list(sys.modules):
        if name == "amaru" or name.startswith("amaru."):
            del sys.modules[name]
    app_mod = importlib.import_module("amaru.app")
    app_mod._bus = _Capture()  # type: ignore[attr-defined]
    app_mod._sse_broadcast = lambda evt: sse.append(evt)  # type: ignore[attr-defined]

    asyncio.run(drive())

    chakra_events = [t for t in published if t[0] == "amaru.chakra"]
    scheduler_events = [t for t in published if t[0] == "amaru.scheduler"]
    assert len(chakra_events) == 7, f"expected 7 amaru.chakra events, got {chakra_events}"
    assert len(scheduler_events) == 1, f"expected 1 amaru.scheduler event, got {scheduler_events}"
    assert [t[1] for t in chakra_events] == [
        "amaru:root", "amaru:sacral", "amaru:solar",
        "amaru:heart", "amaru:throat", "amaru:third_eye", "amaru:crown",
    ]
    sse_types = [e["type"] for e in sse]
    assert sse_types.count("amaru.chakra") == 7
    assert sse_types.count("amaru.scheduler") == 1


def test_tripwires_report_all_ten() -> None:
    client = _client()
    r = client.get("/tripwires")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["total"] == 10
    ids = [t["id"] for t in body["tripwires"]]
    assert ids == [f"huklla-{i}" for i in range(1, 11)]


def test_bus_topic_names_match_contract() -> None:
    # Topic contract: amaru publishes to `amaru.chakra` and `amaru.scheduler`
    # (NOT `amaru.chakra.evaluated` / `amaru.scheduler.tick`). Consumers
    # filter by exact match — keep this test red if names drift again.
    import amaru.app as app_mod
    src = Path(app_mod.__file__).read_text()
    assert 'type_="amaru.chakra"' in src
    assert 'type_="amaru.scheduler"' in src
    assert "amaru.chakra.evaluated" not in src
    assert "amaru.scheduler.tick" not in src


def test_sse_events_endpoint_sends_hello() -> None:
    # Drive the SSE generator directly so the test doesn't hang on the
    # infinite keepalive loop inside the FastAPI endpoint.
    import asyncio
    import amaru.app as app_mod

    async def first_frame() -> str:
        resp = await app_mod.events()
        agen = resp.body_iterator  # async generator
        try:
            chunk = await asyncio.wait_for(agen.__anext__(), timeout=2.0)
        finally:
            await agen.aclose()
        return chunk if isinstance(chunk, str) else chunk.decode("utf-8")

    frame = asyncio.run(first_frame())
    assert "event: hello" in frame
    assert "amaru.chakra" in frame
    assert "amaru.scheduler" in frame


def test_solar_kernel_verdict_thresholds() -> None:
    # Real (non-stub) solar kernel: will = clamp(intent*agency - friction, 0, 1).
    from amaru.chakras.solar import kernel as solar_kernel

    assert solar_kernel.STUBBED is False
    high = solar_kernel.evaluate({"signals": {"intent": 0.9, "agency": 0.9, "friction": 0.0}})
    mid = solar_kernel.evaluate({"signals": {"intent": 0.5, "agency": 0.5, "friction": 0.0}})
    low = solar_kernel.evaluate({"signals": {"intent": 0.3, "agency": 0.3, "friction": 0.3}})
    assert high["verdict"] == "act" and high["will"] >= 0.5
    assert mid["verdict"] == "defer" and 0.2 <= mid["will"] < 0.5
    assert low["verdict"] == "block" and low["will"] < 0.2


def test_third_eye_kernel_verdict_thresholds() -> None:
    # Real (non-stub) third-eye kernel: insight = clamp(pattern*(1-uncertainty), 0, 1).
    from amaru.chakras.third_eye import kernel as te_kernel

    assert te_kernel.STUBBED is False
    foresee = te_kernel.evaluate({"signals": {"pattern_strength": 0.9, "uncertainty": 0.1}})
    peek = te_kernel.evaluate({"signals": {"pattern_strength": 0.5, "uncertainty": 0.4}})
    blind = te_kernel.evaluate({"signals": {"pattern_strength": 0.2, "uncertainty": 0.5}})
    assert foresee["verdict"] == "foresee" and foresee["insight"] >= 0.5
    assert peek["verdict"] == "peek" and 0.25 <= peek["insight"] < 0.5
    assert blind["verdict"] == "blind" and blind["insight"] < 0.25


def test_solar_and_third_eye_absent_from_state_stubbed_array() -> None:
    # Regression guard for the "Done looks like" criterion: /healthz.stubbed
    # must never re-list solar or third_eye.
    client = _client()
    body = client.get("/healthz").json()
    assert "solar" not in body["stubbed"]
    assert "third_eye" not in body["stubbed"]
    assert body["stubbed"] == []


def test_scheduler_wiring_is_ouroboros() -> None:
    client = _client()
    r = client.get("/scheduler/wiring")
    assert r.status_code == 200
    body = r.json()
    assert body["shape"] == "andean-cross-ouroboros"
    assert body["chakras"][0] == "root" and body["chakras"][-1] == "crown"
    assert any(e["src"] == "crown" and e["dst"] == "root" and e["role"] == "ouroboros" for e in body["edges"])
