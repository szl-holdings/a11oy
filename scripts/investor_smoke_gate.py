#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1 (NOT a theorem). Locked-proven kernel = 8.
"""Investor-honest S1–S12 / L1–L6 / D1–D10 smoke gate.

Fail-closed. Never skip-as-green. Never invent PASS. No POST. No genome rewrite.
S7 asserts the UI BIND (kernel slot ← /honest locked_formula_count = 8), not
that genome ``tier_counts['LOCKED-PROVEN']`` must equal 8. Both counts are real:
kernel 8 and genome catalog 144 / LOCKED-PROVEN 25 may coexist when labelled.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]

LOCKED_KERNEL_COUNT = 8
LOCKED_KERNEL_IDS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
HONEST_PATH = "/api/a11oy/v1/honest"
HONEST_FIELD = "locked_formula_count"
SIGNER_ENUM = frozenset({"DSSE-LIVE", "UNSIGNED-LOCAL", "unavailable"})
VALUE_LABELS = frozenset({"MEASURED", "UNAVAILABLE"})
COORD_KEYS = frozenset(
    {"latitude", "longitude", "lat", "lon", "altitude", "velocity"}
)
SNAPSHOT_DATE = "2026-08-28"
CANONICAL_ORIGIN = "https://a-11-oy.com"
SUNSET_ORIGIN = "https://a11oy.net"
HF_SPACE = "https://szlholdings-a11oy.hf.space"
USER_AGENT = "a11oy-investor-smoke-gate/1.0 (+https://github.com/szl-holdings/a11oy)"

ALLOWED_STATUSES = frozenset(
    {"PASS", "FAIL", "UNAVAILABLE", "SNAPSHOT", "UNCONFIGURED"}
)
ALLOWED_UNAVAILABLE_IDS = frozenset({"S4", "S6", "S9"})
ALLOWED_UNCONFIGURED_IDS = frozenset({"wire-D"})
SNAPSHOT_IDS = frozenset({"L1", "L2", "L3", "L4", "L5", "L6"})

HEAD_GET_PATHS = (
    "/console",
    "/trust",
    "/healthz",
    "/readyz",
    "/api/health",
)
HEAD_404_VS_GET_200 = "/api/a11oy/healthz"
SIGNER_REQUIRED_PATHS = (
    "/api/health",
    "/healthz",
    "/api/a11oy/v1/health",
)
LEDGER_GET_PATHS = (
    "/api/a11oy/v1/ledger",
    "/api/a11oy/v1/energy/ledger",
)
SOFT_404_PATH = "/definitely-not-a-declared-asset-zzzz.js"
LIVE_ISS_PATH = "/api/a11oy/v1/live/iss"
LIVE_FETCH_STATUS_PATH = "/api/a11oy/v1/live-fetch/status"
OG_CANDIDATES = (
    "/og-card.png",
    "/social-preview-v5.png",
    "/social-preview-series-a.png",
)

# Kernel-slot bind: genome LOCKED-PROVEN must not land in cnt-locked / setTiers.locked.
_CNT_LOCKED_FROM_GENOME = re.compile(
    r"""\$\(\s*['"]cnt-locked['"]\s*\)[\s\S]{0,240}?"""
    r"""(?:tier_counts|tc)\s*(?:\[\s*['"]LOCKED-PROVEN['"]\s*\]|\.LOCKED)""",
    re.I,
)
_CNT_LOCKED_NODEVALUE_GENOME = re.compile(
    r"""['"]cnt-locked['"][\s\S]{0,160}?nodeValue\s*=\s*[\s\S]{0,80}?"""
    r"""(?:tc|tier_counts)\s*\[\s*['"]LOCKED-PROVEN['"]""",
    re.I,
)
_SETTIERS_LOCKED_GENOME = re.compile(
    r"""setTiers\(\s*\{[^}]*\blocked\s*:\s*(?:tc|g\.tier_counts|tier_counts)"""
    r"""\s*\[\s*['"]LOCKED-PROVEN['"]""",
    re.I | re.S,
)
_SETTIERS_PROOF_TIERS = re.compile(
    r"""setTiers\(\s*\w+\.proof_tiers\s*\)""",
    re.I,
)
_HONEST_FETCH = re.compile(
    r"""/api/a11oy/v1/honest""",
    re.I,
)
_LOCKED_FORMULA_COUNT = re.compile(
    r"""locked_formula_count""",
    re.I,
)


@dataclass
class Verdict:
    id: str
    status: str
    detail: str
    evidence: str = ""
    snapshot_date: str = ""
    owner: str = ""

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_STATUSES:
            raise ValueError(f"{self.id}: illegal status {self.status!r}")
        if self.status == "SNAPSHOT" and not self.snapshot_date:
            raise ValueError(f"{self.id}: SNAPSHOT requires a date")


@dataclass
class Matrix:
    verdicts: list[Verdict] = field(default_factory=list)

    def add(self, verdict: Verdict) -> None:
        self.verdicts.append(verdict)

    def by_id(self, vid: str) -> Verdict | None:
        for item in self.verdicts:
            if item.id == vid:
                return item
        return None

    def missing(self, required: Iterable[str]) -> list[str]:
        have = {item.id for item in self.verdicts}
        return [rid for rid in required if rid not in have]

    def fail_ids(self) -> list[str]:
        return [item.id for item in self.verdicts if item.status == "FAIL"]

    def as_dict(self) -> dict[str, Any]:
        return {"verdicts": [asdict(item) for item in self.verdicts]}


# ---------------------------------------------------------------------------
# Fail-closed matrix rules (tested; skip-as-green is itself a FAIL)
# ---------------------------------------------------------------------------

REQUIRED_MATRIX_IDS = (
    "S1",
    "S2",
    "S3",
    "S4",
    "S5",
    "S6",
    "S7",
    "S8",
    "S9",
    "S10",
    "S11",
    "S12",
    "L1",
    "L2",
    "L3",
    "L4",
    "L5",
    "L6",
    "D1",
    "D2",
    "D3",
    "D4",
    "D5",
    "D6",
    "D7",
    "D8",
    "D9",
    "D10",
    "wire-D",
)
# Contract mode cannot honestly PASS live HTTP rows. It still must include every
# non-network id so a missing static probe is FAIL, never skip-as-green.
CONTRACT_REQUIRED_IDS = (
    "S4",
    "S5",
    "S6",
    "S7",
    "S8",
    "S9",
    "S12",
    "L1",
    "L2",
    "L3",
    "L4",
    "L5",
    "L6",
    "D1",
    "D2",
    "D3",
    "D4",
    "D5",
    "D6",
    "D7",
    "D8",
    "D9",
    "D10",
    "wire-D",
)


def validate_matrix(matrix: Matrix, required: Iterable[str] = REQUIRED_MATRIX_IDS) -> list[str]:
    """Return error strings. A missing probe is FAIL, never skip-as-green."""
    errors: list[str] = []
    required_list = list(required)
    for missing_id in matrix.missing(required_list):
        errors.append(f"missing probe {missing_id}: FAIL (skip-as-green rejected)")
    for item in matrix.verdicts:
        if item.status not in ALLOWED_STATUSES:
            errors.append(f"{item.id}: illegal status {item.status}")
        if item.status == "SNAPSHOT" and not item.snapshot_date:
            errors.append(f"{item.id}: SNAPSHOT without date rejected")
        if item.status == "UNAVAILABLE" and item.id not in ALLOWED_UNAVAILABLE_IDS:
            errors.append(
                f"{item.id}: UNAVAILABLE not allowed here; missing evidence must FAIL"
            )
        if item.status == "UNCONFIGURED" and item.id not in ALLOWED_UNCONFIGURED_IDS:
            errors.append(f"{item.id}: UNCONFIGURED is only allowed for wire-D")
    return errors


# ---------------------------------------------------------------------------
# S7 bind assertion — kernel slot must source /honest (8), not genome 25
# ---------------------------------------------------------------------------

def kernel_slot_bind_failures(text: str, *, source_name: str) -> list[str]:
    """FAIL reasons if a locked-proven kernel slot still reads genome 25.

    Genome 144 / LOCKED-PROVEN 25 may remain as a *separately labelled* count.
    This function only reds the kernel slot: ``cnt-locked`` and ``setTiers.locked``.
    """
    failures: list[str] = []
    if _CNT_LOCKED_FROM_GENOME.search(text) or _CNT_LOCKED_NODEVALUE_GENOME.search(text):
        failures.append(
            f"{source_name}: cnt-locked reads genome tier_counts['LOCKED-PROVEN'] "
            f"into the locked-proven kernel slot. Bind must source {HONEST_PATH} "
            f"{HONEST_FIELD} ({LOCKED_KERNEL_COUNT}), labelled. Genome catalog "
            "144 / LOCKED-PROVEN 25 may remain as a separately labelled count. "
            "INTI owns the product fix."
        )
    if _SETTIERS_LOCKED_GENOME.search(text):
        failures.append(
            f"{source_name}: setTiers.locked reads genome tier_counts['LOCKED-PROVEN'] "
            f"into the kernel slot. Bind must source {HONEST_PATH} {HONEST_FIELD} "
            f"({LOCKED_KERNEL_COUNT}), labelled. INTI owns the product fix."
        )
    if _SETTIERS_PROOF_TIERS.search(text):
        failures.append(
            f"{source_name}: setTiers(*.proof_tiers) paints proof_tiers.locked into "
            "the kernel slot. Current org/overview proof_tiers.locked is the genome "
            f"LOCKED-PROVEN catalog count, not {HONEST_PATH} {HONEST_FIELD}. "
            "INTI owns the product fix."
        )
    claims_kernel_slot = (
        'id="cnt-locked"' in text
        or "setTiers(" in text
        or 'id="pt-locked"' in text
    )
    if claims_kernel_slot and not failures:
        honest_sourced = bool(
            _HONEST_FETCH.search(text) and _LOCKED_FORMULA_COUNT.search(text)
        )
        if not honest_sourced:
            failures.append(
                f"{source_name}: locked-proven kernel slot (cnt-locked / "
                f"setTiers.locked) does not source {HONEST_PATH} {HONEST_FIELD}."
            )
    return failures


def analyze_repo_kernel_binds(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    targets = (
        root / "web" / "trust.html",
        root / "a11oy_landing.html",
    )
    for path in targets:
        if not path.is_file():
            failures.append(f"{path.relative_to(root)}: missing")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        failures.extend(
            kernel_slot_bind_failures(text, source_name=str(path.relative_to(root)))
        )
    return failures


def s7_verdict(root: Path = ROOT) -> Verdict:
    failures = analyze_repo_kernel_binds(root)
    if failures:
        return Verdict(
            id="S7",
            status="FAIL",
            detail="Kernel-slot bind still reads genome LOCKED-PROVEN into "
            "cnt-locked / setTiers.locked.",
            evidence=" | ".join(failures),
            owner="INTI",
        )
    return Verdict(
        id="S7",
        status="PASS",
        detail=(
            f"cnt-locked and setTiers.locked source {HONEST_PATH} "
            f"{HONEST_FIELD}={LOCKED_KERNEL_COUNT}. Genome catalog remains "
            "a separately labelled count."
        ),
        owner="INTI",
    )


# ---------------------------------------------------------------------------
# Genome labelling — both numbers are real; do not demand 25 be deleted
# ---------------------------------------------------------------------------

def genome_catalog_counts(path: Path) -> dict[str, int]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError(f"{path}: genome.json is not a list")
    locked_tags = 0
    for entry in entries:
        if isinstance(entry, dict) and entry.get("tag") == "LOCKED-PROVEN":
            locked_tags += 1
    return {"entry_count": len(entries), "locked_proven_tags": locked_tags}


def evaluate_genome_vs_kernel(counts: dict[str, int], kernel: int = LOCKED_KERNEL_COUNT) -> Verdict:
    """Labelling rule: Lean-8 ≠ genome catalog. Difference is allowed, not a deletion."""
    entries = counts.get("entry_count", 0)
    tags = counts.get("locked_proven_tags", 0)
    detail = (
        f"kernel locked-proven={kernel} (Lean / {HONEST_FIELD}); "
        f"genome entries={entries}; genome tag LOCKED-PROVEN={tags}. "
        "Both numbers are real. Do not demand the genome tag count equal the kernel."
    )
    return Verdict(
        id="D5",
        status="PASS",
        detail=detail,
        evidence="labelling rule Lean-8 ≠ genome-144; not a deletion",
    )


# ---------------------------------------------------------------------------
# README YAML (S12) — stdlib only
# ---------------------------------------------------------------------------

def parse_simple_yaml_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        raise ValueError("README must start with YAML frontmatter ---")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("README must start with ---")
    body: list[str] = []
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        body.append(line)
    if not closed:
        raise ValueError("no closing --- in README frontmatter")
    parsed: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None
    for line in body:
        if current_list is not None and (line.startswith("  - ") or line.startswith("\t- ")):
            current_list.append(line.split("-", 1)[1].strip().strip("'\""))
            continue
        if current_list is not None:
            parsed[current_key] = current_list  # type: ignore[index]
            current_list = None
            current_key = None
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()
        if raw == "":
            current_key = key
            current_list = []
            continue
        parsed[key] = raw.strip("\"'")
    if current_list is not None and current_key is not None:
        parsed[current_key] = current_list
    return parsed


def s12_verdict(root: Path = ROOT) -> Verdict:
    readme = root / "README.md"
    try:
        parsed = parse_simple_yaml_frontmatter(readme.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Verdict(id="S12", status="FAIL", detail=str(exc), evidence=str(readme))
    required = ("title", "sdk", "emoji", "colorFrom", "colorTo")
    missing = [key for key in required if key not in parsed]
    if missing:
        return Verdict(
            id="S12",
            status="FAIL",
            detail=f"README frontmatter missing {missing}",
            evidence="README.md",
        )
    return Verdict(
        id="S12",
        status="PASS",
        detail="README YAML frontmatter parses with required HF card fields",
        evidence="README.md",
    )


# ---------------------------------------------------------------------------
# Static D-row helpers
# ---------------------------------------------------------------------------

def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8", errors="replace")


def static_debug_verdicts(root: Path = ROOT) -> list[Verdict]:
    landing = _read(root, "a11oy_landing.html")
    doctrine = _read(root, "docs/doctrine/DOCTRINE_V11_LOCKED.md")
    doctrine_head = "\n".join(doctrine.splitlines()[:20])
    hardening = _read(root, "szl_prod_hardening.py")
    console = _read(root, "pages/console.html")
    catalog = _read(root, "audit/screenshot-catalog.md")
    csp_test = root / "tests" / "test_security_headers.py"
    aliases = _read(root, "szl_warhacker_aliases.py")

    out: list[Verdict] = []

    out.append(
        Verdict(
            id="D1",
            status="PASS" if 'type="application/ld+json"' in landing else "FAIL",
            detail="Landing JSON-LD SoftwareApplication identity",
            evidence="a11oy_landing.html application/ld+json",
        )
    )
    views_ok = "const VIEWS=" in console or "const VIEWS =" in console
    out.append(
        Verdict(
            id="D2",
            status="PASS" if views_ok else "FAIL",
            detail="Console VIEWS registry present (unrouted views must stay ROADMAP)",
            evidence="pages/console.html VIEWS",
        )
    )
    hero_labelled = 'id="hs-proven">8</div>' in landing and "Locked Lean-proven" in landing
    out.append(
        Verdict(
            id="D3",
            status="PASS" if hero_labelled else "FAIL",
            detail="Hero locked count 8 is labelled as Lean-proven theorems",
            evidence="a11oy_landing.html #hs-proven",
        )
    )
    lambda_ok = "Conjecture 1" in landing
    out.append(
        Verdict(
            id="D4",
            status="PASS" if lambda_ok else "FAIL",
            detail="Λ uniqueness labelled Conjecture 1, not a theorem",
            evidence="a11oy_landing.html",
        )
    )
    genome_path = root / "data" / "genome.json"
    if genome_path.is_file():
        out.append(evaluate_genome_vs_kernel(genome_catalog_counts(genome_path)))
    else:
        out.append(
            Verdict(
                id="D5",
                status="FAIL",
                detail="data/genome.json missing",
                evidence="data/genome.json",
            )
        )
    out.append(
        Verdict(
            id="D6",
            status="PASS" if re.search(r"deprecat", doctrine_head, re.I) else "FAIL",
            detail="Deprecation disclosure in first 20 lines of Doctrine v11 lock",
            evidence="docs/doctrine/DOCTRINE_V11_LOCKED.md",
        )
    )
    ids_ok = all(fid in landing for fid in LOCKED_KERNEL_IDS)
    out.append(
        Verdict(
            id="D7",
            status="PASS" if ids_ok else "FAIL",
            detail="Locked-8 ids appear on the landing surface",
            evidence="a11oy_landing.html locked formula ids",
        )
    )
    out.append(
        Verdict(
            id="D8",
            status="PASS" if "request_id" in hardening else "FAIL",
            detail="5xx envelope carries request_id",
            evidence="szl_prod_hardening.py",
        )
    )
    out.append(
        Verdict(
            id="D9",
            status="PASS" if csp_test.is_file() else "FAIL",
            detail="CSP / security-header regression test exists (not re-run here)",
            evidence="tests/test_security_headers.py",
        )
    )
    snap = "SNAPSHOT" in catalog or "2026-07-25" in catalog
    out.append(
        Verdict(
            id="D10",
            status="SNAPSHOT" if snap else "FAIL",
            detail="Screenshot catalog is a dated SNAPSHOT, not a live capture",
            evidence="audit/screenshot-catalog.md",
            snapshot_date="2026-07-25" if "2026-07-25" in catalog else SNAPSHOT_DATE,
        )
    )
    wire_src = aliases
    unconfigured = (
        "L2" in wire_src
        and ("roadmap" in wire_src.lower() or "not yet claimed" in wire_src.lower())
    )
    out.append(
        Verdict(
            id="wire-D",
            status="UNCONFIGURED" if unconfigured else "FAIL",
            detail="Wire D SLSA L2 attestation remains roadmap / not claimed",
            evidence="szl_warhacker_aliases.py GET /wires/D",
        )
    )
    return out


def static_s_verdicts(root: Path = ROOT) -> list[Verdict]:
    """Contract-mode S rows that do not need the network."""
    out: list[Verdict] = []
    out.append(s7_verdict(root))
    out.append(s12_verdict(root))

    ledger = _read(root, "szl_energy_ledger.py")
    serve = _read(root, "serve.py")
    s5_ok = (
        "def handle_ledger" in ledger
        and "return get_ledger().summary()" in ledger
        and 'methods=["GET"]' in ledger
        and 'receipt_minted": False' in serve
    )
    out.append(
        Verdict(
            id="S5",
            status="PASS" if s5_ok else "FAIL",
            detail="Ledger GET handlers read/summarize; they do not append/mint",
            evidence="szl_energy_ledger.handle_ledger + serve.py /v1/ledger receipt_minted",
        )
    )

    runtime = _read(root, "szl_runtime_contracts.py")
    s8_ok = "_install_soft_404_guard" in runtime and "undeclared path refused SPA fallback" in runtime
    out.append(
        Verdict(
            id="S8",
            status="PASS" if s8_ok else "FAIL",
            detail="Designed 404: undeclared file-like paths refuse SPA HTML 200",
            evidence="szl_runtime_contracts._install_soft_404_guard",
        )
    )

    console = _read(root, "pages/console.html")
    khipu_ok = 'id="try-khipu-panel"' in console and "Try Khipu" in console
    # Console Try Khipu is source-backed after #1390; live HTML is re-probed in live mode.
    out.append(
        Verdict(
            id="S-console-khipu",
            status="PASS" if khipu_ok else "FAIL",
            detail="pages/console.html ships Try Khipu panel source",
            evidence="pages/console.html #try-khipu-panel",
        )
    )
    return out


def snapshot_l_verdicts() -> list[Verdict]:
    labels = {
        "L1": "concurrent GET storm",
        "L2": "receipt-write load",
        "L3": "refuse/abstain under load",
        "L4": "authz empty-state under load",
        "L5": "HEAD/GET mix under load",
        "L6": "dual-origin load",
    }
    return [
        Verdict(
            id=lid,
            status="SNAPSHOT",
            detail=f"{desc} not executed this PR; never claimed production-scale with no N",
            evidence=f"SNAPSHOT {SNAPSHOT_DATE}",
            snapshot_date=SNAPSHOT_DATE,
        )
        for lid, desc in labels.items()
    ]


def unavailable_placeholders() -> list[Verdict]:
    return [
        Verdict(
            id="S4",
            status="UNAVAILABLE",
            detail="Staging receipt-write URL is not published; no POST issued",
            evidence="no staging URL in this smoke PR",
        ),
        Verdict(
            id="S6",
            status="UNAVAILABLE",
            detail="Live refuse/abstain path is not published; no POST issued",
            evidence="szl_willay_gateway has no live public probe URL",
        ),
        Verdict(
            id="S9",
            status="UNAVAILABLE",
            detail="Authz empty-state gated routes are not a public 200 surface",
            evidence="gated routes 404 / unpublished",
        ),
    ]


def contract_matrix(root: Path = ROOT) -> Matrix:
    matrix = Matrix()
    for item in static_s_verdicts(root):
        matrix.add(item)
    for item in static_debug_verdicts(root):
        matrix.add(item)
    for item in snapshot_l_verdicts():
        matrix.add(item)
    for item in unavailable_placeholders():
        matrix.add(item)
    return matrix


# ---------------------------------------------------------------------------
# HTTP (GET/HEAD only)
# ---------------------------------------------------------------------------

@dataclass
class HttpResult:
    method: str
    url: str
    status: int | None
    content_type: str
    body: bytes
    error: str = ""

    def text(self, limit: int = 4000) -> str:
        return self.body[:limit].decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002
        return None


def http_request(
    url: str,
    method: str = "GET",
    timeout: float = 20.0,
    follow: bool = True,
) -> HttpResult:
    if method.upper() not in {"GET", "HEAD"}:
        raise ValueError(f"investor smoke gate forbids {method}")
    req = urllib.request.Request(
        url,
        method=method.upper(),
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )
    opener = urllib.request.build_opener(
        urllib.request.HTTPRedirectHandler() if follow else _NoRedirect()
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = b"" if method.upper() == "HEAD" else resp.read(512_000)
            return HttpResult(
                method=method.upper(),
                url=url,
                status=getattr(resp, "status", None) or resp.getcode(),
                content_type=resp.headers.get("Content-Type", ""),
                body=body,
            )
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read(512_000) if method.upper() != "HEAD" else b""
        except Exception:
            body = b""
        return HttpResult(
            method=method.upper(),
            url=url,
            status=exc.code,
            content_type=exc.headers.get("Content-Type", "") if exc.headers else "",
            body=body,
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001 — probe must never crash the matrix
        return HttpResult(
            method=method.upper(),
            url=url,
            status=None,
            content_type="",
            body=b"",
            error=f"{type(exc).__name__}: {exc}",
        )


def _join(origin: str, path: str) -> str:
    return origin.rstrip("/") + path


def extract_signer_status(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("signer",):
        node = payload.get(key)
        if isinstance(node, dict) and isinstance(node.get("status"), str):
            return node["status"]
    rollup = payload.get("rollup")
    if isinstance(rollup, dict):
        signer = rollup.get("signer")
        if isinstance(signer, dict) and isinstance(signer.get("status"), str):
            return signer["status"]
    return None


def locked_formula_count_from_honest(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get(HONEST_FIELD)
    if isinstance(raw, int):
        return raw
    lock = payload.get("doctrine_lock")
    if isinstance(lock, dict) and isinstance(lock.get(HONEST_FIELD), int):
        return lock[HONEST_FIELD]
    return None


def unlabeled_numeric_coords(payload: Any, path: str = "$") -> list[str]:
    found: list[str] = []

    def parent_labelled(obj: dict[str, Any], key: str) -> bool:
        labels = obj.get("labels") or obj.get("honesty") or obj.get("value_labels")
        if isinstance(labels, dict) and str(labels.get(key, "")).upper() in VALUE_LABELS:
            return True
        for field_name in ("label", "honesty", "value_label", "status"):
            raw = obj.get(field_name)
            if isinstance(raw, str) and raw.upper() in VALUE_LABELS:
                return True
        wrapped = obj.get(key)
        if isinstance(wrapped, dict):
            lab = wrapped.get("label") or wrapped.get("honesty") or wrapped.get("status")
            if isinstance(lab, str) and lab.upper() in VALUE_LABELS:
                return True
        return False

    def walk(node: Any, here: str, parent: dict[str, Any] | None) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                child = f"{here}.{key}"
                if key in COORD_KEYS and isinstance(value, (int, float)):
                    if parent_labelled(node, key):
                        continue
                    found.append(f"{child}={value} unlabeled (need MEASURED or UNAVAILABLE)")
                else:
                    walk(value, child, node)
        elif isinstance(node, list):
            for idx, item in enumerate(node[:50]):
                walk(item, f"{here}[{idx}]", parent)

    walk(payload, path, None)
    return found


def live_matrix(origins: list[str], root: Path = ROOT) -> Matrix:
    matrix = Matrix()
    primary = origins[0] if origins else CANONICAL_ORIGIN

    # S1 GET /
    s1_bits: list[str] = []
    s1_fail = False
    for origin in origins:
        result = http_request(_join(origin, "/"), method="GET", follow=True)
        ok = result.status == 200
        s1_bits.append(f"GET {origin}/ -> {result.status} {result.error}".strip())
        if not ok:
            s1_fail = True
    matrix.add(
        Verdict(
            id="S1",
            status="FAIL" if s1_fail else "PASS",
            detail="GET / must be 200 on both origins (follow redirects)",
            evidence="; ".join(s1_bits),
        )
    )

    # S2 HEAD vs GET + signer enum (KALLPA)
    s2_fail: list[str] = []
    for path in HEAD_GET_PATHS:
        got = http_request(_join(primary, path), method="GET", follow=True)
        head = http_request(_join(primary, path), method="HEAD", follow=False)
        if got.status == 200 and head.status == 405:
            s2_fail.append(f"HEAD {path} = 405 while GET = 200")
        elif got.status != 200:
            s2_fail.append(f"GET {path} = {got.status} {got.error}".strip())
        elif head.status not in {200, 204}:
            # Any HEAD that is not success while GET is 200 is the KALLPA defect class.
            s2_fail.append(f"HEAD {path} = {head.status} while GET = 200")
    hz_get = http_request(_join(primary, HEAD_404_VS_GET_200), method="GET", follow=True)
    hz_head = http_request(_join(primary, HEAD_404_VS_GET_200), method="HEAD", follow=False)
    if hz_get.status == 200 and hz_head.status == 404:
        s2_fail.append(f"HEAD {HEAD_404_VS_GET_200} = 404 while GET = 200")
    elif hz_get.status == 200 and hz_head.status == 405:
        s2_fail.append(f"HEAD {HEAD_404_VS_GET_200} = 405 while GET = 200")
    for path in SIGNER_REQUIRED_PATHS:
        got = http_request(_join(primary, path), method="GET", follow=True)
        if got.status != 200 or "json" not in got.content_type.lower():
            s2_fail.append(f"GET {path} signer probe HTTP {got.status} ct={got.content_type}")
            continue
        try:
            payload = got.json()
        except Exception as exc:  # noqa: BLE001
            s2_fail.append(f"GET {path} not JSON: {exc}")
            continue
        signer = extract_signer_status(payload)
        if signer not in SIGNER_ENUM:
            s2_fail.append(
                f"GET {path} missing signer enum {sorted(SIGNER_ENUM)}; "
                f"got {signer!r}. Lean commit/SHA is not enough. KALLPA owns the fix."
            )
    matrix.add(
        Verdict(
            id="S2",
            status="FAIL" if s2_fail else "PASS",
            detail="HEAD must not 405/404 where GET is 200; health JSON must carry signer enum",
            evidence="; ".join(s2_fail) if s2_fail else f"HEAD/GET pairs + signer enum on {primary}",
            owner="KALLPA",
        )
    )

    # S3 ISS coords labelled MEASURED or UNAVAILABLE
    iss = http_request(_join(primary, LIVE_ISS_PATH), method="GET", follow=True)
    status_ep = http_request(
        _join(primary, LIVE_FETCH_STATUS_PATH), method="GET", follow=True
    )
    s3_fail: list[str] = []
    if status_ep.status == 404:
        # Dedicated live-fetch/status is absent; ISS is the live-fetch surface.
        pass
    if iss.status != 200:
        s3_fail.append(f"GET {LIVE_ISS_PATH} HTTP {iss.status} {iss.error}".strip())
    else:
        try:
            payload = iss.json()
        except Exception as exc:  # noqa: BLE001
            s3_fail.append(f"{LIVE_ISS_PATH} not JSON: {exc}")
            payload = None
        if isinstance(payload, dict):
            unlabeled = unlabeled_numeric_coords(payload)
            if unlabeled:
                s3_fail.append(
                    "unlabeled live coords: " + "; ".join(unlabeled[:8])
                )
    matrix.add(
        Verdict(
            id="S3",
            status="FAIL" if s3_fail else "PASS",
            detail="Live-fetch numbers must be labelled MEASURED or UNAVAILABLE, never bare digits",
            evidence="; ".join(s3_fail) if s3_fail else f"GET {LIVE_ISS_PATH} labelled",
        )
    )

    for item in unavailable_placeholders():
        matrix.add(item)

    # S5 live: GET must not mint
    s5_fail: list[str] = []
    s5_ev: list[str] = []
    for path in LEDGER_GET_PATHS:
        got = http_request(_join(primary, path), method="GET", follow=True)
        s5_ev.append(f"GET {path} -> {got.status}")
        if got.status != 200:
            s5_fail.append(f"{path} HTTP {got.status}")
            continue
        if "json" not in got.content_type.lower():
            s5_fail.append(f"{path} not JSON ({got.content_type})")
            continue
        try:
            payload = got.json()
        except Exception as exc:  # noqa: BLE001
            s5_fail.append(f"{path} JSON parse {exc}")
            continue
        if isinstance(payload, dict) and payload.get("receipt_minted") is True:
            s5_fail.append(f"{path} receipt_minted=true on GET")
    matrix.add(
        Verdict(
            id="S5",
            status="FAIL" if s5_fail else "PASS",
            detail="Ledger GET does not mint receipts",
            evidence="; ".join(s5_fail or s5_ev),
        )
    )

    # S7 static bind (also reported in live matrix)
    matrix.add(s7_verdict(root))

    # S8 live designed 404
    soft = http_request(_join(primary, SOFT_404_PATH), method="GET", follow=True)
    s8_ok = soft.status == 404 and "json" in soft.content_type.lower()
    if s8_ok:
        try:
            body = soft.json()
            s8_ok = isinstance(body, dict) and body.get("status") in {"NOT_FOUND", "not_found"}
        except Exception:
            s8_ok = False
    matrix.add(
        Verdict(
            id="S8",
            status="PASS" if s8_ok else "FAIL",
            detail="Undeclared file-like path must be JSON 404, not SPA HTML 200",
            evidence=f"GET {SOFT_404_PATH} -> {soft.status} {soft.content_type}",
        )
    )

    # S10 OG
    s10_ok = False
    s10_ev: list[str] = []
    for path in OG_CANDIDATES:
        got = http_request(_join(primary, path), method="GET", follow=True)
        s10_ev.append(f"GET {path} -> {got.status} {got.content_type}")
        if got.status == 200 and ("image" in got.content_type.lower() or got.body[:8] == b"\x89PNG\r\n\x1a\n"):
            s10_ok = True
    matrix.add(
        Verdict(
            id="S10",
            status="PASS" if s10_ok else "FAIL",
            detail="At least one OG/social image returns HTTP 200",
            evidence="; ".join(s10_ev),
        )
    )

    # S11 HF Space
    hf = http_request(HF_SPACE + "/", method="GET", follow=True)
    matrix.add(
        Verdict(
            id="S11",
            status="PASS" if hf.status == 200 else "FAIL",
            detail="Canonical HF Space GET / is 200",
            evidence=f"GET {HF_SPACE}/ -> {hf.status} {hf.error}".strip(),
        )
    )

    matrix.add(s12_verdict(root))

    # Honest kernel count on the live SoT (does not rewrite genome)
    honest = http_request(_join(primary, HONEST_PATH), method="GET", follow=True)
    honest_n = None
    honest_ev = f"GET {HONEST_PATH} -> {honest.status}"
    if honest.status == 200:
        try:
            honest_n = locked_formula_count_from_honest(honest.json())
            honest_ev += f" {HONEST_FIELD}={honest_n}"
        except Exception as exc:  # noqa: BLE001
            honest_ev += f" parse error {exc}"
    if honest_n != LOCKED_KERNEL_COUNT:
        # Do not fold this into S7 (S7 is the UI bind). Record as S7-sot evidence.
        matrix.add(
            Verdict(
                id="S7-sot",
                status="FAIL",
                detail=f"Live {HONEST_PATH} must expose {HONEST_FIELD}={LOCKED_KERNEL_COUNT}",
                evidence=honest_ev,
                owner="INTI",
            )
        )
    else:
        matrix.add(
            Verdict(
                id="S7-sot",
                status="PASS",
                detail=f"Live {HONEST_PATH} {HONEST_FIELD}={LOCKED_KERNEL_COUNT}",
                evidence=honest_ev,
                owner="INTI",
            )
        )

    # Try Khipu on live /console HTML if present
    console_live = http_request(_join(primary, "/console"), method="GET", follow=True)
    html = console_live.text(80_000)
    khipu_live = "try-khipu-panel" in html or "Try Khipu" in html
    matrix.add(
        Verdict(
            id="S-console-khipu-live",
            status="PASS" if (console_live.status == 200 and khipu_live) else "FAIL",
            detail="Live /console HTML includes Try Khipu (do not invent the string in this PR)",
            evidence=f"GET /console -> {console_live.status}; try-khipu={'yes' if khipu_live else 'no'}",
        )
    )

    for item in static_debug_verdicts(root):
        matrix.add(item)
    for item in snapshot_l_verdicts():
        matrix.add(item)
    return matrix


def print_matrix(matrix: Matrix) -> None:
    print(f"{'ID':<22} {'STATUS':<14} DETAIL")
    print("-" * 88)
    for item in matrix.verdicts:
        snap = f" ({item.snapshot_date})" if item.snapshot_date else ""
        owner = f" [{item.owner}]" if item.owner else ""
        print(f"{item.id:<22} {item.status:<14} {item.detail}{snap}{owner}")
        if item.evidence:
            print(f"{'':22} {'':14} evidence: {item.evidence}")


def matrix_errors(
    matrix: Matrix, required: Iterable[str] = REQUIRED_MATRIX_IDS
) -> list[str]:
    errors = validate_matrix(matrix, required=required)
    errors.extend(f"FAIL {vid}" for vid in matrix.fail_ids())
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("contract", "live", "all"),
        default="contract",
        help="contract=no network (bind+labelling+S12). live=HTTP GET/HEAD only.",
    )
    parser.add_argument(
        "--origin",
        action="append",
        dest="origins",
        help="Origin to probe (repeatable). Default: a-11-oy.com and a11oy.net",
    )
    parser.add_argument("--json-out", default="", help="Write matrix JSON to this path")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    root = Path(args.root)

    origins = args.origins or [CANONICAL_ORIGIN, SUNSET_ORIGIN]
    if args.mode == "live":
        matrix = live_matrix(origins, root=root)
    elif args.mode == "all":
        # Live matrix already includes static S7/D/L rows.
        matrix = live_matrix(origins, root=root)
    else:
        matrix = contract_matrix(root=root)

    print_matrix(matrix)
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(matrix.as_dict(), indent=2) + "\n", encoding="utf-8"
        )

    required = CONTRACT_REQUIRED_IDS if args.mode == "contract" else REQUIRED_MATRIX_IDS
    errors = matrix_errors(matrix, required=required)
    if errors:
        print("\nFAIL-CLOSED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
