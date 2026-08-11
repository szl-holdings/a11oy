from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Mapping

from .canonical import sha3_256


@dataclass(frozen=True)
class TokenizerProfile:
    tokenizer_id: str
    tokenizer_revision: str
    family: str
    normalization: str
    special_tokens: Mapping[str, int] = field(default_factory=dict)
    added_tokens: tuple[tuple[str, int], ...] = ()
    pre_tokenizer: str = "UNAVAILABLE"
    post_processor: str = "UNAVAILABLE"

    def __post_init__(self) -> None:
        for name in [
            "tokenizer_id",
            "tokenizer_revision",
            "family",
            "normalization",
        ]:
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        if len(set(self.special_tokens.values())) != len(self.special_tokens):
            raise ValueError("special token IDs must be unique")

    def record(self) -> dict:
        value = asdict(self)
        value["special_tokens"] = dict(sorted(self.special_tokens.items()))
        value["added_tokens"] = [list(item) for item in sorted(self.added_tokens)]
        return value

    @property
    def digest_sha3_256(self) -> str:
        return sha3_256(self.record())
