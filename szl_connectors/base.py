# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by SZL Enterprise-Integration Team. Co-Authored-By: Perplexity Computer Agent.
"""szl_connectors.base — the ONE connector abstraction (not N hacks).

Every enterprise CRM/ERP/platform/data-source binds to a single `Connector`
base class. Each provider is a thin subclass whose ONLY per-provider variation
is the body of `health()` / `read()` / `write()` (the real HTTP) + the auth
wiring. The UI, the MCP layer, and the governance layer treat every connector
identically.

HARD DOCTRINE (non-negotiable — woven throughout):
  • NO fabricated records. A connector returns REAL live provider data
    (CONNECTED), an honest empty READY ("provide credentials to activate" +
    the exact secret name), or a clearly-LABELED SAMPLE (`sample_reason` set,
    used ONLY where no free tier exists). ERROR is honest.
  • NO committed keys. Every credential is read from env/Space-secret ONLY.
    Receipts store credential FINGERPRINT HASHES, never the key value.
  • Every write() is Λ-gated (Λ never 1.0) + DSSE/Khipu-receipted.
  • Trust never 100% (conformal anti-overconfidence floor 1/(n+1)).
  • 0 runtime CDN in served apps; these are live DATA fetches (data, not code).

This generalizes the proven honest-state discipline already shipping in
`szl_a11oy_live_feeds.py` (CISA KEV / NVD / arXiv wired live, labelled
`live: true/false` + `source_status`) into a first-class connector framework.

API references targeted (publicly documented shapes; SZL writes its own
original client code, never copies proprietary SDK code) — see each subclass
module's docstring + the package NOTICE.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error as _ue
import urllib.parse as _up
import urllib.request as _ur
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

# ── auth kinds the framework understands ──────────────────────────────────
AuthKind = Literal["none", "api_key", "oauth2", "basic", "aws_sigv4", "token"]

_UA = "SZL-Connectors/1.0 (sovereign enterprise mesh; contact@szlholdings.ai)"
_TIMEOUT = 8.0


class State(str, Enum):
    """The honest state of a connector RIGHT NOW."""
    CONNECTED = "connected"   # creds present + health() passed → LIVE provider data
    READY = "ready"           # implemented + tested vs API shape; awaiting customer creds
    SAMPLE = "sample"         # labeled fixture ONLY where no free tier exists
    ERROR = "error"           # creds present but provider unreachable/denied (honest)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── typed return objects (propagated unchanged to UI + MCP) ────────────────
@dataclass
class HealthReport:
    connector_id: str
    state: State
    auth_kind: AuthKind
    env_vars: list[str]                 # exact secret names this connector reads
    missing_env: list[str]              # which are absent (drives "provide credentials")
    provider_base: str                  # the real API base it will hit
    checked_at: str = field(default_factory=_now)
    detail: str = ""                    # human-readable honest reason
    latency_ms: float | None = None
    sample_reason: str | None = None    # if SAMPLE: WHY (e.g. "no free tier")
    free_tier: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if isinstance(self.state, State) else self.state
        return d


@dataclass
class Records:
    connector_id: str
    category: str
    state: State                        # CONNECTED | READY | SAMPLE — propagated to UI
    records: list[dict[str, Any]]       # [] when READY (no creds) — NEVER faked
    source: str                         # provider name + endpoint actually hit
    fetched_at: str = field(default_factory=_now)
    live: bool = False                  # True only when CONNECTED + real fetch
    receipt_hash: str | None = None     # set for write(); reads are low-gate
    note: str = ""                      # honest label rendered in the UI source-chip
    schema_preview: list[str] = field(default_factory=list)  # column headers for READY tiles
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if isinstance(self.state, State) else self.state
        d["count"] = len(self.records)
        return d


@dataclass
class WriteResult:
    connector_id: str
    ok: bool
    state: State
    receipt_hash: str | None            # DSSE/Khipu receipt — REQUIRED for any write
    lambda_value: float | None          # Λ score of the action (NEVER 1.0)
    quorum: dict | None = None          # 2-person / 3-of-4 status for state-changing
    detail: str = ""
    dsse: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value if isinstance(self.state, State) else self.state
        return d


# ── HTTP helpers (single egress, brief no-op here; subclasses add caching) ─
def http_json(url: str, headers: dict | None = None, method: str = "GET",
              data: bytes | None = None, timeout: float = _TIMEOUT) -> tuple[int, Any]:
    """Return (status_code, parsed_json_or_text). Never raises into the request path."""
    req = _ur.Request(url, headers={"User-Agent": _UA, **(headers or {})},
                      method=method, data=data)
    try:
        with _ur.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw
    except _ue.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return 0, str(e)


def http_text(url: str, headers: dict | None = None, timeout: float = _TIMEOUT) -> tuple[int, str]:
    req = _ur.Request(url, headers={"User-Agent": _UA, **(headers or {})})
    try:
        with _ur.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except _ue.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)


# Credential fingerprints are derived with PBKDF2-HMAC-SHA256, not a single
# SHA-256 pass. A bare hash of a (possibly low-entropy) credential is cheap to
# brute-force / rainbow-table from the fingerprint alone (CodeQL
# py/weak-sensitive-data-hashing). The fixed domain-separation salt keeps the
# fingerprint DETERMINISTIC — the same credential always maps to the same
# fingerprint, which is the whole point of a correlation fingerprint — while the
# work factor makes recovery expensive. An optional deployment pepper
# (SZL_FINGERPRINT_PEPPER) adds a keyed secret an attacker cannot precompute.
_CRED_FP_SALT = b"szl.killinchu.cred-fingerprint.v1"
_CRED_FP_ITERATIONS = 200_000


def cred_fingerprint(value: str) -> str:
    """Brute-force-resistant fingerprint of a credential — what a receipt may
    carry. NEVER the value. PBKDF2-HMAC-SHA256 over a deterministic salt (+ the
    optional SZL_FINGERPRINT_PEPPER) so a low-entropy credential cannot be
    recovered from its fingerprint, yet the same credential always maps to the
    same fingerprint."""
    salt = _CRED_FP_SALT + os.environ.get("SZL_FINGERPRINT_PEPPER", "").encode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, _CRED_FP_ITERATIONS)
    return "pbkdf2-sha256:" + dk.hex()[:32]


# ── the honesty core — resolve_state() ─────────────────────────────────────
def resolve_state(*, auth_kind: AuthKind, missing_env: list[str],
                  has_fixture: bool, free_tier: bool,
                  probe_ok: bool | None, probe_detail: str = "",
                  ) -> tuple[State, str, str | None]:
    """The single decision function every connector uses to report an honest state.

    Returns (state, detail, sample_reason).

    Rules (verbatim from ENTERPRISE_INTEGRATION_SPEC §1.1):
      missing_env != []                          → READY  (render "provide credentials")
      auth_kind == "none" and provider reachable → CONNECTED (keyless live NOW)
      creds present and health() 200             → CONNECTED
      creds present and health() fails           → ERROR  (honest reason)
      no free tier AND no creds AND fixture set  → SAMPLE (sample_reason mandatory)
    """
    # keyless: reachability decides
    if auth_kind == "none":
        if probe_ok is True:
            return State.CONNECTED, probe_detail or "keyless public API reachable — live data", None
        if probe_ok is False:
            if has_fixture:
                return (State.SAMPLE,
                        probe_detail or "keyless provider unreachable; labelled sample",
                        "provider unreachable at request time")
            return State.ERROR, probe_detail or "keyless provider unreachable", None
        # probe not run (manifest cheap path) → optimistic CONNECTED label, verified on read
        return State.CONNECTED, "keyless public API — verified live on read", None

    # credentialed connectors
    if missing_env:
        # no creds yet
        if has_fixture and not free_tier:
            return (State.SAMPLE, "no free tier; labelled sample until credentials provided",
                    "no free tier — connect to activate")
        secret_list = ", ".join(missing_env)
        return (State.READY, f"provide credentials to activate — set {secret_list}", None)

    # creds present → reachability decides
    if probe_ok is True:
        return State.CONNECTED, probe_detail or "credentials present + provider reachable — live data", None
    if probe_ok is False:
        return State.ERROR, probe_detail or "credentials present but provider unreachable/denied", None
    # creds present, probe deferred
    return State.CONNECTED, "credentials present — verified live on read", None


# ── the base Connector ─────────────────────────────────────────────────────
class Connector:
    """Base. Subclass per provider. Real HTTP only; honest states only.

    Subclass MUST set the class attributes below and override `read()`
    (and `write()` if the connector is writable). `health()` has a sane
    default that calls `_probe()` (override `_probe()` for a cheap reachability
    check).
    """
    id: str = "base"
    category: str = "data_source"   # crm|erp|identity|comms|itsm|warehouse|storage|observability|data_source|mesh|maritime|air|geo|vuln
    auth_kind: AuthKind = "none"
    env_vars: list[str] = []        # secret names; NEVER hardcode the values
    provider_base: str = ""         # real API base URL
    free_tier: bool = False         # True if a free dev sandbox / open demo / keyless exists
    writable: bool = False
    mcp_tool: str = "szl_connector_read"
    sample_records: list[dict[str, Any]] | None = None
    sample_reason_text: str | None = None
    schema_preview: list[str] = []  # column headers the tile shows in READY state
    docs_url: str = ""              # "verify it yourself" link
    label: str = ""                 # human display name

    # ── credential resolution (env-only) ──────────────────────────────────
    def _creds(self) -> dict[str, str]:
        return {k: os.environ[k] for k in self.env_vars if os.environ.get(k)}

    def _missing_env(self) -> list[str]:
        # OAuth2 connectors: only the CLIENT_ID/SECRET (+ refresh) gate activation;
        # we report ALL declared env_vars that are absent.
        return [k for k in self.env_vars if not os.environ.get(k)]

    # ── cheap reachability probe (override per provider) ──────────────────
    def _probe(self) -> tuple[bool | None, str]:
        """Return (probe_ok, detail). None = deferred (manifest cheap path)."""
        return None, ""

    # ── default health() using resolve_state() ────────────────────────────
    def health(self, *, probe: bool = False) -> HealthReport:
        missing = self._missing_env()
        probe_ok: bool | None = None
        detail_probe = ""
        latency = None
        if probe:
            # only probe if keyless OR creds present
            if self.auth_kind == "none" or not missing:
                t0 = time.time()
                probe_ok, detail_probe = self._probe()
                latency = round((time.time() - t0) * 1000, 1)
        state, detail, sample_reason = resolve_state(
            auth_kind=self.auth_kind, missing_env=missing,
            has_fixture=bool(self.sample_records), free_tier=self.free_tier,
            probe_ok=probe_ok, probe_detail=detail_probe,
        )
        return HealthReport(
            connector_id=self.id, state=state, auth_kind=self.auth_kind,
            env_vars=list(self.env_vars), missing_env=missing,
            provider_base=self.provider_base, detail=detail,
            latency_ms=latency, sample_reason=sample_reason or self.sample_reason_text,
            free_tier=self.free_tier,
        )

    # ── read() — subclasses override; default returns honest READY/SAMPLE ─
    def read(self, query: dict | None = None) -> Records:
        h = self.health(probe=True)
        if h.state == State.SAMPLE and self.sample_records:
            return Records(
                connector_id=self.id, category=self.category, state=State.SAMPLE,
                records=list(self.sample_records), source=f"{self.label or self.id} (labelled SAMPLE)",
                live=False, note=h.sample_reason or "labelled sample (no free tier)",
                schema_preview=list(self.schema_preview),
            )
        # READY / ERROR → zero rows, honest note (NEVER fabricated)
        return Records(
            connector_id=self.id, category=self.category, state=h.state,
            records=[], source=self.provider_base, live=False, note=h.detail,
            schema_preview=list(self.schema_preview),
        )

    def write(self, action: dict | None = None) -> WriteResult:
        raise NotImplementedError(f"connector {self.id} is read-only")

    # ── convenience: a READY/SAMPLE Records helper for subclasses ─────────
    def _ready_records(self, detail: str) -> Records:
        return Records(
            connector_id=self.id, category=self.category, state=State.READY,
            records=[], source=self.provider_base, live=False, note=detail,
            schema_preview=list(self.schema_preview),
        )


__all__ = [
    "AuthKind", "State", "HealthReport", "Records", "WriteResult",
    "Connector", "resolve_state", "http_json", "http_text",
    "cred_fingerprint", "_now",
]
