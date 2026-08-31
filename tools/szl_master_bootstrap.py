#!/usr/bin/env python3
"""szl_master_bootstrap.py — scaffold the a11oy v1 slice repo tree.

Week 1, gate zero. Creates (idempotently):

  predicate.schema.json                              GovernedAction/v1 schema
  README.md                                          truth-state block + laws
  docs/positioning/AUTO_REVIEW_DELTA.md              12-row Codex comparison
  docs/RUNBOOK_WEEK1.md                              bootstrap-to-green runbook
  evidence/conformance/eu-ai-act-article-12.yaml     11 mapped Art. 12 entries,
                                                     retention_minimum_days: 180
  COMMERCIAL_LEDGER.yaml                             24 rows, all UNKNOWN,
                                                     all blocks_raise: true
  claims-ledger.yaml                                 seeded claims with states
  tools/*.py, tools/_templates/*, src/a11oy/*.py     the code of this slice

Stdlib-only: pyyaml is never assumed. YAML artifacts are emitted in the
SZL-YAML-1 subset by tools/szl_miniyaml.py and re-parsed after writing as a
self-check. Usage:

  python3 tools/szl_master_bootstrap.py            # dry run, prints plan
  python3 tools/szl_master_bootstrap.py --run      # write (idempotent)
  python3 tools/szl_master_bootstrap.py --run --root /path/to/new/repo

Wired-repo policy (szl-holdings/a11oy, round-10 wiring): this bootstrap
NEVER overwrites a pre-existing file whose contents differ. Such files are
reported as conflicts and kept as-is (Zero-Bandaid Law: silent overwrite
would hide the divergence; a listed conflict is an audited state). On a
fresh, empty target tree behavior is identical to the round-10 payload:
every artifact is created and both gates exit 1 by design. In this repo the
round-10 gates live at tools/docs_lexicon_gate.py and
tools/commercial_release_gate.py because tools/lexicon_gate.py and
tools/release_gate.py are already owned by the round-5 gates; the bootstrap
installs them under their canonical names when scaffolding a fresh tree.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAYLOAD_ROOT = HERE.parent
TEMPLATES = HERE / "_templates"

EXIT_OK = 0
EXIT_ERROR = 2


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_artifacts() -> dict[str, str]:
    """Return {relative_path: content} for every governed text artifact."""
    miniyaml = _load_module("szl_miniyaml", HERE / "szl_miniyaml.py")
    content_data = _load_module("content_data", TEMPLATES / "content_data.py")

    schema_text = (TEMPLATES / "predicate_schema.json").read_text(encoding="utf-8")
    schema_obj = json.loads(schema_text)  # validates the JSON before writing

    artifacts = {
        "predicate.schema.json": json.dumps(schema_obj, indent=2) + "\n",
        "README.md": (TEMPLATES / "README.md").read_text(encoding="utf-8"),
        "docs/positioning/AUTO_REVIEW_DELTA.md": (
            TEMPLATES / "AUTO_REVIEW_DELTA.md"
        ).read_text(encoding="utf-8"),
        "docs/RUNBOOK_WEEK1.md": (TEMPLATES / "RUNBOOK_WEEK1.md").read_text(
            encoding="utf-8"
        ),
        "evidence/conformance/eu-ai-act-article-12.yaml": miniyaml.dump(
            content_data.CONFORMANCE_PROFILE
        ),
        "COMMERCIAL_LEDGER.yaml": miniyaml.dump(content_data.LEDGER_DOC),
        "claims-ledger.yaml": miniyaml.dump(content_data.CLAIMS_LEDGER_DOC),
    }

    # Self-check: every YAML artifact must round-trip before it is written.
    for rel, text in artifacts.items():
        if rel.endswith(".yaml"):
            parsed = miniyaml.load(text)
            source = {
                "evidence/conformance/eu-ai-act-article-12.yaml": content_data.CONFORMANCE_PROFILE,
                "COMMERCIAL_LEDGER.yaml": content_data.LEDGER_DOC,
                "claims-ledger.yaml": content_data.CLAIMS_LEDGER_DOC,
            }[rel]
            if parsed != source:
                raise RuntimeError(f"self-check failed: {rel} does not round-trip")
    return artifacts


def code_files() -> list[tuple[str, Path]]:
    """Code and template files copied into the target tree (rel path, source).

    In this wired repo the round-10 gates are stored under non-clobbering
    names; they install into a fresh scaffold under the canonical payload
    names (tools/lexicon_gate.py, tools/release_gate.py) so the runbook
    commands work there.
    """
    wired_names = {
        "lexicon_gate.py": "docs_lexicon_gate.py",
        "release_gate.py": "commercial_release_gate.py",
    }
    files: list[tuple[str, Path]] = []
    for name in (
        "szl_miniyaml.py",
        "lexicon_gate.py",
        "release_gate.py",
        "demo_harness.py",
        "szl_master_bootstrap.py",
    ):
        files.append((f"tools/{name}", HERE / wired_names.get(name, name)))
    for template in sorted(TEMPLATES.iterdir()):
        if template.is_file():
            files.append((f"tools/_templates/{template.name}", template))
    a11oy_src = PAYLOAD_ROOT / "src" / "a11oy"
    for module in sorted(a11oy_src.glob("*.py")):
        if module.name == "__init__.py":
            # This repo owns src/a11oy/__init__.py (import-light front-door
            # namespace). Fresh scaffolds get the payload slice init from
            # templates instead, so the two never clobber each other.
            continue
        files.append((f"src/a11oy/{module.name}", module))
    files.append(("src/a11oy/__init__.py", TEMPLATES / "a11oy_slice_init.py"))
    # Only the payload's own test ships with the slice. (In the wired repo,
    # tests/ holds the full a11oy suite; scaffolding must not drag it along.)
    test_slice = PAYLOAD_ROOT / "tests" / "test_slice.py"
    if test_slice.is_file():
        files.append(("tests/test_slice.py", test_slice))
    return files


# Seed documents are written once and thereafter owned by hand: bootstrap
# never overwrites them (the AUTO_REVIEW_DELTA footnote is deleted in Week 1;
# re-running bootstrap must not resurrect it).
SEED_ONLY = {"README.md", "docs/positioning/AUTO_REVIEW_DELTA.md", "docs/RUNBOOK_WEEK1.md"}


def write_idempotent(path: Path, content: bytes, report: dict[str, list[str]]) -> None:
    owner_key = None
    for seed in SEED_ONLY:
        if path.as_posix().endswith(seed):
            owner_key = seed
            break
    if owner_key and path.exists():
        report["kept"].append(str(path))
        return
    if path.exists():
        if path.read_bytes() == content:
            report["unchanged"].append(str(path))
            return
        # Wired-repo policy: never overwrite a pre-existing file that
        # differs. Record the conflict and keep the repo's version; the
        # conflict list is the reconciliation work queue.
        report["conflicts"].append(str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    report["created"].append(str(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", action="store_true", help="write files (default: dry run)")
    parser.add_argument(
        "--root",
        default=".",
        help="target repo root (default: current working directory)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        artifacts = build_artifacts()
    except Exception as exc:
        print(f"bootstrap ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    plan: list[tuple[Path, bytes]] = []
    for rel, text in sorted(artifacts.items()):
        plan.append((root / rel, text.encode("utf-8")))
    missing_sources = []
    for rel, src in code_files():
        if src.exists():
            plan.append((root / rel, src.read_bytes()))
        else:
            missing_sources.append(rel)

    if not args.run:
        print(f"DRY RUN — target root: {root}")
        for dest, content in plan:
            state = "missing" if not dest.exists() else (
                "unchanged" if dest.read_bytes() == content else "conflict (would keep)"
            )
            print(f"  {state:12s} {dest.relative_to(root)}  ({len(content)} bytes)")
        if missing_sources:
            print(f"  WARNING: sources not found under {PAYLOAD_ROOT}: {missing_sources}")
        print("re-run with --run to write")
        return EXIT_OK

    report: dict[str, list[str]] = {
        "created": [],
        "updated": [],
        "unchanged": [],
        "kept": [],
        "conflicts": [],
    }
    for dest, content in plan:
        write_idempotent(dest, content, report)

    print(f"bootstrap complete under {root}")
    print(f"  created:   {len(report['created'])}")
    print(f"  updated:   {len(report['updated'])}")
    print(f"  unchanged: {len(report['unchanged'])}")
    print(f"  kept (seed docs, hand-editable): {len(report['kept'])}")
    if report["conflicts"]:
        print(f"  conflicts (kept existing, NOT overwritten): {len(report['conflicts'])}")
        for conflict in report["conflicts"]:
            print(f"    {conflict}")
    if missing_sources:
        print(f"  WARNING: skipped missing sources: {missing_sources}")
    print("next: python3 tools/lexicon_gate.py && python3 tools/release_gate.py "
          "(canonical fresh-scaffold names; in szl-holdings/a11oy the wired names are "
          "tools/docs_lexicon_gate.py and tools/commercial_release_gate.py — both are "
          "EXPECTED to exit 1 on a fresh scaffold — see docs/RUNBOOK_WEEK1.md)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
