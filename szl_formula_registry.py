"""Canonical SZL formula authority.

The transport filename is retained for deployed-image compatibility, but the
embedded schema is ``szl.formula-authority.v2``.  The v2 record supersedes the
former dispute-scoped locked-five crosswalk.

Authority boundaries:
- ``lutar-lean`` owns formal F-ID maturity and the exact locked count.
- ``szl-formulas`` owns 21 callable software functions.
- no F-ID-to-callable mapping is asserted without a proved binding artifact.
- formulas constrain only after an evidence-bound applicability decision.
- no formula independently authorizes a consequential action.
- F23/Lambda remains Conjecture 1 advisory.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
# Legacy transport path retained because existing container publishers copy it.
REGISTRY_PATH = ROOT / "formula_registry" / "formula-registry.v1.json"

SCHEMA_VERSION = "szl.formula-authority.v2"
EXPECTED_CANONICALIZATION = (
    "UTF-8 JSON; object keys sorted; separators ',', ':'; "
    "ensure_ascii=false; digest scope=payload"
)
EXPECTED_SIGNATURE_STATUS = "UNSIGNED"
EXPECTED_SIGNATURE_REASON = (
    "The SHA-256 digest and immutable Git commit/blob pins provide integrity "
    "and lineage, not signer identity; no approved online signing key is stored "
    "in this repository."
)
EXPECTED_COVERAGE_SCOPE = (
    "Exact locked-eight authority plus the F23 Lambda boundary, which "
    "remains Conjecture 1 and is not a theorem; not an exhaustive "
    "inventory of every SZL formula or formal result."
)
FORMAL_REPOSITORY = "szl-holdings/lutar-lean"
FORMAL_COMMIT = "c497b4ed402249f23da7f290426f0e21c70ab926"
FORMULA_KERNEL_REPOSITORY = "szl-holdings/szl-formulas"
FORMULA_KERNEL_COMMIT = "46cfa948367e8133eaa8dd6bcfb781b19165b9bb"
LOCKED_COUNT_THEOREM = "Lutar.Wave8.AxiomDisclosure.locked_count_eight"
CALLABLE_FORMULA_COUNT = 21
F_ID_TO_CALLABLE_MAPPING = "UNKNOWN_NOT_ASSERTED"

EXPECTED_LOCKED_IDS = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
EXPECTED_COVERED_IDS = (*EXPECTED_LOCKED_IDS, "F23")
EXPECTED_HISTORICAL_NON_AUTHORITIES = (
    "static/thesis.json",
    "corpus/formulas/lutar-lean__PROVEN_FORMULAS.md",
    "proofs/lutar-lean/**",
    "knowledge.json",
)
EXPECTED_SOURCE_ASSETS = (
    {
        "id": "locked-count",
        "repository": FORMAL_REPOSITORY,
        "commit": FORMAL_COMMIT,
        "path": "Lutar/Wave8/AxiomDisclosure.lean",
        "blob_sha": "bbf5deac32e1558eecf13115ea954393788d0e35",
        "role": "machine-enforced exact locked-eight disclosure",
    },
    {
        "id": "proved-formulas",
        "repository": FORMAL_REPOSITORY,
        "commit": FORMAL_COMMIT,
        "path": "Lutar/Puriq/Formulas/ProvedFormulas.lean",
        "blob_sha": "727115c587e8977428abe76d1313b171bcb23ff2",
        "role": "zero-sorry locked formula theorem source",
    },
    {
        "id": "lambda-boundary",
        "repository": FORMAL_REPOSITORY,
        "commit": FORMAL_COMMIT,
        "path": "Lutar/Round13/Lambda_Uniqueness.lean",
        "blob_sha": "b0f2c24d8b7fd4c9c87ad24eb2ed115a75288504",
        "role": "conditional Lambda theorem and unconditional counterexample source",
    },
)
EXPECTED_FORMULA_SEMANTICS = {
    "F1": (
        "LOCKED_PROVEN",
        True,
        ("f1_replay_hash_determinism", "f1_replay_trace_stable"),
        "proved-formulas",
        True,
    ),
    "F4": (
        "LOCKED_PROVEN",
        True,
        (
            "f4_khipu_reach_decreases",
            "f4_khipu_no_cycle",
            "f4_khipu_dag_acyclic_preserved",
        ),
        "proved-formulas",
        True,
    ),
    "F7": (
        "LOCKED_PROVEN",
        True,
        (
            "f7_chaski_enqueue_preserves_prefix",
            "f7_chaski_head_is_oldest",
            "f7_chaski_fifo_order",
            "f7_chaski_fifo_positional",
        ),
        "proved-formulas",
        True,
    ),
    "F11": (
        "LOCKED_PROVEN",
        True,
        ("f11_ayni_reciprocity_conservation",),
        "proved-formulas",
        True,
    ),
    "F12": (
        "LOCKED_PROVEN_LIMITED_FRAGMENT",
        True,
        ("f12_kuramoto_additive",),
        "proved-formulas",
        True,
    ),
    "F18": (
        "LOCKED_PROVEN",
        True,
        ("f18_reed_solomon_parity_count", "f18_erasure_tolerance"),
        "proved-formulas",
        True,
    ),
    "F19": (
        "LOCKED_PROVEN_LIMITED_FRAGMENT",
        True,
        ("f19_bekenstein_additive", "f19_budget_monotone"),
        "proved-formulas",
        True,
    ),
    "F22": (
        "LOCKED_PROVEN",
        True,
        (
            "f22_emit_appends_length",
            "f22_emit_strictly_greater",
            "f22_khipu_emit_monotone",
        ),
        "proved-formulas",
        True,
    ),
    "F23": (
        "CONJECTURE_1_ADVISORY",
        False,
        ("lambda_unique_of_factors", "maxAgg_ne_Lambda"),
        "lambda-boundary",
        False,
    ),
}

TOP_LEVEL_KEYS = frozenset(
    {"schema_version", "registry_digest", "signature", "payload"}
)
DIGEST_KEYS = frozenset({"algorithm", "canonicalization", "scope", "value"})
SIGNATURE_KEYS = frozenset({"status", "reason"})
PAYLOAD_KEYS = frozenset(
    {
        "registry_version",
        "doctrine_version",
        "authority",
        "coverage_scope",
        "exhaustive",
        "covered_formula_ids",
        "formal_source",
        "kernel_source",
        "locked_proven_count",
        "locked_proven_ids",
        "lambda",
        "policy",
        "source_assets",
        "formulas",
        "historical_non_authorities",
    }
)
FORMULA_KEYS = frozenset(
    {
        "id",
        "name",
        "maturity",
        "locked_proven",
        "theorem_refs",
        "source_asset",
        "scope",
        "caveat",
        "applicability_required",
        "can_constrain_execution",
        "can_authorize_action",
    }
)
PIN_RE = re.compile(r"^[0-9a-f]{40}$")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def compute_payload_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _assert_exact_keys(value: Any, expected: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} key set drift")
    return value


def validate_registry_document(
    document: dict[str, Any],
    *,
    root: Path = ROOT,
    verify_source_hashes: bool = True,
) -> None:
    """Validate the authority record without network access.

    ``root`` and ``verify_source_hashes`` are retained for caller compatibility.
    v2 source verification is an immutable Git identity check: repository,
    full commit, path and Git blob SHA must all match the reviewed record.
    """
    del root
    _assert_exact_keys(document, TOP_LEVEL_KEYS, "formula authority top-level")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported formula authority schema_version")

    digest = _assert_exact_keys(
        document.get("registry_digest"), DIGEST_KEYS, "formula authority digest"
    )
    if (
        digest.get("algorithm") != "sha256"
        or digest.get("canonicalization") != EXPECTED_CANONICALIZATION
        or digest.get("scope") != "payload"
    ):
        raise ValueError("formula authority digest contract drift")

    signature = _assert_exact_keys(
        document.get("signature"), SIGNATURE_KEYS, "formula authority signature"
    )
    if signature.get("status") != EXPECTED_SIGNATURE_STATUS:
        raise ValueError("formula authority must remain honestly UNSIGNED")
    if signature.get("reason") != EXPECTED_SIGNATURE_REASON:
        raise ValueError("formula authority unsigned reason drift")

    payload = _assert_exact_keys(
        document.get("payload"), PAYLOAD_KEYS, "formula authority payload"
    )
    actual_digest = compute_payload_digest(payload)
    if digest.get("value") != actual_digest:
        raise ValueError(
            f"formula authority digest mismatch: {digest.get('value')} != {actual_digest}"
        )

    fixed = {
        "registry_version": "2.0.0",
        "doctrine_version": "v11",
        "authority": "FORMAL_SOURCE_PINNED",
        "coverage_scope": EXPECTED_COVERAGE_SCOPE,
        "exhaustive": False,
    }
    for key, expected in fixed.items():
        if payload.get(key) != expected:
            raise ValueError(f"formula authority {key} drift")

    if tuple(payload.get("covered_formula_ids") or ()) != EXPECTED_COVERED_IDS:
        raise ValueError("formula authority covered formula IDs drift")
    if tuple(payload.get("locked_proven_ids") or ()) != EXPECTED_LOCKED_IDS:
        raise ValueError("formula authority locked set must be the exact formal eight")
    if payload.get("locked_proven_count") != len(EXPECTED_LOCKED_IDS):
        raise ValueError("formula authority locked count/list mismatch")

    formal = payload.get("formal_source")
    if not isinstance(formal, dict) or formal != {
        "repository": FORMAL_REPOSITORY,
        "commit": FORMAL_COMMIT,
        "locked_count_theorem": LOCKED_COUNT_THEOREM,
        "locked_count_source_asset": "locked-count",
    }:
        raise ValueError("formal source binding drift")
    if not PIN_RE.fullmatch(str(formal.get("commit") or "")):
        raise ValueError("formal source commit must be a full Git SHA")

    kernel = payload.get("kernel_source")
    if not isinstance(kernel, dict) or kernel != {
        "repository": FORMULA_KERNEL_REPOSITORY,
        "commit": FORMULA_KERNEL_COMMIT,
        "callable_formula_count": CALLABLE_FORMULA_COUNT,
        "f_id_to_callable_mapping": F_ID_TO_CALLABLE_MAPPING,
    }:
        raise ValueError("callable formula kernel binding drift")
    if not PIN_RE.fullmatch(str(kernel.get("commit") or "")):
        raise ValueError("formula kernel commit must be a full Git SHA")
    if kernel["f_id_to_callable_mapping"] != "UNKNOWN_NOT_ASSERTED":
        raise ValueError("an unproved F-ID-to-callable mapping may not be asserted")

    lambda_rule = payload.get("lambda")
    if lambda_rule != {
        "formula_id": "F23",
        "status": "CONJECTURE_1_ADVISORY",
        "can_authorize": False,
        "can_be_sole_allow_basis": False,
    }:
        raise ValueError("F23 Lambda must remain Conjecture 1 and non-authorizing")

    policy = payload.get("policy")
    if not isinstance(policy, dict) or set(policy) != {
        "identity_rule",
        "applicability_rule",
        "namespace_rule",
        "authorization_rule",
        "lambda_rule",
        "training_rule",
    }:
        raise ValueError("formula authority policy drift")
    if any(not isinstance(value, str) or len(value) < 40 for value in policy.values()):
        raise ValueError("formula authority policy statements are incomplete")

    assets = payload.get("source_assets")
    if not isinstance(assets, list) or assets != list(EXPECTED_SOURCE_ASSETS):
        raise ValueError("formula authority source asset identity drift")
    if verify_source_hashes:
        for asset in assets:
            if not (
                PIN_RE.fullmatch(asset["commit"])
                and PIN_RE.fullmatch(asset["blob_sha"])
                and asset["repository"] == FORMAL_REPOSITORY
            ):
                raise ValueError("formula authority source pin is not immutable")
    asset_ids = {asset["id"] for asset in assets}

    formulas = payload.get("formulas")
    if not isinstance(formulas, list) or len(formulas) != len(EXPECTED_COVERED_IDS):
        raise ValueError("formula authority coverage drift")
    ids = [entry.get("id") for entry in formulas if isinstance(entry, dict)]
    if tuple(ids) != EXPECTED_COVERED_IDS or len(ids) != len(set(ids)):
        raise ValueError("formula authority formula order, identity, or uniqueness drift")

    for entry in formulas:
        _assert_exact_keys(entry, FORMULA_KEYS, f"{entry.get('id')} formula")
        formula_id = entry["id"]
        expected = EXPECTED_FORMULA_SEMANTICS[formula_id]
        actual = (
            entry.get("maturity"),
            entry.get("locked_proven"),
            tuple(entry.get("theorem_refs") or ()),
            entry.get("source_asset"),
            entry.get("can_constrain_execution"),
        )
        if actual != expected:
            raise ValueError(f"{formula_id} semantic drift")
        if entry["source_asset"] not in asset_ids:
            raise ValueError(f"{formula_id} source asset is not pinned")
        if entry.get("applicability_required") is not True:
            raise ValueError(f"{formula_id} must require an applicability decision")
        if entry.get("can_authorize_action") is not False:
            raise ValueError(f"{formula_id} may not independently authorize an action")
        if not entry.get("scope") or not entry.get("caveat"):
            raise ValueError(f"{formula_id} scope/caveat must be explicit")

    flagged = tuple(
        entry["id"] for entry in formulas if entry.get("locked_proven") is True
    )
    if flagged != EXPECTED_LOCKED_IDS:
        raise ValueError("only the exact formal eight may be locked_proven")
    if any(
        entry["id"] == "F23" and entry["can_constrain_execution"]
        for entry in formulas
    ):
        raise ValueError("F23 Lambda cannot constrain or authorize execution")

    historical = tuple(payload.get("historical_non_authorities") or ())
    if historical != EXPECTED_HISTORICAL_NON_AUTHORITIES:
        raise ValueError("historical non-authority quarantine list drift")
    source_paths = {asset["path"] for asset in assets}
    if source_paths & set(historical):
        raise ValueError("historical snapshots cannot re-enter the authority source set")


def load_registry(
    *, verify: bool = True, path: Path = REGISTRY_PATH
) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if verify:
        validate_registry_document(document)
    return document


REGISTRY = load_registry(verify=True)
PAYLOAD = REGISTRY["payload"]
LOCKED_PROVEN_IDS = tuple(PAYLOAD["locked_proven_ids"])
LOCKED_PROVEN_COUNT = PAYLOAD["locked_proven_count"]
FORMULA_REGISTRY_DIGEST = REGISTRY["registry_digest"]["value"]
FORMULA_REGISTRY_SIGNATURE_STATUS = REGISTRY["signature"]["status"]
LAMBDA_STATUS = PAYLOAD["lambda"]["status"]


def formula(formula_id: str) -> dict[str, Any]:
    for entry in PAYLOAD["formulas"]:
        if entry["id"] == formula_id:
            return copy.deepcopy(entry)
    raise KeyError(formula_id)


def applicability_basis(
    formula_id: str,
    *,
    applicability: str,
    basis_sha256: str,
) -> dict[str, Any]:
    """Build a strict runtime applicability binding for Forge/Nemo envelopes."""
    entry = formula(formula_id)
    if applicability != "APPLIES":
        raise ValueError("only explicit APPLIES may enter a runtime formula binding")
    if not re.fullmatch(r"^[0-9a-f]{64}$", basis_sha256):
        raise ValueError("basis_sha256 must be 64 lowercase hex characters")
    return {
        "formula_id": formula_id,
        "maturity": entry["maturity"],
        "applicability": applicability,
        "basis_sha256": basis_sha256,
        "authority_digest": FORMULA_REGISTRY_DIGEST,
        "formal_source_commit": FORMAL_COMMIT,
        "can_constrain_execution": entry["can_constrain_execution"],
        "can_authorize_action": False,
    }


def receipt_basis() -> dict[str, Any]:
    """Return the non-signing formula authority fields bound into receipts."""
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_version": PAYLOAD["registry_version"],
        "authority": PAYLOAD["authority"],
        "authority_for_locked8": True,
        "coverage_scope": PAYLOAD["coverage_scope"],
        "exhaustive": PAYLOAD["exhaustive"],
        "formula_registry_digest": FORMULA_REGISTRY_DIGEST,
        "digest_algorithm": REGISTRY["registry_digest"]["algorithm"],
        "signature_status": FORMULA_REGISTRY_SIGNATURE_STATUS,
        "formal_source_repository": FORMAL_REPOSITORY,
        "formal_source_commit": FORMAL_COMMIT,
        "locked_count_theorem": LOCKED_COUNT_THEOREM,
        "locked_proven_count": LOCKED_PROVEN_COUNT,
        "locked_proven_ids": list(LOCKED_PROVEN_IDS),
        "formula_kernel_repository": FORMULA_KERNEL_REPOSITORY,
        "formula_kernel_commit": FORMULA_KERNEL_COMMIT,
        "callable_formula_count": CALLABLE_FORMULA_COUNT,
        "f_id_to_callable_mapping": F_ID_TO_CALLABLE_MAPPING,
        "lambda_status": LAMBDA_STATUS,
        "lambda_can_authorize": False,
        "historical_non_authorities": list(EXPECTED_HISTORICAL_NON_AUTHORITIES),
    }


__all__ = [
    "CALLABLE_FORMULA_COUNT",
    "EXPECTED_COVERED_IDS",
    "EXPECTED_HISTORICAL_NON_AUTHORITIES",
    "EXPECTED_LOCKED_IDS",
    "FORMAL_COMMIT",
    "FORMAL_REPOSITORY",
    "FORMULA_KERNEL_COMMIT",
    "FORMULA_KERNEL_REPOSITORY",
    "FORMULA_REGISTRY_DIGEST",
    "FORMULA_REGISTRY_SIGNATURE_STATUS",
    "F_ID_TO_CALLABLE_MAPPING",
    "LAMBDA_STATUS",
    "LOCKED_COUNT_THEOREM",
    "LOCKED_PROVEN_COUNT",
    "LOCKED_PROVEN_IDS",
    "PAYLOAD",
    "REGISTRY",
    "SCHEMA_VERSION",
    "applicability_basis",
    "compute_payload_digest",
    "formula",
    "load_registry",
    "receipt_basis",
    "validate_registry_document",
]
