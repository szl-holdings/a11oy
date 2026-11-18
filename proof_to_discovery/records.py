#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Evidence records, witness tiers, and fail-closed record verification.

A record is a claim about one obligation. The engine never accepts a record
at face value: every record is checked for content integrity, signature
validity (when its tier requires one), signer registration, and freshness
before it can influence a verdict. The invariant from the A11oy
Proof-to-Discovery doctrine is enforced here: MODEL_GENERATED records are
annotations only and can never make a record admissible, no matter how
confident their text sounds.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum

from . import ed25519


class WitnessTier(IntEnum):
    """Ordered witness tiers. Higher tiers are strictly stronger evidence."""

    MODEL_GENERATED = 10
    CONTENT_HASH_BINDING = 20
    SIGNED_WITNESS = 30
    OWNER_DIRECTIVE = 40


TIER_NAMES = {tier.value: tier.name for tier in WitnessTier}

STANCE_SUPPORTS = "supports"
STANCE_REFUTES = "refutes"
VALID_STANCES = frozenset({STANCE_SUPPORTS, STANCE_REFUTES})


def canonical_payload_bytes(payload: dict) -> bytes:
    """Deterministic JSON encoding used for every hash and signature."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def parse_instant(value: str) -> int:
    """Parse a strict UTC ISO-8601 instant; raise on anything else."""
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        raise ValueError(f"malformed instant: {value!r}")
    try:
        moment = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError(f"malformed instant: {value!r}") from error
    return int(moment.timestamp())


@dataclass(frozen=True)
class EvidenceRecord:
    """One witnessed claim about one obligation of one decision.

    ``content_sha256`` and ``signature`` cover the binding bytes:
    canonical JSON payload bytes, the witness tier name, and the observation
    instant. Changing any of them invalidates the record.
    """

    record_id: str
    obligation_id: str
    stance: str
    witness_tier: str
    payload: dict
    content_sha256: str
    observed_at: str
    signature: str | None = None
    signer_key: str | None = None
    source_uri: str = ""

    def binding_bytes(self) -> bytes:
        return (
            canonical_payload_bytes(self.payload)
            + b"\n"
            + self.stance.encode("ascii")
            + b"\n"
            + self.witness_tier.encode("ascii")
            + b"\n"
            + self.observed_at.encode("ascii")
        )

    @classmethod
    def build(
        cls,
        *,
        record_id: str,
        obligation_id: str,
        stance: str,
        witness_tier: str,
        payload: dict,
        observed_at: str,
        signer_seed: bytes | None = None,
        source_uri: str = "",
    ) -> "EvidenceRecord":
        """Construct an honestly hashed (and, above hash tier, signed) record."""
        if witness_tier not in TIER_NAMES.values() and witness_tier not in TIER_NAMES:
            raise ValueError(f"unknown witness tier: {witness_tier!r}")
        if stance not in VALID_STANCES:
            raise ValueError(f"unknown stance: {stance!r}")
        signature: str | None = None
        signer_key: str | None = None
        if WitnessTier[witness_tier] >= WitnessTier.SIGNED_WITNESS:
            if signer_seed is None:
                raise ValueError(f"{witness_tier} records require a signer seed")
            signer_key = ed25519.public_key(signer_seed).hex()
        record = cls(
            record_id=record_id,
            obligation_id=obligation_id,
            stance=stance,
            witness_tier=witness_tier,
            payload=payload,
            content_sha256="",
            observed_at=observed_at,
            signature=signature,
            signer_key=signer_key,
            source_uri=source_uri,
        )
        digest = hashlib.sha256(record.binding_bytes()).hexdigest()
        if signer_seed is not None and WitnessTier[witness_tier] >= WitnessTier.SIGNED_WITNESS:
            signature = ed25519.sign(signer_seed, record.binding_bytes()).hex()
        return cls(
            record_id=record_id,
            obligation_id=obligation_id,
            stance=stance,
            witness_tier=witness_tier,
            payload=payload,
            content_sha256=digest,
            observed_at=observed_at,
            signature=signature,
            signer_key=signer_key,
            source_uri=source_uri,
        )


@dataclass(frozen=True)
class RecordCheck:
    """Fail-closed verdict for one record against one obligation's requirements."""

    record_id: str
    intact: bool
    tier_sufficient: bool
    signature_valid: bool
    signer_registered: bool
    fresh: bool
    admissible: bool
    notes: tuple[str, ...] = field(default_factory=tuple)


