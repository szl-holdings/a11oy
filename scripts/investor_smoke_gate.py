#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED. Λ = Conjecture 1 (NOT a theorem). Locked-proven kernel = 8.
"""Investor-honest S1–S12 / L1–L6 / D1–D10 smoke gate.

Fail-closed. Never skip-as-green. Never invent PASS. Never invent LIVE.
No POST. No genome rewrite. No Trust Center copy rewrite. Does not add
HEAD handlers or signer fields (1394 identity lock is already on main).

S1/S2 product is 1394 on main; this gate only probes the live origin.
S3: UNAVAILABLE, MEASURED with method, or unit-labelled — never invent MEASURED.
S7 is a BIND: landing #pt-locked via loadLockedKernel/loadKernelLocked and
trust/console #cnt-locked bind to GET /api/a11oy/v1/honest locked_formula_count
(show 8 or N/A). Genome LOCKED-PROVEN=25 is catalog. PR 1396 landed the
console chip on main; this gate does not re-edit that chrome. Do not touch 1363.
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
SIGNER_ABSENT_ENUM = frozenset({"ABSENT", "UNAVAILABLE", "unavailable"})
VALUE_LABELS = frozenset({"MEASURED", "UNAVAILABLE"})
COORD_KEYS = frozenset(
    {"latitude", "longitude", "lat", "lon", "altitude", "velocity"}
)
SNAPSHOT_DATE = "2026-08-28"
CANONICAL_ORIGIN = "https://a-11-oy.com"
HF_SPACE = "https://szlholdings-a11oy.hf.space"
USER_AGENT = "a11oy-investor-smoke-gate/1.0 (+https://github.com/szl-holdings/a11oy)"

ALLOWED_STATUSES = frozenset(
    {"PASS", "FAIL", "UNAVAILABLE", "SNAPSHOT", "UNCONFIGURED"}
)
ALLOWED_UNAVAILABLE_IDS = frozenset({"S4", "S6", "S9"})
ALLOWED_UNCONFIGURED_IDS = frozenset({"wire-D"})
SNAPSHOT_IDS = frozenset({"L1", "L2", "L3", "L4", "L5", "L6"})

HEAD_GET_PATHS = (
    "/",
    "/verify",
    "/console",
    "/trust",
    "/assurance",
    "/robots.txt",
    "/sitemap.xml",
    "/healthz",
    "/readyz",
    "/api/health",
    "/api/a11oy/healthz",
    "/api/a11oy/v1/health",
)
SIGNER_LIVE_PATH = "/api/a11oy/healthz"
SIGNER_ABSENT_PATHS = (
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

# Kernel-chip bind: FAIL when surfaces paint genome LOCKED-PROVEN / proof_tiers.locked
# into the kernel slot. Catalog LOCKED-PROVEN elsewhere is allowed (labelled, never
# the kernel). PR 1396 landed console #cnt-locked; this detector only asserts the bind.
_CNT_LOCKED_ID = re.compile(r"""id\s*=\s*['"]cnt-locked['"]""", re.I)
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
_PT_LOCKED_FROM_GENOME = re.compile(
    r"""['"]pt-locked['"][\s\S]{0,200}?(?:tier_counts|tc)\s*\[\s*['"]LOCKED-PROVEN['"]"""
    r"""|"""
    r"""(?:tier_counts|tc)\s*\[\s*['"]LOCKED-PROVEN['"][\s\S]{0,200}?['"]pt-locked['"]""",
    re.I,
)
_HONEST_PATH_RE = re.compile(r"/api/a11oy/v1/honest|/v1/honest", re.I)
_LOCKED_FORMULA_COUNT_RE = re.compile(r"locked_formula_count")
_LOAD_LOCKED_KERNEL_RE = re.compile(
    r"(?:async\s+)?function\s+load(?:LockedKernel|KernelLocked)\s*\(", re.I
)
_KERNEL_LOCK_FUNCS = ("loadLockedKernel", "loadKernelLocked")

