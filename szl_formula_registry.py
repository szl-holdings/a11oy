"""Authoritative, digest-verified dispute-relevant maturity crosswalk.

This registry reconciles the local lutar-lean snapshot with Doctrine v11.  A
deterministic SHA-256 digest is exposed as a receipt basis; it is deliberately
UNSIGNED until an approved signing key is available.  It is intentionally not
an exhaustive inventory of the estate's roughly 200 formula/theorem artifacts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "formula_registry" / "formula-registry.v1.json"
EXPECTED_CANONICALIZATION = "SZL deterministic JSON for this restricted integer/string/boolean/array/object payload: UTF-8, object keys sorted, separators ',', ':', ensure_ascii=false"
EXPECTED_UNSIGNED_REASON = "No approved signing key was available for this reconciliation wave. The deterministic digest is not a signature."
EXPECTED_COVERAGE_SCOPE = "Dispute-relevant maturity crosswalk for the Doctrine-v11 locked baseline, the challenged F4/F7/F22 classifications, and F23 Lambda status; this is not an inventory of every formula or theorem in the estate."
EXPECTED_POLICY = {
    "locked_set_rule": "Only the five formulas named by the canonical Doctrine-v11 locked-kernel report are LOCKED_PROVEN.",
    "experimental_rule": "A source declaration or CI-green experimental theorem does not promote a formula into the locked set.",
    "lambda_rule": "F23 unconditional uniqueness remains Conjecture 1; conditional theorems do not promote it, and maxAgg_ne_Lambda refutes the bare A1-A5 uniqueness claim.",
    "signing_rule": "No signature is emitted without an approved signing key.",
}
EXPECTED_LOCKED_IDS = ("F1", "F11", "F12", "F18", "F19")
EXPECTED_EXPERIMENTAL_IDS = ("F4", "F7", "F22")
EXPECTED_COVERED_IDS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22", "F23")
EXPECTED_SOURCE_PATHS = (
    "corpus/formulas/lutar-lean__PROVEN_FORMULAS.md",
    "proofs/lutar-lean/Lutar/Puriq/Formulas/PuriqFormulaLean.lean",
    "proofs/lutar-lean/Lutar/Puriq/Formulas/ProvedFormulas.lean",
    "proofs/lutar-lean/Lutar/Round13/Lambda_Uniqueness.lean",
)
EXPECTED_SOURCE_ASSETS = (
    (EXPECTED_SOURCE_PATHS[0], "authoritative maturity and locked-set report", "9692d973c443fb46fa9031a92bf1f6587d5a03ab0abf1e62feec6fce7b01b8d9"),
    (EXPECTED_SOURCE_PATHS[1], "local Lean theorem source snapshot", "0a7ea54762a96b335d3e6e082835542dbd0a22c1ea08db8d7315f77adb1dd8ea"),
    (EXPECTED_SOURCE_PATHS[2], "local compact Lean theorem source snapshot", "847d2e332017a5bfe3e7823092acf0245840f6b20f3d6f1544f723fd1607612e"),
    (EXPECTED_SOURCE_PATHS[3], "Lambda conditional results and unconditional counterexample source", "ea7667f8c20deb469396d822273ede4577e53d5ce0f273dee590a4928b617525"),
)
EXPECTED_FORMULA_SEMANTICS = {
    "F1": ("LOCKED_PROVEN", True, ("f1_replay_hash_determinism", "f1_replay_trace_stable"), EXPECTED_SOURCE_PATHS[1], "LEAN_CORE_ONLY", "LOCKED_KERNEL_REPORT_AND_SOURCE_PRESENT"),
    "F4": ("EXPERIMENTAL", False, ("f4_khipu_no_self_loop", "f4_khipu_acyclic_irrefl", "f4_khipu_reach_strictly_smaller", "f4_khipu_dag_acyclic"), EXPECTED_SOURCE_PATHS[1], "NOT_REEVALUATED_BY_THIS_REGISTRY", "SOURCE_PRESENT_EXPERIMENTAL_NOT_LOCKED"),
    "F7": ("EXPERIMENTAL", False, ("f7_chaski_enqueue_preserves_prefix", "f7_chaski_head_is_oldest", "f7_chaski_fifo", "f7_chaski_take_drop_roundtrip"), EXPECTED_SOURCE_PATHS[1], "NOT_REEVALUATED_BY_THIS_REGISTRY", "SOURCE_PRESENT_EXPERIMENTAL_NOT_LOCKED"),
    "F11": ("LOCKED_PROVEN", True, ("f11_ayni_reciprocity_conservation", "f11_tit_for_tat_parity"), EXPECTED_SOURCE_PATHS[1], "LEAN_CORE_ONLY", "LOCKED_KERNEL_REPORT_AND_SOURCE_PRESENT"),
    "F12": ("LOCKED_PROVEN_LIMITED_FRAGMENT", True, ("f12_kuramoto_additive",), EXPECTED_SOURCE_PATHS[1], "LEAN_CORE_ONLY", "LOCKED_KERNEL_REPORT_AND_SOURCE_PRESENT"),
    "F18": ("LOCKED_PROVEN", True, ("f18_reed_solomon_parity_count", "f18_erasure_tolerance"), EXPECTED_SOURCE_PATHS[1], "LEAN_CORE_ONLY", "LOCKED_KERNEL_REPORT_AND_SOURCE_PRESENT"),
    "F19": ("LOCKED_PROVEN_LIMITED_FRAGMENT", True, ("f19_bekenstein_additive", "f19_budget_monotone"), EXPECTED_SOURCE_PATHS[1], "LEAN_CORE_ONLY", "LOCKED_KERNEL_REPORT_AND_SOURCE_PRESENT"),
    "F22": ("EXPERIMENTAL", False, ("f22_emit_appends_length", "f22_emit_strictly_greater", "f22_khipu_emit_monotone"), EXPECTED_SOURCE_PATHS[1], "NOT_REEVALUATED_BY_THIS_REGISTRY", "SOURCE_PRESENT_EXPERIMENTAL_NOT_LOCKED"),
    "F23": ("CONJECTURE_1_ADVISORY", False, ("lambda_unique_of_factors", "maxAgg_ne_Lambda"), EXPECTED_SOURCE_PATHS[3], "CONDITIONAL_RESULTS_ONLY", "UNCONDITIONAL_CLAIM_REFUTED_BY_COUNTEREXAMPLE"),
}
EXPECTED_FORMULA_NAMES = {
    "F1": "Replay-Hash Determinism",
    "F4": "Khipu DAG Acyclicity",
    "F7": "Chaski FIFO Ordering",
    "F11": "Ayni Reciprocity Conservation",
    "F12": "Kuramoto Additive Fragment",
    "F18": "Reed-Solomon RS(10,6) Recovery Arithmetic",
    "F19": "Bekenstein Additive Scaffolding",
    "F22": "Khipu Emit Monotonicity",
    "F23": "Lambda Aggregator Uniqueness",
}
EXPECTED_FORMULA_CAVEATS = {
    "F12": "Additive fragment only; not nonlinear Kuramoto synchronization.",
    "F19": "Additive/monotone scaffolding only; not the full physical Bekenstein bound.",
    "F23": "Never promote conditional uniqueness results to unconditional theorem status.",
}
TOP_LEVEL_KEYS = frozenset(("schema_version", "registry_digest", "signature", "payload"))
DIGEST_KEYS = frozenset(("algorithm", "canonicalization", "scope", "value"))
SIGNATURE_KEYS = frozenset(("status", "reason"))
PAYLOAD_KEYS = frozenset((
    "registry_version", "doctrine_version", "coverage_scope", "exhaustive",
    "covered_formula_ids", "source_repository", "locked_kernel_commit_prefix",
    "experimental_scope_commit_prefix", "locked_proven_count", "locked_proven_ids",
    "lambda_status", "policy", "source_assets", "formulas",
))
FORMULA_KEYS = frozenset((
    "id", "name", "maturity", "locked_proven", "theorem_refs", "source_path",
    "axiom_status", "evidence_status",
))


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def compute_payload_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _confined_source(root: Path, source_path: str) -> Path:
    relative = Path(source_path)
    if relative.is_absolute() or not source_path or "\\" in source_path:
        raise ValueError(f"formula source path is not a confined POSIX-relative path: {source_path!r}")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"formula source path escapes registry root: {source_path!r}") from exc
    return candidate


def validate_registry_document(
    document: dict[str, Any], *, root: Path = ROOT, verify_source_hashes: bool = True
) -> None:
    """Fail-closed semantic validation independent of optional jsonschema tooling."""
    if not isinstance(document, dict) or set(document) != TOP_LEVEL_KEYS:
        raise ValueError("formula registry top-level key set drift")
    if document.get("schema_version") != "szl.formula-registry.v1":
        raise ValueError("unsupported formula registry schema_version")
    digest = document.get("registry_digest")
    if not isinstance(digest, dict) or set(digest) != DIGEST_KEYS:
        raise ValueError("formula registry digest metadata key set drift")
    if (
        digest.get("algorithm") != "sha256"
        or digest.get("canonicalization") != EXPECTED_CANONICALIZATION
        or digest.get("scope") != "payload"
    ):
        raise ValueError("formula registry digest contract must be sha256 over payload")
    signature = document.get("signature")
    if not isinstance(signature, dict) or set(signature) != SIGNATURE_KEYS:
        raise ValueError("formula registry signature metadata key set drift")
    if signature.get("status") != "UNSIGNED":
        raise ValueError("formula registry must remain UNSIGNED without an approved key")
    if signature.get("reason") != EXPECTED_UNSIGNED_REASON:
        raise ValueError("formula registry UNSIGNED reason drift")

    payload = document.get("payload")
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_KEYS:
        raise ValueError("formula registry payload key set drift")
    expected_digest = digest.get("value")
    actual_digest = compute_payload_digest(payload)
    if expected_digest != actual_digest:
        raise ValueError(f"formula registry digest mismatch: {expected_digest} != {actual_digest}")

    fixed_payload_metadata = {
        "registry_version": "1.0.0",
        "doctrine_version": "v11",
        "coverage_scope": EXPECTED_COVERAGE_SCOPE,
        "exhaustive": False,
        "source_repository": "https://github.com/szl-holdings/lutar-lean",
        "locked_kernel_commit_prefix": "c7c0ba17",
        "experimental_scope_commit_prefix": "7885fd9",
    }
    for key, expected in fixed_payload_metadata.items():
        if payload.get(key) != expected:
            raise ValueError(f"formula registry {key} drift")
    if payload.get("exhaustive") is not False:
        raise ValueError("formula registry is a non-exhaustive maturity crosswalk")
    if tuple(payload.get("covered_formula_ids", ())) != EXPECTED_COVERED_IDS:
        raise ValueError("formula registry covered_formula_ids drift")
    if tuple(payload.get("locked_proven_ids", ())) != EXPECTED_LOCKED_IDS:
        raise ValueError("formula registry locked set drift")
    if payload.get("locked_proven_count") != len(EXPECTED_LOCKED_IDS):
        raise ValueError("formula registry locked count/list mismatch")
    if payload.get("lambda_status") != "CONJECTURE_1_ADVISORY":
        raise ValueError("Lambda must remain Conjecture 1/advisory")
    policy = payload.get("policy")
    if not isinstance(policy, dict) or policy != EXPECTED_POLICY:
        raise ValueError("formula registry policy drift")

    formulas = payload.get("formulas")
    if not isinstance(formulas, list) or len(formulas) != len(EXPECTED_COVERED_IDS):
        raise ValueError("formula registry formula coverage drift")
    ids = [entry.get("id") for entry in formulas if isinstance(entry, dict)]
    if len(ids) != len(formulas) or len(set(ids)) != len(ids):
        raise ValueError("formula registry contains duplicate or malformed formula IDs")
    if tuple(ids) != EXPECTED_COVERED_IDS:
        raise ValueError("formula registry formula order/coverage drift")
    by_id = {entry["id"]: entry for entry in formulas}
    for formula_id, entry in by_id.items():
        expected_keys = FORMULA_KEYS | ({"caveat"} if formula_id in EXPECTED_FORMULA_CAVEATS else set())
        if set(entry) != expected_keys:
            raise ValueError(f"{formula_id} formula metadata key set drift")
        if entry.get("name") != EXPECTED_FORMULA_NAMES[formula_id]:
            raise ValueError(f"{formula_id} formula name drift")
        if formula_id in EXPECTED_FORMULA_CAVEATS:
            if entry.get("caveat") != EXPECTED_FORMULA_CAVEATS[formula_id]:
                raise ValueError(f"{formula_id} caveat drift")
    flagged_locked = tuple(entry["id"] for entry in formulas if entry.get("locked_proven") is True)
    if flagged_locked != EXPECTED_LOCKED_IDS:
        raise ValueError("only the exact Doctrine-v11 locked five may be locked_proven")
    for formula_id in EXPECTED_LOCKED_IDS:
        if not str(by_id[formula_id].get("maturity", "")).startswith("LOCKED_PROVEN"):
            raise ValueError(f"{formula_id} locked maturity drift")
    for formula_id in EXPECTED_EXPERIMENTAL_IDS:
        entry = by_id[formula_id]
        if entry.get("maturity") != "EXPERIMENTAL" or entry.get("locked_proven") is not False:
            raise ValueError(f"{formula_id} must remain EXPERIMENTAL and unlocked")
        if entry.get("evidence_status") != "SOURCE_PRESENT_EXPERIMENTAL_NOT_LOCKED":
            raise ValueError(f"{formula_id} evidence status drift")
    lambda_entry = by_id["F23"]
    if lambda_entry.get("maturity") != "CONJECTURE_1_ADVISORY" or lambda_entry.get("locked_proven") is not False:
        raise ValueError("F23 must remain Conjecture 1/advisory and unlocked")
    if "maxAgg_ne_Lambda" not in lambda_entry.get("theorem_refs", []):
        raise ValueError("F23 must retain the unconditional counterexample reference")

    global_theorem_refs: list[str] = []
    for entry in formulas:
        refs = entry.get("theorem_refs")
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or not ref for ref in refs):
            raise ValueError(f"{entry['id']} theorem_refs must be a non-empty string list")
        if len(refs) != len(set(refs)):
            raise ValueError(f"{entry['id']} contains duplicate theorem_refs")
        global_theorem_refs.extend(refs)
    if len(global_theorem_refs) != len(set(global_theorem_refs)):
        raise ValueError("formula registry theorem_refs must be globally unique")

    semantic_fields = (
        "maturity", "locked_proven", "theorem_refs", "source_path", "axiom_status", "evidence_status"
    )
    for formula_id, expected in EXPECTED_FORMULA_SEMANTICS.items():
        entry = by_id[formula_id]
        actual = (
            entry.get("maturity"), entry.get("locked_proven"), tuple(entry.get("theorem_refs", ())),
            entry.get("source_path"), entry.get("axiom_status"), entry.get("evidence_status"),
        )
        if actual != expected:
            drift = ", ".join(
                field for field, observed, wanted in zip(semantic_fields, actual, expected)
                if observed != wanted
            )
            raise ValueError(f"{formula_id} semantic drift: {drift}")

    source_assets = payload.get("source_assets")
    if not isinstance(source_assets, list) or not source_assets:
        raise ValueError("formula registry requires pinned source assets")
    if any(not isinstance(source, dict) or set(source) != {"path", "role", "sha256"} for source in source_assets):
        raise ValueError("formula registry source asset metadata key set drift")
    source_paths = [source.get("path") for source in source_assets if isinstance(source, dict)]
    if (
        len(source_paths) != len(source_assets)
        or any(not isinstance(path, str) or not path for path in source_paths)
        or len(set(source_paths)) != len(source_paths)
    ):
        raise ValueError("formula registry contains duplicate or malformed source paths")
    confined_sources = {path: _confined_source(root, path) for path in source_paths}
    if tuple(source_paths) != EXPECTED_SOURCE_PATHS:
        raise ValueError("formula registry source asset coverage/order drift")
    actual_asset_metadata = tuple(
        (source.get("path"), source.get("role"), source.get("sha256")) for source in source_assets
    )
    if actual_asset_metadata != EXPECTED_SOURCE_ASSETS:
        raise ValueError("formula registry source asset metadata/digest drift")
    source_files: dict[str, Path] = {}
    for source in source_assets:
        path = source["path"]
        candidate = confined_sources[path]
        expected_source_digest = source.get("sha256")
        if not isinstance(expected_source_digest, str) or len(expected_source_digest) != 64:
            raise ValueError(f"invalid source digest for {path}")
        if verify_source_hashes:
            if not candidate.is_file():
                raise ValueError(f"formula source asset missing: {path}")
            actual_source = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if actual_source != expected_source_digest:
                raise ValueError(
                    f"formula source digest mismatch for {path}: "
                    f"{expected_source_digest} != {actual_source}"
                )
        source_files[path] = candidate
    for entry in formulas:
        source_path = entry.get("source_path")
        if source_path not in source_files:
            raise ValueError(f"{entry['id']} source_path is not a pinned source asset")
        if verify_source_hashes:
            text = source_files[source_path].read_text(encoding="utf-8")
            missing = [ref for ref in entry["theorem_refs"] if ref not in text]
            if missing:
                raise ValueError(f"{entry['id']} theorem refs absent from pinned source: {missing}")


def load_registry(*, verify: bool = True, path: Path = REGISTRY_PATH) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if verify:
        validate_registry_document(document, root=ROOT, verify_source_hashes=True)
    return document


REGISTRY = load_registry(verify=True)
PAYLOAD = REGISTRY["payload"]
LOCKED_PROVEN_IDS = tuple(PAYLOAD["locked_proven_ids"])
LOCKED_PROVEN_COUNT = PAYLOAD["locked_proven_count"]
FORMULA_REGISTRY_DIGEST = REGISTRY["registry_digest"]["value"]
FORMULA_REGISTRY_SIGNATURE_STATUS = REGISTRY["signature"]["status"]
LAMBDA_STATUS = PAYLOAD["lambda_status"]


def formula(formula_id: str) -> dict[str, Any]:
    for entry in PAYLOAD["formulas"]:
        if entry["id"] == formula_id:
            return entry
    raise KeyError(formula_id)


def receipt_basis() -> dict[str, Any]:
    """Return a non-signing basis future Pool receipts can bind to."""
    return {
        "schema_version": REGISTRY["schema_version"],
        "registry_version": PAYLOAD["registry_version"],
        "coverage_scope": PAYLOAD["coverage_scope"],
        "exhaustive": PAYLOAD["exhaustive"],
        "formula_registry_digest": FORMULA_REGISTRY_DIGEST,
        "digest_algorithm": REGISTRY["registry_digest"]["algorithm"],
        "signature_status": FORMULA_REGISTRY_SIGNATURE_STATUS,
        "locked_proven_ids": list(LOCKED_PROVEN_IDS),
        "lambda_status": LAMBDA_STATUS,
    }