def check_record(
    record: EvidenceRecord,
    *,
    required_tier: WitnessTier,
    freshness_seconds: int | None,
    evaluated_at: str,
    policy,
) -> RecordCheck:
    """Verify one record. Any failed check makes the record inadmissible."""
    notes: list[str] = []
    record_tier_name = record.witness_tier
    if record.stance not in VALID_STANCES:
        notes.append(f"record {record.record_id} has unknown stance {record.stance!r}")
    if record_tier_name not in TIER_NAMES.values():
        return RecordCheck(record.record_id, False, False, False, False, False, False,
                           (f"record {record.record_id} has unknown witness tier {record_tier_name!r}",))
    tier = WitnessTier[record_tier_name]

    intact = hashlib.sha256(record.binding_bytes()).hexdigest() == record.content_sha256
    if not intact:
        notes.append(f"record {record.record_id} content hash mismatch; treated as corrupted")

    tier_sufficient = tier >= required_tier
    if not tier_sufficient:
        notes.append(
            f"record {record.record_id} witness tier {tier.name} below required "
            f"{required_tier.name}"
        )

    signature_valid = False
    signer_registered = False
    if tier == WitnessTier.MODEL_GENERATED:
        notes.append(
            f"record {record.record_id} is MODEL_GENERATED; stored as annotation only and "
            "never admissible for any obligation"
        )
    elif tier == WitnessTier.CONTENT_HASH_BINDING:
        signature_valid = record.signature is None
        signer_registered = record.signer_key is None
        if not signature_valid:
            notes.append(
                f"record {record.record_id} carries a signature under CONTENT_HASH_BINDING; "
                "misclassified record refused"
            )
    else:
        if record.signature is None or record.signer_key is None:
            notes.append(f"record {record.record_id} at {tier.name} lacks a signature or signer key")
        else:
            try:
                signature_valid = ed25519.verify(
                    bytes.fromhex(record.signer_key),
                    record.binding_bytes(),
                    bytes.fromhex(record.signature),
                )
            except ValueError:
                signature_valid = False
            if not signature_valid:
                notes.append(f"record {record.record_id} signature does not verify")
            registered = (
                policy.owner_keys
                if tier == WitnessTier.OWNER_DIRECTIVE
                else policy.witness_keys
            )
            signer_registered = record.signer_key in registered
            if signature_valid and not signer_registered:
                notes.append(
                    f"record {record.record_id} signed by an unregistered key for tier {tier.name}"
                )

    fresh = True
    if freshness_seconds is not None:
        try:
            age = parse_instant(evaluated_at) - parse_instant(record.observed_at)
            fresh = 0 <= age <= freshness_seconds
            if age < 0:
                notes.append(f"record {record.record_id} is observed in the future; refused")
            elif not fresh:
                notes.append(
                    f"record {record.record_id} is stale (age {age}s exceeds bound {freshness_seconds}s)"
                )
        except ValueError:
            fresh = False
            notes.append(f"record {record.record_id} has an unparseable observation instant")

    admissible = (
        record.stance in VALID_STANCES
        and intact
        and tier_sufficient
        and tier != WitnessTier.MODEL_GENERATED
        and signature_valid
        and signer_registered
        and fresh
    )
    return RecordCheck(
        record_id=record.record_id,
        intact=intact,
        tier_sufficient=tier_sufficient,
        signature_valid=signature_valid,
        signer_registered=signer_registered,
        fresh=fresh,
        admissible=admissible,
        notes=tuple(notes),
    )
