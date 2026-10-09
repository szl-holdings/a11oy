#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Portable, synthetic checks for the repair helper's logical identity gate."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

import gdw_sqlite_repair as repair


class LogicalFingerprintTests(unittest.TestCase):
    def connection(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        return connection

    def test_implicit_row_identity_is_bound(self):
        connection = self.connection()
        connection.execute("CREATE TABLE sample(value TEXT)")
        connection.execute("INSERT INTO sample(rowid, value) VALUES(7, 'example')")
        before = repair.logical_fingerprint(connection)
        connection.execute("UPDATE sample SET rowid=42")
        self.assertNotEqual(before, repair.logical_fingerprint(connection))

    def test_declared_rowid_names_do_not_hide_the_real_identity(self):
        connection = self.connection()
        connection.execute('CREATE TABLE sample("ROWID" TEXT, "OID" TEXT)')
        connection.execute("INSERT INTO sample(_rowid_, ROWID, OID) VALUES(7, 'a', 'b')")
        before = repair.logical_fingerprint(connection)
        connection.execute("UPDATE sample SET _rowid_=42")
        self.assertNotEqual(before, repair.logical_fingerprint(connection))

    def test_all_shadowed_rowid_aliases_fail_closed(self):
        connection = self.connection()
        connection.execute("CREATE TABLE sample(rowid TEXT, oid TEXT, _rowid_ TEXT)")
        with self.assertRaises(repair.OrphanRepairError) as raised:
            repair.logical_fingerprint(connection)
        self.assertEqual(raised.exception.code, "ROW_IDENTITY_UNAVAILABLE")

    def test_without_rowid_is_independent_of_insert_order(self):
        first, second = self.connection(), self.connection()
        for connection in (first, second):
            connection.execute(
                "CREATE TABLE sample(k TEXT PRIMARY KEY, value TEXT) WITHOUT ROWID"
            )
        rows = [("b", "two"), ("a", "one")]
        first.executemany("INSERT INTO sample VALUES(?,?)", rows)
        second.executemany("INSERT INTO sample VALUES(?,?)", reversed(rows))
        self.assertEqual(repair.logical_fingerprint(first), repair.logical_fingerprint(second))

    def test_without_rowid_may_declare_every_special_name(self):
        connection = self.connection()
        connection.execute(
            "CREATE TABLE sample(rowid TEXT PRIMARY KEY, oid TEXT, _rowid_ TEXT) WITHOUT ROWID"
        )
        connection.execute("INSERT INTO sample VALUES('a', 'b', 'c')")
        self.assertEqual(repair.logical_fingerprint(connection)["rows"], 1)

    def test_without_rowid_generated_columns_remain_bound(self):
        connection = self.connection()
        connection.execute(
            "CREATE TABLE sample(k INTEGER PRIMARY KEY, value INTEGER, "
            "doubled INTEGER GENERATED ALWAYS AS (value * 2)) WITHOUT ROWID"
        )
        connection.execute("INSERT INTO sample(k, value) VALUES(7, 3)")
        before = repair.logical_fingerprint(connection)
        connection.execute("UPDATE sample SET value=4")
        self.assertNotEqual(before, repair.logical_fingerprint(connection))

    def test_candidate_with_changed_rowid_is_not_logical_identity(self):
        # This is a synthetic candidate alteration, not a claim that this
        # SQLite build's VACUUM INTO changes rowids.
        with tempfile.TemporaryDirectory() as directory:
            source = sqlite3.connect(str(Path(directory) / "source.sqlite3"))
            candidate = None
            try:
                source.execute("CREATE TABLE sample(value TEXT)")
                source.executemany(
                    "INSERT INTO sample(rowid, value) VALUES(?,?)", [(7, "a"), (42, "b")]
                )
                source.commit()
                before = repair.logical_fingerprint(source)
                output = Path(directory) / "candidate.sqlite3"
                source.execute("VACUUM INTO ?", (str(output),))
                candidate = sqlite3.connect(str(output))
                candidate.execute("UPDATE sample SET rowid=rowid+100")
                self.assertNotEqual(
                    source.execute("SELECT rowid FROM sample").fetchall(),
                    candidate.execute("SELECT rowid FROM sample").fetchall(),
                )
                self.assertNotEqual(before, repair.logical_fingerprint(candidate))
            finally:
                if candidate is not None:
                    candidate.close()
                source.close()

    def test_integer_primary_key_survives_vacuum(self):
        with tempfile.TemporaryDirectory() as directory:
            source = sqlite3.connect(str(Path(directory) / "source.sqlite3"))
            candidate = None
            try:
                source.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value BLOB, note TEXT)")
                source.execute("INSERT INTO sample VALUES(42, ?, NULL)", (b"example",))
                source.commit()
                before = repair.logical_fingerprint(source)
                output = Path(directory) / "candidate.sqlite3"
                source.execute("VACUUM INTO ?", (str(output),))
                candidate = sqlite3.connect(str(output))
                self.assertEqual(before, repair.logical_fingerprint(candidate))
            finally:
                if candidate is not None:
                    candidate.close()
                source.close()


if __name__ == "__main__":
    unittest.main()
