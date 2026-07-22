from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "verify_canonical_a11oy.py"
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
        self.private = False
        self.sdk = "docker"
        self.stage = "RUNNING"
        self.files = {"Dockerfile", "console/3d/holographic.html", "serve.py"}
        self.variables = {"SZL_GIT_SHA": SimpleNamespace(value=source_sha)}
        self.clones: dict[str, bool] = {}

    def space_info(self, _repo_id: str):
        return SimpleNamespace(
            sha=self.repository_sha,
            sdk=self.sdk,
            private=self.private,
            runtime=SimpleNamespace(
                sha=self.runtime_sha,
                stage=SimpleNamespace(value=self.stage),
            ),
        )

    def list_repo_files(self, _repo_id: str, repo_type: str):
        assert repo_type == "space"
        return sorted(self.files)

    def get_space_variables(self, _repo_id: str):
        return self.variables

    def repo_exists(self, repo_id: str, repo_type: str):
        assert repo_type == "space"
        return self.clones.get(repo_id, False)


def success_session(origin: str, source_sha: str) -> FakeSession:
    payloads = {
        "livez": {
            "status": "LIVE",
            "process": {"pid": 1},
            "scope": "process liveness only",
            "receipt_minted": False,
        },
        "build_info": {
            "status": "OBSERVED",
            "build": {"state": "OBSERVED", "revision": source_sha},
            "runtime": {"python": "3.12"},
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
            "matrix_available": True,
            "probe_verdict_available": True,
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
        self.assertFalse(any(report["clone_presence"].values()))
        self.assertTrue(report["routes"]["build_info"]["source_bound"])

    def test_source_variable_mismatch_fails_closed(self) -> None:
        api = FakeApi(self.source)
        api.variables["SZL_GIT_SHA"] = SimpleNamespace(value="c" * 40)
        with self.assertRaisesRegex(relock.RelockError, "variable mismatch"):
            relock.evaluate_once(api, success_session(self.origin, self.source), self.contract)

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
            "uses: szl-holdings/.github/.github/workflows/reusable-hf-deploy.yml@9aa36ed914e88bdef2873b26c022e0cecb1e6ec8",
            self.workflow,
        )
        self.assertIn("ref: ${{ github.sha }}", self.workflow)
        self.assertIn("source-revision-variable: SZL_GIT_SHA", self.workflow)
        self.assertIn("source-revision-probe-path: /api/build-info", self.workflow)
        self.assertIn("HF_TOKEN: ${{ secrets.HF_ORG_TOKEN || secrets.HF_TOKEN }}", self.workflow)

    def test_workflow_contains_no_inline_binding_or_verifier_implementation(self) -> None:
        self.assertNotIn("add_space_variable", self.workflow)
        self.assertNotIn("python - <<'PY'", self.workflow)
        self.assertNotIn("def probe(", self.workflow)
        self.assertIn("python .github/scripts/verify_canonical_a11oy.py", self.workflow)

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
            "/static/3d/holographic.html",
        ):
            self.assertIn(route, self.workflow)
        self.assertIn("prune: true", self.workflow)
        self.assertIn("wait-running: 1200", self.workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
