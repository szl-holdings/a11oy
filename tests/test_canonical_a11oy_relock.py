from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import types
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "verify_canonical_a11oy.py"
RUNTIME_CONFIG_SCRIPT = ROOT / "scripts" / "configure_hf_series_a_runtime.py"
WORKFLOW = ROOT / ".github" / "workflows" / "hf-sync.yml"

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = object
    requests_stub.Response = object
    sys.modules["requests"] = requests_stub
if "huggingface_hub" not in sys.modules:
    hub_stub = types.ModuleType("huggingface_hub")
    hub_stub.HfApi = object
    sys.modules["huggingface_hub"] = hub_stub

SPEC = importlib.util.spec_from_file_location("verify_canonical_a11oy", SCRIPT)
assert SPEC and SPEC.loader
relock = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(relock)
CONFIG_SPEC = importlib.util.spec_from_file_location(
    "configure_hf_series_a_runtime",
    RUNTIME_CONFIG_SCRIPT,
)
assert CONFIG_SPEC and CONFIG_SPEC.loader
runtime_config = importlib.util.module_from_spec(CONFIG_SPEC)
CONFIG_SPEC.loader.exec_module(runtime_config)


class FakeResponse:
    def __init__(
        self,
        url: str,
        *,
        status: int = 200,
        payload=None,
        text: str | None = None,
        content_type: str | None = None,
    ) -> None:
        self.url = url
        self.status_code = status
        self._payload = payload
        if text is None and payload is not None:
            text = json.dumps(payload, sort_keys=True)
        self.text = text or ""
        self.content = self.text.encode("utf-8")
        self.headers = {
            "content-type": content_type
            or ("application/json" if payload is not None else "text/html; charset=utf-8")
        }

    def json(self):
        if self._payload is None:
            raise ValueError("not JSON")
        return self._payload


