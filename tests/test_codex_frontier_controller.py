from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_PATH = ROOT / "tools" / "codex_frontier_controller.py"
SPEC = importlib.util.spec_from_file_location("codex_frontier_controller", CONTROLLER_PATH)
assert SPEC is not None and SPEC.loader is not None
controller = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = controller
SPEC.loader.exec_module(controller)


def invoke(root: Path, *argv: str) -> str:
    completed = subprocess.run(
        list(argv),
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def initialize_repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    invoke(root, "git", "init", "-b", "main")
    invoke(root, "git", "config", "user.name", "Controller Test")
    invoke(root, "git", "config", "user.email", "controller@example.invalid")
    invoke(root, "git", "config", "core.autocrlf", "false")
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    invoke(root, "git", "add", "tracked.txt")
    invoke(root, "git", "commit", "-m", "base")
    return root, invoke(root, "git", "rev-parse", "HEAD")


def write_effective_estate(root: Path) -> None:
    (root / "governance" / "owner-directives").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "governance" / "owner-directives" / "2026-09-04-sentra.yaml").write_text(
        """directive:
  id: owner-2026-09-04-sentra-assurance-command
  issued: "2026-09-04"
  authority: owner
  states:
    - id: SZLHOLDINGS/sentra
      state: FLAGSHIP_KEPT
      role: sole-assurance-command
      planes: [gate, yawar, evidence]
      absorbs: [SZLHOLDINGS/aegis-assurance]
    - id: SZLHOLDINGS/aegis-assurance
      state: DECOMMISSIONED
      mission_routes_to: SZLHOLDINGS/sentra
    - id: SZLHOLDINGS/killinchu
      state: FLAGSHIP_KEPT
      role: sole-cyber-physical-resilience-command
    - id: SZLHOLDINGS/immune
      state: ENGINE_LIBRARY_UNDER_SENTRA
""",
        encoding="utf-8",
    )
    (root / "scripts" / "hf_publish_vertical_flagships_v4.py").write_text(
        """PUBLIC_FLAGSHIP_SLUGS = ("terra", "counsel", "finance", "lyte", "sentra")
FOLDED_INTO_KILLINCHU = ("vessels",)
KILLINCHU_SPACE = "SZLHOLDINGS/killinchu"
SENTRA_SPACE = "SZLHOLDINGS/sentra"
""",
        encoding="utf-8",
    )
    urls = controller.CANONICAL_PRODUCTS
    manifest = {
        "platform_count": 1,
        "public_vertical_product_count": 6,
        "platforms": [
            {
                "id": "a11oy",
                "class": "platform",
                "public": True,
                "hf_repository": "SZLHOLDINGS/a11oy",
                "base_url": urls["a11oy"].rstrip("/"),
            }
        ],
        "public_products": [
            {
                "id": slug,
                "class": (
                    "assurance-command"
                    if slug == "sentra"
                    else "cyber-physical-resilience-and-maritime-command"
                    if slug == "killinchu"
                    else f"{slug}-product"
                ),
                "public": True,
                "hf_repository": f"SZLHOLDINGS/{slug}",
                "base_url": urls[slug].rstrip("/"),
            }
            for slug in ("killinchu", "sentra", "lyte", "finance", "terra", "counsel")
        ],
        "capability_planes": [
            {
                "id": "vessels",
                "status": "folded",
                "runtime": "killinchu",
                "independent_public_space_allowed": False,
            },
            {
                "id": "aegis",
                "status": "decommissioned",
                "runtime": "sentra:absorbed-history",
                "independent_public_space_allowed": False,
            },
            {
                "id": "immune",
                "status": "engine-library",
                "runtime": "sentra",
                "independent_public_space_allowed": False,
            },
        ],
        "retirement_candidates": [],
        "decommissioned_surfaces": [
            {
                "hf_repository": "SZLHOLDINGS/aegis-assurance",
                "state": "DECOMMISSIONED",
                "mission_routes_to": "SZLHOLDINGS/sentra",
                "history_preserved": True,
            }
        ],
    }
    (root / "governance" / "public-estate.v1.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_child_environment_is_allowlisted_and_credentials_are_removed() -> None:
    environment = {
        "PATH": "safe-path",
        "SYSTEMROOT": r"C:\Windows",
        "GITHUB_TOKEN": "ghp_" + "a" * 40,
        "UNRECOGNIZED_SECRET": "sensitive-value",
        "PYTHONPATH": "unsafe-import-path",
    }

    child, removed_names, removed_values = controller.sanitized_child_environment(environment)

    assert child["PATH"] == "safe-path"
    assert child["SYSTEMROOT"] == r"C:\Windows"
    assert "GITHUB_TOKEN" not in child
    assert "UNRECOGNIZED_SECRET" not in child
    assert "PYTHONPATH" not in child
    assert set(removed_names) == {
        "GITHUB_TOKEN",
        "PYTHONPATH",
        "UNRECOGNIZED_SECRET",
    }
    assert "sensitive-value" in removed_values
    assert child["GIT_CONFIG_GLOBAL"] == controller.os.devnull
    assert child["GIT_TERMINAL_PROMPT"] == "0"


def test_changed_file_inventory_covers_all_four_git_surfaces(tmp_path: Path) -> None:
    root, base = initialize_repo(tmp_path)
    (root / "committed.txt").write_text("committed\n", encoding="utf-8")
    invoke(root, "git", "add", "committed.txt")
    invoke(root, "git", "commit", "-m", "committed change")
    (root / "staged.txt").write_text("staged\n", encoding="utf-8")
    invoke(root, "git", "add", "staged.txt")
    (root / "tracked.txt").write_text("unstaged\n", encoding="utf-8")
    (root / "untracked.txt").write_text("untracked\n", encoding="utf-8")

    paths, gate = controller.changed_files(root, base)

    assert gate.status == "PASS"
    assert {path.name for path in paths} == {
        "committed.txt",
        "staged.txt",
        "tracked.txt",
        "untracked.txt",
    }
    categories = gate.detail["categories"]
    assert categories["committed"] == ["committed.txt"]
    assert categories["staged"] == ["staged.txt"]
    assert categories["unstaged"] == ["tracked.txt"]
    assert categories["untracked"] == ["untracked.txt"]
    assert len(gate.detail["worktree_snapshot_sha256"]) == 64


def test_git_state_rejects_dirty_main_stale_base_and_dirty_terminal(tmp_path: Path) -> None:
    root, base = initialize_repo(tmp_path)
    (root / "tracked.txt").write_text("dirty main\n", encoding="utf-8")
    assert controller.check_git_state(root, base, "verify").status == "FAIL"

    invoke(root, "git", "restore", "tracked.txt")
    invoke(root, "git", "checkout", "-b", "feature")
    (root / "tracked.txt").write_text("feature work\n", encoding="utf-8")
    assert controller.check_git_state(root, base, "verify").status == "PASS"
    assert controller.check_git_state(root, base, "terminal").status == "FAIL"

    invoke(root, "git", "restore", "tracked.txt")
    invoke(root, "git", "checkout", "main")
    (root / "main-only.txt").write_text("main advanced\n", encoding="utf-8")
    invoke(root, "git", "add", "main-only.txt")
    invoke(root, "git", "commit", "-m", "advance main")
    invoke(root, "git", "checkout", "feature")
    stale = controller.check_git_state(root, "main", "verify")
    assert stale.status == "FAIL"
    assert stale.detail["base_is_ancestor"] is False


def test_estate_gate_uses_exact_structured_semantics(tmp_path: Path) -> None:
    root = tmp_path / "estate"
    root.mkdir()
    write_effective_estate(root)

    passing = controller.check_effective_estate(root)
    assert passing.status == "PASS", passing.detail

    directive_path = root / "governance" / "owner-directives" / "2026-09-04-sentra.yaml"
    directive_path.write_text(
        "# owner-2026-09-04-sentra-assurance-command\n"
        + directive_path.read_text(encoding="utf-8").replace(
            "id: owner-2026-09-04-sentra-assurance-command", "id: wrong-directive"
        ),
        encoding="utf-8",
    )
    failing = controller.check_effective_estate(root)
    assert failing.status == "FAIL"
    assert failing.detail["directive_valid"] is False


def test_estate_gate_rejects_duplicate_or_malformed_retirement_state(tmp_path: Path) -> None:
    root = tmp_path / "estate"
    root.mkdir()
    write_effective_estate(root)
    manifest_path = root / "governance" / "public-estate.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["retirement_candidates"] = [{}]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    gate = controller.check_effective_estate(root)

    assert gate.status == "FAIL"
    assert gate.detail["retirement_exact"] is False


def test_compile_and_secret_gates_inspect_staged_blob_not_only_worktree(
    tmp_path: Path,
) -> None:
    root, base = initialize_repo(tmp_path)
    hidden_token = "ghp_" + "a" * 40
    staged_source = f"TOKEN = {hidden_token!r}\ndef broken(:\n"
    path = root / "hidden.py"
    path.write_text(staged_source, encoding="utf-8")
    invoke(root, "git", "add", "hidden.py")
    path.write_text("VALUE = 'clean worktree'\n", encoding="utf-8")
    paths, inventory = controller.changed_files(root, base)
    assert inventory.status == "PASS"

    compile_gate = controller.check_python_compile(root, paths, base=base)
    secret_gate = controller.check_changed_secrets(root, paths, base=base)

    assert compile_gate.status == "FAIL"
    assert any(item["file"] == "index:hidden.py" for item in compile_gate.detail["failures"])
    assert secret_gate.status == "FAIL"
    assert {item["file"] for item in secret_gate.detail["hits"]} == {"index:hidden.py"}


def test_required_verification_commands_are_never_silently_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(controller.shutil, "which", lambda _name: None)

    commands = controller.verification_commands(
        tmp_path, base="origin/main", full=True, docker=True
    )
    by_name = {command.name: command for command in commands}

    assert "readiness_matrix_check" in by_name
    assert "targeted_pytest" in by_name
    assert set(controller.REQUIRED_TARGETED_TESTS).issubset(
        set(by_name["targeted_pytest"].argv)
    )
    assert {
        "pnpm_install",
        "doctrine_tests",
        "doctrine_typecheck",
        "doctrine_build",
        "jest_compliance",
        "qec_lineage",
        "a11oy_core_standalone",
        "docker_build",
    }.issubset(by_name)


def test_report_derives_activity_and_never_claims_global_operation(tmp_path: Path) -> None:
    results = [
        controller.Result(
            name="fetch_origin_main",
            status="PASS",
            required=True,
            detail={
                "argv": ["git", "fetch"],
                "local_mutations": ["git_remote_tracking_refs"],
                "network_access": "GIT_REMOTE_READ",
            },
        ),
        controller.Result(
            name="local_gate",
            status="PASS",
            required=True,
            detail={},
        ),
    ]

    output = controller.write_report(
        tmp_path,
        phase="terminal",
        base="origin/main",
        results=results,
        output_root=tmp_path / "report",
    )
    report = json.loads((output / "terminal.json").read_text(encoding="utf-8"))

    assert report["schema"] == "szl.codex-frontier-controller/v2"
    assert report["terminal_status"] == "TERMINAL_WITNESS_PASS"
    assert report["operational_claim"] == "NOT_ESTABLISHED_BY_THIS_CONTROLLER_ALONE"
    evidence = report["execution_evidence"]
    assert (
        evidence["git_ref_mutation_evidence"]
        == "FETCH_SUCCEEDED_REF_CHANGE_NOT_COMPARED"
    )
    assert evidence["provider_mutation"] == "UNVERIFIED_NO_PROVIDER_WRITE_DECLARED"
    assert evidence["declared_network_access"] == ["GIT_REMOTE_READ"]


def test_report_terminal_failure_is_failed_closed(tmp_path: Path) -> None:
    output = controller.write_report(
        tmp_path,
        phase="terminal",
        base="origin/main",
        results=[controller.result("required_gate", False, {"evidence": "missing"})],
        output_root=tmp_path / "report",
    )
    report = json.loads((output / "terminal.json").read_text(encoding="utf-8"))

    assert report["complete"] is False
    assert report["terminal_status"] == "FAILED_CLOSED"
    assert report["required_failures"] == ["required_gate"]
