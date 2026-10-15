# SPDX-License-Identifier: Apache-2.0
"""A selected generated source repair must never publish sibling Spaces."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

def _hub_stand_in() -> ModuleType | None:
    """The hash-locked CI test closure omits the SDK. These tests drive the
    publisher through fixtures and only need the guard's HfApi name; the stand-in
    is installed per test, never left in sys.modules for other suites."""
    try:
        import huggingface_hub  # noqa: F401
    except ImportError:
        stand_in = ModuleType("huggingface_hub")
        stand_in.HfApi = type("HfApi", (), {})
        return stand_in
    return None


_HUB_STAND_IN = _hub_stand_in()
if _HUB_STAND_IN is not None:
    sys.modules["huggingface_hub"] = _HUB_STAND_IN
try:
    from scripts.hf_existing_space_guard import (
        SpaceGuardError, require_existing_public_space,
    )
finally:
    if _HUB_STAND_IN is not None:
        sys.modules.pop("huggingface_hub", None)


@pytest.fixture(autouse=True)
def _hub_client(monkeypatch: pytest.MonkeyPatch):
    if _HUB_STAND_IN is not None:
        monkeypatch.setitem(sys.modules, "huggingface_hub", _HUB_STAND_IN)


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "scripts/hf_publish_vertical_flagships_v4.py"
WORKFLOW = ROOT / ".github/workflows/hf-publish-vertical-flagships.yml"
REVISION = "a" * 40
RUN_ID = "36963769185"


@pytest.fixture
def publisher(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    spec = importlib.util.spec_from_file_location("vertical_scope_test", ENTRYPOINT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_SHA", REVISION)
    monkeypatch.setenv("GITHUB_RUN_ID", RUN_ID)
    return module


@pytest.fixture
def sentra_admission_transport(publisher, monkeypatch):
    """Fixture the wire reads, preserving the actual dedicated source admission."""
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "szl-holdings/a11oy")
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-only-github-token")
    branch_path = "/repos/szl-holdings/a11oy/branches/main"
    commit_path = f"/repos/szl-holdings/a11oy/commits/{REVISION}"
    checks_path = commit_path + "/check-runs?filter=latest&per_page=100&page=1"
    required = ("fixture-native-check", *publisher.SENTRA_DOCTRINE_CHECKS)
    rows = [{"name": name, "head_sha": REVISION, "app": {"id": 15368},
             "status": "completed", "conclusion": "success"} for name in required]
    payloads = {
        branch_path: {"commit": {"sha": REVISION}, "protected": True, "protection": {
            "enabled": True, "required_status_checks": {
                "contexts": [required[0]], "checks": [{"context": required[0], "app_id": 15368}]}}},
        commit_path: {"sha": REVISION, "commit": {"verification": {"verified": True, "reason": "valid"}}},
        checks_path: {"total_count": len(rows), "check_runs": rows},
    }
    requests = []
    class Response:
        def __init__(self, payload): self.body = json.dumps(payload).encode()
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit):
            assert 0 < limit <= 2 * 1024 * 1024 + 1
            return self.body[:limit]
    def urlopen(request, *, timeout):
        assert request.get_method() == "GET" and request.data is None
        assert request.full_url.startswith("https://api.github.com/")
        assert request.get_header("Authorization") == "Bearer fixture-only-github-token"
        assert 0 < timeout <= 30
        path = request.full_url.removeprefix("https://api.github.com")
        assert path in payloads, f"unexpected admission read: {path}"
        requests.append(path)
        return Response(payloads[path])
    def opener(*handlers):
        assert handlers == (publisher._SentraNoRedirect,)
        return SimpleNamespace(open=urlopen)
    monkeypatch.setattr(publisher.urllib.request, "build_opener", opener)
    return SimpleNamespace(payloads=payloads, requests=requests,
                           paths=[branch_path, commit_path, checks_path], rows=rows)


@pytest.mark.parametrize("slug", ["terra", "sentra", "counsel"])
def test_selected_renderer_exposes_only_one_target(publisher, monkeypatch, slug):
    renderer = SimpleNamespace(
        FLAGSHIPS=tuple(
            {"slug": candidate}
            for candidate in (*publisher.PUBLIC_FLAGSHIP_SLUGS, *publisher.FOLDED_INTO_KILLINCHU)
        )
    )

    def render():
        assert renderer.FLAGSHIPS == ({"slug": slug},)
        return 0

    renderer.main = render
    monkeypatch.setattr(publisher, "load_module", lambda *args: renderer)
    assert publisher.run_publisher(
        "szl_flagship_v4", publisher.FLAGSHIP_IMPL, selected_slug=slug
    ) == (0, None, (slug,))


@pytest.mark.parametrize("slug", ["finance", "lyte", "vessels", "other"])
def test_selected_renderer_refuses_unauthorized_target(publisher, monkeypatch, slug):
    monkeypatch.setattr(publisher, "load_module", lambda *args: pytest.fail("renderer loaded"))
    code, error, admitted = publisher.run_publisher(
        "szl_flagship_v4", publisher.FLAGSHIP_IMPL, selected_slug=slug
    )
    assert code == 1 and "scope" in error and admitted is None


@pytest.mark.parametrize("slug", ["terra", "sentra", "counsel"])
def test_selected_scope_uses_one_writer_and_verifies_one_row(publisher, monkeypatch, slug):
    calls = []
    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": REVISION})
    monkeypatch.setattr(publisher, "selected_generated_space_preflight", lambda *args: None)

    def run(name, path, **kwargs):
        calls.append((name, path, kwargs))
        publisher.FLAGSHIP_RECEIPT.write_text(json.dumps({
            "complete": True,
            "rows": [{"id": f"SZLHOLDINGS/{slug}", "source_revision": REVISION,
                      "workflow_run_id": int(RUN_ID), "operational": True}],
        }))
        return 0, None, (slug,)

    monkeypatch.setattr(publisher, "run_publisher", run)
    guard = SimpleNamespace(guard_report=lambda: {"existing_only": True})
    assert publisher.publish_selected_generated(slug, guard) == 0
    assert calls == [("szl_flagship_v4", publisher.FLAGSHIP_IMPL, {"selected_slug": slug})]
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["complete"] is True
    assert receipt["publication_scope"] == slug
    assert receipt["sibling_publications"] == 0
    assert receipt["delete_operations"] == 0
    assert receipt["secret_values_recorded"] is False


def test_selected_target_preflight_uses_generated_writer_credential(publisher, monkeypatch):
    module = SimpleNamespace(_BASE=SimpleNamespace(
        token_from_env=lambda: ("synthetic-writer", "HF_ORG_TOKEN")
    ))
    monkeypatch.setattr(publisher, "load_module", lambda *args: module)
    observed = []
    guard = SimpleNamespace(require_existing_public_space=lambda *args: observed.append(args))

    publisher.selected_generated_space_preflight("sentra", guard)

    assert observed == [("SZLHOLDINGS/sentra", "synthetic-writer")]


@pytest.mark.parametrize("slug", ["terra", "sentra", "counsel"])
def test_unverified_public_target_blocks_before_writer(publisher, monkeypatch, slug):
    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": REVISION})
    module = SimpleNamespace(_BASE=SimpleNamespace(
        token_from_env=lambda: ("synthetic-writer", "HF_ORG_TOKEN")
    ))
    monkeypatch.setattr(publisher, "load_module", lambda *args: module)

    def reject(*args):
        raise SpaceGuardError("public visibility is unconfirmed")

    guard = SimpleNamespace(require_existing_public_space=reject)
    monkeypatch.setattr(publisher, "run_publisher", lambda *args, **kwargs: pytest.fail("write attempted"))

    assert publisher.publish_selected_generated(slug, guard) == 1
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["complete"] is False
    assert receipt["error"] == "SpaceGuardError"
    assert "synthetic-writer" not in json.dumps(receipt)


def test_provider_echoed_token_never_enters_failure_receipt(publisher, monkeypatch):
    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": REVISION})
    module = SimpleNamespace(_BASE=SimpleNamespace(
        token_from_env=lambda: ("synthetic-writer", "HF_ORG_TOKEN")
    ))
    monkeypatch.setattr(publisher, "load_module", lambda *args: module)

    class EchoApi:
        def __init__(self, token):
            self.token = token

        def repo_info(self, **kwargs):
            return SimpleNamespace(id=self.token, private=False)

    guard = SimpleNamespace(require_existing_public_space=lambda rid, token:
        require_existing_public_space(rid, token, api_class=EchoApi))
    monkeypatch.setattr(publisher, "run_publisher", lambda *args, **kwargs: pytest.fail("write attempted"))

    assert publisher.publish_selected_generated("sentra", guard) == 1
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["error"] == "SpaceGuardError"
    assert "synthetic-writer" not in json.dumps(receipt)


@pytest.mark.parametrize("slug", ["terra", "sentra", "counsel"])
def test_selected_scope_installs_existing_only_guard(publisher, monkeypatch, slug, sentra_admission_transport):
    installs = []
    guard = SimpleNamespace(install_existing_space_guard=lambda **kwargs: installs.append(kwargs))
    monkeypatch.setenv("SZL_FLAGSHIP_SCOPE", slug)
    monkeypatch.setattr(publisher, "load_module", lambda *args: guard)
    monkeypatch.setattr(publisher, "normalize_github_token_alias", lambda: "NONE")
    routed = []
    def publish_generated(scope, loaded):
        assert scope == slug and scope != "sentra" and loaded is guard
        routed.append(("generated", scope))
        return 0
    def publish_sentra():
        assert publisher._sentra_source_admission() == REVISION
        routed.append(("sentra-existing", "sentra"))
        return 0
    monkeypatch.setattr(publisher, "publish_selected_generated", publish_generated)
    monkeypatch.setattr(publisher, "publish_sentra_existing", publish_sentra)

    assert publisher.main() == 0
    assert installs == [{"require_existing": True}]
    assert routed == [("sentra-existing" if slug == "sentra" else "generated", slug)]
    assert sentra_admission_transport.requests == (sentra_admission_transport.paths if slug == "sentra" else [])


@pytest.mark.parametrize("defect", ["moved-main", "unverified-signature", "wrong-check-app", "failed-check"])
def test_dedicated_sentra_admission_rejects_bad_wire_evidence_before_renderer(
    publisher, monkeypatch, sentra_admission_transport, defect,
):
    transport = sentra_admission_transport
    branch, commit, _ = transport.paths
    if defect == "moved-main": transport.payloads[branch]["commit"]["sha"] = "b" * 40
    elif defect == "unverified-signature":
        transport.payloads[commit]["commit"]["verification"]["verified"] = False
    elif defect == "wrong-check-app": transport.rows[0]["app"]["id"] = 999
    else: transport.rows[0]["conclusion"] = "failure"
    installs = []
    renderer_calls = []
    guard = SimpleNamespace(install_existing_space_guard=lambda **kwargs: installs.append(kwargs))
    def load(name, path):
        if name != "szl_hf_existing_space_guard":
            renderer_calls.append(name)
            raise RuntimeError("unadmitted source reached the publication renderer")
        return guard
    monkeypatch.setattr(publisher, "load_module", load)
    monkeypatch.setattr(publisher, "normalize_github_token_alias", lambda: "NONE")
    monkeypatch.setenv("SZL_FLAGSHIP_SCOPE", "sentra")
    # A moved main is supersession (a newer run owns Sentra), never completion.
    expected_code = publisher.SUPERSEDED_EXIT_CODE if defect == "moved-main" else 1
    assert publisher.main() == expected_code
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert installs == [{"require_existing": True}]
    assert renderer_calls == []
    assert transport.requests == transport.paths[:{
        "moved-main": 1, "unverified-signature": 2, "wrong-check-app": 3, "failed-check": 3,
    }[defect]]
    assert receipt["state"] == ("SUPERSEDED" if defect == "moved-main" else "BLOCKED")
    assert receipt["complete"] is False
    assert receipt.get("superseded", False) is (defect == "moved-main")
    assert receipt["provider_write_attempted"] is False
    assert receipt["provider_write_confirmed"] is False
    assert "fixture-only-github-token" not in json.dumps(receipt)


@pytest.mark.parametrize("slug", ["terra", "sentra", "counsel"])
def test_moved_main_blocks_before_any_publication(publisher, monkeypatch, slug):
    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": "b" * 40})
    monkeypatch.setattr(publisher, "run_publisher", lambda *args, **kwargs: pytest.fail("write attempted"))
    guard = SimpleNamespace(guard_report=lambda: {})
    assert publisher.publish_selected_generated(slug, guard) == publisher.SUPERSEDED_EXIT_CODE
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["complete"] is False
    assert receipt["superseded"] is True and receipt["state"] == "SUPERSEDED"
    assert receipt["provider_write_attempted"] is False
    assert receipt["publication_scope"] == slug


@pytest.mark.parametrize("revision", ["", "0" * 40, "not-a-sha"])
def test_unbound_source_blocks_before_any_publication(publisher, monkeypatch, revision):
    monkeypatch.setenv("GITHUB_SHA", revision)
    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: pytest.fail("head queried"))
    monkeypatch.setattr(publisher, "run_publisher", lambda *args, **kwargs: pytest.fail("write attempted"))
    assert publisher.publish_selected_generated(
        "terra", SimpleNamespace(guard_report=lambda: {})
    ) == 1


def test_main_moving_during_publication_cannot_produce_complete_receipt(publisher, monkeypatch):
    seen = iter([REVISION, "b" * 40])
    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": next(seen)})
    monkeypatch.setattr(publisher, "selected_generated_space_preflight", lambda *args: None)

    def run(*args, **kwargs):
        publisher.FLAGSHIP_RECEIPT.write_text(json.dumps({
            "complete": True,
            "rows": [{"id": "SZLHOLDINGS/terra", "source_revision": REVISION,
                      "workflow_run_id": int(RUN_ID), "operational": True}],
        }))
        return 0, None, ("terra",)

    monkeypatch.setattr(publisher, "run_publisher", run)
    assert publisher.publish_selected_generated(
        "terra", SimpleNamespace(guard_report=lambda: {})
    ) == publisher.SUPERSEDED_EXIT_CODE
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["complete"] is False
    assert receipt["superseded"] is True and receipt["source_still_current"] is False


@pytest.mark.parametrize("slug", ["terra", "sentra", "counsel"])
@pytest.mark.parametrize("wrong_row", ["sibling", "stale", "nonoperational", "wrong_run", "extra_row"])
def test_selected_scope_rejects_unverified_receipt(publisher, monkeypatch, slug, wrong_row):
    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": REVISION})
    monkeypatch.setattr(publisher, "selected_generated_space_preflight", lambda *args: None)
    row = {"id": f"SZLHOLDINGS/{slug}", "source_revision": REVISION,
           "workflow_run_id": int(RUN_ID), "operational": True}
    if wrong_row == "sibling":
        row["id"] = "SZLHOLDINGS/terra" if slug == "sentra" else "SZLHOLDINGS/sentra"
    elif wrong_row == "stale":
        row["source_revision"] = "b" * 40
    else:
        if wrong_row == "nonoperational":
            row["operational"] = False
        elif wrong_row == "wrong_run":
            row["workflow_run_id"] = 1

    def run(*args, **kwargs):
        sibling = "SZLHOLDINGS/terra" if slug == "sentra" else "SZLHOLDINGS/sentra"
        rows = [row, {"id": sibling}] if wrong_row == "extra_row" else [row]
        publisher.FLAGSHIP_RECEIPT.write_text(json.dumps({"complete": True, "rows": rows}))
        return 0, None, (slug,)

    monkeypatch.setattr(publisher, "run_publisher", run)
    assert publisher.publish_selected_generated(slug, SimpleNamespace(guard_report=lambda: {})) == 1
    assert json.loads(publisher.FLAGSHIP_RECEIPT.read_text())["complete"] is False


def test_dispatch_exposes_explicit_narrow_scopes():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "options: [finance, lyte, terra, sentra, counsel, estate]" in workflow
    sync = (ROOT / ".github/workflows/hf-sync.yml").read_text(encoding="utf-8")
    vertical_job = sync.split("\n  publish-vertical-flagships:", 1)[1].split(
        "\n  publish-finance-projection:", 1
    )[0]
    assert (
        "    concurrency:\n"
        "      group: hf-vertical-estate\n"
        "      cancel-in-progress: false"
    ) in vertical_job


def test_postflight_read_error_is_failure_not_supersession(publisher, monkeypatch):
    seen = iter([{"sha": REVISION}, RuntimeError("GitHub unavailable")])

    def head(*args, **kwargs):
        value = next(seen)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(publisher, "_github_json", head)
    monkeypatch.setattr(publisher, "selected_generated_space_preflight", lambda *args: None)

    def run(*args, **kwargs):
        publisher.FLAGSHIP_RECEIPT.write_text(json.dumps({
            "complete": True,
            "rows": [{"id": "SZLHOLDINGS/terra", "source_revision": REVISION,
                      "workflow_run_id": int(RUN_ID), "operational": True}],
        }))
        return 0, None, ("terra",)

    monkeypatch.setattr(publisher, "run_publisher", run)
    assert publisher.publish_selected_generated("terra", SimpleNamespace(guard_report=lambda: {})) == 1
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["complete"] is False and "superseded" not in receipt


def test_unverified_publication_on_moved_main_stays_a_failure(publisher, monkeypatch):
    seen = iter([REVISION, "b" * 40])
    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": next(seen)})
    monkeypatch.setattr(publisher, "selected_generated_space_preflight", lambda *args: None)

    def run(*args, **kwargs):
        publisher.FLAGSHIP_RECEIPT.write_text(json.dumps({
            "complete": False,
            "rows": [{"id": "SZLHOLDINGS/terra", "source_revision": REVISION,
                      "workflow_run_id": int(RUN_ID), "operational": False}],
        }))
        return 1, None, ("terra",)

    monkeypatch.setattr(publisher, "run_publisher", run)
    assert publisher.publish_selected_generated("terra", SimpleNamespace(guard_report=lambda: {})) == 1
    assert "superseded" not in json.loads(publisher.FLAGSHIP_RECEIPT.read_text())


@pytest.mark.parametrize("status, conclusion, pending", [
    ("in_progress", None, True), ("queued", None, True), ("completed", "failure", False),
])
def test_sentra_admission_separates_pending_checks_from_failed_checks(
    publisher, sentra_admission_transport, status, conclusion, pending,
):
    sentra_admission_transport.rows[0].update(status=status, conclusion=conclusion)
    with pytest.raises(publisher.SentraPublicationError, match="unresolved") as caught:
        publisher._sentra_source_admission()
    assert isinstance(caught.value, publisher.SentraChecksPending) is pending
    assert not isinstance(caught.value, publisher.SentraSourceSuperseded)


def test_sentra_missing_required_check_is_pending(publisher, sentra_admission_transport):
    sentra_admission_transport.rows.pop(0)
    payload = sentra_admission_transport.payloads[sentra_admission_transport.paths[2]]
    payload["total_count"] = len(sentra_admission_transport.rows)
    with pytest.raises(publisher.SentraChecksPending):
        publisher._sentra_source_admission()


def test_finance_moved_main_is_superseded_before_any_write(publisher, monkeypatch):
    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": "b" * 40})
    monkeypatch.setattr(publisher, "run_publisher", lambda *args, **kwargs: pytest.fail("write attempted"))
    assert publisher.publish_finance_only(SimpleNamespace(guard_report=lambda: {})) == publisher.SUPERSEDED_EXIT_CODE
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["complete"] is False and receipt["state"] == "SUPERSEDED"
    assert receipt["provider_write_attempted"] is False


@pytest.mark.parametrize("state, expected", [("SUPERSEDED", 75), ("FAILED", 1), ("OUTCOME_UNCERTAIN", 1)])
def test_lyte_superseded_transaction_is_reported_distinctly(publisher, monkeypatch, state, expected):
    # No release journal: the transaction stopped before any provider phase.
    monkeypatch.setattr(publisher, "run_publisher", lambda *args, **kwargs: (1, None, None))
    monkeypatch.setattr(publisher, "read_receipt", lambda path: {"state": state, "complete": False})
    assert publisher.publish_lyte_only(SimpleNamespace(guard_report=lambda: {})) == expected
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["complete"] is False
    assert receipt.get("superseded", False) is (state == "SUPERSEDED")


def _lyte_release_phases():
    """The Lyte transaction's actual phase order, read from its source."""
    import ast

    tree = ast.parse((ROOT / "scripts/hf_publish_lyte_enterprise.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and getattr(node.targets[0], "id", None) == "RELEASE_PHASES"):
            return list(ast.literal_eval(node.value))
    raise AssertionError("RELEASE_PHASES is not declared")


@pytest.mark.parametrize("failed_phase, expected, boundary", [
    ("recheck-source", 75, "BEFORE_PROVIDER_WRITE"),
    ("publish-files", 1, "AFTER_PROVIDER_WRITE"),
    ("bind-source", 1, "AFTER_PROVIDER_WRITE"),
    ("restart", 1, "AFTER_PROVIDER_WRITE"),
    ("attest-runtime", 1, "AFTER_PROVIDER_WRITE"),
    ("verify-source-again", 75, "AFTER_LIVE_VERIFICATION"),
])
def test_lyte_supersession_is_neutral_only_before_a_write_or_after_verification(
        publisher, monkeypatch, failed_phase, expected, boundary):
    """bind-source and restart re-check A11oy main, so any unrelated A11oy
    commit supersedes a Lyte release whose files are already committed. That
    Space is written but not bound, restarted or verified: a failure."""
    phases = _lyte_release_phases()
    completed = phases[:phases.index(failed_phase)]
    lyte = {"state": "SUPERSEDED", "complete": False, "error": "SourceSuperseded",
            "release_journal": {"required_phases": phases, "completed_phases": completed,
                                "failed": True, "complete": False}}
    monkeypatch.setattr(publisher, "run_publisher", lambda *args, **kwargs: (1, None, None))
    monkeypatch.setattr(publisher, "read_receipt", lambda path: lyte)
    assert publisher.publish_lyte_only(SimpleNamespace(guard_report=lambda: {})) == expected
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["complete"] is False and receipt["supersession_boundary"] == boundary
    assert receipt.get("superseded", False) is (expected == 75)
    if expected == 1:
        assert receipt["state"] == "SUPERSEDED_AFTER_UNVERIFIED_WRITE"


def test_lyte_supersession_with_an_inconsistent_journal_is_a_failure(publisher, monkeypatch):
    phases = _lyte_release_phases()
    lyte = {"state": "SUPERSEDED", "complete": False,
            "release_journal": {"required_phases": phases, "completed_phases": ["publish-files"]}}
    monkeypatch.setattr(publisher, "run_publisher", lambda *args, **kwargs: (1, None, None))
    monkeypatch.setattr(publisher, "read_receipt", lambda path: lyte)
    assert publisher.publish_lyte_only(SimpleNamespace(guard_report=lambda: {})) == 1
    assert json.loads(publisher.FLAGSHIP_RECEIPT.read_text())["supersession_boundary"] == "UNKNOWN"


def _finance_run(publisher, *, complete=True):
    def run(*args, **kwargs):
        publisher.FLAGSHIP_RECEIPT.write_text(json.dumps({
            "complete": complete, "rows": [{"id": "SZLHOLDINGS/finance", "operational": complete}]}))
        return (0 if complete else 1), None, ("finance",)
    return run


def test_finance_main_moving_during_publication_is_superseded_not_complete(publisher, monkeypatch):
    # finance_preflight (stubbed) saw REVISION as main; after the publication
    # and its live verification, main is another commit.
    monkeypatch.setattr(publisher, "finance_preflight", lambda: {"source_revision": REVISION})
    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": "b" * 40})
    monkeypatch.setattr(publisher, "run_publisher", _finance_run(publisher))
    guard = SimpleNamespace(guard_report=lambda: {})
    assert publisher.publish_finance_only(guard) == publisher.SUPERSEDED_EXIT_CODE
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["complete"] is False and receipt["superseded"] is True
    assert receipt["source_still_current"] is False


def test_finance_postflight_read_error_and_unverified_publication_are_failures(publisher, monkeypatch):
    guard = SimpleNamespace(guard_report=lambda: {})
    monkeypatch.setattr(publisher, "finance_preflight", lambda: {"source_revision": REVISION})

    def unavailable(*args, **kwargs):
        raise RuntimeError("GitHub unavailable")

    monkeypatch.setattr(publisher, "_github_json", unavailable)
    monkeypatch.setattr(publisher, "run_publisher", _finance_run(publisher))
    assert publisher.publish_finance_only(guard) == 1
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["complete"] is False and "superseded" not in receipt
    assert receipt["postflight_error"] == "RuntimeError"

    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": "b" * 40})
    monkeypatch.setattr(publisher, "run_publisher", _finance_run(publisher, complete=False))
    assert publisher.publish_finance_only(guard) == 1
    assert "superseded" not in json.loads(publisher.FLAGSHIP_RECEIPT.read_text())

    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": REVISION})
    monkeypatch.setattr(publisher, "run_publisher", _finance_run(publisher))
    assert publisher.publish_finance_only(guard) == 0
    assert json.loads(publisher.FLAGSHIP_RECEIPT.read_text())["complete"] is True
