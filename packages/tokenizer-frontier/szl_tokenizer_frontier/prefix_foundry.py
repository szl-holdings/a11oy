from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .canonical import canonical_json, sha3_256, write_json_atomic
from .profile import TokenizerProfile
from .tokenizer import Tokenizer


TENANT_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
ALLOWED_KINDS = {
    "system_prompt",
    "persona",
    "tool_schema",
    "enterprise_header",
    "code_analysis_scaffold",
    "retrieval_header",
}


@dataclass(frozen=True)
class PrefixObject:
    object_id: str
    tenant: str
    kind: str
    text_digest_sha3_256: str
    tokenizer_profile: dict
    tokenizer_profile_digest_sha3_256: str
    token_ids: tuple[int, ...]
    offsets: tuple[tuple[int, int], ...]
    metadata: dict[str, Any]

    def record(self) -> dict:
        return {
            "schema": "szl.tokenized-prefix/v1",
            "object_id": self.object_id,
            "tenant": self.tenant,
            "kind": self.kind,
            "text_digest_sha3_256": self.text_digest_sha3_256,
            "tokenizer_profile": self.tokenizer_profile,
            "tokenizer_profile_digest_sha3_256": self.tokenizer_profile_digest_sha3_256,
            "token_ids": list(self.token_ids),
            "offsets": [list(item) for item in self.offsets],
            "metadata": self.metadata,
            "raw_text_persisted": False,
        }


class PrefixStore:
    """Append-only, tenant-bound content-addressed prefix-object store."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, tenant: str, object_id: str) -> Path:
        if not TENANT_PATTERN.fullmatch(tenant):
            raise ValueError("tenant must match [A-Za-z0-9._-]{1,128}")
        digest = object_id.removeprefix("prefix:")
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("invalid prefix object ID")
        return self.root / sha3_256(tenant) / f"{digest}.json"

    def put(self, prefix: PrefixObject) -> Path:
        path = self._path(prefix.tenant, prefix.object_id)
        record = prefix.record()
        if path.exists():
            if path.read_bytes().strip() != canonical_json(record):
                raise RuntimeError("content-addressed prefix object collision")
            return path
        write_json_atomic(path, record)
        return path

    def read(self, tenant: str, object_id: str) -> dict:
        path = self._path(tenant, object_id)
        import json

        return json.loads(path.read_text(encoding="utf-8"))


class PrefixFoundry:
    def __init__(self, store: PrefixStore):
        self.store = store

    def build(
        self,
        *,
        tenant: str,
        kind: str,
        text: str,
        profile: TokenizerProfile,
        tokenizer: Tokenizer,
        metadata: Mapping[str, Any] | None = None,
    ) -> PrefixObject:
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"unsupported prefix kind: {kind}")
        if not text:
            raise ValueError("prefix text is required")
        encoded = tokenizer.encode_with_offsets(text)
        identity = {
            "tenant": tenant,
            "kind": kind,
            "text_digest_sha3_256": sha3_256(text),
            "tokenizer_profile_digest_sha3_256": profile.digest_sha3_256,
            "token_ids": list(encoded.token_ids),
            "offsets": [list(item) for item in encoded.offsets],
            "metadata": dict(metadata or {}),
        }
        prefix = PrefixObject(
            object_id="prefix:" + sha3_256(identity),
            tenant=tenant,
            kind=kind,
            text_digest_sha3_256=identity["text_digest_sha3_256"],
            tokenizer_profile=profile.record(),
            tokenizer_profile_digest_sha3_256=profile.digest_sha3_256,
            token_ids=encoded.token_ids,
            offsets=encoded.offsets,
            metadata=dict(metadata or {}),
        )
        self.store.put(prefix)
        return prefix
