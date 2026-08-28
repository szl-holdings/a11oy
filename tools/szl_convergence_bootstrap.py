#!/usr/bin/env python3
"""SZL frontier convergence bootstrap and evidence bundle writer.

This one-shot helper runs the live/operational probes required by the round-5
convergence stack and emits a machine-readable artifact set:

* audit/frontier-convergence-manifest.json
* audit/frontier-claims-ledger.json
* audit/frontier-contradictions-ledger.json
* audit/frontier-command-probes.json
* evidence/conformance/eu-ai-act-article-12.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import textwrap
import time
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DOC_ROOT = ROOT / "docs"
A11OY_LANDING = ROOT / "a11oy_landing.html"
PAYLOAD_DOC = ROOT / "SZL_FINAL_FRONTIER_CONVERGENCE_PAYLOAD.md"
REGULATORY_DOC = ROOT / "SZL_REGULATORY_SPINE.md"
AUDIT_DIR = ROOT / "audit"
CONFORMANCE_DIR = ROOT / "evidence" / "conformance"
SCHEMA_PATH = ROOT / "schemas" / "szl-governed-action-predicate.v1.schema.json"
GITHUB_CHECKLIST = DOC_ROOT / "github-enterprise-access-checklist.json"
HUGGINGFACE_MANIFEST = DOC_ROOT / "huggingface-ecosystem-manifest.json"
PYTHON = [sys.executable, "-I", "-B"]

KNOWN_PROBES: list[tuple[str, list[str], bool]] = [
    ("frontdoor_truth", PYTHON + ["scripts/check_a11oy_frontdoor_truth.py", str(A11OY_LANDING)], False),
    ("frontdoor_repair_idempotent", PYTHON + ["scripts/repair_a11oy_frontdoor.py", str(A11OY_LANDING), "--check"], False),
    ("hf_ecosystem_check", PYTHON + ["scripts/audit_huggingface_ecosystem.py", "--check"], False),
    (
        "github_access_audit",
        PYTHON + ["scripts/audit_github_access_permissions.py", "--checklist", str(GITHUB_CHECKLIST), "--output", str(AUDIT_DIR / "github-access-audit.json"), "--validate"],
        False,
    ),
]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def scalar(value: Any) -> str:
    """Return a safe scalarized string used in YAML/markdown fields."""

    if value is None:
        return "UNKNOWN"
    if isinstance(value, str):
        clean = value.strip()
        return clean if clean else "UNKNOWN"
    if isinstance(value, (bool, int, float)):
        return str(value)
    return "UNKNOWN"


def _preview(value: str, max_len: int = 280) -> str:
    return value[:max_len].replace("\r", "").replace("\n", "\\n") if value else ""


@dataclass
class ProbeRecord:
    name: str
    command: list[str]
    status: str
    return_code: int | None
    duration_ms: int
    stdout_sha256: str | None = None
    stderr_sha256: str | None = None
    error: str | None = None
    excerpt: str = ""


def _run_probe(name: str, command: list[str], timeout_seconds: int = 90) -> ProbeRecord:
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            check=False,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        elapsed = int((time.perf_counter() - start) * 1000)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        status = "PASS" if completed.returncode == 0 else "FAIL"
        return ProbeRecord(
            name=name,
            command=command,
            status=status,
            return_code=completed.returncode,
            duration_ms=elapsed,
            stdout_sha256=_sha256_text(stdout),
            stderr_sha256=_sha256_text(stderr),
            excerpt=_preview(f"{stdout}\n{stderr}".strip()),
            error=None,
        )
    except FileNotFoundError as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        return ProbeRecord(
            name=name,
            command=command,
            status="NOT_FOUND",
            return_code=None,
            duration_ms=elapsed,
            error=f"command_not_found: {exc}",
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        return ProbeRecord(
            name=name,
            command=command,
            status="TIMEOUT",
            return_code=None,
            duration_ms=elapsed,
            error=f"timeout_after_{exc.timeout}s",
        )
    except Exception as exc:  # pragma: no cover - defensive path
        elapsed = int((time.perf_counter() - start) * 1000)
        return ProbeRecord(
            name=name,
            command=command,
            status="NOT_INSPECTED",
            return_code=None,
            duration_ms=elapsed,
            error=str(exc),
        )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    return json.loads(raw)


def _run_domain_probe() -> str:
    try:
        from a11oy_canonical_domain import CANONICAL_HOST, REGISTRY_HOST, _is_registry_host

        return (
            f"canonical={CANONICAL_HOST};"
            f"registry={REGISTRY_HOST};"
            f"a11oy.net_is_registry_host={_is_registry_host('a11oy.net')}"
        )
    except Exception as exc:
        return f"ERROR:{exc}"


def _claim_state_from_probe(probe_name: str, probes: dict[str, ProbeRecord], default_state: str = "MODELED") -> str:
    probe = probes.get(probe_name)
    if not probe:
        return default_state
    if probe.status == "PASS":
        return "MEASURED"
    if probe.status in {"TIMEOUT", "NOT_FOUND", "NOT_INSPECTED"}:
        return "SAMPLE"
    if probe.status == "FAIL":
        return "UNKNOWN"
    return "ROADMAP"


@dataclass
class Claim:
    claim_id: str
    statement: str
    evidence_state: str
    evidence_uri: str | None = None
    severity: str = "LOW"
    public_allowed: bool = True
    freshness: str = "SNAPSHOT(2026-05-12)"
    status: str = "OPEN"
    notes: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.notes is None:
            self.notes = []

        if self.public_allowed and not self.evidence_uri:
            self.evidence_state = "UNKNOWN"
            self.notes.append("public_allowed=true requires evidence_uri; demoted to UNKNOWN")
        if self.evidence_state == "UNKNOWN":
            self.status = "OPEN"


@dataclass
class Contradiction:
    contradiction_id: str
    statement: str
    status: str
    refutes_claim_ids: list[str]
    blocks_release: bool
    evidence_uri: str | None = None
    severity: str = "MEDIUM"
    notes: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.notes is None:
            self.notes = []


def _render_payload_md(
    claims: list[Claim],
    contradictions: list[Contradiction],
    probes: dict[str, ProbeRecord],
) -> str:
    probe_lines = []
    for name in sorted(probes):
        probe = probes[name]
        probe_lines.append(f"- `{name}`: {probe.status} (return={scalar(probe.return_code)}, duration_ms={probe.duration_ms})")

    claim_rows = "\n".join(
        [f"| {item.claim_id} | {item.evidence_state} | {item.severity} | {scalar(item.evidence_uri)} | {item.statement[:120]}... |" for item in claims]
    )
    contradiction_rows = "\n".join(
        [
            f"| {item.contradiction_id} | {item.status} | {str(item.blocks_release)} | {', '.join(item.refutes_claim_ids)} | {item.statement[:150]}... |"
            for item in contradictions
        ]
    )

    return textwrap.dedent(
        f"""\
        # SZL FINAL FRONTIER CONVERGENCE PAYLOAD

        Canonical sentence:
        **SZL Holdings builds a11oy: AI that can demonstrate its work through governed execution and offline-verifiable receipts.**

        ## One-shot Python payload

        ```python
        import pathlib
        import subprocess

        ROOT = pathlib.Path(__file__).resolve().parent
        subprocess.run([sys.executable, "-I", "-B", str(ROOT / "tools" / "szl_convergence_bootstrap.py"), "--run"], check=True)
        ```

        ## Command probe status

        {chr(10).join(probe_lines)}

        ## Claims ledger (seeded)

        | Claim | State | Severity | Evidence | Statement |
        | --- | --- | --- | --- | --- |
        {claim_rows}

        ## Contradictions ledger (seeded)

        | ID | Status | Release blocker | Refutes | Statement |
        | --- | --- | --- | --- | --- |
        {contradiction_rows}

        ## Verification rules

        * Do not fabricate values. `UNKNOWN` is explicit debt.
        * Banned legacy names are blocked by `tools/lexicon_gate.py`.
        * `tools/release_gate.py` must pass for production release.

        ## In-toto action predicate

        This run uses `schemas/szl-governed-action-predicate.v1.schema.json`.
        """
    ).strip()


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []

    def _dump_obj(prefix: str, value: Any, indent: int = 0) -> None:
        pad = " " * indent
        if isinstance(value, dict):
            for idx, (k, v) in enumerate(value.items()):
                if isinstance(v, (dict, list)):
                    lines.append(f"{pad}{k}:")
                    _dump_obj(k, v, indent + 2)
                else:
                    lines.append(f"{pad}{k}: {json.dumps(v)}")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (dict, list)):
                    lines.append(f"{pad}-")
                    _dump_obj(prefix, item, indent + 2)
                else:
                    lines.append(f"{pad}- {json.dumps(item)}")
        else:
            lines.append(f"{pad}{json.dumps(value)}")

    _dump_obj("", payload, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_claims(probes: dict[str, ProbeRecord]) -> list[Claim]:
    github_audit = _load_json(AUDIT_DIR / "github-access-audit.json")
    github_summary = github_audit.get("summary", {})
    github_public = f"writeReady={github_summary.get('writeReady', 'unknown')} readOnly={github_summary.get('readOnly', 'unknown')} unavailable={github_summary.get('unavailable', 'unknown')}"

    hf_manifest = _load_json(HUGGINGFACE_MANIFEST)
    hf_summary = hf_manifest.get("counts", {})
    hf_public = f"models={hf_summary.get('models', 'unknown')} datasets={hf_summary.get('datasets', 'unknown')} spaces={hf_summary.get('spaces', 'unknown')}"
    frontdoor_probe = probes["frontdoor_truth"]
    hf_probe = probes["hf_ecosystem_check"]
    canonical_probe = _run_domain_probe()

    return [
        Claim(
            claim_id="C-01",
            statement="Two-origin lock: a-11-oy.com is the product command center; a11oy.net is the separate public proof/registry. This app does not 301 .net onto the product host.",
            evidence_state=_claim_state_from_probe("frontdoor_truth", probes, default_state="ROADMAP"),
            evidence_uri="audit/frontier-command-probes.json#frontdoor_truth",
            severity="HIGH",
            public_allowed=True,
            freshness="MEASURED",
        ),
        Claim(
            claim_id="C-02",
            statement="GitHub access and entitlement evidence reflects 9 checked sibling targets and 4 write-ready repos in one authenticated session.",
            evidence_state=scalar(github_summary.get("errors", 0) and "UNKNOWN" or _claim_state_from_probe("github_access_audit", probes, default_state="SNAPSHOT(2026-05-12)")),
            evidence_uri="audit/github-access-audit.json",
            severity="HIGH",
            public_allowed=True,
            freshness=github_public,
        ),
        Claim(
            claim_id="C-03",
            statement=f"Hugging Face public snapshot is live and auditable from {github_audit.get('viewer', {}).get('login', 'authenticated user') if isinstance(github_audit, dict) else 'unknown user'}.",
            evidence_state=_claim_state_from_probe("hf_ecosystem_check", probes, default_state="SNAPSHOT(2026-05-12)"),
            evidence_uri="docs/huggingface-ecosystem-manifest.json",
            severity="HIGH",
            public_allowed=True,
            freshness=f"{hf_public}",
        ),
        Claim(
            claim_id="C-04",
            statement="Domain policy and landing page claim text are reconciled with 26-space public registry semantics.",
            evidence_state=_claim_state_from_probe("frontdoor_repair_idempotent", probes, default_state="SNAPSHOT(2026-05-12)"),
            evidence_uri="a11oy_frontier_page.py",
            severity="HIGH",
            public_allowed=True,
            freshness="ROADMAP",
        ),
        Claim(
            claim_id="C-05",
            statement="Lexicon lock (five disallowed legacy names) is enforced by repository gate, not marketing copy.",
            evidence_state="ROADMAP",
            evidence_uri="tools/lexicon_gate.py",
            severity="MEDIUM",
            public_allowed=False,
            freshness="ROADMAP",
            status="BLOCKED",
            notes=["run tools/lexicon_gate.py prior to release"],
        ),
        Claim(
            claim_id="C-06",
            statement=f"Domain guard status: {canonical_probe}",
            evidence_state="MEASURED" if "ERROR" not in canonical_probe else "UNKNOWN",
            evidence_uri="a11oy_canonical_domain.py",
            severity="HIGH",
            public_allowed=True,
            freshness="MEASURED",
        ),
    ]


def _build_contradictions() -> list[Contradiction]:
    return [
        Contradiction(
            contradiction_id="B-01",
            statement="Flagship vs full-space publication claims must not mix 26-space registry with 5-space doctrine.",
            status="OPEN",
            refutes_claim_ids=["C-01", "C-04"],
            blocks_release=True,
            evidence_uri="a11oy_landing.html",
            severity="CRITICAL",
            notes=["Keep both public claims and doctrine true; classify 26-space registry with explicit tiers instead of flattening."],
        ),
        Contradiction(
            contradiction_id="B-02",
            statement="Stale operational counts must remain SNAPSHOT(2026-05-12) until new public evidence is re-probed.",
            status="OPEN",
            refutes_claim_ids=["C-03"],
            blocks_release=True,
            evidence_uri="docs/huggingface-ecosystem-manifest.json",
            severity="MEDIUM",
            notes=["If the count is re-probed and stored with fresh timestamp, this can resolve."],
        ),
        Contradiction(
            contradiction_id="B-03",
            statement="Legacy names (e.g., discontinued product labels) must not be presented as current doctrine.",
            status="OPEN",
            refutes_claim_ids=["C-05"],
            blocks_release=False,
            evidence_uri="docs/doctrine-v11.md",
            severity="LOW",
            notes=["Resolved by lexicon gate and phrase cleanup in claim materials."],
        ),
    ]


def _conformance_payload(profile_name: str, claims: list[Claim], contradictions: list[Contradiction]) -> dict[str, Any]:
    required_fields = {
        "actor": {"who": "authenticated_human", "id": "required"},
        "context": {"system": "a11oy", "jurisdiction": "EU AI Act Article 12"},
        "action": {"category": "governed_execution"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "claimState": {
            c.claim_id: c.evidence_state for c in claims
        },
        "contradictions": {
            c.contradiction_id: {"status": c.status, "blocks_release": c.blocks_release}
            for c in contradictions
        },
        "profile": profile_name,
        "required_controls": [
            "human_identity",
            "risk_context",
            "decision_reason",
            "policy_decision",
            "immutable_evidence_hash",
            "retention_floor_6_months",
        ],
        "evidence": {
            "local_durability": True,
            "remote_submission": False,
            "storage": "audit/frontier-command-probes.json",
        },
    }
    return required_fields


def _build_manifest(probes: dict[str, ProbeRecord], claims: list[Claim], contradictions: list[Contradiction], article12: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "generatedBy": "tools/szl_convergence_bootstrap.py",
        "artifacts": {
            "claims": "audit/frontier-claims-ledger.json",
            "contradictions": "audit/frontier-contradictions-ledger.json",
            "probes": "audit/frontier-command-probes.json",
            "article12": str(CONFORMANCE_DIR / "eu-ai-act-article-12.yaml"),
            "schema": str(SCHEMA_PATH),
            "payload": "SZL_FINAL_FRONTIER_CONVERGENCE_PAYLOAD.md",
        },
        "summaries": {
            "commandStates": {name: record.status for name, record in probes.items()},
            "claimStateCounts": {
                "MEASURED": sum(1 for c in claims if c.evidence_state == "MEASURED"),
                "SAMPLE": sum(1 for c in claims if c.evidence_state == "SAMPLE"),
                "SNAPSHOT": sum(1 for c in claims if c.evidence_state.startswith("SNAPSHOT")),
                "UNKNOWN": sum(1 for c in claims if c.evidence_state == "UNKNOWN"),
                "ROADMAP": sum(1 for c in claims if c.evidence_state == "ROADMAP"),
            },
            "contradictions": {
                "total": len(contradictions),
                "releaseBlocking": sum(1 for c in contradictions if c.blocks_release),
            },
        },
        "article12": article12,
    }


def _validate_payload(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {"schemaVersion", "generatedAt", "generatedBy", "artifacts", "summaries", "article12"}
    missing = [key for key in required if key not in manifest]
    if missing:
        errors.append(f"manifest_missing_fields={missing}")
    if not manifest.get("artifacts", {}).get("claims"):
        errors.append("missing claims artifact")
    if not manifest.get("artifacts", {}).get("contradictions"):
        errors.append("missing contradiction artifact")
    if not manifest.get("artifacts", {}).get("probes"):
        errors.append("missing probe artifact")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Execute convergence probes and emit artifacts")
    parser.add_argument("--verify", action="store_true", help="Validate previously written artifacts")
    parser.add_argument("--pretty", action="store_true", help="Pretty print artifacts to stdout")
    args = parser.parse_args()

    if not args.run and not args.verify:
        args.run = True

    if args.run:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        probes = {name: _run_probe(name, command) for name, command, _ in KNOWN_PROBES}
        claims = _build_claims(probes)
        contradictions = _build_contradictions()
        article12 = _conformance_payload("eu-ai-act-article-12", claims, contradictions)

        if not SCHEMA_PATH.is_file():
            raise FileNotFoundError(f"required predicate schema missing: {SCHEMA_PATH}")
        if not GITHUB_CHECKLIST.is_file():
            raise FileNotFoundError(f"missing checklist baseline: {GITHUB_CHECKLIST}")

        claim_records = [asdict(c) for c in claims]
        contradiction_records = [asdict(c) for c in contradictions]
        manifest = _build_manifest(probes, claims, contradictions, article12)

        (AUDIT_DIR / "frontier-claims-ledger.json").write_text(json.dumps(claim_records, indent=2) + "\n", encoding="utf-8")
        (AUDIT_DIR / "frontier-contradictions-ledger.json").write_text(json.dumps(contradiction_records, indent=2) + "\n", encoding="utf-8")
        (AUDIT_DIR / "frontier-command-probes.json").write_text(
            json.dumps([asdict(p) for p in probes.values()], indent=2) + "\n", encoding="utf-8"
        )
        (AUDIT_DIR / "frontier-convergence-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        _write_yaml(CONFORMANCE_DIR / "eu-ai-act-article-12.yaml", article12)
        PAYLOAD_DOC.write_text(_render_payload_md(claims, contradictions, probes), encoding="utf-8")
        if not REGULATORY_DOC.is_file():
            raise FileNotFoundError(f"missing regulatory spine baseline: {REGULATORY_DOC}")

        print(f"Wrote frontier bootstrap artifacts into {AUDIT_DIR}")
        if args.pretty:
            print(json.dumps(manifest, indent=2))

    manifest_path = AUDIT_DIR / "frontier-convergence-manifest.json"
    if args.verify:
        manifest = _load_json(manifest_path)
        errors = _validate_payload(manifest)
        if errors:
            print("frontier-bootstrap verify failed:")
            for error in errors:
                print(f"- {error}")
            return 1
        print("frontier-bootstrap verify: PASS")
        if args.pretty:
            print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
