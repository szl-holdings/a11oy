# SPDX-License-Identifier: MIT
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Authored by A11oy Full-Stack Team. Co-Authored-By: Perplexity Computer Agent.
#
# THIRD-PARTY PATTERN ADOPTION (fashion-thinking, NOTICE attribution):
#   BudgetMem — ViktorAxelsen/BudgetMem — Apache-2.0 —
#   https://github.com/ViktorAxelsen/BudgetMem
#   MemSkill — ViktorAxelsen/MemSkill — Apache-2.0 —
#   https://github.com/ViktorAxelsen/MemSkill
#   GraphPlanner — ulab-uiuc/GraphPlanner — MIT —
#   https://github.com/ulab-uiuc/GraphPlanner
#
# We retain those cited budget/meta-memory patterns and extend the same bounded
# runtime seam with original SZL token-ingress controls. No third-party source is
# copied into the implementation.
"""Cost-aware budget routing, Decision Skeletons, and semantic token ingress.

Existing endpoints (preserved):
  GET  /budget-router
  GET  /api/a11oy/v1/budget/tiers
  POST /api/a11oy/v1/budget/route
  GET  /api/a11oy/v1/budget/skeletons

Token-ingress endpoints (bounded computation only):
  GET  /api/a11oy/v1/token-ingress/status
  POST /api/a11oy/v1/token-ingress/route
  POST /api/a11oy/v1/token-ingress/qualify
  POST /api/a11oy/v1/token-ingress/verification-budget

No token-ingress route reads arbitrary repository files, persists a prefix,
contacts a provider, mutates a model, signs data, or performs a deployment.
"""

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

DOCTRINE = {"version": "v11", "counts": "749/14/163", "lambda": "Conjecture 1"}

# ---------------------------------------------------------------------------
# Existing mission budget router
# ---------------------------------------------------------------------------

TIERS: list[dict[str, Any]] = [
    {
        "tier": "TACTICAL",
        "budget": "LOW",
        "deadline_s": 1,
        "max_model_tier": "T1",
        "cot": "none",
        "note": "time-critical: cheapest sufficient model, no chain-of-thought",
    },
    {
        "tier": "OPERATIONAL",
        "budget": "MID",
        "deadline_s": 10,
        "max_model_tier": "T3",
        "cot": "short",
        "note": "balanced: mid-tier reasoning with a short rationale",
    },
    {
        "tier": "STRATEGIC",
        "budget": "HIGH",
        "deadline_s": 60,
        "max_model_tier": "T6",
        "cot": "full",
        "note": "deliberate: high-tier model, full chain-of-thought permitted",
    },
]
_TIER_BY_NAME = {tier["tier"]: tier for tier in TIERS}

_IRREVERSIBLE_RX = re.compile(
    r"\b(launch|fire|strike|delete|destroy|deploy|commit|authoriz|release|publish|"
    r"terminate|engage|weapon|kill)\b",
    re.I,
)
_REVERSIBLE_RX = re.compile(
    r"\b(draft|preview|simulate|estimate|summari|triage|sort|list|query)\b",
    re.I,
)


def _classify_sensitivity(text: str, declared: str | None) -> dict[str, Any]:
    """Reuse the live governance classifier when present; otherwise fail safe."""

    try:
        import szl_governance_gateway as governance_gateway  # type: ignore

        return governance_gateway.classify(text, declared)
    except Exception:
        return {
            "class": (declared or "PUBLIC").upper(),
            "rank": 0,
            "signals": ["fallback"],
        }


def _reversibility(text: str) -> tuple[float, str]:
    if _IRREVERSIBLE_RX.search(text or ""):
        return 1.0, "irreversible"
    if _REVERSIBLE_RX.search(text or ""):
        return 0.0, "reversible"
    return 0.5, "uncertain"


def assess_risk(
    query: str,
    *,
    declared: str | None = None,
    deadline_s: float | None = None,
) -> dict[str, Any]:
    """Decision risk = f(sensitivity, reversibility), deadline-capped."""

    sensitivity = _classify_sensitivity(query, declared)
    sensitivity_normalized = sensitivity["rank"] / 3.0
    reversibility_score, reversibility_label = _reversibility(query)
    risk = round(0.65 * sensitivity_normalized + 0.35 * reversibility_score, 4)

    if risk >= 0.6:
        wanted = "STRATEGIC"
    elif risk >= 0.3:
        wanted = "OPERATIONAL"
    else:
        wanted = "TACTICAL"

    chosen = wanted
    capped_by_deadline = False
    if deadline_s is not None:
        affordable = [
            tier["tier"] for tier in TIERS if tier["deadline_s"] <= deadline_s
        ]
        order = ["TACTICAL", "OPERATIONAL", "STRATEGIC"]
        if affordable:
            best_affordable = max(affordable, key=order.index)
            if order.index(best_affordable) < order.index(wanted):
                chosen = best_affordable
                capped_by_deadline = True
        else:
            chosen = "TACTICAL"
            capped_by_deadline = True

    return {
        "sensitivity": sensitivity,
        "reversibility": {
            "score": reversibility_score,
            "label": reversibility_label,
        },
        "risk": risk,
        "risk_band": (
            "HIGH" if risk >= 0.6 else "MODERATE" if risk >= 0.3 else "LOW"
        ),
        "risk_implied_tier": wanted,
        "chosen_tier": chosen,
        "capped_by_deadline": capped_by_deadline,
    }


