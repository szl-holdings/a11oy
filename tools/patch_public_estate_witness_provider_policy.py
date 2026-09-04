#!/usr/bin/env python3
"""Repair public-estate identity normalization without weakening truth boundaries."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "public_estate_live_witness.py"
MANIFEST = ROOT / "governance" / "public-estate.v1.json"
TESTS = ROOT / "tests" / "test_public_estate_live_witness.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_script() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'ALLOWED_REVISION_POLICIES = {"exact-default-branch", "declared-commit"}\n',
        'ALLOWED_REVISION_POLICIES = {"exact-default-branch", "declared-commit"}\n'
        'ALLOWED_SOURCE_REPOSITORY_POLICIES = {\n'
        '    "runtime-declared",\n'
        '    "manifest-fixed-runtime-revision",\n'
        '}\n'
        'ALLOWED_HF_REVISION_POLICIES = {"runtime-declared", "provider-observed"}\n',
        "policy constants",
    )

    old_validation = '''    policy = require_string(value.get("revision_policy"), f"{surface_id}.revision_policy")
    require(policy in ALLOWED_REVISION_POLICIES, f"{surface_id} has unknown revision policy")
    if policy == "exact-default-branch":
        require_string(value.get("default_branch"), f"{surface_id}.default_branch")
    required_paths = require_string_list(
'''
    new_validation = '''    policy = require_string(value.get("revision_policy"), f"{surface_id}.revision_policy")
    require(policy in ALLOWED_REVISION_POLICIES, f"{surface_id} has unknown revision policy")
    if policy == "exact-default-branch":
        require_string(value.get("default_branch"), f"{surface_id}.default_branch")

    source_policy = str(
        value.get("source_repository_policy", "runtime-declared")
    ).strip()
    require(
        source_policy in ALLOWED_SOURCE_REPOSITORY_POLICIES,
        f"{surface_id} has unknown source-repository policy",
    )
    if source_policy == "manifest-fixed-runtime-revision":
        require(
            policy == "exact-default-branch",
            f"{surface_id} manifest-fixed source policy requires exact-default-branch",
        )
    value["source_repository_policy"] = source_policy

    hf_policy = str(value.get("hf_revision_policy", "runtime-declared")).strip()
    require(
        hf_policy in ALLOWED_HF_REVISION_POLICIES,
        f"{surface_id} has unknown Hugging Face revision policy",
    )
    value["hf_revision_policy"] = hf_policy

    required_paths = require_string_list(
'''
    text = replace_once(text, old_validation, new_validation, "surface policy validation")

    old_selected_tail = '''    for canonical, names in aliases.items():
        for candidate in candidates:
            value = next((candidate[name] for name in names if name in candidate), None)
            if value not in (None, ""):
                selected[canonical] = value
                break
    return selected


def github_token() -> str | None:
'''
    new_selected_tail = '''    for canonical, names in aliases.items():
        for candidate in candidates:
            value = next((candidate[name] for name in names if name in candidate), None)
            if value not in (None, ""):
                selected[canonical] = value
                break

    # Killinchu's strict public route intentionally exposes build.revision rather
    # than duplicating a repository claim inside the process. Normalize only this
    # unambiguous nested runtime field; never treat an arbitrary deployment
    # revision as source identity.
    build = payload.get("build")
    if "source_revision" not in selected and isinstance(build, dict):
        revision = build.get("revision")
        if revision not in (None, ""):
            selected["source_revision"] = revision
    return selected


def apply_source_repository_policy(
    fields: Mapping[str, Any],
    payload: Mapping[str, Any],
    surface: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve a repository claim only under an explicit manifest policy.

    ``manifest-fixed-runtime-revision`` is deliberately narrow: the fixed route
    must identify the expected service, report an OBSERVED 40-hex revision, and
    disclose that the revision came from the deployer's ``SZL_GIT_SHA``. The
    manifest then supplies the immutable repository name. Missing or ambiguous
    evidence fails closed.
    """

    result = dict(fields)
    if result.get("source_repository"):
        return result
    if surface.get("source_repository_policy") != "manifest-fixed-runtime-revision":
        return result

    build = payload.get("build")
    require(isinstance(build, dict), "manifest-fixed source policy requires build object")
    require(
        str(payload.get("service", "")) == str(surface.get("id", "")),
        "manifest-fixed source policy service mismatch",
    )
    revision = str(result.get("source_revision", "")).lower()
    require(bool(SHA40.fullmatch(revision)), "manifest-fixed source revision is invalid")
    require(build.get("state") == "OBSERVED", "manifest-fixed source revision is not observed")
    require(
        build.get("revision_source") == "env:SZL_GIT_SHA",
        "manifest-fixed source revision has an untrusted origin",
    )
    result["source_repository"] = str(surface["deployment_source_repository"])
    result["source_repository_evidence"] = "MANIFEST_FIXED_RUNTIME_REVISION"
    return result


