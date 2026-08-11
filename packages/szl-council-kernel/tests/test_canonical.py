from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from szl_council_kernel.canonical import (
    b64url_decode,
    b64url_encode,
    canonical_json_bytes,
    canonical_json_text,
    digest_bytes,
    digest_object,
    isoformat_utc,
    normalize,
    parse_utc,
    require_digest,
    require_identifier,
)
from szl_council_kernel.errors import ValidationError


def test_dict_order_is_canonical():
    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'


def test_set_is_stably_sorted():
    assert normalize({"z", "a"}) == ["a", "z"]


def test_bytes_are_explicitly_tagged():
    assert normalize(b"abc") == {"$bytes": "YWJj"}


def test_decimal_is_stable_string():
    assert normalize(Decimal("1.2300")) == "1.23"


def test_non_finite_float_rejected():
    with pytest.raises(ValidationError):
        canonical_json_bytes({"x": float("nan")})


def test_unsupported_object_rejected():
    with pytest.raises(ValidationError):
        canonical_json_bytes(object())


def test_datetime_normalized_to_utc_seconds():
    assert isoformat_utc(datetime(2026, 8, 3, 8, tzinfo=UTC)) == "2026-08-03T08:00:00Z"


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        parse_utc(datetime(2026, 8, 3))


def test_digest_prefix_and_length():
    value = digest_object({"x": 1})
    assert value.startswith("sha256:") and len(value) == 71
    assert require_digest(value) == value


def test_sha3_digest_supported():
    assert digest_bytes(b"x", algorithm="sha3-256").startswith("sha3-256:")


def test_identifier_validation():
    assert require_identifier("spiffe://td/workload/a") == "spiffe://td/workload/a"
    with pytest.raises(ValidationError):
        require_identifier(" has spaces ")


def test_base64url_roundtrip():
    assert b64url_decode(b64url_encode(b"\x00binary\xff")) == b"\x00binary\xff"


def test_pretty_json_ends_newline():
    assert canonical_json_text({"a": 1}, pretty=True).endswith("\n")


def test_dataclass_normalization():
    @dataclass
    class X:
        a: int
    assert normalize(X(1)) == {"a": 1}


@pytest.mark.parametrize("value", ["a=", "a!", "A"])
def test_base64url_rejects_noncanonical_or_invalid(value):
    with pytest.raises(ValidationError):
        b64url_decode(value)


def test_canonical_json_rejects_non_interoperable_integer():
    with pytest.raises(ValidationError):
        canonical_json_bytes(2**53)
