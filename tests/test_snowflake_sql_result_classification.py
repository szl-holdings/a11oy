"""Proposed synthetic SQL-API response tests; NOT original runner/kit tests.

Never run against an account. Run only in an authorized network-disabled sandbox.
No source execution or test pass is claimed by this unapplied proposal.
"""
import importlib
import json
import unittest
from unittest.mock import patch


def completed(rows):
    return {
        "code": "090001",
        "sqlState": "00000",
        "resultSetMetaData": {
            "format": "jsonv2",
            "numRows": len(rows),
            "rowType": [{"name": "SYNTHETIC_TABLE"}],
            "partitionInfo": [{"rowCount": len(rows)}],
        },
        "data": rows,
    }


class SyntheticSnowflakeSQLResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Block real network before importing the implementation under test.
        for target in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
            blocked = patch(target, side_effect=AssertionError("network forbidden"))
            blocked.start()
            cls.addClassCleanup(blocked.stop)
        cls.environment = patch.dict("os.environ", {}, clear=True)
        cls.environment.start()
        cls.addClassCleanup(cls.environment.stop)
        cls.mod = importlib.import_module(
            "szl_connectors.warehouse.warehouse_connectors")

    def read_synthetic(self, status, payload):
        connector = self.mod.SnowflakeConnector()
        with patch.object(connector, "_primary_missing", return_value=False), \
             patch.object(connector, "_base_url", return_value="https://fixture.invalid/api/v2"), \
             patch.object(connector, "_auth_header", return_value={}), \
             patch.object(self.mod, "http_json", return_value=(status, payload)) as http:
            result = connector.read()
        self.assertEqual(http.call_count, 1)  # no GET polling or cancel POST
        args, kw = http.call_args
        self.assertEqual(args[0], "https://fixture.invalid/api/v2/statements")
        self.assertEqual(kw["method"], "POST")
        self.assertEqual(json.loads(kw["data"]), {
            "statement": "SHOW TABLES LIMIT 10", "timeout": 30})
        self.assertEqual(kw["headers"]["Accept"], "application/json")
        self.assertNotIn("Authorization", kw["headers"])
        return result

    def assert_unproved(self, status, payload, reason=None):
        result = self.read_synthetic(status, payload)
        self.assertEqual(result.state, self.mod.State.ERROR)
        self.assertFalse(result.live)
        self.assertEqual(result.records, [])
        if reason:
            self.assertIn(reason, result.note)

    def test_202_is_pending_even_with_rows(self):
        for payload in ({"code": "333334", "statementHandle": "synthetic-handle"},
                        completed([]), completed([["SYNTHETIC"]]), None):
            with self.subTest(payload=payload):
                self.assert_unproved(202, payload, "pending")

    def test_non_200_statuses_are_not_results(self):
        for status in (0, 201, 204, 400, 401, 403, 404, 408, 422, 429, 500, 503):
            with self.subTest(status=status):
                self.assert_unproved(status, completed([["SYNTHETIC"]]), f"HTTP {status}")

    def test_valid_empty_nonempty_null_and_ten_rows(self):
        for rows in ([], [["SYNTHETIC"]], [[None]], [[str(i)] for i in range(10)]):
            with self.subTest(rows=rows):
                result = self.read_synthetic(200, completed(rows))
                self.assertEqual(result.state, self.mod.State.CONNECTED)
                self.assertTrue(result.live)  # synthetic assertion only, not a qualification
                self.assertEqual(result.records, [{"row": r} for r in rows])

    def test_missing_or_malformed_bodies_and_rows(self):
        for payload in (None, [], "", {}, {"data": []}):
            with self.subTest(payload=payload):
                self.assert_unproved(200, payload)
        for value in (None, "", {}, "SYNTHETIC", [None], ["SYNTHETIC"],
                      [{"row": "SYNTHETIC"}], [[1]], [[False]], [["A", "B"]]):
            payload = completed([])
            payload["data"] = value
            payload["resultSetMetaData"]["numRows"] = len(value) if isinstance(value, list) else 0
            # Isolate data-shape failures from the independent partition validator.
            del payload["resultSetMetaData"]["partitionInfo"]
            with self.subTest(data=value):
                self.assert_unproved(200, payload)
        payload = completed([])
        del payload["data"]
        self.assert_unproved(200, payload)

    def test_missing_error_and_oversize_codes(self):
        for field, values in (("code", (None, "333334", "391908", "000904", 90001)),
                              ("sqlState", (None, "42000", "57014", 0))):
            for value in values:
                payload = completed([])
                payload[field] = value
                with self.subTest(field=field, value=value):
                    self.assert_unproved(200, payload)
        payload = completed([])
        payload["statementHandles"] = []
        self.assert_unproved(200, payload, "multiple-statement")

    def test_metadata_counts_and_columns(self):
        for field, values in (("format", (None, "json", 1)),
                              ("numRows", (None, True, "0", -1, 1, 11)),
                              ("rowType", (None, [], [None], [{}], [{"name": ""}]))):
            for value in values:
                payload = completed([])
                payload["resultSetMetaData"][field] = value
                with self.subTest(field=field, value=value):
                    self.assert_unproved(200, payload)
        self.assert_unproved(200, completed([["SYNTHETIC"]] * 11))
        payload = completed([])
        del payload["resultSetMetaData"]
        self.assert_unproved(200, payload)

    def test_partitions_are_bounded_and_consistent(self):
        for parts in (None, {}, [{"rowCount": True}], [{"rowCount": 1}],
                      [{"rowCount": 0}, {"rowCount": 0}]):
            payload = completed([])
            payload["resultSetMetaData"]["partitionInfo"] = parts
            with self.subTest(parts=parts):
                self.assert_unproved(200, payload, "partition")
        for alteration in ("absent", "empty"):
            payload = completed([])
            if alteration == "absent":
                del payload["resultSetMetaData"]["partitionInfo"]
            else:
                payload["resultSetMetaData"]["partitionInfo"] = []
            self.assertTrue(self.read_synthetic(200, payload).live)
        payload = completed([["SYNTHETIC"]])
        payload["resultSetMetaData"]["partitionInfo"] = []
        self.assert_unproved(200, payload, "partition")

    def test_provider_error_body_is_not_echoed(self):
        payload = {"message": "SYNTHETIC_PRIVATE_MARKER", "data": []}
        result = self.read_synthetic(422, payload)
        self.assertNotIn("SYNTHETIC_PRIVATE_MARKER", result.note)

    def test_no_credentials_still_performs_zero_http_calls(self):
        connector = self.mod.SnowflakeConnector()
        with patch.object(connector, "_primary_missing", return_value=True), \
             patch.object(self.mod, "http_json", side_effect=AssertionError("HTTP forbidden")):
            result = connector.read()
        self.assertEqual(result.state, self.mod.State.READY)
        self.assertFalse(result.live)
        self.assertEqual(result.records, [])


if __name__ == "__main__":
    unittest.main()
