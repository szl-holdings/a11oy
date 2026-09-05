#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate and render every public-estate consumer from one A11oy contract.

The product topology lives in ``static/shared/public-estate-contract.v1.json``.
Current public Hub inventory remains measured in
``docs/huggingface-ecosystem-manifest.json``. This program combines those two
sources without contacting a provider, validates every measured Space against
either a topology binding or an explicit inventory-only classification, and
emits deterministic Markdown fragments for the GitHub organization, Hugging
Face organization card, and proof estate. Inventory is observational and never
promotes a Space into the separately governed keep-list.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "static/shared/public-estate-contract.v1.json"
HF_MANIFEST = ROOT / "docs/huggingface-ecosystem-manifest.json"
KEEP_POLICY = ROOT / "docs/series-a/hf-space-keep-list.yaml"
OUTPUTS = {
    "github": ROOT / "docs/generated/github-org-public-estate.md",
    "huggingface": ROOT / "docs/generated/huggingface-org-card.md",
    "proof": ROOT / "docs/generated/a11oy-net-public-estate.md",
}


class ContractError(RuntimeError):
    """Raised when public-estate topology cannot be proven exactly."""


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ContractError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain a JSON object")
    return value


def _unique(values: Iterable[str], label: str) -> list[str]:
    rows = list(values)
    if any(not isinstance(row, str) or not row for row in rows):
        raise ContractError(f"{label} contains a blank or non-string value")
    if len(rows) != len(set(rows)):
        raise ContractError(f"{label} contains duplicates")
    return rows


def topology_spaces(contract: dict[str, Any]) -> list[str]:
    spaces: list[str] = [contract["fabric"]["huggingFaceRepository"]]
    for row in contract["publicDomainBodies"]:
        spaces.extend(row["huggingFaceRepositories"])
    for row in contract["supportingSystems"]:
        spaces.extend(row["huggingFaceRepositories"])
    spaces.extend(contract["laboratorySurfaces"])
    return sorted(_unique(spaces, "Hugging Face topology bindings"), key=str.casefold)


def inventory_only_spaces(contract: dict[str, Any]) -> list[str]:
    rows = contract.get("inventoryOnlyHuggingFaceRepositories")
    if not isinstance(rows, list):
        raise ContractError("inventory-only Hub classifications are missing")
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ContractError("inventory-only Hub classification must be an object")
        if row.get("classification") != "INVENTORY_ONLY":
            raise ContractError("inventory-only Hub classification drifted")
        if row.get("governedKeep") is not False:
            raise ContractError("inventory-only Space cannot be a governed keeper")
        if row.get("disposition") != "FOLD":
            raise ContractError("inventory-only Space must retain its FOLD disposition")
        if row.get("policySource") != str(KEEP_POLICY.relative_to(ROOT)):
            raise ContractError("inventory-only Space must cite the canonical keep policy")
        ids.append(row.get("id"))
    return sorted(_unique(ids, "inventory-only Hub Spaces"), key=str.casefold)


