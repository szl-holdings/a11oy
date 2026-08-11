from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class EncodedDocument:
    token_ids: tuple[int, ...]
    offsets: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if len(self.token_ids) != len(self.offsets):
            raise ValueError("token_ids and offsets must have equal length")
        last_end = 0
        for start, end in self.offsets:
            if start < 0 or end < start or start < last_end:
                raise ValueError("offsets must be ordered non-overlapping spans")
            last_end = end


class Tokenizer(Protocol):
    def encode_with_offsets(self, text: str) -> EncodedDocument: ...


class Utf8ByteTokenizer:
    """Deterministic test/reference tokenizer with one token per UTF-8 byte."""

    def encode_with_offsets(self, text: str) -> EncodedDocument:
        data = text.encode("utf-8")
        return EncodedDocument(
            token_ids=tuple(data),
            offsets=tuple((index, index + 1) for index in range(len(data))),
        )


class MappingTokenizer:
    """Fixture adapter for exact, deterministic contract tests."""

    def __init__(self, mapping: dict[str, EncodedDocument]):
        self.mapping = dict(mapping)

    def encode_with_offsets(self, text: str) -> EncodedDocument:
        try:
            return self.mapping[text]
        except KeyError as error:
            raise KeyError(f"no encoded fixture for {text!r}") from error
