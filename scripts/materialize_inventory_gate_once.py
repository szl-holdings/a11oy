#!/usr/bin/env python3
"""One-use exact-blob source repair; never publishes to a remote service."""
from pathlib import Path
import hashlib
import json

ROOT = Path.cwd()
path = ROOT / 'scripts/audit_huggingface_ecosystem.py'
raw = path.read_bytes()
blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
if blob != '6a963fdf602fed8705c9bd704705354763d97f92':
    raise SystemExit('Collector changed: preserve concurrent work and review a new diff')
source = raw.decode('utf-8')

def replace_once(old: str, new: str) -> None:
    global source
    if source.count(old) != 1:
        raise SystemExit('Reviewed patch anchor no longer unique: ' + old[:100])
    source = source.replace(old, new, 1)

helpers = '''def _gate_mode(value: Any) -> str | None:
    """Normalize only provider-documented gate states; unknown states fail closed."""
    if value is None or value is False:
        return None
    if value is True:
        return "enabled"
    if isinstance(value, str) and value in {"auto", "manual"}:
        return value
    raise ValueError("gated must be false, true, auto, manual, or absent")


def _public_metadata_digest(value: Any) -> str:
    """Commit public API metadata only, never substitute it for README bytes."""
    if value is not None and not isinstance(value, dict):
        raise ValueError("public card metadata must be an object or null")
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > 262144:
        raise ValueError("public card metadata exceeds the 256 KiB evidence budget")
    return hashlib.sha256(encoded).hexdigest()


def _restricted_card_observation(item: dict[str, Any], mode: str) -> dict[str, Any]:
    """Record the declared gate without attempting any protected file download."""
    metadata = item.get("cardData")
    digest = _public_metadata_digest(metadata)
    # Copy canonical JSON so mutable provider dictionaries cannot alter evidence.
    metadata = json.loads(json.dumps(metadata, allow_nan=False))
    return {
        "state": "ACCESS_RESTRICTED",
        "scope": "PUBLIC_METADATA_ONLY",
        "gateMode": mode,
        "metadata": metadata,
        "metadataSha256": digest,
    }


def _validate_card_evidence(item: dict[str, Any], *, label: str) -> None:
    digest = item.get("cardSemanticSha256")
    observation = item.get("cardObservation")
    if item.get("gated") is True:
        if digest is not None:
            raise ValueError(f"{label} gated card must not claim a README digest")
        expected_keys = {"state", "scope", "gateMode", "metadata", "metadataSha256"}
        if not isinstance(observation, dict) or set(observation) != expected_keys:
            raise ValueError(f"{label} gated card requires explicit restricted evidence")
        if (observation["state"] != "ACCESS_RESTRICTED"
                or observation["scope"] != "PUBLIC_METADATA_ONLY"
                or observation["gateMode"] not in {"auto", "manual", "enabled"}):
            raise ValueError(f"{label} restricted card scope or gate mode is invalid")
        actual = _public_metadata_digest(observation["metadata"])
        if observation["metadataSha256"] != actual:
            raise ValueError(f"{label} public metadata digest mismatch")
        return
    if observation is not None:
        raise ValueError(f"{label} ungated card cannot declare restricted evidence")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise ValueError(f"{label} cardSemanticSha256 must be a SHA-256 digest")


'''
replace_once('def validate_snapshot_revisions(\n', helpers + 'def validate_snapshot_revisions(\n')
replace_once('''            if (
                not isinstance(stored_card_digest, str)
                or not SHA256_RE.fullmatch(stored_card_digest)
            ):
                raise ValueError(
                    f"{item_id} cardSemanticSha256 must be a SHA-256 digest"
                )
''', '''            _validate_card_evidence(item, label=item_id)
''')
replace_once('''            live_card_digest = live_item.get("cardSemanticSha256")
''', '')
replace_once('''            if (
                not isinstance(live_card_digest, str)
                or not SHA256_RE.fullmatch(live_card_digest)
            ):
                raise ValueError(
                    f"live {item_id} cardSemanticSha256 must be a SHA-256 digest"
                )
''', '''            _validate_card_evidence(live_item, label=f"live {item_id}")
''')
replace_once('''            if live_sha == stored_sha:
''', '''            if item.get("gated") or live_item.get("gated"):
                if item.get("gated") != live_item.get("gated"):
                    raise ValueError(f"{item_id} gate policy changed; refresh the snapshot")
                # Unreadable README changes cannot be called source-only changes.
                # Pin every restricted revision, even when public metadata matches.
                if live_sha != stored_sha:
                    raise ValueError(
                        f"{item_id} restricted revision changed; refresh the snapshot"
                    )
            if live_sha == stored_sha:
''')
replace_once('''            card_digest = item.get("cardSemanticSha256")
''', '')
replace_once('''            if (
                not isinstance(card_digest, str)
                or not SHA256_RE.fullmatch(card_digest)
            ):
                raise ValueError(
                    f"{item_id} cardSemanticSha256 must be a SHA-256 digest"
                )
''', '''            _validate_card_evidence(item, label=item_id)
''')
replace_once('''            item.pop("sha", None)
            item.pop("lastModified", None)
''', '''            # A restricted README is unobserved: never ignore revision drift.
            if item.get("gated") is not True:
                item.pop("sha", None)
                item.pop("lastModified", None)
''')
replace_once('''    card_digest = card_semantic_sha256(
        fetch_card_markdown(str(item_id), repo_type, revision)
    )
    return {
''', '''    mode = _gate_mode(item.get("gated"))
    if mode is not None:
        card_fields = {
            "cardSemanticSha256": None,
            "cardObservation": _restricted_card_observation(item, mode),
        }
    else:
        card_fields = {"cardSemanticSha256": card_semantic_sha256(
            fetch_card_markdown(str(item_id), repo_type, revision)
        )}
    return {
''')
replace_once('''        "cardSemanticSha256": card_digest,
''', '''        **card_fields,
''')
replace_once('''        "schemaVersion": 1,
''', '''        "schemaVersion": 2,
''')
replace_once('''            "revisionFields": (
''', '''            "cardEvidenceBoundary": (
                "Gated repositories are inventoried from public API metadata only. "
                "Their cardObservation is ACCESS_RESTRICTED and cardSemanticSha256 "
                "is null; metadataSha256 is not a README or weight digest. "
                "No access request, authentication, or protected download is attempted. "
                "Restricted revisions remain exact-pinned in --check."
            ),
            "revisionFields": (
''')
replace_once('''                "Every item has sha and lastModified snapshot evidence plus a "
                "cardSemanticSha256 claim digest at observedAt; --check verifies "
''', '''                "Every item has sha and lastModified snapshot evidence. Ungated "
                "cards have a cardSemanticSha256 claim digest at observedAt; "
                "gated cards have explicit restricted metadata evidence. --check verifies "
''')
compile(source, str(path), 'exec')
path.write_text(source, encoding='utf-8')