class FakeSession:
    def __init__(self, responses: dict[tuple[str, str], FakeResponse]) -> None:
        self.responses = responses
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, str, dict]] = []

    def head(self, url: str, **kwargs):
        self.calls.append(("HEAD", url, kwargs))
        return self.responses[("HEAD", url)]

    def get(self, url: str, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses[("GET", url)]


class FakeApi:
    def __init__(self, source_sha: str) -> None:
        self.source_sha = source_sha
        self.repository_sha = "b" * 40
        self.runtime_sha = self.repository_sha
        self.runtime_revision_shape = "attribute"
        self.private = False
        self.sdk = "docker"
        self.stage = "RUNNING"
        self.files = {"Dockerfile", "static/3d/holographic.html", "serve.py"}
        self.variables = {
            "SZL_GIT_SHA": SimpleNamespace(value=source_sha),
            **{
                name: SimpleNamespace(value=value)
                for name, value in relock.SERIES_A_VARIABLES.items()
            },
        }
        self.secrets = {
            relock.CANONICAL_SIGNING_SECRET: SimpleNamespace(
                key=relock.CANONICAL_SIGNING_SECRET
            )
        }
        self.volumes = [
            SimpleNamespace(
                type="bucket",
                source=relock.CANONICAL_SERIES_A_BUCKET,
                mount_path="/data",
                read_only=False,
                path=None,
                revision=None,
            )
        ]
        self.clones: dict[str, bool] = {}

    def space_info(self, _repo_id: str):
        if self.runtime_revision_shape == "raw":
            runtime = SimpleNamespace(
                raw={"sha": self.runtime_sha},
                stage=SimpleNamespace(value=self.stage),
                volumes=self.volumes,
            )
        else:
            runtime = SimpleNamespace(
                sha=self.runtime_sha,
                stage=SimpleNamespace(value=self.stage),
                volumes=self.volumes,
            )
        return SimpleNamespace(
            sha=self.repository_sha,
            sdk=self.sdk,
            private=self.private,
            runtime=runtime,
        )

    def list_repo_files(self, _repo_id: str, repo_type: str):
        assert repo_type == "space"
        return sorted(self.files)

    def get_space_variables(self, _repo_id: str):
        return self.variables

    def get_space_secrets(self, _repo_id: str):
        return self.secrets

    def get_space_runtime(self, _repo_id: str):
        return SimpleNamespace(volumes=self.volumes)

    def repo_exists(self, repo_id: str, repo_type: str):
        assert repo_type == "space"
        return self.clones.get(repo_id, False)


def success_session(origin: str, source_sha: str) -> FakeSession:
    verdict_checked_at = datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )
    payloads = {
        "livez": {
            "status": "LIVE",
            "process": {"pid": 1},
            "scope": "process liveness only",
            "receipt_minted": False,
        },
        "build_info": {
            "status": "OBSERVED",
            "build": {
                "state": "OBSERVED",
                "revision": source_sha,
                "revision_source": "env:SZL_GIT_SHA",
                "version": None,
                "version_source": "UNKNOWN",
                "working_tree": "UNKNOWN",
                "working_tree_source": "UNKNOWN",
                "field_evidence": {
                    "revision": "OBSERVED",
                    "version": "UNKNOWN",
                    "working_tree": "UNKNOWN",
                },
            },
            "runtime": {"python": "3.12", "platform": "linux"},
            "receipt_minted": False,
        },
        "brain_capabilities": {
            "schema": "szl.brain-capabilities.v1",
            "overall_status": "PARTIALLY OPERATIONAL",
            "capabilities": [],
            "claim_policy": {},
        },
        "readiness": {
            "view": "summary",
            "honest": True,
            "available": True,
            "matrix_available": True,
            "probe_verdict_available": True,
            "verdict_source_revision": source_sha,
            "verdict_checked_at": verdict_checked_at,
            "verdict_base": origin,
            "verdict_expected_base": origin,
            "verdict_summary": {
                "endpoints": 5,
                "ok": 4,
                "skippedStateChanging": 0,
                "lies": 0,
                "unreachable": 0,
                "throttled": 1,
                "p95_worst": 1806,
            },
        },
        "series_a_status": {
            "schema": "szl.series-a-status/v1",
            "state": "OBSERVED",
            "terminal": True,
            "source_revision": source_sha,
            "signing_key_source": "persistent:env:SZL_COSIGN_PRIVATE_PEM",
            "database": "/data/a11oy/series-a/control-plane-v2.sqlite3",
            "storage": {
                "persistence_required": True,
                "required_mount": "/data",
                "mount_verified": True,
                "journal_mode": "DELETE",
                "instance_id": "store_" + ("1" * 32),
                "created_at": "2026-07-28T15:00:00.000Z",
                "receipt_count": 1,
                "last_receipt_sequence": 1,
                "chain_head": "2" * 64,
            },
        },
    }
    responses: dict[tuple[str, str], FakeResponse] = {}
    for name, path in relock.ROUTES.items():
        url = origin + path
        responses[("HEAD", url)] = FakeResponse(url, status=200, text="")
        if name == "holographic":
            responses[("GET", url)] = FakeResponse(
                url,
                text=(
                    "<title>A11oy Holographic Operations</title>"
                    "<h2>The estate, observed—not assumed.</h2>"
                ),
            )
        else:
            responses[("GET", url)] = FakeResponse(url, payload=payloads[name])
    return FakeSession(responses)


