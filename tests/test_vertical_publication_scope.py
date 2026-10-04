# SPDX-License-Identifier: Apache-2.0
"""A selected generated source repair must never publish sibling Spaces."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.hf_existing_space_guard import (
    SpaceGuardError, require_existing_public_space,
)


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
def test_selected_scope_installs_existing_only_guard(publisher, monkeypatch, slug):
    installs = []
    guard = SimpleNamespace(install_existing_space_guard=lambda **kwargs: installs.append(kwargs))
    monkeypatch.setenv("SZL_FLAGSHIP_SCOPE", slug)
    monkeypatch.setattr(publisher, "load_module", lambda *args: guard)
    monkeypatch.setattr(publisher, "normalize_github_token_alias", lambda: "NONE")
    routed = []
    monkeypatch.setattr(publisher, "publish_selected_generated",
                        lambda scope, loaded: routed.append(("generated", scope)) or 0)
    monkeypatch.setattr(publisher, "publish_sentra_existing",
                        lambda: routed.append(("sentra-existing", "sentra")) or 0)

    assert publisher.main() == 0
    assert installs == [{"require_existing": True}]
    assert routed == [("sentra-existing" if slug == "sentra" else "generated", slug)]


@pytest.mark.parametrize("slug", ["terra", "sentra", "counsel"])
def test_moved_main_blocks_before_any_publication(publisher, monkeypatch, slug):
    monkeypatch.setattr(publisher, "_github_json", lambda *args, **kwargs: {"sha": "b" * 40})
    monkeypatch.setattr(publisher, "run_publisher", lambda *args, **kwargs: pytest.fail("write attempted"))
    guard = SimpleNamespace(guard_report=lambda: {})
    assert publisher.publish_selected_generated(slug, guard) == 1
    receipt = json.loads(publisher.FLAGSHIP_RECEIPT.read_text())
    assert receipt["complete"] is False
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
    ) == 1
    assert json.loads(publisher.FLAGSHIP_RECEIPT.read_text())["complete"] is False


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
        "      group: hf-publish-vertical-flagships\n"
        "      cancel-in-progress: false"
    ) in vertical_job