def github_token() -> str | None:
'''
    text = replace_once(text, old_selected_tail, new_selected_tail, "field normalization")

    text = replace_once(
        text,
        '    fields = selected_build_fields(build_payload or {})\n',
        '    fields = apply_source_repository_policy(\n'
        '        selected_build_fields(build_payload or {}),\n'
        '        build_payload or {},\n'
        '        surface,\n'
        '    )\n',
        "source policy application",
    )

    old_hf = '''        declared_hf_revision = str(fields.get("hf_revision", "")).lower()
        hf_proof = {
            "current_revision": current_hf_revision,
            "declared_revision": declared_hf_revision or None,
            "metadata": proof,
        }
        if not SHA40.fullmatch(declared_hf_revision):
            failures.append("hf_revision: missing or invalid")
        elif declared_hf_revision != current_hf_revision:
            failures.append(
                f"hf_revision: metadata is {current_hf_revision}, build declares {declared_hf_revision}"
            )
'''
    new_hf = '''        hf_revision_policy = str(surface["hf_revision_policy"])
        declared_hf_revision = str(fields.get("hf_revision", "")).lower()
        hf_proof = {
            "policy": hf_revision_policy,
            "current_revision": current_hf_revision,
            "declared_revision": declared_hf_revision or None,
            "metadata": proof,
        }
        if hf_revision_policy == "provider-observed":
            # Provider metadata is evidence of the current Space repository tip,
            # not a claim that the running process can introspect that tip. Keep
            # the two facts separate in the receipt.
            fields["hf_revision_observed_by_witness"] = current_hf_revision
            fields["hf_revision_evidence"] = "HUGGING_FACE_PROVIDER_API"
        elif not SHA40.fullmatch(declared_hf_revision):
            failures.append("hf_revision: missing or invalid")
        elif declared_hf_revision != current_hf_revision:
            failures.append(
                f"hf_revision: metadata is {current_hf_revision}, build declares {declared_hf_revision}"
            )
'''
    text = replace_once(text, old_hf, new_hf, "Hugging Face policy")
    SCRIPT.write_text(text, encoding="utf-8")


def patch_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    killinchu = next(
        item for item in manifest["public_products"] if item["id"] == "killinchu"
    )
    killinchu["source_repository_policy"] = "manifest-fixed-runtime-revision"
    killinchu["hf_revision_policy"] = "provider-observed"
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    addition = r'''


def test_killinchu_identity_policies_are_explicit_and_narrow():
    manifest = witness.load_and_validate_manifest(MANIFEST)
    killinchu = next(
        item for item in manifest["public_products"] if item["id"] == "killinchu"
    )
    assert killinchu["source_repository_policy"] == "manifest-fixed-runtime-revision"
    assert killinchu["hf_revision_policy"] == "provider-observed"
    for item in manifest["platforms"] + manifest["public_products"]:
        if item["id"] != "killinchu":
            assert item["source_repository_policy"] == "runtime-declared"
            assert item["hf_revision_policy"] == "runtime-declared"


def test_killinchu_runtime_shape_requires_fixed_service_and_deployer_origin():
    manifest = witness.load_and_validate_manifest(MANIFEST)
    surface = next(
        item for item in manifest["public_products"] if item["id"] == "killinchu"
    )
    payload = {
        "status": "OBSERVED",
        "service": "killinchu",
        "build": {
            "state": "OBSERVED",
            "revision": "d" * 40,
            "revision_source": "env:SZL_GIT_SHA",
        },
    }
    fields = witness.apply_source_repository_policy(
        witness.selected_build_fields(payload), payload, surface
    )
    assert fields["source_revision"] == "d" * 40
    assert fields["source_repository"] == "szl-holdings/killinchu"
    assert fields["source_repository_evidence"] == "MANIFEST_FIXED_RUNTIME_REVISION"

    wrong_service = copy.deepcopy(payload)
    wrong_service["service"] = "other"
    with pytest.raises(witness.ContractError, match="service mismatch"):
        witness.apply_source_repository_policy(
            witness.selected_build_fields(wrong_service), wrong_service, surface
        )

    wrong_origin = copy.deepcopy(payload)
    wrong_origin["build"]["revision_source"] = "request:caller"
    with pytest.raises(witness.ContractError, match="untrusted origin"):
        witness.apply_source_repository_policy(
            witness.selected_build_fields(wrong_origin), wrong_origin, surface
        )


def test_manifest_rejects_unknown_identity_policies(tmp_path: Path):
    value = raw_manifest()
    value["public_products"][0]["source_repository_policy"] = "guess"
    with pytest.raises(witness.ContractError, match="unknown source-repository policy"):
        witness.load_and_validate_manifest(write_manifest(tmp_path, value))

    value = raw_manifest()
    value["public_products"][0]["hf_revision_policy"] = "trust-me"
    with pytest.raises(witness.ContractError, match="unknown Hugging Face revision policy"):
        witness.load_and_validate_manifest(write_manifest(tmp_path, value))
'''
    if "test_killinchu_identity_policies_are_explicit_and_narrow" in text:
        raise RuntimeError("tests already patched")
    TESTS.write_text(text.rstrip() + addition + "\n", encoding="utf-8")


def main() -> int:
    patch_script()
    patch_manifest()
    patch_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