def _pick_model(max_model_tier: str, sensitivity_rank: int) -> dict[str, Any] | None:
    """Choose the smallest sufficient model inside the declared ceiling."""

    try:
        import szl_governance_gateway as governance_gateway  # type: ignore

        catalog = getattr(governance_gateway, "CATALOG", [])
        order = getattr(governance_gateway, "_TIER_ORDER", {})
        airgap_floor = getattr(governance_gateway, "_AIRGAP_FLOOR", 2)
    except Exception:
        return None

    ceiling = order.get(max_model_tier, 9)
    airgap_required = sensitivity_rank >= airgap_floor
    eligible = [
        model
        for model in catalog
        if order.get(model["tier"], 9) <= ceiling
        and (not airgap_required or model.get("zone") == "AIRGAP")
    ]
    if not eligible:
        return None
    eligible.sort(key=lambda model: (order.get(model["tier"], 9), -model.get("ctx", 0)))
    return eligible[0]


def route(
    query: str,
    *,
    declared: str | None = None,
    deadline_s: float | None = None,
) -> dict[str, Any]:
    risk = assess_risk(query, declared=declared, deadline_s=deadline_s)
    tier = _TIER_BY_NAME[risk["chosen_tier"]]
    model = _pick_model(tier["max_model_tier"], risk["sensitivity"]["rank"])
    decision = {
        "query": query,
        "tier": tier,
        "risk": risk,
        "chosen_model": model,
        "airgap_required": risk["sensitivity"]["rank"] >= 2,
        "policy": (
            "risk(sensitivity×reversibility) → mission tier (deadline-capped) "
            "→ smallest sufficient air-gap-safe model"
        ),
        "honest": (
            None
            if model
            else "no model within tier ceiling + air-gap floor — raise the tier or add an AIRGAP model"
        ),
    }
    _learn_skeleton(decision)
    return decision


_SKELETONS: dict[str, dict[str, Any]] = {}


def _learn_skeleton(decision: dict[str, Any]) -> None:
    band = decision["risk"]["risk_band"]
    tier = decision["tier"]["tier"]
    airgap = decision["airgap_required"]
    model_family = ((decision.get("chosen_model") or {}).get("id") or "—").split("-")[0]
    key = f"{band}|{tier}|{'airgap' if airgap else 'cloud'}|{model_family}"
    skeleton = _SKELETONS.get(key)
    if skeleton is None:
        skeleton = {
            "key": key,
            "risk_band": band,
            "tier": tier,
            "airgap": airgap,
            "model_family": model_family,
            "uses": 0,
            "first_seen": time.time(),
            "last_seen": time.time(),
            "lesson": _lesson(band, tier, airgap),
        }
        _SKELETONS[key] = skeleton
    skeleton["uses"] += 1
    skeleton["last_seen"] = time.time()
    if len(_SKELETONS) > 64:
        least_valuable = min(
            _SKELETONS.values(),
            key=lambda item: (item["uses"], item["last_seen"]),
        )
        _SKELETONS.pop(least_valuable["key"], None)


def _lesson(band: str, tier: str, airgap: bool) -> str:
    zone = "air-gapped (classified)" if airgap else "cloud-eligible"
    return (
        f"{band}-risk decisions routed to the {tier} budget tier on {zone} compute "
        "resolved within budget; reuse this skeleton for the same risk class."
    )


def skeletons() -> dict[str, Any]:
    rows = sorted(_SKELETONS.values(), key=lambda item: item["uses"], reverse=True)
    return {
        "skeleton_count": len(rows),
        "skeletons": rows,
        "hint": (
            None
            if rows
            else "no skeletons yet — route decisions via POST /api/a11oy/v1/budget/route to learn them"
        ),
    }


# ---------------------------------------------------------------------------
# Semantic token ingress
# ---------------------------------------------------------------------------

MAX_PREFIX_ENTRIES = 256
MAX_PREFIX_BYTES = 16 * 1024 * 1024
MAX_INGEST_FILES = 4096
MAX_INGEST_FILE_BYTES = 8 * 1024 * 1024
MAX_INGEST_TOTAL_BYTES = 128 * 1024 * 1024
MAX_TOKEN_BODY = 64 * 1024
MAX_TOKEN_NODES = 64
MAX_TOKEN_CASES = 256
MAX_TOKEN_IDS_PER_CASE = 8192
MAX_TOKEN_TEXT_CHARS_PER_CASE = 256 * 1024

