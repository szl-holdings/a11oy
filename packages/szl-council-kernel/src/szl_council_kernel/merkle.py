from __future__ import annotations

"""Portable local Merkle transparency mechanics.

The tree uses domain-separated SHA-256 leaf/node hashes and promotes an unpaired
node unchanged to the next level. It is a reference transparency mechanism and
is not labeled as a hosted RFC 9162 service.
"""

import hashlib
from dataclasses import dataclass
from typing import Iterable

from .canonical import digest_bytes
from .errors import IntegrityError, ValidationError


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _levels(leaves: Iterable[bytes]) -> list[list[bytes]]:
    first = [leaf_hash(item) for item in leaves]
    if not first:
        return [[]]
    levels = [first]
    current = first
    while len(current) > 1:
        next_level: list[bytes] = []
        for index in range(0, len(current), 2):
            if index + 1 < len(current):
                next_level.append(node_hash(current[index], current[index + 1]))
            else:
                next_level.append(current[index])
        levels.append(next_level)
        current = next_level
    return levels


def merkle_root(leaves: Iterable[bytes]) -> str:
    levels = _levels(leaves)
    if not levels[0]:
        return digest_bytes(b"")
    return "sha256:" + levels[-1][0].hex()


@dataclass(frozen=True, slots=True)
class InclusionProof:
    leaf_index: int
    tree_size: int
    leaf_digest: str
    root_hash: str
    path: tuple[tuple[str, str], ...]
    schema: str = "szl.local-merkle-inclusion/v1"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "leaf_index": self.leaf_index,
            "tree_size": self.tree_size,
            "leaf_digest": self.leaf_digest,
            "root_hash": self.root_hash,
            "path": [{"side": side, "hash": digest} for side, digest in self.path],
        }


def inclusion_proof(leaves: list[bytes], index: int) -> InclusionProof:
    if index < 0 or index >= len(leaves):
        raise ValidationError("Merkle inclusion index is outside tree")
    levels = _levels(leaves)
    current_index = index
    path: list[tuple[str, str]] = []
    for level in levels[:-1]:
        if current_index % 2 == 0:
            sibling = current_index + 1
            if sibling < len(level):
                path.append(("RIGHT", "sha256:" + level[sibling].hex()))
        else:
            sibling = current_index - 1
            path.append(("LEFT", "sha256:" + level[sibling].hex()))
        current_index //= 2
    return InclusionProof(
        leaf_index=index,
        tree_size=len(leaves),
        leaf_digest="sha256:" + leaf_hash(leaves[index]).hex(),
        root_hash="sha256:" + levels[-1][0].hex(),
        path=tuple(path),
    )


def verify_inclusion(data: bytes, proof: InclusionProof) -> bool:
    current = leaf_hash(data)
    for side, digest in proof.path:
        try:
            sibling = bytes.fromhex(digest.split(":", 1)[1])
        except Exception as exc:
            raise IntegrityError("invalid Merkle sibling digest") from exc
        if side == "LEFT":
            current = node_hash(sibling, current)
        elif side == "RIGHT":
            current = node_hash(current, sibling)
        else:
            raise IntegrityError("invalid Merkle path side")
    return "sha256:" + current.hex() == proof.root_hash