class CanonicalA11oyRelockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = "a" * 40
        self.origin = "https://szlholdings-a11oy.hf.space"
        self.contract = relock.normalize(
            "SZLHOLDINGS/a11oy", self.origin, self.source, "SZL_GIT_SHA"
        )

    def test_normalize_rejects_credentials_non_https_and_bad_sha(self) -> None:
        self.assertEqual(self.contract["source_sha"], self.source)
        for args in (
            ("bad", self.origin, self.source, "SZL_GIT_SHA"),
            ("SZLHOLDINGS/a11oy", "http://example.com", self.source, "SZL_GIT_SHA"),
            ("SZLHOLDINGS/a11oy", "https://u:p@example.com", self.source, "SZL_GIT_SHA"),
            ("SZLHOLDINGS/a11oy", self.origin, "short", "SZL_GIT_SHA"),
            ("SZLHOLDINGS/a11oy", self.origin, self.source, "bad-key"),
        ):
            with self.subTest(args=args), self.assertRaises(relock.RelockError):
                relock.normalize(*args)

    def test_success_requires_exact_source_runtime_routes_and_singleton(self) -> None:
        report = relock.evaluate_once(
            FakeApi(self.source), success_session(self.origin, self.source), self.contract
        )
        self.assertTrue(report["ok"])
        self.assertEqual(report["github_source_sha"], self.source)
        self.assertEqual(report["hf_repository_sha"], report["hf_runtime_sha"])
        self.assertTrue(report["source_revision_variable"]["matched"])
        self.assertTrue(
            report["series_a_runtime"]["persistent_contract_matched"]
        )
        self.assertFalse(any(report["clone_presence"].values()))
        self.assertTrue(report["routes"]["build_info"]["source_bound"])
        self.assertEqual(
            report["routes"]["build_info"]["build_identity"]["version_source"],
            "UNKNOWN",
        )

    def test_runtime_config_and_relock_share_exact_durability_contract(self) -> None:
        self.assertEqual(
            relock.CANONICAL_SIGNING_SECRET,
            runtime_config.CANONICAL_SIGNING_SECRET,
        )
        self.assertEqual(
            relock.CANONICAL_SERIES_A_BUCKET,
            runtime_config.CANONICAL_BUCKET,
        )
        self.assertEqual(
            relock.SERIES_A_VARIABLES,
            runtime_config.SERIES_A_VARIABLES,
        )

    def test_relock_rejects_any_doctrine_lie(self) -> None:
        session = success_session(self.origin, self.source)
        readiness_url = self.origin + relock.ROUTES["readiness"]
        readiness = session.responses[("GET", readiness_url)]._payload
        readiness["verdict_summary"]["ok"] = 3
        readiness["verdict_summary"]["lies"] = 1

        with self.assertRaisesRegex(relock.RelockError, "doctrine lies"):
            relock.evaluate_once(FakeApi(self.source), session, self.contract)

    def test_reviewed_markers_are_bound_to_the_deployed_holographic_source(self) -> None:
        self.assertEqual(
            relock.HOLOGRAPHIC_SOURCE_PATH,
            relock.ROUTES["holographic"].lstrip("/"),
        )
        source = (ROOT / relock.HOLOGRAPHIC_SOURCE_PATH).read_text(encoding="utf-8")
        for marker in relock.HOLOGRAPHIC_SOURCE_MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertIn(relock.HOLOGRAPHIC_SOURCE_PATH, relock.REQUIRED_REMOTE_FILES)
        self.assertNotIn(
            "console/3d/holographic.html",
            relock.REQUIRED_REMOTE_FILES,
        )

    def test_live_holographic_surface_missing_either_marker_fails_closed(self) -> None:
        for marker in relock.HOLOGRAPHIC_SOURCE_MARKERS:
            session = success_session(self.origin, self.source)
            url = self.origin + relock.ROUTES["holographic"]
            response = session.responses[("GET", url)]
            response.text = response.text.replace(marker, "")
            response.content = response.text.encode("utf-8")
            with self.subTest(marker=marker), self.assertRaisesRegex(
                relock.RelockError,
                "reviewed source markers",
            ):
                relock.evaluate_once(FakeApi(self.source), session, self.contract)

    def test_observed_badge_stays_unverified_until_both_probes_verify(self) -> None:
        source = (ROOT / relock.HOLOGRAPHIC_SOURCE_PATH).read_text(encoding="utf-8")
        self.assertIn(
            'id="estate-observation-badge" data-state="UNVERIFIED">'
            "Evidence status: UNVERIFIED",
            source,
        )
        self.assertIn(
            'estateObservationBadge.textContent = "Evidence status: UNVERIFIED"',
            source,
        )
        self.assertIn(
            "const observed = _hasObservedEvidence(readiness, revision)",
            source,
        )
        self.assertIn(
            'estateObservationBadge.dataset.state = observed ? "OBSERVED" : '
            '"UNVERIFIED"',
            source,
        )
        self.assertIn(
            '? "The estate, observed—not assumed."\n'
            '        : "Evidence status: UNVERIFIED"',
            source,
        )

    def test_observed_evidence_predicate_fails_closed(self) -> None:
        source = (ROOT / relock.HOLOGRAPHIC_SOURCE_PATH).read_text(encoding="utf-8")
        match = re.search(
            r"function _hasObservedEvidence\(readiness, revision,"
            r" nowMs = Date\.now\(\)\) \{.*?^\}",
            source,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        valid = {
            "view": "summary",
            "honest": True,
            "available": True,
            "matrix_available": True,
            "probe_verdict_available": True,
            "verdict_source_revision": "a" * 40,
            "verdict_checked_at": "2026-07-26T05:00:00Z",
            "verdict_base": "https://szlholdings-a11oy.hf.space",
            "verdict_expected_base": "https://szlholdings-a11oy.hf.space",
            "verdict_summary": {
                "endpoints": 5,
                "ok": 4,
                "skippedStateChanging": 0,
                "lies": 0,
                "unreachable": 0,
                "throttled": 1,
                "p95_worst": 1806,
            },
        }
        now_ms = 1785045600000
        cases = [
            {
                "name": "complete verdict",
                "readiness": valid,
                "revision": "a" * 40,
            },
            {
                "name": "probe verdict unavailable",
                "readiness": {**valid, "probe_verdict_available": False},
                "revision": "a" * 40,
            },
            {
                "name": "verdict summary missing",
                "readiness": {**valid, "verdict_summary": None},
                "revision": "a" * 40,
            },
            {
                "name": "verdict counts inconsistent",
                "readiness": {
                    **valid,
                    "verdict_summary": {**valid["verdict_summary"], "endpoints": 6},
                },
                "revision": "a" * 40,
            },
            {
                "name": "doctrine lie",
                "readiness": {
                    **valid,
                    "verdict_summary": {
                        **valid["verdict_summary"],
                        "ok": 3,
                        "lies": 1,
                    },
                },
                "revision": "a" * 40,
            },
            {"name": "revision missing", "readiness": valid, "revision": None},
            {
                "name": "revision malformed",
                "readiness": valid,
                "revision": "OBSERVED",
            },
            {
                "name": "verdict revision mismatch",
                "readiness": {
                    **valid,
                    "verdict_source_revision": "b" * 40,
                },
                "revision": "a" * 40,
            },
            {
                "name": "verdict origin mismatch",
                "readiness": {
                    **valid,
                    "verdict_base": "https://unrelated.example",
                },
                "revision": "a" * 40,
            },
            {
                "name": "verdict stale",
                "readiness": {
                    **valid,
                    "verdict_checked_at": "2026-07-24T05:00:00Z",
                },
                "revision": "a" * 40,
            },
            {
                "name": "verdict future",
                "readiness": {
                    **valid,
                    "verdict_checked_at": "2026-07-26T07:00:01Z",
                },
                "revision": "a" * 40,
            },
            {
                "name": "every endpoint skipped",
                "readiness": {
                    **valid,
                    "verdict_summary": {
                        "endpoints": 5,
                        "ok": 0,
                        "skippedStateChanging": 5,
                        "lies": 0,
                        "unreachable": 0,
                        "throttled": 0,
                        "p95_worst": 0,
                    },
                },
                "revision": "a" * 40,
            },
        ]
        script = (
            "const EVIDENCE_MAX_AGE_MS = 24 * 60 * 60 * 1000;\n"
            + match.group(0)
            + "\nconst cases = "
            + json.dumps(cases)
            + ";\nconst nowMs = "
            + str(now_ms)
            + ";\nconsole.log(JSON.stringify(cases.map(({readiness, revision}) => "
            "_hasObservedEvidence(readiness, revision, nowMs))));"
        )
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(result.stdout),
            [
                True,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
            ],
        )

    def test_observed_evidence_rechecks_at_the_freshness_deadline(self) -> None:
        source = (ROOT / relock.HOLOGRAPHIC_SOURCE_PATH).read_text(encoding="utf-8")
        match = re.search(
            r"function _nextEvidenceRefreshDelay\(readiness,"
            r" nowMs = Date\.now\(\)\) \{.*?^\}",
            source,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        script = (
            "const EVIDENCE_MAX_AGE_MS = 24 * 60 * 60 * 1000;\n"
            "const EVIDENCE_REFRESH_INTERVAL_MS = 5 * 60 * 1000;\n"
            + match.group(0)
            + "\nconst checked = Date.parse('2026-07-26T05:00:00Z');"
            + "\nconsole.log(JSON.stringify(["
            + "_nextEvidenceRefreshDelay({verdict_checked_at:"
            + "'2026-07-26T05:00:00Z'}, checked + EVIDENCE_MAX_AGE_MS - 1000),"
            + "_nextEvidenceRefreshDelay({verdict_checked_at:"
            + "'2026-07-26T05:00:00Z'}, checked + EVIDENCE_MAX_AGE_MS + 1)"
            + "]));"
        )
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(result.stdout),
            [1050, 5 * 60 * 1000],
        )
        self.assertIn(
            "() => _updateEvidenceRail(def, true)",
            source,
        )

    def test_observed_evidence_rechecks_when_a_suspended_page_resumes(self) -> None:
        source = (ROOT / relock.HOLOGRAPHIC_SOURCE_PATH).read_text(encoding="utf-8")
        match = re.search(
            r"function _resumeEvidenceRefresh\(\) \{.*?^\}",
            source,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        script = (
            "const calls = [];\n"
            "const document = {hidden: false};\n"
            "let current = {def: {id: 'brain'}};\n"
            "function _updateEvidenceRail(def, forceRefresh) {"
            "calls.push([def.id, forceRefresh]);}\n"
            + match.group(0)
            + "\n_resumeEvidenceRefresh();"
            + "\ndocument.hidden = true;"
            + "\n_resumeEvidenceRefresh();"
            + "\nconsole.log(JSON.stringify(calls));"
        )
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(result.stdout), [["brain", True]])
        self.assertIn(
            'document.addEventListener("visibilitychange", _resumeEvidenceRefresh)',
            source,
        )
        self.assertIn(
            'window.addEventListener("pageshow", _resumeEvidenceRefresh)',
            source,
        )

    def test_superseded_evidence_fetch_cannot_overwrite_newer_evidence(self) -> None:
        source = (ROOT / relock.HOLOGRAPHIC_SOURCE_PATH).read_text(encoding="utf-8")
        match = re.search(
            r"async function _fetchEvidenceSnapshot\(forceRefresh = false\) \{.*?^\}",
            source,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        script = (
            "let evidenceSnapshotPromise = null;\n"
            "let evidenceRefreshGeneration = 0;\n"
            "const pending = [];\n"
            "function fetch(url) { return new Promise((resolve) => "
            "pending.push(() => resolve({ok:true,json:async()=>({url})}))); }\n"
            + match.group(0)
            + "\n(async () => {"
            + "\n  const oldRequest = _fetchEvidenceSnapshot();"
            + "\n  const newRequest = _fetchEvidenceSnapshot(true);"
            + "\n  pending.slice(2).forEach((resolve) => resolve());"
            + "\n  const newResult = await newRequest;"
            + "\n  pending.slice(0, 2).forEach((resolve) => resolve());"
            + "\n  const oldResult = await oldRequest;"
            + "\n  console.log(JSON.stringify([oldResult.generation,"
            + " newResult.generation, evidenceRefreshGeneration]));"
            + "\n})();"
        )
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(result.stdout), [0, 1, 1])
        self.assertIn(
            "if (generation !== evidenceRefreshGeneration) return;",
            source,
        )

    def test_rejected_verdict_is_visibly_unverified(self) -> None:
        source = (ROOT / relock.HOLOGRAPHIC_SOURCE_PATH).read_text(encoding="utf-8")
        match = re.search(
            r"function _readinessEvidenceText\(readiness, observed\) \{.*?^\}",
            source,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        script = (
            "const SURFACES = Array(139);\n"
            + match.group(0)
            + "\nconst readiness = {matrix_summary:{tabs:139},"
            + "verdict_summary:{endpoints:5,ok:3}};"
            + "\nconsole.log(JSON.stringify(["
            + "_readinessEvidenceText(readiness, false),"
            + "_readinessEvidenceText(readiness, true)]));"
        )
        result = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        labels = json.loads(result.stdout)
        self.assertIn("probe UNVERIFIED", labels[0])
        self.assertNotIn("observed clean", labels[0])
        self.assertIn("complete verdict", labels[1])

    def test_relock_rejects_unavailable_stale_or_unbound_verdicts(self) -> None:
        readiness_url = self.origin + relock.ROUTES["readiness"]
        invalid_updates = (
            {"available": False, "probe_verdict_available": False},
            {"verdict_source_revision": "b" * 40},
            {"verdict_base": "https://unrelated.example"},
            {"verdict_checked_at": "2000-01-01T00:00:00Z"},
            {"verdict_summary": None},
            {
                "verdict_summary": {
                    "endpoints": 5,
                    "ok": 0,
                    "skippedStateChanging": 5,
                    "lies": 0,
                    "unreachable": 0,
                    "throttled": 0,
                    "p95_worst": 0,
                }
            },
        )
        for update in invalid_updates:
            session = success_session(self.origin, self.source)
            session.responses[("GET", readiness_url)]._payload.update(update)
            with self.subTest(update=update), self.assertRaises(relock.RelockError):
                relock.evaluate_once(FakeApi(self.source), session, self.contract)

    def test_runtime_revision_is_read_from_current_hub_raw_metadata(self) -> None:
        api = FakeApi(self.source)
        api.runtime_revision_shape = "raw"
        report = relock.evaluate_once(
            api, success_session(self.origin, self.source), self.contract
        )
        self.assertEqual(report["hf_runtime_sha"], api.runtime_sha)
        self.assertEqual(
            report["hf_runtime_sha_source"], "space_info.runtime.raw.sha"
        )

    def test_build_identity_evidence_conflicts_fail_closed(self) -> None:
        session = success_session(self.origin, self.source)
        build_url = self.origin + relock.ROUTES["build_info"]
        build = session.responses[("GET", build_url)]._payload["build"]
        build["working_tree"] = "CLEAN"
        with self.assertRaisesRegex(relock.RelockError, "working-tree"):
            relock.evaluate_once(FakeApi(self.source), session, self.contract)

    def test_source_variable_mismatch_fails_closed(self) -> None:
        api = FakeApi(self.source)
        api.variables["SZL_GIT_SHA"] = SimpleNamespace(value="c" * 40)
        with self.assertRaisesRegex(relock.RelockError, "variable mismatch"):
            relock.evaluate_once(api, success_session(self.origin, self.source), self.contract)

    def test_series_a_runtime_variable_or_volume_drift_fails_closed(self) -> None:
        api = FakeApi(self.source)
        api.variables["A11OY_REQUIRE_PERSISTENT_STORAGE"] = SimpleNamespace(
            value="0"
        )
        with self.assertRaisesRegex(relock.RelockError, "variable drift"):
            relock.evaluate_once(
                api,
                success_session(self.origin, self.source),
                self.contract,
            )

        api = FakeApi(self.source)
        api.volumes[0].source = "SZLHOLDINGS/other"
        with self.assertRaisesRegex(relock.RelockError, "bucket is not attached"):
            relock.evaluate_once(
                api,
                success_session(self.origin, self.source),
                self.contract,
            )

    def test_series_a_status_rejects_ephemeral_or_unmounted_storage(self) -> None:
        status_url = self.origin + relock.ROUTES["series_a_status"]
        for update in (
            {"signing_key_source": "ephemeral"},
            {"storage": {"mount_verified": False}},
            {"storage": {"created_at": None}},
            {
                "storage": {
                    "receipt_count": 0,
                    "last_receipt_sequence": 0,
                    "chain_head": None,
                }
            },
        ):
            session = success_session(self.origin, self.source)
            payload = session.responses[("GET", status_url)]._payload
            if "storage" in update:
                payload["storage"].update(update["storage"])
            else:
                payload.update(update)
            with self.subTest(update=update), self.assertRaisesRegex(
                relock.RelockError,
                "persistent storage contract",
            ):
                relock.evaluate_once(
                    FakeApi(self.source),
                    session,
                    self.contract,
                )

    def test_stale_runtime_revision_fails_closed(self) -> None:
        api = FakeApi(self.source)
        api.runtime_sha = "c" * 40
        with self.assertRaisesRegex(relock.RelockError, "runtime does not serve"):
            relock.evaluate_once(api, success_session(self.origin, self.source), self.contract)

    def test_head_or_build_identity_failure_is_not_downgraded(self) -> None:
        session = success_session(self.origin, self.source)
        livez_url = self.origin + relock.ROUTES["livez"]
        session.responses[("HEAD", livez_url)].status_code = 405
        with self.assertRaisesRegex(relock.RelockError, "not operational"):
            relock.evaluate_once(FakeApi(self.source), session, self.contract)

        session = success_session(self.origin, self.source)
        build_url = self.origin + relock.ROUTES["build_info"]
        session.responses[("GET", build_url)]._payload["build"]["revision"] = "c" * 40
        with self.assertRaisesRegex(relock.RelockError, "exact protected source"):
            relock.evaluate_once(FakeApi(self.source), session, self.contract)

    def test_clone_reappearance_fails_closed(self) -> None:
        api = FakeApi(self.source)
        api.clones["SZLHOLDINGS/a11oy-clone-1"] = True
        with self.assertRaisesRegex(relock.RelockError, "clone reappeared"):
            relock.evaluate_once(api, success_session(self.origin, self.source), self.contract)

    def test_verifier_source_contains_no_external_mutation(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "add_space_variable",
            "add_space_secret",
            "upload_file",
            "upload_folder",
            "create_commit",
            "restart_space",
            "request_space_hardware",
            "update_repo_settings",
            "gh issue",
        ):
            self.assertNotIn(forbidden, source)


class HfSyncWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_deployment_is_one_exact_pinned_reusable_call(self) -> None:
        self.assertIn(
            "uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@e3ec47ad2e99a535839afe0f30fefbd8973d52da",
            self.workflow,
        )
        self.assertIn("ref: ${{ github.sha }}", self.workflow)
        self.assertIn("restart-space: true", self.workflow)
        self.assertIn("source-revision-variable: SZL_GIT_SHA", self.workflow)
        self.assertIn("source-revision-probe-path: /api/build-info", self.workflow)
        self.assertIn("HF_TOKEN: ${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}", self.workflow)

    def test_workflow_contains_no_inline_binding_or_verifier_implementation(self) -> None:
        self.assertNotIn("add_space_variable", self.workflow)
        self.assertNotIn("python - <<'PY'", self.workflow)
        self.assertNotIn("def probe(", self.workflow)
        self.assertIn("python .github/scripts/verify_canonical_a11oy.py", self.workflow)

    def test_post_deploy_probe_is_ingested_before_relock(self) -> None:
        self.assertIn("readiness-verdict:", self.workflow)
        self.assertIn(
            "node tools/readiness-harness/probe_runner.mjs",
            self.workflow,
        )
        self.assertIn(
            "python .github/scripts/publish_readiness_verdict.py",
            self.workflow,
        )
        runtime_config = self.workflow.split(
            "  runtime-config:", 1
        )[1].split("\n  deploy:", 1)[0]
        self.assertIn("needs: deploy", runtime_config)
        self.assertIn("needs: runtime-config", self.workflow)
        self.assertIn(
            "needs: [runtime-config, readiness-verdict]",
            self.workflow,
        )
        self.assertIn("--expected-origin \"$CANONICAL_ORIGIN\"", self.workflow)
        self.assertIn("--expected-source-sha \"$SOURCE_SHA\"", self.workflow)
        self.assertIn("--soft", self.workflow)
        self.assertLess(
            self.workflow.index("node tools/readiness-harness/probe_runner.mjs"),
            self.workflow.index("Upload immutable full probe evidence"),
        )
        self.assertLess(
            self.workflow.index("Upload immutable full probe evidence"),
            self.workflow.index(
                "python .github/scripts/publish_readiness_verdict.py"
            ),
        )
        publisher = (
            ROOT / ".github" / "scripts" / "publish_readiness_verdict.py"
        ).read_text(encoding="utf-8")
        self.assertIn("probe summary contains doctrine lies", publisher)

    def test_runtime_config_proves_a_persisted_receipt_across_restart(self) -> None:
        self.assertIn(
            "python scripts/prove_hf_series_a_restart.py",
            self.workflow,
        )
        self.assertIn(
            "--output \"$SERIES_A_LIVE_REPORT\"",
            self.workflow,
        )
        self.assertIn(
            "${{ env.SERIES_A_LIVE_REPORT }}",
            self.workflow,
        )
        self.assertIn(
            "- name: Upload secret-free runtime configuration evidence\n"
            "        if: ${{ always() }}",
            self.workflow,
        )
        self.assertLess(
            self.workflow.index("python scripts/prove_hf_series_a_restart.py"),
            self.workflow.index(
                "python .github/scripts/verify_canonical_a11oy.py"
            ),
        )

    def test_immutable_artifacts_are_unique_across_rerun_attempts(self) -> None:
        self.assertIn(
            "name: canonical-a11oy-readiness-${{ github.run_id }}-${{ github.run_attempt }}",
            self.workflow,
        )
        self.assertIn(
            "name: canonical-a11oy-relock-${{ github.run_id }}-${{ github.run_attempt }}",
            self.workflow,
        )

    def test_issue_write_is_limited_to_relock_job(self) -> None:
        self.assertIn("contents: read", self.workflow)
        self.assertIn("issues: write", self.workflow)
        self.assertIn('RELOCK_ISSUE: "1043"', self.workflow)
        self.assertIn("gh issue edit", self.workflow)
        self.assertIn("gh issue close", self.workflow)
        self.assertIn("gh issue reopen", self.workflow)

    def test_required_routes_and_pruning_remain_enforced(self) -> None:
        for route in (
            "/",
            "/api/livez",
            "/api/build-info",
            "/api/a11oy/v1/brain/capabilities",
            "/api/a11oy/v1/readiness/tab-matrix?view=summary",
            "/api/a11oy/v1/series-a/status",
            "/static/3d/holographic.html",
        ):
            self.assertIn(route, self.workflow)
        self.assertIn("prune: true", self.workflow)
        self.assertIn("wait-running: 1200", self.workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