_SEMANTIC_DIGEST_FIELDS = (
    "vocabulary_sha256",
    "normalization_sha256",
    "special_tokens_sha256",
    "added_tokens_sha256",
    "chat_template_sha256",
    "document_separator_sha256",
)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class TokenizerNodeSignal:
    node_id: str
    tokenizer_tokens_per_sec: float
    tokenizer_cache_warmth: float
    prefix_cache_hit_rate: float
    kv_cache_hit_rate: float
    available: bool = True
    measured: bool = False

    def validate(self) -> None:
        if not self.node_id.strip():
            raise ValueError("node_id is required")
        if not math.isfinite(self.tokenizer_tokens_per_sec) or self.tokenizer_tokens_per_sec < 0:
            raise ValueError("tokenizer_tokens_per_sec must be finite and non-negative")
        for name, value in (
            ("tokenizer_cache_warmth", self.tokenizer_cache_warmth),
            ("prefix_cache_hit_rate", self.prefix_cache_hit_rate),
            ("kv_cache_hit_rate", self.kv_cache_hit_rate),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and between 0 and 1")


@dataclass(frozen=True)
class IngressWorkload:
    prefix_heavy: bool = False
    corpus_heavy: bool = False
    prefill_heavy: bool = False

    @property
    def ingress_weight(self) -> float:
        flags = sum((self.prefix_heavy, self.corpus_heavy, self.prefill_heavy))
        return min(1.0, 0.25 + 0.25 * flags)


def choose_ingress_node(
    nodes: Sequence[TokenizerNodeSignal],
    workload: IngressWorkload,
) -> dict[str, object]:
    eligible = [node for node in nodes if node.available]
    if not eligible:
        return {
            "status": "BLOCKED",
            "reason": "no available ingress nodes",
            "node": None,
        }
    for node in eligible:
        node.validate()

    maximum_throughput = max(node.tokenizer_tokens_per_sec for node in eligible) or 1.0
    ingress_weight = workload.ingress_weight

    def score(node: TokenizerNodeSignal) -> float:
        throughput = node.tokenizer_tokens_per_sec / maximum_throughput
        cache_locality = (
            0.45 * node.tokenizer_cache_warmth
            + 0.35 * node.prefix_cache_hit_rate
            + 0.20 * node.kv_cache_hit_rate
        )
        return round(
            (1.0 - ingress_weight) * throughput + ingress_weight * cache_locality,
            6,
        )

    ranked = sorted(eligible, key=lambda node: (-score(node), node.node_id))
    winner = ranked[0]
    return {
        "status": "PASS",
        "node": winner.node_id,
        "score": score(winner),
        "evidence": "MEASURED" if winner.measured else "SAMPLE",
        "policy": "tokenizer-throughput + cache-warmth + prefix/KV reuse",
        "ranking": [{"node": node.node_id, "score": score(node)} for node in ranked],
    }


@dataclass(frozen=True)
class SemanticTokenContract:
    source: str
    tokenizer_family: str
    vocabulary_sha256: str
    normalization_sha256: str
    special_tokens_sha256: str
    added_tokens_sha256: str
    chat_template_sha256: str
    document_separator_sha256: str

    def validate(self) -> None:
        if not self.source.strip():
            raise ValueError("semantic token contract source is required")
        if not self.tokenizer_family.strip():
            raise ValueError("tokenizer_family is required")
        for field_name in _SEMANTIC_DIGEST_FIELDS:
            if not _is_sha256(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be one lowercase SHA-256 digest")

    def semantic_fields(self) -> dict[str, str]:
        self.validate()
        return {
            "tokenizer_family": self.tokenizer_family,
            **{name: getattr(self, name) for name in _SEMANTIC_DIGEST_FIELDS},
        }

    def digest(self) -> str:
        return _canonical_sha256(self.semantic_fields())

    def mismatches(self, other: "SemanticTokenContract") -> list[str]:
        left = self.semantic_fields()
        right = other.semantic_fields()
        return sorted(name for name in left if left[name] != right[name])


@dataclass(frozen=True)
class TokenizerParityCase:
    name: str
    oracle_ids: tuple[int, ...]
    candidate_ids: tuple[int, ...]
    oracle_decoded_text: str
    candidate_decoded_text: str

    def exact_match(self) -> bool:
        return (
            self.oracle_ids == self.candidate_ids
            and self.oracle_decoded_text == self.candidate_decoded_text
        )


def qualify_tokenizer_candidate(
    oracle: SemanticTokenContract,
    candidate: SemanticTokenContract,
    cases: Sequence[TokenizerParityCase],
) -> dict[str, object]:
    oracle.validate()
    candidate.validate()
    if not cases:
        return {
            "status": "BLOCKED",
            "eligible": False,
            "reason": "no representative semantic-parity cases supplied",
            "oracle_source": oracle.source,
            "candidate_source": candidate.source,
        }

    contract_mismatches = oracle.mismatches(candidate)
    case_mismatches = [case.name for case in cases if not case.exact_match()]
    eligible = not contract_mismatches and not case_mismatches
    return {
        "status": "PASS" if eligible else "FAIL",
        "eligible": eligible,
        "oracle_source": oracle.source,
        "candidate_source": candidate.source,
        "oracle_contract_sha256": oracle.digest(),
        "candidate_contract_sha256": candidate.digest(),
        "contract_mismatches": contract_mismatches,
        "case_mismatches": case_mismatches,
        "cases": len(cases),
        "policy": (
            "exact vocabulary/normalization/special-token/added-token/chat-template/"
            "document-separator digests + token IDs + decoded text"
        ),
    }


@dataclass
class PrefixFoundry:
    max_entries: int = MAX_PREFIX_ENTRIES
    max_bytes: int = MAX_PREFIX_BYTES
    _entries: dict[str, bytes] = field(default_factory=dict)
    _bytes: int = 0

    @staticmethod
    def digest(namespace: str, semantic_contract_sha256: str, content: bytes) -> str:
        if not namespace.strip():
            raise ValueError("namespace is required")
        if not _is_sha256(semantic_contract_sha256):
            raise ValueError("semantic_contract_sha256 must be one lowercase SHA-256 digest")
        digest = hashlib.sha256()
        digest.update(namespace.encode("utf-8"))
        digest.update(b"\0")
        digest.update(semantic_contract_sha256.encode("ascii"))
        digest.update(b"\0")
        digest.update(content)
        return digest.hexdigest()

    def put(self, namespace: str, semantic_contract_sha256: str, content: bytes) -> str:
        if self.max_entries < 1 or self.max_bytes < 1:
            raise ValueError("foundry budgets must be positive")
        if not content:
            raise ValueError("prefix content must not be empty")
        if len(content) > self.max_bytes:
            raise ValueError("prefix exceeds foundry byte budget")
        key = self.digest(namespace, semantic_contract_sha256, content)
        if key in self._entries:
            return key
        while self._entries and (
            len(self._entries) >= self.max_entries
            or self._bytes + len(content) > self.max_bytes
        ):
            oldest_key = next(iter(self._entries))
            old = self._entries.pop(oldest_key)
            self._bytes -= len(old)
        self._entries[key] = bytes(content)
        self._bytes += len(content)
        return key

    def get(self, key: str) -> bytes | None:
        return self._entries.get(key)

    def snapshot(self) -> dict[str, int]:
        return {"entries": len(self._entries), "bytes": self._bytes}


@dataclass(frozen=True)
class IngestedFile:
    path: str
    sha256: str
    size_bytes: int
    text: bool


def _is_probably_binary(data: bytes) -> bool:
    return bool(data) and b"\0" in data[:4096]


def _path_contains_symlink(root: Path, relative_path: Path) -> bool:
    cursor = root
    for part in relative_path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return True
    return False


def ingest_repository_files(
    root: Path,
    relative_paths: Iterable[str],
    *,
    max_files: int = MAX_INGEST_FILES,
    max_file_bytes: int = MAX_INGEST_FILE_BYTES,
    max_total_bytes: int = MAX_INGEST_TOTAL_BYTES,
) -> dict[str, object]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("root must be an existing directory")
    if max_files < 1 or max_file_bytes < 1 or max_total_bytes < 1:
        raise ValueError("ingest budgets must be positive")

    normalized = sorted(set(relative_paths))
    if len(normalized) > max_files:
        return {
            "status": "BLOCKED",
            "reason": "file-count-budget",
            "files": [],
            "text_payloads": {},
            "skipped": [],
            "total_bytes": 0,
        }

    total = 0
    manifest: list[IngestedFile] = []
    text_payloads: dict[str, str] = {}
    skipped: list[dict[str, str]] = []

    for raw_path in normalized:
        relative = Path(raw_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"path escapes repository root: {raw_path}")
        if _path_contains_symlink(root, relative):
            skipped.append({"path": relative.as_posix(), "reason": "symlink"})
            continue

        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"path escapes repository root: {raw_path}") from exc
        if not target.is_file():
            skipped.append({"path": relative.as_posix(), "reason": "not-a-file"})
            continue

        stat_size = target.stat().st_size
        if stat_size > max_file_bytes:
            skipped.append({"path": relative.as_posix(), "reason": "file-budget"})
            continue
        if total + stat_size > max_total_bytes:
            return {
                "status": "BLOCKED",
                "reason": "total-ingest-byte-budget",
                "files": [item.__dict__ for item in manifest],
                "text_payloads": text_payloads,
                "skipped": skipped,
                "total_bytes": total,
            }

        data = target.read_bytes()
        if len(data) > max_file_bytes or total + len(data) > max_total_bytes:
            return {
                "status": "BLOCKED",
                "reason": "post-read-byte-budget",
                "files": [item.__dict__ for item in manifest],
                "text_payloads": text_payloads,
                "skipped": skipped,
                "total_bytes": total,
            }

        total += len(data)
        is_text = not _is_probably_binary(data)
        manifest.append(
            IngestedFile(
                path=relative.as_posix(),
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
                text=is_text,
            )
        )
        if is_text:
            text_payloads[relative.as_posix()] = data.decode("utf-8", errors="replace")
        else:
            skipped.append({"path": relative.as_posix(), "reason": "binary"})

    rows = [item.__dict__ for item in manifest]
    return {
        "status": "PASS",
        "files": rows,
        "text_payloads": text_payloads,
        "skipped": skipped,
        "total_bytes": total,
        "batch_sha256": _canonical_sha256(rows),
    }


def verifier_reinvestment(
    saved_milliseconds: float,
    *,
    measured: bool = False,
    weights: Mapping[str, float] | None = None,
) -> dict[str, object]:
    if not math.isfinite(saved_milliseconds) or saved_milliseconds < 0:
        raise ValueError("saved_milliseconds must be finite and non-negative")
    allocation = dict(
        weights
        or {
            "branch_scoring": 0.30,
            "static_analysis": 0.25,
            "policy_checks": 0.20,
            "replay": 0.15,
            "counterexamples": 0.10,
        }
    )
    if not allocation or any(
        not math.isfinite(value) or value < 0 for value in allocation.values()
    ):
        raise ValueError("verification weights must be finite and non-negative")
    total = sum(allocation.values())
    if total <= 0:
        raise ValueError("verification weights must have positive total")
    budget = {
        name: round(saved_milliseconds * value / total, 3)
        for name, value in allocation.items()
    }
    return {
        "evidence": "MEASURED" if measured else "MODELED",
        "saved_milliseconds": saved_milliseconds,
        "verification_budget_ms": budget,
        "policy": "reinvest ingress savings into verification before expanding interactive traffic",
    }


_TOKEN_FOUNDRY = PrefixFoundry()


def _token_error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {
            "ready": status < 500,
            "accepted": False,
            "status": "BLOCKED" if status < 500 else "UNAVAILABLE",
            "error": {"code": code, "message": message[:240]},
            "effectors": 0,
        },
        status_code=status,
    )


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