schema_path = ROOT / 'docs/huggingface-ecosystem-manifest.schema.json'
schema = json.loads(schema_path.read_text(encoding='utf-8'))
if schema['properties']['schemaVersion'] != {'const': 1}:
    raise SystemExit('Manifest schema changed; review before migration')
schema['properties']['schemaVersion'] = {'const': 2}
item = schema['$defs']['items']['items']
item['properties']['cardSemanticSha256']['type'] = ['string', 'null']
item['properties']['cardObservation'] = {
    'type': 'object', 'additionalProperties': False,
    'required': ['state', 'scope', 'gateMode', 'metadata', 'metadataSha256'],
    'properties': {
        'state': {'const': 'ACCESS_RESTRICTED'},
        'scope': {'const': 'PUBLIC_METADATA_ONLY'},
        'gateMode': {'enum': ['auto', 'manual', 'enabled']},
        'metadata': {'type': ['object', 'null']},
        'metadataSha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
    },
}
item['allOf'] = [{
    'if': {'required': ['gated'], 'properties': {'gated': {'const': True}}},
    'then': {'required': ['cardObservation'],
             'properties': {'cardSemanticSha256': {'type': 'null'}}},
    'else': {'properties': {'cardSemanticSha256': {'type': 'string'}},
             'not': {'required': ['cardObservation']}},
}]
schema['properties']['inventoryScope']['required'].append('cardEvidenceBoundary')
schema['properties']['inventoryScope']['properties']['cardEvidenceBoundary'] = {'type': 'string'}
schema_path.write_text(json.dumps(schema, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'source_blob_before': blob, 'source_sha256_after': hashlib.sha256(source.encode()).hexdigest(), 'schema_version': 2}))
