"""Read-only evidence bridge for ORO, Second Brain and Living Anatomy.

No network calls, execution authority, or inferred proof promotions.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

LOCKED_PROVEN = frozenset({'F1', 'F4', 'F7', 'F11', 'F12', 'F18', 'F19', 'F22'})
_SOURCE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]*\Z')
_REVISION = re.compile(r'(?:commit:[0-9a-f]{40}|sha256:[0-9a-f]{64})\Z')
_SHA256 = re.compile(r'[0-9a-f]{64}\Z')
_FORMULA = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,63}\Z')


@dataclass(frozen=True)
class EvidenceHandle:
    source: str
    revision: str
    digest: str
    classification: str = 'PUBLIC'

    def validate(self) -> None:
        if self.classification != 'PUBLIC':
            raise PermissionError('Public bridge refuses restricted evidence')
        if (not isinstance(self.source, str) or len(self.source) > 256
                or not _SOURCE.fullmatch(self.source)
                or any(part in ('', '.', '..') for part in self.source.split('/'))):
            raise ValueError('Expected bounded public source identifier')
        if not isinstance(self.revision, str) or not _REVISION.fullmatch(self.revision):
            raise ValueError('Expected immutable commit or SHA-256 revision')
        if not isinstance(self.digest, str) or not _SHA256.fullmatch(self.digest):
            raise ValueError('Expected lowercase SHA-256 digest')


def evidence_projection(handle: EvidenceHandle, *, formula: str | None = None,
                        proof_status: str = 'UNVERIFIED') -> dict[str, Any]:
    """Return only validated handles; never expose corpus or grant execution."""
    handle.validate()
    allowed = {'PROVEN', 'CONDITIONAL', 'CONJECTURE', 'REFUTED', 'EMPIRICAL', 'UNVERIFIED'}
    if not isinstance(proof_status, str) or proof_status not in allowed:
        raise ValueError('Unknown proof status')
    if proof_status == 'PROVEN':
        raise ValueError('This read-only bridge cannot verify proof status')
    if formula is not None and (not isinstance(formula, str)
                                or not _FORMULA.fullmatch(formula)):
        raise ValueError('Expected bounded public formula identifier')
    return {'source': handle.source, 'revision': handle.revision,
            'sha256': handle.digest, 'classification': handle.classification,
            'formula': formula, 'proof_status': proof_status,
            'execution_authority': False, 'promotion_authority': False}


def projection_digest(projection: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(projection), sort_keys=True, separators=(',', ':'),
                         ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()