async def _token_body(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise ValueError("content-type must be application/json")

    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            size = int(declared)
        except ValueError as exc:
            raise ValueError("content-length must be an integer") from exc
        if size < 0 or size > MAX_TOKEN_BODY:
            raise ValueError("request body exceeds 64 KiB")

    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_TOKEN_BODY:
            raise ValueError("request body exceeds 64 KiB")
        raw.extend(chunk)

    try:
        value = json.loads(
            bytes(raw).decode("utf-8"),
            object_pairs_hook=_closed_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("request body must be strict JSON with unique fields") from exc
    if not isinstance(value, dict):
        raise ValueError("request body must be one JSON object")
    return value


def _closed_fields(value: dict[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(value) - allowed)
    if extras:
        raise ValueError(f"{field} contains unsupported fields: {','.join(extras)}")


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _strict_bool(value: Any, field_name: str, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _token_ids(value: Any, field_name: str) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) > MAX_TOKEN_IDS_PER_CASE:
        raise ValueError(
            f"{field_name} must be an array with at most {MAX_TOKEN_IDS_PER_CASE} entries"
        )
    if any(
        isinstance(item, bool) or not isinstance(item, int) or item < 0
        for item in value
    ):
        raise ValueError(f"{field_name} must contain non-negative integer token IDs")
    return tuple(value)


def _bounded_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if len(value) > MAX_TOKEN_TEXT_CHARS_PER_CASE:
        raise ValueError(f"{field_name} exceeds the text boundary")
    return value


def _semantic_contract(value: Any, field_name: str) -> SemanticTokenContract:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    allowed = {"source", "tokenizer_family", *_SEMANTIC_DIGEST_FIELDS}
    _closed_fields(value, allowed, field_name)
    source = value.get("source")
    family = value.get("tokenizer_family")
    if not isinstance(source, str) or not isinstance(family, str):
        raise ValueError(
            f"{field_name}.source and {field_name}.tokenizer_family must be strings"
        )
    digests: dict[str, str] = {}
    for digest_field in _SEMANTIC_DIGEST_FIELDS:
        digest = value.get(digest_field)
        if not isinstance(digest, str):
            raise ValueError(f"{field_name}.{digest_field} must be a string")
        digests[digest_field] = digest
    contract = SemanticTokenContract(
        source=source,
        tokenizer_family=family,
        **digests,
    )
    contract.validate()
    return contract


def _register_token_ingress(app: FastAPI, ns: str) -> dict[str, Any]:
    prefix = f"/api/{ns}/v1/token-ingress"
    if any(
        getattr(existing, "path", None) == f"{prefix}/status"
        for existing in app.router.routes
    ):
        return {"ok": True, "state": "ALREADY_REGISTERED", "routes": []}

    @app.get(f"{prefix}/status", include_in_schema=False)
    async def token_ingress_status() -> JSONResponse:
        return JSONResponse(
            {
                "ready": True,
                "implementation": "REAL",
                "execution": "BOUNDED_COMPUTATION_ONLY",
                "telemetry": "CALLER_SAMPLE_ONLY",
                "tokenizer_promotion": "FAIL_CLOSED_SEMANTIC_CONTRACT_REQUIRED",
                "semantic_contract_fields": [
                    "tokenizer_family",
                    *_SEMANTIC_DIGEST_FIELDS,
                ],
                "prefix_foundry": _TOKEN_FOUNDRY.snapshot(),
                "repository_ingestion": "INTERNAL_LIBRARY_ONLY",
                "effectors": 0,
                "provider_calls": 0,
                "network_calls": 0,
            }
        )

    @app.post(f"{prefix}/route", include_in_schema=False)
    async def token_ingress_route(request: Request) -> JSONResponse:
        try:
            payload = await _token_body(request)
            _closed_fields(payload, {"nodes", "workload"}, "request")
            raw_nodes = payload.get("nodes")
            if not isinstance(raw_nodes, list) or not 1 <= len(raw_nodes) <= MAX_TOKEN_NODES:
                raise ValueError(f"nodes must contain 1..{MAX_TOKEN_NODES} entries")

            nodes: list[TokenizerNodeSignal] = []
            node_fields = {
                "node_id",
                "tokenizer_tokens_per_sec",
                "tokenizer_cache_warmth",
                "prefix_cache_hit_rate",
                "kv_cache_hit_rate",
                "available",
                "measured",
            }
            for index, item in enumerate(raw_nodes):
                if not isinstance(item, dict):
                    raise ValueError("every node must be an object")
                _closed_fields(item, node_fields, f"node[{index}]")
                node_id = item.get("node_id")
                if not isinstance(node_id, str):
                    raise ValueError("node_id must be a string")
                nodes.append(
                    TokenizerNodeSignal(
                        node_id=node_id,
                        tokenizer_tokens_per_sec=_number(
                            item.get("tokenizer_tokens_per_sec", 0),
                            "tokenizer_tokens_per_sec",
                        ),
                        tokenizer_cache_warmth=_number(
                            item.get("tokenizer_cache_warmth", 0),
                            "tokenizer_cache_warmth",
                        ),
                        prefix_cache_hit_rate=_number(
                            item.get("prefix_cache_hit_rate", 0),
                            "prefix_cache_hit_rate",
                        ),
                        kv_cache_hit_rate=_number(
                            item.get("kv_cache_hit_rate", 0),
                            "kv_cache_hit_rate",
                        ),
                        available=_strict_bool(
                            item.get("available"),
                            "available",
                            default=True,
                        ),
                        measured=False,
                    )
                )

            raw_workload = payload.get("workload") or {}
            if not isinstance(raw_workload, dict):
                raise ValueError("workload must be an object")
            _closed_fields(
                raw_workload,
                {"prefix_heavy", "corpus_heavy", "prefill_heavy"},
                "workload",
            )
            workload = IngressWorkload(
                prefix_heavy=_strict_bool(
                    raw_workload.get("prefix_heavy"),
                    "prefix_heavy",
                    default=False,
                ),
                corpus_heavy=_strict_bool(
                    raw_workload.get("corpus_heavy"),
                    "corpus_heavy",
                    default=False,
                ),
                prefill_heavy=_strict_bool(
                    raw_workload.get("prefill_heavy"),
                    "prefill_heavy",
                    default=False,
                ),
            )
            result = choose_ingress_node(nodes, workload)
            result["evidence"] = "SAMPLE"
            result["telemetry_authority"] = "CALLER_SUPPLIED_NOT_MEASURED"
            accepted = result["status"] == "PASS"
            return JSONResponse(
                {"ready": True, "accepted": accepted, **result},
                status_code=200 if accepted else 409,
            )
        except (TypeError, ValueError) as exc:
            return _token_error(422, "invalid_ingress_route", str(exc))

    @app.post(f"{prefix}/qualify", include_in_schema=False)
    async def token_ingress_qualify(request: Request) -> JSONResponse:
        try:
            payload = await _token_body(request)
            _closed_fields(
                payload,
                {"oracle_contract", "candidate_contract", "cases"},
                "request",
            )
            oracle = _semantic_contract(
                payload.get("oracle_contract"),
                "oracle_contract",
            )
            candidate = _semantic_contract(
                payload.get("candidate_contract"),
                "candidate_contract",
            )
            raw_cases = payload.get("cases")
            if not isinstance(raw_cases, list) or len(raw_cases) > MAX_TOKEN_CASES:
                raise ValueError(
                    f"cases must be a list with at most {MAX_TOKEN_CASES} entries"
                )

            cases: list[TokenizerParityCase] = []
            case_fields = {
                "name",
                "oracle_ids",
                "candidate_ids",
                "oracle_decoded_text",
                "candidate_decoded_text",
            }
            for index, item in enumerate(raw_cases):
                if not isinstance(item, dict):
                    raise ValueError("every parity case must be an object")
                _closed_fields(item, case_fields, f"case[{index}]")
                name = item.get("name")
                if not isinstance(name, str) or not name:
                    raise ValueError("case name must be a non-empty string")
                cases.append(
                    TokenizerParityCase(
                        name=name,
                        oracle_ids=_token_ids(item.get("oracle_ids"), "oracle_ids"),
                        candidate_ids=_token_ids(
                            item.get("candidate_ids"),
                            "candidate_ids",
                        ),
                        oracle_decoded_text=_bounded_text(
                            item.get("oracle_decoded_text"),
                            "oracle_decoded_text",
                        ),
                        candidate_decoded_text=_bounded_text(
                            item.get("candidate_decoded_text"),
                            "candidate_decoded_text",
                        ),
                    )
                )

            result = qualify_tokenizer_candidate(oracle, candidate, cases)
            status_code = (
                200
                if result["status"] == "PASS"
                else 409
                if result["status"] == "FAIL"
                else 422
            )
            return JSONResponse(
                {
                    "ready": True,
                    "accepted": result["status"] == "PASS",
                    **result,
                    "effectors": 0,
                },
                status_code=status_code,
            )
        except (TypeError, ValueError) as exc:
            return _token_error(422, "invalid_tokenizer_qualification", str(exc))

    @app.post(f"{prefix}/verification-budget", include_in_schema=False)
    async def token_ingress_verification_budget(request: Request) -> JSONResponse:
        try:
            payload = await _token_body(request)
            _closed_fields(
                payload,
                {"saved_milliseconds", "measured"},
                "request",
            )
            saved = _number(
                payload.get("saved_milliseconds", 0),
                "saved_milliseconds",
            )
            result = verifier_reinvestment(saved, measured=False)
            result["evidence"] = "MODELED"
            result["measurement_authority"] = "NOT_ACCEPTED_FROM_PUBLIC_CALLER"
            return JSONResponse(
                {"ready": True, "accepted": True, **result, "effectors": 0}
            )
        except (TypeError, ValueError) as exc:
            return _token_error(422, "invalid_verification_budget", str(exc))

    return {
        "ok": True,
        "state": "REGISTERED",
        "routes": [
            f"{prefix}/status",
            f"{prefix}/route",
            f"{prefix}/qualify",
            f"{prefix}/verification-budget",
        ],
        "effectors": 0,
    }


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/budget/tiers", include_in_schema=False)
    async def budget_tiers() -> JSONResponse:
        return JSONResponse(
            {
                "doctrine": DOCTRINE,
                "tiers": TIERS,
                "pattern_source": (
                    "ViktorAxelsen/BudgetMem (Apache-2.0) — module budget tiers, "
                    "evolved to mission constraints"
                ),
            }
        )

    @app.post(f"/api/{ns}/v1/budget/route", include_in_schema=False)
    async def budget_route(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        query = (body or {}).get("query") or (body or {}).get("q") or ""
        declared = (body or {}).get("classification")
        deadline = (body or {}).get("deadline_s")
        try:
            deadline = float(deadline) if deadline is not None else None
        except Exception:
            deadline = None
        if not query:
            return JSONResponse({"error": "provide {query: ...}"}, status_code=400)
        return JSONResponse(
            {
                "doctrine": DOCTRINE,
                **route(query, declared=declared, deadline_s=deadline),
            }
        )

    @app.get(f"/api/{ns}/v1/budget/skeletons", include_in_schema=False)
    async def budget_skeletons() -> JSONResponse:
        return JSONResponse(
            {
                "doctrine": DOCTRINE,
                **skeletons(),
                "pattern_source": (
                    "ViktorAxelsen/MemSkill (Apache-2.0) — meta-memory, "
                    "evolved to Decision Skeletons"
                ),
            }
        )

    token_status = _register_token_ingress(app, ns)

    @app.get("/budget-router", include_in_schema=False)
    async def budget_router_page() -> HTMLResponse:
        return HTMLResponse(_PAGE_HTML)

    return (
        f"budget-router mounted: GET /budget-router + /api/{ns}/v1/budget/"
        f"(tiers|route|skeletons); token-ingress={token_status['state']}"
    )


_PAGE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>a11oy · Budget-Tier Router + Decision Skeletons</title>
<style>
:root{--bg:#0b0f14;--panel:#121922;--ink:#e8eef5;--muted:#8aa0b4;--gold:#d9b46a;
--green:#3fb950;--blue:#1f6feb;--red:#f85149;--amber:#d29922;--line:#1e2a36;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:24px 18px 64px}
h1{font-size:24px;margin:.2em 0}.sub{color:var(--muted);margin:0 0 18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input,select{background:#0d141c;border:1px solid var(--line);border-radius:8px;color:var(--ink);padding:9px 11px;font-size:14px}
input{flex:1;min-width:200px}
button{background:var(--gold);color:#1a1205;border:0;border-radius:8px;padding:9px 16px;font-weight:700;cursor:pointer}
button:hover{filter:brightness(1.08)}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.green{background:rgba(63,185,80,.15);color:var(--green)}
.blue{background:rgba(31,111,235,.18);color:#79b8ff}
.red{background:rgba(248,81,73,.15);color:var(--red)}
.amber{background:rgba(210,153,34,.15);color:var(--amber)}
.tiers{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:6px}
.tcard{background:#0d141c;border:1px solid var(--line);border-radius:10px;padding:12px}
.tcard h3{margin:.1em 0;font-size:16px}
pre{background:#0d141c;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;font-size:12.5px;white-space:pre-wrap}
.foot{color:var(--muted);font-size:12px;margin-top:24px;border-top:1px solid var(--line);padding-top:12px}
code{color:var(--gold)}
.sk{border-top:1px solid var(--line);padding:10px 0}.sk:first-child{border-top:0}
.sk .k{color:var(--gold);font-weight:700}.sk .l{color:var(--muted);font-size:13px}
.uses{float:right;color:var(--green);font-variant-numeric:tabular-nums}
.chips{margin-top:10px}.chip{display:inline-block;margin:2px 4px 2px 0;padding:4px 10px;border:1px solid var(--line);
border-radius:999px;font-size:12px;color:var(--muted);cursor:pointer;background:#0d141c}.chip:hover{border-color:var(--gold);color:var(--gold)}
</style></head>
<body><div class="wrap">
<h1>Budget-Tier Router <span class="pill green">cost-aware</span> <span class="pill blue">Decision Skeletons</span></h1>
<p class="sub">Routes each governed decision by <b>risk</b> (sensitivity × reversibility) to the
cheapest mission budget tier that still satisfies it — <b>Tactical (≤1s)</b>, <b>Operational (≤10s)</b>,
<b>Strategic (≤1min)</b> — then to the smallest sufficient air-gap-safe model. Patterns from
<code>BudgetMem</code> + <code>MemSkill</code> (Apache-2.0) and <code>GraphPlanner</code> (MIT),
evolved into mission-bound budget routing with reusable Decision Skeletons. 0 CDN.</p>

<div class="card">
<h3 style="margin-top:0">Mission budget tiers</h3>
<div class="tiers" id="tiers"></div>
</div>

<div class="card">
<h3 style="margin-top:0">Route a decision</h3>
<div class="row">
<input id="q" placeholder="describe the decision (e.g. authorize drone strike on classified grid ref)…"/>
<select id="cls"><option value="">auto-classify</option><option>PUBLIC</option><option>INTERNAL</option><option>RESTRICTED</option><option>SECRET</option></select>
<select id="dl"><option value="">no deadline</option><option value="1">≤1s</option><option value="10">≤10s</option><option value="60">≤60s</option></select>
<button id="go">Route</button>
</div>
<div class="chips" id="chips">
<span class="chip">summarize today's maritime intel feed</span>
<span class="chip">authorize a drone strike on classified grid ref</span>
<span class="chip">draft an internal roadmap memo</span>
</div>
<pre id="out" style="margin-top:12px">Route a decision to see the tier + model + risk verdict.</pre>
</div>

<div class="card">
<div class="row" style="justify-content:space-between"><h3 style="margin:0">Decision Skeletons (learned)</h3>
<button id="ref" style="background:#1f6feb;color:#fff">Refresh</button></div>
<div id="sks" style="margin-top:8px">No skeletons yet.</div>
</div>

<p class="foot">a11oy · Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 ·
patterns: BudgetMem + MemSkill (Apache-2.0), GraphPlanner (MIT), evolved · sovereign 0-CDN.</p>
</div>
<script>
const $=s=>document.querySelector(s);
async function tiers(){
  const d=await(await fetch('/api/a11oy/v1/budget/tiers')).json();
  const box=$('#tiers');box.innerHTML='';
  for(const t of d.tiers){
    const el=document.createElement('div');el.className='tcard';
    el.innerHTML='<h3>'+t.tier+' <span class="pill blue">'+t.budget+'</span></h3>'
      +'<div class="l" style="color:var(--muted);font-size:13px">deadline ≤'+t.deadline_s+'s · max model '+t.max_model_tier+' · CoT '+t.cot+'</div>'
      +'<div style="margin-top:6px;font-size:13px">'+t.note+'</div>';
    box.appendChild(el);
  }
}
async function route(){
  const q=$('#q').value;if(!q)return;
  const body={query:q};const c=$('#cls').value;const dl=$('#dl').value;
  if(c)body.classification=c;if(dl)body.deadline_s=Number(dl);
  const d=await(await fetch('/api/a11oy/v1/budget/route',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)})).json();
  const r=d.risk||{};const m=d.chosen_model;
  $('#out').textContent=
    'TIER: '+(d.tier&&d.tier.tier)+'  (budget '+(d.tier&&d.tier.budget)+', deadline ≤'+(d.tier&&d.tier.deadline_s)+'s)\\n'
    +'RISK: '+r.risk+'  ['+r.risk_band+']  sensitivity='+(r.sensitivity&&r.sensitivity.class)
    +'  reversibility='+(r.reversibility&&r.reversibility.label)+(r.capped_by_deadline?'  (tier capped by deadline)':'')+'\\n'
    +'AIR-GAP REQUIRED: '+d.airgap_required+'\\n'
    +'MODEL: '+(m?(m.id+'  ['+m.tier+'/'+m.zone+', '+m.license+']'):('— '+(d.honest||'')))+'\\n\\n'
    +'policy: '+d.policy;
  loadSk();
}
async function loadSk(){
  const d=await(await fetch('/api/a11oy/v1/budget/skeletons')).json();
  const box=$('#sks');box.innerHTML='';
  if(!d.skeletons.length){box.innerHTML='<div class="l">'+(d.hint||'No skeletons yet.')+'</div>';return}
  for(const s of d.skeletons){
    const el=document.createElement('div');el.className='sk';
    el.innerHTML='<span class="uses">×'+s.uses+'</span>'
      +'<div class="k">'+s.key+'</div><div class="l">'+s.lesson+'</div>';
    box.appendChild(el);
  }
}
$('#go').addEventListener('click',route);
$('#q').addEventListener('keydown',event=>{if(event.key==='Enter')route()});
$('#ref').addEventListener('click',loadSk);
document.querySelectorAll('.chip').forEach(chip=>chip.addEventListener('click',()=>{$('#q').value=chip.textContent;route();}));
tiers();loadSk();
</script>
</body></html>"""
