from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from ..errors import ValidationError

_TRUST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_PATH = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@/-]+$")


@dataclass(frozen=True, slots=True)
class SpiffeIdentity:
    trust_domain: str
    path: str

    @classmethod
    def parse(cls, value: str) -> "SpiffeIdentity":
        if not isinstance(value, str) or not value or len(value) > 2048:
            raise ValidationError("SPIFFE ID must be a bounded string")
        parsed = urlsplit(value)
        if parsed.scheme != "spiffe" or not parsed.netloc or not parsed.path.startswith("/"):
            raise ValidationError("invalid SPIFFE ID")
        if parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port:
            raise ValidationError("SPIFFE ID contains forbidden URL components")
        trust_domain = parsed.hostname
        if trust_domain is None or parsed.netloc != trust_domain or trust_domain != trust_domain.lower():
            raise ValidationError("SPIFFE trust domain must be canonical lowercase DNS form")
        if len(trust_domain) > 253 or trust_domain.endswith("."):
            raise ValidationError("SPIFFE trust domain is invalid")
        labels = trust_domain.split(".")
        if any(not _TRUST_LABEL.fullmatch(label) for label in labels):
            raise ValidationError("SPIFFE trust domain labels are invalid")
        path = parsed.path
        if (
            not _PATH.fullmatch(path)
            or "//" in path
            or "\\" in path
            or "%" in path
            or any(segment in {"", ".", ".."} for segment in path[1:].split("/"))
        ):
            raise ValidationError("SPIFFE workload path is non-canonical")
        return cls(trust_domain=trust_domain, path=path)

    def __str__(self) -> str:
        return f"spiffe://{self.trust_domain}{self.path}"
