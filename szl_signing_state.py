#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Provenance: passive projections of lifecycle-owned signer observations.

The owner samples the already loaded local backend, never configuration on GET.
This record is not an authorization, source attestation, or signing exercise.
No permission/capability promotion API is provided: those require a separately
reviewed binding to authorized, retained, verified write evidence.
"""

from dataclasses import dataclass, replace
import math
import re
import threading
import time


SCHEMA = "szl.signing-state/v1"
FINGERPRINT_ALGORITHM = "SHA256_STRIPPED_ASCII_PEM"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except (OverflowError, ValueError):
        return False


@dataclass(frozen=True)
class SignerObservation:
    """Public metadata only; constructed by the signer lifecycle, not a request."""

    boot_id: str | None
    generation: int
    sequence: int
    observed_at: str
    observed_mono: float
    max_age_seconds: float
    configured: bool | None
    key_source: str
    backend_loaded: bool
    backend_state: str
    verification_key_fingerprint: str | None
    loaded_key_fingerprint: str | None
    expected_key_fingerprint: str | None


def project(observation, now_mono):
    """Recompute freshness from original observations; never accept derived JSON."""
    valid = type(observation) is SignerObservation
    o = observation if valid else None
    clock_valid = bool(o is not None and _finite(now_mono)
                       and _finite(o.observed_mono) and _finite(o.max_age_seconds)
                       and o.max_age_seconds > 0 and now_mono >= o.observed_mono)
    age = float(now_mono - o.observed_mono) if clock_valid else None
    fresh = bool(clock_valid and age < o.max_age_seconds)
    fingerprint = o.verification_key_fingerprint if o else None
    known = isinstance(fingerprint, str) and bool(_DIGEST.fullmatch(fingerprint))
    loaded_fingerprint = o.loaded_key_fingerprint if o else None
    expected = o.expected_key_fingerprint if o else None
    match = ("UNKNOWN" if not known or not loaded_fingerprint or not expected else
             "MATCH" if fingerprint == loaded_fingerprint == expected else "MISMATCH")
    loaded = bool(o and o.backend_loaded is True and o.backend_state == "LOADED_LOCAL")
    key_available = bool(fresh and loaded and match == "MATCH")
    blockers = []
    if not valid:
        blockers.append("SIGNER_OBSERVATION_UNAVAILABLE")
    if not clock_valid:
        blockers.append("OBSERVATION_CLOCK_INVALID")
    elif not fresh:
        blockers.append("SIGNER_OBSERVATION_EXPIRED")
    if not (o and o.boot_id):
        blockers.append("RUNTIME_BOOT_ID_UNKNOWN")
    if not loaded:
        blockers.append("SIGNER_BACKEND_UNAVAILABLE")
    if not known:
        blockers.append("VERIFICATION_KEY_UNKNOWN")
    if match != "MATCH":
        blockers.append("KEY_AGREEMENT_" + match)
    blockers.extend(("PERMISSION_UNOBSERVED", "RETAINED_SIGNING_CAPABILITY_UNOBSERVED"))
    return {
        "schema": SCHEMA,
        "evidence_class": "DECLARED",
        "scope": "PROCESS_LOCAL_SIGNER_METADATA",
        "runtime_boot_id": o.boot_id if o else None,
        "generation": o.generation if o else None,
        "observation_sequence": o.sequence if o else None,
        "observed_at": o.observed_at if o else None,
        "age_seconds": age,
        "max_age_seconds": o.max_age_seconds if o and _finite(o.max_age_seconds) else None,
        "freshness": "FRESH" if fresh else "UNKNOWN" if not clock_valid else "STALE",
        "verification_key_known": known,
        "verification_key_scope": "CAPTURED_SHARED_SIGNER_IDENTITY",
        "historical_verification_keys_evaluated": False,
        "public_key_fingerprint": fingerprint if known else None,
        "fingerprint_algorithm": FINGERPRINT_ALGORITHM,
        "expected_key_fingerprint": expected,
        "loaded_key_fingerprint": loaded_fingerprint,
        "key_agreement": match,
        "signer_configured": o.configured if o else None,
        "configuration_state": ("UNKNOWN" if not o or o.configured is None else
                                "CONFIGURED" if o.configured else "UNCONFIGURED"),
        "key_source": o.key_source if o else "unavailable",
        "backend": {
            "kind": "PROCESS_LOCAL_ECDSA_P256",
            "loaded": loaded,
            "state": o.backend_state if o else "UNAVAILABLE",
            "reachability": "NOT_APPLICABLE_LOCAL",
            "operating_capability_observed": False,
        },
        "key_material_available": key_available,
        "permission": {"state": "UNKNOWN", "evidence": None},
        "observed_capability": {"state": "UNKNOWN", "evidence": None},
        "signing_ready": False,
        "execution_authorized": False,
        "non_repudiation": "UNKNOWN",
        "source_binding": "UNKNOWN",
        "source_status_endpoint": "/api/a11oy/v1/series-a/status",
        "blockers": blockers,
        "sign_on_read": False,
    }


class SigningState:
    """Atomic immutable observations; only sample() is a lifecycle write."""

    def __init__(self, *, clock=None, max_age_seconds=60.0):
        if not _finite(max_age_seconds) or max_age_seconds <= 0:
            raise ValueError("positive finite signing observation TTL required")
        self._clock = clock or time.monotonic
        self._max_age = max_age_seconds
        self._observation = None
        self._lock = threading.Lock()

    def sample(self, *, boot_id, observed_at, configured, key_source,
               backend_loaded, backend_state, verification_key_fingerprint=None,
               loaded_key_fingerprint=None, expected_key_fingerprint=None):
        """Called at startup/periodic lifecycle refresh, never from a status read."""
        if (configured is not None and type(configured) is not bool) or type(backend_loaded) is not bool:
            raise ValueError("signer facts must be booleans")
        if backend_state not in {"LOADED_LOCAL", "ABSENT", "UNAVAILABLE"}:
            raise ValueError("unsupported backend state")
        if backend_loaded != (backend_state == "LOADED_LOCAL"):
            raise ValueError("contradictory backend state")
        if boot_id is not None and (type(boot_id) is not str or not 0 < len(boot_id) <= 160):
            raise ValueError("invalid runtime boot identifier")
        if type(observed_at) is not str or not observed_at or len(observed_at) > 64:
            raise ValueError("invalid observation timestamp")
        if type(key_source) is not str or len(key_source) > 512:
            raise ValueError("invalid source label")
        for value in (verification_key_fingerprint, loaded_key_fingerprint, expected_key_fingerprint):
            if value is not None and (type(value) is not str or not _DIGEST.fullmatch(value)):
                raise ValueError("invalid public fingerprint")
        now = self._clock()
        if not _finite(now):
            raise ValueError("invalid monotonic clock")
        facts = (boot_id, configured, key_source, backend_loaded, backend_state,
                 verification_key_fingerprint, loaded_key_fingerprint, expected_key_fingerprint)
        with self._lock:
            old = self._observation
            old_facts = ((old.boot_id, old.configured, old.key_source, old.backend_loaded,
                          old.backend_state, old.verification_key_fingerprint,
                          old.loaded_key_fingerprint, old.expected_key_fingerprint) if old else None)
            generation = old.generation + (facts != old_facts) if old else 1
            self._observation = SignerObservation(
                boot_id, generation, old.sequence + 1 if old else 1, observed_at,
                float(now), self._max_age, configured, key_source, backend_loaded,
                backend_state, verification_key_fingerprint, loaded_key_fingerprint,
                expected_key_fingerprint)
        return self._observation

    def read(self):
        with self._lock:
            observation = self._observation
        try:
            now = self._clock()
        except Exception:
            now = None
        return project(observation, now)

    def invalidate(self):
        """Lifecycle failure revokes availability without inventing fresh evidence."""
        with self._lock:
            old = self._observation
            if old is not None:
                self._observation = replace(
                    old, generation=old.generation + 1, sequence=old.sequence + 1,
                    backend_loaded=False, backend_state="UNAVAILABLE",
                    loaded_key_fingerprint=None)


def read_state(app):
    """The registered owner is local state; fallback never loads a key or signs."""
    owner = getattr(app.state, "szl_signing_state", None)
    return owner.read() if type(owner) is SigningState else project(None, None)


def legacy_signer_view(state):
    """Compatibility only: DSSE-LIVE historically means local key availability."""
    available = state["key_material_available"]
    source = state["key_source"]
    persistent = source.startswith("persistent:")
    status = "DSSE-LIVE" if available else (
        "ABSENT" if state["backend"]["state"] == "ABSENT" else "UNAVAILABLE")
    return {
        "status": status,
        "signing_available": available,
        "scheme": "DSSEv1 / ECDSA-P256-SHA256" if available else "UNAVAILABLE",
        "scope": "RUNTIME_KEY_AVAILABILITY",
        "legacy_status_deprecated": True,
        "legacy_status_semantics": "LOCAL_KEY_METADATA_ONLY_NOT_SIGNING_READINESS",
        "receipt_verification_asserted": False,
        "signing_ready": state["signing_ready"],
        "public_key_fingerprint": state["public_key_fingerprint"],
        "key_source": source,
        "key_scope": "DEPLOYMENT_PERSISTENT" if persistent else (
            "PROCESS_BOOT_EPHEMERAL" if source == "ephemeral" else "UNAVAILABLE"),
        "key_lifetime": "UNTIL_SECRET_ROTATION" if persistent else (
            "UNTIL_PROCESS_RESTART" if source == "ephemeral" else "UNAVAILABLE"),
        "signing_state": state,
    }