def governed_keep_spaces(path: Path = KEEP_POLICY) -> list[str]:
    """Read the top-level ``keep`` IDs from the dependency-free policy subset."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ContractError(f"cannot load canonical keep policy: {exc}") from exc

    try:
        start = lines.index("keep:") + 1
    except ValueError as exc:
        raise ContractError("canonical keep policy has no top-level keep section") from exc

    ids: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith(" "):
            break
        if line.startswith("  - id: "):
            identifier = line.removeprefix("  - id: ").strip()
            if not identifier or any(character.isspace() for character in identifier):
                raise ContractError("canonical keep policy contains an invalid keeper id")
            ids.append(identifier)
    if not ids:
        raise ContractError("canonical keep policy has no keeper ids")
    return sorted(_unique(ids, "canonical governed keep-set"), key=str.casefold)


def measured_spaces(manifest: dict[str, Any]) -> list[str]:
    inventory = manifest.get("inventory")
    if not isinstance(inventory, dict):
        raise ContractError("Hub manifest inventory is missing")
    rows = inventory.get("spaces")
    if not isinstance(rows, list):
        raise ContractError("Hub manifest Space inventory is missing")
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    return sorted(_unique(ids, "measured Hub Space inventory"), key=str.casefold)


def validate(contract: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    if contract.get("schema") != "szl.public-estate/v1":
        raise ContractError("unsupported public-estate schema")
    if contract.get("version") != "1.0.1":
        raise ContractError("unsupported public-estate version")

    canonical = contract.get("canonical")
    if not isinstance(canonical, dict):
        raise ContractError("canonical origins are missing")
    required_origins = {
        "product": "https://a-11-oy.com",
        "proof": "https://a11oy.net",
        "source": "https://github.com/szl-holdings/a11oy",
        "githubOrganization": "https://github.com/szl-holdings",
        "huggingFaceOrganization": "https://huggingface.co/SZLHOLDINGS",
    }
    if canonical != required_origins:
        raise ContractError("canonical origin contract drifted")

    bodies = contract.get("publicDomainBodies")
    engines = contract.get("internalEngines")
    if not isinstance(bodies, list) or not isinstance(engines, list):
        raise ContractError("public bodies or internal engines are missing")
    if [row.get("id") for row in bodies] != ["immune", "lyte", "terra", "counsel", "finance"]:
        raise ContractError("five-domain-body contract drifted")
    if len(engines) != 6:
        raise ContractError("exactly six internal engines are required")
    _unique([row.get("id") for row in bodies], "public body ids")
    _unique([row.get("id") for row in engines], "engine ids")

    formula = next((row for row in engines if row.get("id") == "formula-kernel"), None)
    if not isinstance(formula, dict):
        raise ContractError("formula-kernel engine is missing")
    if formula.get("lockedProvenCount") != 8:
        raise ContractError("locked-proven formula count must remain exactly eight")
    if formula.get("lambdaStatus") != "CONJECTURE_1_OPEN_ADVISORY_ONLY":
        raise ContractError("Lambda truth state drifted")

    authority = contract.get("authority")
    if authority != {
        "externalWrites": "DISABLED_BY_DEFAULT",
        "publicEffectors": [],
        "automaticRemediation": False,
        "productionAuthorization": False,
        "humanApprovalRequired": True,
    }:
        raise ContractError("public authority boundary drifted")

    topology = topology_spaces(contract)
    inventory_only = inventory_only_spaces(contract)
    governed_keep = governed_keep_spaces()
    observed = measured_spaces(manifest)
    overlap = sorted(set(topology) & set(inventory_only), key=str.casefold)
    if overlap:
        raise ContractError(
            f"inventory-only Spaces cannot be topology bindings; overlap={overlap}"
        )
    governed_overlap = sorted(
        set(inventory_only) & set(governed_keep), key=str.casefold
    )
    if governed_overlap:
        raise ContractError(
            "inventory-only Spaces cannot be governed keepers; "
            f"overlap={governed_overlap}"
        )
    declared = sorted(topology + inventory_only, key=str.casefold)
    if declared != observed:
        missing = sorted(set(declared) - set(observed), key=str.casefold)
        undeclared = sorted(set(observed) - set(declared), key=str.casefold)
        raise ContractError(
            f"Hub inventory classification mismatch; missing={missing}, "
            f"undeclared={undeclared}"
        )

    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        raise ContractError("Hub manifest counts are missing")
    if counts.get("spaces") != len(observed):
        raise ContractError("Hub Space count does not match inventory")
    for key in ("models", "datasets", "spaces"):
        if not isinstance(counts.get(key), int) or counts[key] < 0:
            raise ContractError(f"invalid Hub count: {key}")

    payload = {
        # Bind every rendered mapping, truth state, and authority field, not
        # just counts: different public claims must produce different hashes.
        "contractSha256": hashlib.sha256(
            json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "contractSchema": contract["schema"],
        "contractVersion": contract["version"],
        "publicDomainBodies": len(bodies),
        "internalEngines": len(engines),
        "huggingFaceTopologyBindings": topology,
        "huggingFaceInventoryOnly": inventory_only,
        "governedKeepSet": governed_keep,
        "governedKeepPolicySource": str(KEEP_POLICY.relative_to(ROOT)),
        "keepPolicySha256": hashlib.sha256(KEEP_POLICY.read_bytes()).hexdigest(),
        "huggingFaceCounts": counts,
        "huggingFaceObservedAt": manifest.get("observedAt"),
    }
    payload["alignmentSha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def _body_lines(contract: dict[str, Any]) -> list[str]:
    rows = []
    for body in contract["publicDomainBodies"]:
        hf = ", ".join(f"`{repo}`" for repo in body["huggingFaceRepositories"])
        rows.append(
            f"- **{body['name']}** — {body['domain']} · "
            f"[`{body['githubRepository']}`](https://github.com/{body['githubRepository']}) · {hf}"
        )
    return rows


def _inventory_policy_line(evidence: dict[str, Any]) -> str:
    inventory_only = ", ".join(
        f"`{space}`" for space in evidence["huggingFaceInventoryOnly"]
    )
    return (
        "Measured Hub inventory is observational and is not the governed keep-list. "
        f"Inventory-only / FOLD (not governed keepers): {inventory_only}. "
        "Canonical keep policy: "
        f"`{evidence['governedKeepPolicySource']}`."
    )


def render_github(contract: dict[str, Any], evidence: dict[str, Any]) -> str:
    counts = evidence["huggingFaceCounts"]
    lines = [
        "<!-- BEGIN SZL PUBLIC ESTATE — GENERATED -->",
        "## One public estate",
        "",
        "[A11oy](https://a-11-oy.com) is the product and command fabric; "
        "[a11oy.net](https://a11oy.net) is the proof and diligence surface. "
        "GitHub is canonical source, and Hugging Face is the generated runtime and artifact estate.",
        "",
        f"**Measured Hub inventory:** {counts['spaces']} public Spaces · "
        f"{counts['models']} models · {counts['datasets']} datasets "
        f"as of `{evidence['huggingFaceObservedAt']}`.",
        _inventory_policy_line(evidence),
        "",
        "### Five public domain bodies",
        "",
        *_body_lines(contract),
        "",
        "### Six internal engines",
        "",
    ]
    lines.extend(
        f"- **{row['name']}** — `{row['authority']}`"
        for row in contract["internalEngines"]
    )
    lines += [
        "",
        "All public claims use explicit truth states. External writes are disabled by default, "
        "public effectors are empty, production authorization is false, and consequential action requires human approval.",
        "",
        f"Alignment receipt: `{evidence['alignmentSha256']}`.",
        "<!-- END SZL PUBLIC ESTATE — GENERATED -->",
        "",
    ]
    return "\n".join(lines)


def render_huggingface(contract: dict[str, Any], evidence: dict[str, Any]) -> str:
    counts = evidence["huggingFaceCounts"]
    lines = [
        "<!-- BEGIN SZL PUBLIC ESTATE — GENERATED -->",
        "# SZL Holdings on Hugging Face",
        "",
        "This organization is the generated model, dataset, and runtime estate for "
        "[A11oy](https://a-11-oy.com). Canonical source and release evidence live in "
        "[GitHub](https://github.com/szl-holdings); public proof lives at "
        "[a11oy.net](https://a11oy.net).",
        "",
        f"**Current public inventory:** {counts['spaces']} Spaces · {counts['models']} models · "
        f"{counts['datasets']} datasets (`{evidence['huggingFaceObservedAt']}`).",
        _inventory_policy_line(evidence),
        "",
        "## Product bodies",
        "",
        *_body_lines(contract),
        "",
        "## Runtime truth boundary",
        "",
        "A repository card is not a production certificate. Runtime, source revision, evidence freshness, "
        "and receipt state are verified separately. Λ remains Conjecture 1 and advisory only. "
        "No public model or formula may authorize consequential action.",
        "",
        f"Alignment receipt: `{evidence['alignmentSha256']}`.",
        "<!-- END SZL PUBLIC ESTATE — GENERATED -->",
        "",
    ]
    return "\n".join(lines)


def render_proof(contract: dict[str, Any], evidence: dict[str, Any]) -> str:
    lines = [
        "<!-- BEGIN SZL PUBLIC ESTATE — GENERATED -->",
        "## Product → source → runtime map",
        "",
        "This proof surface follows the A11oy public-estate contract. Product, GitHub source, "
        "Hugging Face runtime, and evidence state are distinct and must agree before a lane is called current.",
        _inventory_policy_line(evidence),
        "",
        "| Product body | GitHub source | Hugging Face runtime | Truth class |",
        "|---|---|---|---|",
    ]
    for body in contract["publicDomainBodies"]:
        hf = "<br>".join(body["huggingFaceRepositories"])
        lines.append(
            f"| {body['name']} | `{body['githubRepository']}` | `{hf}` | `{body['truth']}` |"
        )
    lines += [
        "",
        f"Contract alignment SHA-256: `{evidence['alignmentSha256']}`.",
        "<!-- END SZL PUBLIC ESTATE — GENERATED -->",
        "",
    ]
    return "\n".join(lines)


def generated() -> dict[Path, str]:
    contract = load_json(CONTRACT)
    manifest = load_json(HF_MANIFEST)
    evidence = validate(contract, manifest)
    return {
        OUTPUTS["github"]: render_github(contract, evidence),
        OUTPUTS["huggingface"]: render_huggingface(contract, evidence),
        OUTPUTS["proof"]: render_proof(contract, evidence),
    }


def apply(check: bool) -> None:
    drift: list[str] = []
    for path, content in generated().items():
        normalized = content.rstrip() + "\n"
        if check:
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current != normalized:
                drift.append(str(path.relative_to(ROOT)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(normalized, encoding="utf-8")
    if drift:
        raise ContractError(f"generated public-estate outputs are stale: {drift}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    apply(args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
