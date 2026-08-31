"""Regression tests for One Lathe Sigstore bundle metadata parsing."""
from __future__ import annotations

import pytest

from scripts.verify_lathe_snapshot_receipt import (
    MAX_PROTOBUF_INT64,
    _protobuf_nonnegative_int64,
    verified_rekor_log_index,
)


def envelope(log_index):
    return {
        "_sigstore": {
            "bundle": {
                "verificationMaterial": {
                    "tlogEntries": [{"logIndex": log_index}],
                }
            }
        }
    }


def test_rekor_index_accepts_current_protobuf_json_decimal_string():
    assert verified_rekor_log_index(envelope("240781641")) == 240781641


def test_rekor_index_accepts_legacy_json_integer():
    assert verified_rekor_log_index(envelope(240781641)) == 240781641


@pytest.mark.parametrize(
    "value",
    (
        True,
        False,
        None,
        -1,
        "-1",
        "+1",
        "01",
        " 1",
        "1 ",
        "1.0",
        "1e3",
        "",
        MAX_PROTOBUF_INT64 + 1,
        str(MAX_PROTOBUF_INT64 + 1),
    ),
)
def test_rekor_index_rejects_noncanonical_or_out_of_range_values(value):
    with pytest.raises(ValueError, match="invalid Rekor log index"):
        verified_rekor_log_index(envelope(value))


def test_rekor_index_requires_exactly_one_entry():
    with pytest.raises(ValueError, match="exactly one Rekor entry"):
        verified_rekor_log_index(
            {"_sigstore": {"bundle": {"verificationMaterial": {"tlogEntries": []}}}}
        )


def test_generic_int64_parser_preserves_zero_and_upper_bound():
    assert _protobuf_nonnegative_int64(0, field="field") == 0
    assert _protobuf_nonnegative_int64("0", field="field") == 0
    assert _protobuf_nonnegative_int64(MAX_PROTOBUF_INT64, field="field") == MAX_PROTOBUF_INT64
    assert _protobuf_nonnegative_int64(
        str(MAX_PROTOBUF_INT64), field="field"
    ) == MAX_PROTOBUF_INT64
