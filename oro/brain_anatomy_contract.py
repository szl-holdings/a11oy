"""Read-only evidence bridge for ORO, Second Brain and Living Anatomy.

No network calls, execution authority, or inferred proof promotions.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

LOCKED_PROVEN = frozenset({'F1', 'F4', 'F7', 'F11', 'F12', 'F18', 'F19', 'F22'})


@dataclass(frozen=True)
class EvidenceHandle:
    source: str
    revision: str
    digest: str
    classification: str = 'PUBLIC'

    def validate(self) -> None:
        if not self.source or not self.revision:
            raise ValueError('Source and immutable revision required')
        if len(self.digest) != 64 or any(c not in '0123456789abcdef' for c in self.digest):
            raise ValueError('Expected lowercase SHA-256 digest')
        if self.classification != 'PUBLIC':
            raise PermissionError('Public bridge refuses restricted evidence')


def evidence_projection(handle: EvidenceHandle, *, formula: str | None = None,
                        proof_status: str = 'UNVERIFIED') -> dict[str, Any]:
    """Return only validated handles; never expose corpus or grant execution."""
    handle.validate()
    allowed = {'PROVEN', 'CONDITIONAL', 'CONJECTURE', 'REFUTED', 'EMPIRICAL', 'UNVERIFIED'}
    if proof_status not in allowed:
        raise ValueError('Unknown proof status')
    if proof_status == 'PROVEN' and formula not in LOCKED_PROVEN:
        raise ValueError('Only the locked eight can use this proven projection')
    return {'source': handle.source, 'revision': handle.revision,
            'sha256': handle.digest, 'classification': handle.classification,
            'formula': formula, 'proof_status': proof_status,
            'execution_authority': False, 'promotion_authority': False}


def projection_digest(projection: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(projection), sort_keys=True, separators=(',', ':'),
                         ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()
