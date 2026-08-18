from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime
from types import SimpleNamespace
from typing import AsyncIterator

from routers.readiness_phase_b import (
    KEVGATE_PATHS,
    PHASE_B_OBSERVATION_ALIASES,
    PHASE_B_OBSERVATION_PATHS,
    install_phase_b_response_contract,
    normalize_phase_b_payload,
)


FIXED_OBSERVATION = "2026-08-18T01:23:45Z"


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


class _FakeApp:
    def __init__(self) -> None:
        self.state = SimpleNamespace()
        self.middleware_function = None
        self.middleware_registrations = 0

    def middleware(self, kind: str):
        if kind != "http":
            raise AssertionError(f"unexpected middleware kind: {kind}")

        def _decorator(function):
            self.middleware_function = function
            self.middleware_registrations += 1
            return function

        return _decorator


class _FakeResponse:
    def __init__(
        self,
        payload: object,
        *,
        status_code: int = 200,
        content_type: str = "application/json; charset=utf-8",
    ) -> None:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        midpoint = max(1, len(raw) // 2)
        self.status_code = status_code
        self.headers = {
            "content-type": content_type,
            "content-length": str(len(raw)),
            "etag": '"stale-validator"',
            "x-contract-test": "preserved",
        }
        self.body_iterator = _stream(raw[:midpoint], raw[midpoint:])


async def _read_body(response: _FakeResponse) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    return b"".join(chunks)


class PhaseBPayloadTests(unittest.TestCase):
    def test_exact_current_main_observation_paths_are_closed(self) -> None:
        self.assertEqual(
            PHASE_B_OBSERVATION_PATHS,
            frozenset(
                {
                    "/api/a11oy/provenance",
                    "/api/a11oy/v1/energy/sci",
                    "/api/a11oy/v1/observability/summary",
                    "/api/a11oy/v1/observability/business",
                    "/api/a11oy/v1/mesh/state",
                }
            ),
        )
        self.assertEqual(
            PHASE_B_OBSERVATION_ALIASES,
            frozenset({"/v1/observability/business"}),
        )
        self.assertEqual(
            KEVGATE_PATHS,
            frozenset({"/api/a11oy/v1/sec/kev"}),
        )

    def test_every_phase_b_surface_gets_the_supplied_clock(self) -> None:
        paths = PHASE_B_OBSERVATION_PATHS | PHASE_B_OBSERVATION_ALIASES
        for path in paths:
            with self.subTest(path=path):
                source = {
                    "ok": True,
                    "nested": {"fetched_at": "older-source-time"},
                }
                result = normalize_phase_b_payload(
                    path,
                    source,
                    observed_at=FIXED_OBSERVATION,
                )
                self.assertEqual(result["observed_at"], FIXED_OBSERVATION)
                self.assertEqual(
                    result["nested"]["fetched_at"],
                    "older-source-time",
                )
                self.assertNotIn("observed_at", source)

    def test_unrelated_path_and_non_object_values_are_not_relabelled(self) -> None:
        source = {"data_kind": "sample", "value": 7}
        result = normalize_phase_b_payload(
            "/api/a11oy/v1/unrelated",
            source,
            observed_at=FIXED_OBSERVATION,
        )
        self.assertEqual(result, source)

        array = [{"data_kind": "sample"}]
        self.assertIs(
            normalize_phase_b_payload(
                "/api/a11oy/provenance",
                array,
                observed_at=FIXED_OBSERVATION,
            ),
            array,
        )

    def test_bundled_kev_snapshot_is_cached_with_separate_detail(self) -> None:
        source = {
            "data_kind": "sample",
            "note": "Verbatim real KEV entries from the bundled snapshot.",
            "count": 28,
        }
        result = normalize_phase_b_payload(
            "/api/a11oy/v1/sec/kev",
            source,
        )
        self.assertEqual(result["data_kind"], "cached")
        self.assertEqual(result["detail"], source["note"])
        self.assertEqual(source["data_kind"], "sample")
        self.assertNotIn("detail", source)

    def test_live_kev_remains_exact_lowercase_live(self) -> None:
        result = normalize_phase_b_payload(
            "/api/a11oy/v1/sec/kev",
            {"data_kind": "LIVE", "items": []},
        )
        self.assertEqual(result["data_kind"], "live")
        self.assertIsInstance(result["detail"], str)
        self.assertTrue(result["detail"])

    def test_kev_error_is_not_rewritten_as_cached_evidence(self) -> None:
        source = {
            "error": "upstream unavailable",
            "data_kind": "sample",
        }
        result = normalize_phase_b_payload(
            "/api/a11oy/v1/sec/kev",
            source,
            status_code=503,
        )
        self.assertEqual(result, source)
        self.assertNotIn("detail", result)


class PhaseBMiddlewareTests(unittest.TestCase):
    def test_installer_is_idempotent(self) -> None:
        app = _FakeApp()
        install_phase_b_response_contract(app)
        install_phase_b_response_contract(app)
        self.assertEqual(app.middleware_registrations, 1)
        self.assertIsNotNone(app.middleware_function)

    def test_middleware_adds_clock_and_preserves_headers(self) -> None:
        app = _FakeApp()
        install_phase_b_response_contract(app)
        response = _FakeResponse({"ok": True, "source": "runtime"})
        request = SimpleNamespace(
            url=SimpleNamespace(path="/api/a11oy/v1/mesh/state")
        )

        async def _call_next(_request):
            return response

        async def _exercise():
            result = await app.middleware_function(request, _call_next)
            body = await _read_body(result)
            return result, body

        result, raw = asyncio.run(_exercise())
        payload = json.loads(raw)
        observed = datetime.fromisoformat(
            payload["observed_at"].replace("Z", "+00:00")
        )
        self.assertIsNotNone(observed.tzinfo)
        self.assertEqual(result.headers["x-contract-test"], "preserved")
        self.assertNotIn("etag", result.headers)
        self.assertEqual(result.headers["content-length"], str(len(raw)))

    def test_middleware_canonicalizes_kev_without_false_live(self) -> None:
        app = _FakeApp()
        install_phase_b_response_contract(app)
        note = "Bundled snapshot; no live catalog fetch occurred."
        response = _FakeResponse(
            {
                "data_kind": "sample",
                "note": note,
                "vulnerabilities": [],
            }
        )
        request = SimpleNamespace(
            url=SimpleNamespace(path="/api/a11oy/v1/sec/kev")
        )

        async def _call_next(_request):
            return response

        async def _exercise():
            result = await app.middleware_function(request, _call_next)
            return json.loads(await _read_body(result))

        payload = asyncio.run(_exercise())
        self.assertEqual(payload["data_kind"], "cached")
        self.assertEqual(payload["detail"], note)
        self.assertEqual(payload["note"], note)
        self.assertNotIn("observed_at", payload)

    def test_non_json_response_is_not_consumed(self) -> None:
        app = _FakeApp()
        install_phase_b_response_contract(app)
        response = _FakeResponse(
            {"ok": True},
            content_type="text/plain; charset=utf-8",
        )
        original_iterator = response.body_iterator
        request = SimpleNamespace(
            url=SimpleNamespace(path="/api/a11oy/provenance")
        )

        async def _call_next(_request):
            return response

        result = asyncio.run(app.middleware_function(request, _call_next))
        self.assertIs(result, response)
        self.assertIs(result.body_iterator, original_iterator)


if __name__ == "__main__":
    unittest.main()