KERNEL_SURFACES = (
    ("a11oy_landing.html", "landing"),
    ("web/trust.html", "trust"),
    ("pages/console.html", "console"),
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
# S7 — kernel chips must bind to /honest locked_formula_count (8 or N/A)
# Genome LOCKED-PROVEN is a catalog tier (25 today). Do not demand it equal 8.
# ---------------------------------------------------------------------------

def _strip_js_comments(text: str) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return re.sub(r"//[^\n]*", "", text)


def _js_function_body(text: str, name: str) -> str | None:
    match = re.search(
        rf"(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{",
        text,
    )
    if not match:
        return None
    start = match.end() - 1
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return text[start:]


def _cnt_locked_bound_to_honest(text: str) -> bool:
    """True when #cnt-locked is sourced from /honest locked_formula_count."""
    if not _CNT_LOCKED_ID.search(text):
        return False
    if not _HONEST_PATH_RE.search(text) or not _LOCKED_FORMULA_COUNT_RE.search(text):
        return False
    window = re.compile(
        r"(?:/api/a11oy/v1/honest|/v1/honest)[\s\S]{0,1200}?locked_formula_count"
        r"[\s\S]{0,1200}?cnt-locked"
        r"|"
        r"cnt-locked[\s\S]{0,1200}?(?:/api/a11oy/v1/honest|/v1/honest)"
        r"[\s\S]{0,1200}?locked_formula_count"
        r"|"
        r"locked_formula_count[\s\S]{0,1200}?cnt-locked",
        re.I,
    )
    return bool(window.search(text))


def _load_locked_kernel_binds_pt_locked(text: str) -> bool:
    """Landing kernel chip: loadLockedKernel or 1394 loadKernelLocked → /honest."""
    for name in _KERNEL_LOCK_FUNCS:
        body = _js_function_body(text, name)
        if not body:
            continue
        has_honest = bool(_HONEST_PATH_RE.search(body))
        has_field = "locked_formula_count" in body
        has_chip = "pt-locked" in body
        has_na = "N/A" in body
        if has_honest and has_field and has_chip and has_na:
            return True
    return False


def kernel_slot_bind_failures(
    text: str, *, source_name: str, role: str = ""
) -> list[str]:
    """Fail-closed kernel-chip bind. Catalog LOCKED-PROVEN elsewhere is allowed."""
    return _kernel_slot_bind_failures_impl(text, source_name=source_name, role=role)


def _kernel_slot_bind_failures_impl(
    text: str, *, source_name: str, role: str
) -> list[str]:
    failures: list[str] = []
    check_landing = role == "landing"
    check_cnt = role in {"trust", "console"}
    if not role:
        check_landing = bool(_LOAD_LOCKED_KERNEL_RE.search(text) or "pt-locked" in text)
        check_cnt = bool(_CNT_LOCKED_ID.search(text))

    if check_landing:
        if not _load_locked_kernel_binds_pt_locked(text):
            failures.append(
                f"{source_name}: #pt-locked must be painted by loadLockedKernel "
                f"or loadKernelLocked from GET {HONEST_PATH} {HONEST_FIELD} "
                "(show 8 or N/A), not genome / proof_tiers.locked."
            )
        set_tiers_body = _js_function_body(text, "setTiers")
        if set_tiers_body and "pt-locked" in _strip_js_comments(set_tiers_body):
            failures.append(
                f"{source_name}: setTiers still writes #pt-locked; kernel chip must "
                "be loadLockedKernel/loadKernelLocked only (not setTiers.locked)."
            )
        if _SETTIERS_LOCKED_GENOME.search(text):
            failures.append(
                f"{source_name}: setTiers.locked still reads genome "
                "tier_counts['LOCKED-PROVEN'] (catalog, not the kernel)."
            )
        if _SETTIERS_PROOF_TIERS.search(text):
            failures.append(
                f"{source_name}: setTiers(*.proof_tiers) still paints proof_tiers.locked "
                "into the kernel slot."
            )
        if _PT_LOCKED_FROM_GENOME.search(text):
            failures.append(
                f"{source_name}: #pt-locked still reads genome LOCKED-PROVEN."
            )

    if check_cnt:
        if not _CNT_LOCKED_ID.search(text):
            failures.append(
                f"{source_name}: missing #cnt-locked kernel chip (must bind to "
                f"{HONEST_PATH} {HONEST_FIELD}, show 8 or N/A)."
            )
        else:
            if _CNT_LOCKED_FROM_GENOME.search(text) or _CNT_LOCKED_NODEVALUE_GENOME.search(
                text
            ):
                failures.append(
                    f"{source_name}: #cnt-locked still reads genome "
                    "tier_counts['LOCKED-PROVEN'] (catalog, never the kernel)."
                )
            if not _cnt_locked_bound_to_honest(text):
                failures.append(
                    f"{source_name}: #cnt-locked is not bound to GET {HONEST_PATH} "
                    f"{HONEST_FIELD} (show 8 or N/A)."
                )
    return failures


def analyze_repo_kernel_binds(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    for rel, role in KERNEL_SURFACES:
        path = root / rel
        if not path.is_file():
            failures.append(f"{rel}: missing")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        failures.extend(
            kernel_slot_bind_failures(text, source_name=rel, role=role)
        )
    return failures


def s7_kernel_chip_bind(
    *,
    failures: Iterable[str],
    extra_evidence: Iterable[str] = (),
    catalog_locked_proven: int | None = None,
    honest_count: int | None = None,
) -> Verdict:
    """PASS iff every kernel chip binds to /honest locked_formula_count.

    Genome LOCKED-PROVEN is a catalog tier. Catalog 25 vs kernel 8 is not this FAIL.
    """
    fail_list = [str(item) for item in failures if item]
    extras = [str(item) for item in extra_evidence if item]
    evidence_parts = list(extras)
    if catalog_locked_proven is not None:
        evidence_parts.append(
            f"catalog LOCKED-PROVEN={catalog_locked_proven} (catalog, not kernel)"
        )
    if honest_count is not None:
        evidence_parts.append(f"{HONEST_FIELD}={honest_count}")
    evidence_parts.extend(fail_list)

    honest_wrong = (
        honest_count is not None and honest_count != LOCKED_KERNEL_COUNT
    )
    if fail_list or honest_wrong:
        detail = (
            "S7 bind: landing #pt-locked via loadLockedKernel and trust/console "
            f"#cnt-locked must read GET {HONEST_PATH} {HONEST_FIELD} "
            f"(show {LOCKED_KERNEL_COUNT} or N/A). Genome LOCKED-PROVEN is a "
            "catalog tier and may remain labelled, never green, never the kernel. "
            "Lean-8 ≠ genome-144. Do not rewrite genome.json."
        )
        if honest_wrong:
            detail += (
                f" Live {HONEST_FIELD}={honest_count} "
                f"(expected {LOCKED_KERNEL_COUNT})."
            )
        return Verdict(
            id="S7",
            status="FAIL",
            detail=detail,
            evidence=" | ".join(evidence_parts) or "kernel chips unbound",
            owner="INTI",
        )
    return Verdict(
        id="S7",
        status="PASS",
        detail=(
            f"Kernel chips bind to {HONEST_PATH} {HONEST_FIELD}="
            f"{LOCKED_KERNEL_COUNT} (8 or N/A). Genome LOCKED-PROVEN remains "
            "catalog, labelled, not the kernel."
        ),
        evidence=" | ".join(evidence_parts),
        owner="INTI",
    )


def s7_verdict(root: Path = ROOT, extra_evidence: Iterable[str] = ()) -> Verdict:
    genome_path = root / "data" / "genome.json"
    catalog = None
    if genome_path.is_file():
        catalog = genome_catalog_counts(genome_path)["locked_proven_tags"]
    return s7_kernel_chip_bind(
        failures=analyze_repo_kernel_binds(root),
        extra_evidence=extra_evidence,
        catalog_locked_proven=catalog,
        honest_count=LOCKED_KERNEL_COUNT,
    )


# ---------------------------------------------------------------------------
# D5 — catalog size 144 is not the locked kernel; S7 owns the chip bind
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
    """Catalog *size* is not the locked kernel. S7 owns the chip bind, not this count."""
    entries = counts.get("entry_count", 0)
    tags = counts.get("locked_proven_tags", 0)
    return Verdict(
        id="D5",
        status="PASS",
        detail=(
            f"genome catalog entries={entries} is not the locked kernel "
            f"({kernel} ids). LOCKED-PROVEN tag count={tags} is a catalog tier "
            f"(not kernel {kernel}). S7 is the chip bind; this row only labels "
            "catalog size. Lean-8 ≠ genome-144."
        ),
        evidence="Lean-8 ≠ genome-144 catalog size; S7 is kernel-chip bind not catalog count",
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
            detail="Wire D attestation remains roadmap / not claimed",
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
    attempts: int = 1,
) -> HttpResult:
    if method.upper() not in {"GET", "HEAD"}:
        raise ValueError(f"investor smoke gate forbids {method}")
    last = HttpResult(
        method=method.upper(),
        url=url,
        status=None,
        content_type="",
        body=b"",
        error="no attempt",
    )
    for _ in range(max(1, int(attempts))):
        last = _http_request_once(
            url, method=method, timeout=timeout, follow=follow
        )
        if last.status is not None:
            return last
        err = last.error or ""
        if "TimeoutError" not in err:
            return last
    return last


def _http_request_once(
    url: str,
    *,
    method: str,
    timeout: float,
    follow: bool,
) -> HttpResult:
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


def _coord_label_ok(obj: dict[str, Any], key: str) -> bool:
    """True only for UNAVAILABLE, or MEASURED with a method. Never invent MEASURED."""

    def _ok(label: Any, method: Any) -> bool:
        if not isinstance(label, str):
            return False
        lab = label.upper()
        if lab == "UNAVAILABLE":
            return True
        if lab == "MEASURED":
            return bool(method)
        return False

    wrapped = obj.get(key)
    if isinstance(wrapped, dict):
        lab = wrapped.get("label") or wrapped.get("honesty") or wrapped.get("status")
        method = wrapped.get("method") or wrapped.get("method_label") or obj.get("method")
        if _ok(lab, method):
            return True
    labels = obj.get("labels") or obj.get("honesty") or obj.get("value_labels")
    if isinstance(labels, dict):
        lab = labels.get(key)
        method = None
        if isinstance(lab, dict):
            method = lab.get("method")
            lab = lab.get("label") or lab.get("status")
        else:
            method = (labels.get("method") if isinstance(labels, dict) else None) or obj.get("method")
        if _ok(lab, method):
            return True
    units = obj.get("units")
    if isinstance(units, dict):
        unit = units.get(key)
        if isinstance(unit, str) and unit.strip():
            return True
    for field_name in ("label", "honesty", "value_label", "status"):
        raw = obj.get(field_name)
        if _ok(raw, obj.get("method") or obj.get("method_label")):
            return True
    return False


def unlabeled_numeric_coords(payload: Any, path: str = "$") -> list[str]:
    found: list[str] = []

    def walk(node: Any, here: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                child = f"{here}.{key}"
                if key in COORD_KEYS:
                    if isinstance(value, (int, float)):
                        if not _coord_label_ok(node, key):
                            found.append(
                                f"{child}={value} unlabeled "
                                "(need UNAVAILABLE, MEASURED with method, or units)"
                            )
                        continue
                    if isinstance(value, dict):
                        inner = value.get("value")
                        if isinstance(inner, (int, float)) and not _coord_label_ok(node, key):
                            found.append(
                                f"{child}.value={inner} unlabeled "
                                "(need UNAVAILABLE, MEASURED with method, or units)"
                            )
                        continue
                walk(value, child)
        elif isinstance(node, list):
            for idx, item in enumerate(node[:50]):
                walk(item, f"{here}[{idx}]")

    walk(payload, path)
    return found


def first_viewport_unlabeled_latitude(html: str, *, char_limit: int = 20000) -> list[str]:
    """Fail-closed: no raw unlabeled latitude in the first viewport HTML."""
    chunk = html[:char_limit]
    hits: list[str] = []
    if not re.search(r"\blatitude\b", chunk, re.I):
        return hits
    for match in re.finditer(r"\blatitude\b", chunk, re.I):
        window = chunk[max(0, match.start() - 100) : match.end() + 160]
        has_number = re.search(r"-?\d+\.\d+", window)
        if not has_number:
            continue
        if re.search(r"UNAVAILABLE", window, re.I):
            continue
        if re.search(r"MEASURED", window, re.I) and re.search(r"method", window, re.I):
            continue
        hits.append("unlabeled latitude in first viewport (need UNAVAILABLE or MEASURED with method)")
        break
    return hits


def live_matrix(origins: list[str], root: Path = ROOT) -> Matrix:
    matrix = Matrix()
    primary = origins[0] if origins else CANONICAL_ORIGIN

    # S1 HEAD vs GET — product fix is 1394 on main. This job only probes live origin.
    s1_fail: list[str] = []
    for path in HEAD_GET_PATHS:
        got = http_request(_join(primary, path), method="GET", follow=True)
        head = http_request(_join(primary, path), method="HEAD", follow=False)
        if got.status == 200 and head.status in {404, 405}:
            s1_fail.append(f"HEAD {path} = {head.status} while GET = 200")
        elif got.status != 200:
            s1_fail.append(f"GET {path} = {got.status} {got.error}".strip())
        elif head.status not in {200, 204}:
            s1_fail.append(f"HEAD {path} = {head.status} while GET = {got.status}")
    matrix.add(
        Verdict(
            id="S1",
            status="FAIL" if s1_fail else "PASS",
            detail="HEAD must not 405/404 where GET is 200 (1394 identity lock on main)",
            evidence="; ".join(s1_fail) if s1_fail else f"HEAD/GET pairs on {primary}",
            owner="KALLPA",
        )
    )

    # S2 signer: DSSE-LIVE only on /api/a11oy/healthz rollup.signer (1394).
    # Lean health JSON must be ABSENT/UNAVAILABLE — never copy DSSE-LIVE.
    s2_fail: list[str] = []
    live = http_request(_join(primary, SIGNER_LIVE_PATH), method="GET", follow=True)
    if live.status != 200 or "json" not in live.content_type.lower():
        s2_fail.append(
            f"GET {SIGNER_LIVE_PATH} HTTP {live.status} ct={live.content_type}"
        )
    else:
        try:
            live_payload = live.json()
        except Exception as exc:  # noqa: BLE001
            s2_fail.append(f"GET {SIGNER_LIVE_PATH} not JSON: {exc}")
        else:
            signer = extract_signer_status(live_payload)
            if signer not in SIGNER_ENUM:
                s2_fail.append(
                    f"GET {SIGNER_LIVE_PATH} rollup.signer.status={signer!r} "
                    f"not in {sorted(SIGNER_ENUM)}"
                )
    for path in SIGNER_ABSENT_PATHS:
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
        if signer in {"DSSE-LIVE"}:
            s2_fail.append(
                f"GET {path} must not stamp DSSE-LIVE (1394: only "
                f"{SIGNER_LIVE_PATH} rollup.signer may); got {signer!r}"
            )
        elif signer not in SIGNER_ABSENT_ENUM:
            s2_fail.append(
                f"GET {path} lean signer must be ABSENT/UNAVAILABLE; got {signer!r}"
            )
    matrix.add(
        Verdict(
            id="S2",
            status="FAIL" if s2_fail else "PASS",
            detail=(
                "DSSE-LIVE only on /api/a11oy/healthz rollup.signer; "
                "lean health JSON signer is ABSENT/UNAVAILABLE (1394)"
            ),
            evidence="; ".join(s2_fail) if s2_fail else f"signer contract on {primary}",
            owner="KALLPA",
        )
    )

    # S3 ISS coords + first viewport — UNAVAILABLE or MEASURED with method.
    # One TimeoutError retry only; persistent timeout stays FAIL (not UNAVAILABLE).
    iss = http_request(
        _join(primary, LIVE_ISS_PATH), method="GET", follow=True, attempts=2
    )
    home = http_request(_join(primary, "/"), method="GET", follow=True)
    s3_fail: list[str] = []
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
                s3_fail.append("unlabeled live coords: " + "; ".join(unlabeled[:8]))
    s3_fail.extend(first_viewport_unlabeled_latitude(home.text(24_000)))
    landing = root / "a11oy_landing.html"
    if landing.is_file():
        s3_fail.extend(
            first_viewport_unlabeled_latitude(
                landing.read_text(encoding="utf-8", errors="replace")
            )
        )
    matrix.add(
        Verdict(
            id="S3",
            status="FAIL" if s3_fail else "PASS",
            detail=(
                "Live coords must be UNAVAILABLE, labelled MEASURED with method, "
                "or unit-labelled; no raw unlabeled latitude in first viewport"
            ),
            evidence="; ".join(s3_fail) if s3_fail else f"GET {LIVE_ISS_PATH} + first viewport labelled",
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

    # S7 live: bind kernel chips to /honest 8. Catalog LOCKED-PROVEN may stay.
    genome_live = http_request(_join(primary, "/api/a11oy/v1/genome"), method="GET", follow=True)
    honest_live = http_request(_join(primary, HONEST_PATH), method="GET", follow=True)
    live_tags = None
    live_honest = None
    extras: list[str] = []
    if genome_live.status == 200:
        try:
            gpayload = genome_live.json()
            tc = gpayload.get("tier_counts") if isinstance(gpayload, dict) else None
            if isinstance(tc, dict) and isinstance(tc.get("LOCKED-PROVEN"), int):
                live_tags = tc["LOCKED-PROVEN"]
        except Exception as exc:  # noqa: BLE001
            extras.append(f"genome parse {exc}")
    else:
        extras.append(f"GET /genome HTTP {genome_live.status}")
    if honest_live.status == 200:
        try:
            live_honest = locked_formula_count_from_honest(honest_live.json())
        except Exception as exc:  # noqa: BLE001
            extras.append(f"honest parse {exc}")
    else:
        extras.append(f"GET {HONEST_PATH} HTTP {honest_live.status}")
    repo_counts = genome_catalog_counts(root / "data" / "genome.json")
    tags = live_tags if live_tags is not None else repo_counts["locked_proven_tags"]
    extras.append(f"repo catalog LOCKED-PROVEN tags={repo_counts['locked_proven_tags']}")
    extras.append(f"live catalog LOCKED-PROVEN={tags} (catalog, not kernel)")
    bind_failures = analyze_repo_kernel_binds(root)
    matrix.add(
        s7_kernel_chip_bind(
            failures=bind_failures,
            extra_evidence=extras,
            catalog_locked_proven=tags,
            honest_count=live_honest if live_honest is not None else -1,
        )
    )

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
        help="Origin to probe (repeatable). Default: https://a-11-oy.com (a11oy.net is a later cut)",
    )
    parser.add_argument("--json-out", default="", help="Write matrix JSON to this path")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    root = Path(args.root)

    origins = args.origins or [CANONICAL_ORIGIN]
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
