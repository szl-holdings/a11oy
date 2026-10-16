# SPDX-License-Identifier: Apache-2.0
"""Strict, identity-bound acknowledgements; offline fakes and temporary storage only."""
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import szl_lake_ingest as ingest
import szl_lake_store as store
import szl_materials_predict as materials


def acknowledgement(receipt, organ, duplicate=False):
    return {"accepted": not duplicate, "duplicate": duplicate,
            "receipt_id": store.receipt_identity(receipt), "organ": organ}


@pytest.mark.parametrize("duplicate", [False, True])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), object()])
def test_non_json_append_ack_never_queues_mirror(duplicate, bad):
    receipt = {"id": "strict-append"}
    status = dict(acknowledgement(receipt, "materials", duplicate), extra=bad)
    led = Mock()
    led.append.return_value = status
    with patch.object(ingest, "get_default_ledger", return_value=led), \
         patch.object(ingest, "_mirror_to_dataset") as mirror:
        result = ingest.record_receipt(receipt, organ="materials")
    assert result["state"] == "UNKNOWN"
    assert result["accepted"] is False and result["duplicate"] is False
    assert result["receipt_id"] == receipt["id"]
    assert result["organ"] == "materials"
    json.dumps(result, allow_nan=False)
    led.append.assert_called_once()
    mirror.assert_not_called()


@pytest.mark.parametrize("duplicate", [False, True])
@pytest.mark.parametrize("organ", [None, "foreign"])
def test_foreign_or_missing_organ_never_authorizes_mirror(duplicate, organ):
    receipt = {"id": "organ-bound"}
    status = acknowledgement(receipt, organ, duplicate)
    if organ is None:
        status.pop("organ")
    led = Mock()
    led.append.return_value = status
    with patch.object(ingest, "get_default_ledger", return_value=led), \
         patch.object(ingest, "_mirror_to_dataset") as mirror:
        result = ingest.record_receipt(receipt, organ="Materials")
    assert result["state"] == "UNKNOWN"
    assert result["organ"] == "materials"
    mirror.assert_not_called()


@pytest.mark.parametrize("duplicate", [False, True])
@pytest.mark.parametrize("bad", [float("nan"), float("-inf"), object()])
def test_non_json_hook_ack_is_unknown_not_recorded(duplicate, bad):
    receipt = {"id": "strict-hook"}
    status = dict(acknowledgement(receipt, materials.RECEIPT_ORGAN, duplicate), extra=bad)
    with patch.object(ingest, "record_receipt", return_value=status) as hook:
        result = materials._ledger(receipt)
    assert result["state"] == "UNKNOWN" and result["recorded"] is None
    assert result["accepted"] is False and result["duplicate"] is False
    assert result["retry_admitted"] is False
    json.dumps(result, allow_nan=False)
    hook.assert_called_once()


@pytest.mark.parametrize("duplicate", [False, True])
@pytest.mark.parametrize("field", ["receipt_id", "organ"])
@pytest.mark.parametrize("replacement", [None, "foreign"])
def test_hook_ack_requires_exact_receipt_and_organ(duplicate, field, replacement):
    receipt = {"id": "expected-receipt"}
    status = acknowledgement(receipt, materials.RECEIPT_ORGAN, duplicate)
    if replacement is None:
        status.pop(field)
    else:
        status[field] = replacement
    with patch.object(ingest, "record_receipt", return_value=status) as hook:
        result = materials._ledger(receipt)
    assert result["state"] == "UNKNOWN" and result["recorded"] is None
    assert result["receipt_id"] == receipt["id"]
    assert result["retry_admitted"] is False
    hook.assert_called_once()


@pytest.mark.parametrize("field", ["ts", "timestamp", "time", "created_at"])
@pytest.mark.parametrize("timestamp", [10**100, -(10**100)])
def test_invalid_epoch_is_rejected_before_accessing_storage(field, timestamp):
    with patch.object(ingest, "get_default_ledger") as getter, \
         patch.object(ingest, "_mirror_to_dataset") as mirror:
        result = ingest.record_receipt({"id": "invalid-time", field: timestamp}, organ="materials")
    assert result["state"] == "REJECTED"
    assert result["write_attempted"] is False
    getter.assert_not_called()
    mirror.assert_not_called()


@pytest.mark.parametrize("duplicate", [False, True])
def test_valid_normalized_acknowledgement_retains_local_only_semantics(duplicate):
    receipt = {"id": "valid-ack", "organ": " Materials "}
    led = Mock()
    led.append.return_value = acknowledgement(receipt, "materials", duplicate)
    with patch.object(ingest, "get_default_ledger", return_value=led), \
         patch.object(ingest, "_mirror_to_dataset", return_value={"state": "queued"}) as mirror:
        result = ingest.record_receipt(receipt)
    assert result["state"] == ("LOCAL_DUPLICATE" if duplicate else "LOCAL_ACKNOWLEDGED")
    assert result["mirror"]["publication"] == "NOT_ACKNOWLEDGED"
    mirror.assert_called_once()


def test_direct_append_rejects_invalid_timestamp_without_files(tmp_path):
    led = store.ReceiptLedger(str(tmp_path / "ledger"))
    with pytest.raises((OverflowError, ValueError, OSError)):
        led.append({"id": "invalid-time", "organ": "materials", "ts": 10**100})
    assert not list(tmp_path.rglob("*"))


@pytest.mark.parametrize("duplicate", [False, True])
@pytest.mark.parametrize("malformed", [None, 0, 1, "false", "true", [], {}])
def test_hook_ack_requires_explicit_boolean_flags(duplicate, malformed):
    receipt = {"id": "boolean-flags"}
    status = acknowledgement(receipt, materials.RECEIPT_ORGAN, duplicate)
    status["accepted" if duplicate else "duplicate"] = malformed
    with patch.object(ingest, "record_receipt", return_value=status) as hook:
        result = materials._ledger(receipt)
    assert result["state"] == "UNKNOWN" and result["recorded"] is None
    assert result["retry_admitted"] is False
    hook.assert_called_once()


@pytest.mark.parametrize("duplicate", [False, True])
def test_hook_ack_requires_both_flags_to_be_present(duplicate):
    receipt = {"id": "missing-flag"}
    status = acknowledgement(receipt, materials.RECEIPT_ORGAN, duplicate)
    status.pop("accepted" if duplicate else "duplicate")
    with patch.object(ingest, "record_receipt", return_value=status) as hook:
        result = materials._ledger(receipt)
    assert result["state"] == "UNKNOWN" and result["recorded"] is None
    assert result["retry_admitted"] is False
    hook.assert_called_once()
