#!/usr/bin/env python3
"""Preserve bounded-retention semantics inside the cross-process ledger repair."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "szl_energy_ledger.py"
TESTS = ROOT / "tests" / "test_energy_ledger_process_safety.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    text = LEDGER.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "        self._recovery_info: Optional[dict[str, Any]] = None\n",
        "        self._recovery_info: Optional[dict[str, Any]] = None\n"
        "        self._retention_anchor: Optional[dict[str, Any]] = None\n",
        "retention anchor state",
    )
    text = replace_once(
        text,
        "    def _replace_memory(self, records: list[dict]) -> None:\n"
        "        self._entries = list(records)\n",
        "    def _replace_memory(self, records: list[dict]) -> None:\n"
        "        self._entries = list(records)\n"
        "        self._retention_anchor = None\n",
        "retention anchor reset",
    )
    text = replace_once(
        text,
        "        strict = _strict_read(self.path, backup_count)\n"
        "        self._replace_memory(list(strict.records))\n"
        "        verdict = self.verify()\n",
        "        strict = _strict_read(self.path, backup_count)\n"
        "        self._replace_memory(list(strict.records))\n"
        "        active_name = Path(self.path).name\n"
        "        rotated_retention = any(row.get(\"name\") != active_name for row in strict.files)\n"
        "        if self._entries and rotated_retention:\n"
        "            first = self._entries[0]\n"
        "            first_seq = first.get(\"seq\")\n"
        "            first_prev = first.get(\"prev_digest\")\n"
        "            if (\n"
        "                isinstance(first_seq, int)\n"
        "                and first_seq > 0\n"
        "                and isinstance(first_prev, str)\n"
        "                and len(first_prev) == 64\n"
        "                and first_prev != GENESIS_PREV\n"
        "            ):\n"
        "                self._retention_anchor = {\n"
        "                    \"first_seq\": first_seq,\n"
        "                    \"external_prev_digest\": first_prev,\n"
        "                    \"evidence\": \"ROTATED_SEGMENTS_PRESENT\",\n"
        "                    \"retained_segments\": [row.get(\"name\") for row in strict.files],\n"
        "                }\n"
        "        verdict = self.verify()\n",
        "retained-chain anchor",
    )
    text = replace_once(
        text,
        "        self._replace_memory([])\n"
        "        if _DurableStore is not None:\n"
        "            self._store = _DurableStore(self.path)\n",
        "        self._replace_memory([])\n"
        "        if _DurableStore is not None:\n"
        "            previous = self._store\n"
        "            kwargs = {}\n"
        "            for name in (\"max_bytes\", \"backup_count\", \"pressure_ratio\", \"min_free_bytes\", \"fsync\"):\n"
        "                if previous is not None and hasattr(previous, name):\n"
        "                    kwargs[name] = getattr(previous, name)\n"
        "            self._store = _DurableStore(self.path, **kwargs)\n",
        "preserve bounded-store configuration",
    )
    text = replace_once(
        text,
        "        except (_LedgerLockTimeout, _LedgerLockUnavailable) as exc:\n"
        "            self._replace_memory([])\n"
        "            self._load_error = {\"code\": type(exc).__name__, \"message\": str(exc)}\n"
        "        except Exception as exc:\n"
        "            self._replace_memory([])\n",
        "        except (_LedgerLockTimeout, _LedgerLockUnavailable) as exc:\n"
        "            self._replace_memory([])\n"
        "            self._last_store_status = \"unavailable\"\n"
        "            self._load_error = {\"code\": type(exc).__name__, \"message\": str(exc)}\n"
        "        except Exception as exc:\n"
        "            self._replace_memory([])\n"
        "            self._last_store_status = \"unavailable\"\n",
        "honest initialization status",
    )
    text = replace_once(
        text,
        "        seq = len(self._entries)\n",
        "        seq = (int(self._entries[-1].get(\"seq\", -1)) + 1) if self._entries else 0\n",
        "monotonic retained sequence",
    )
    text = replace_once(
        text,
        "        if not self.path or _exclusive_writer_lock is None:\n"
        "            return {\n",
        "        if not self.path or _exclusive_writer_lock is None:\n"
        "            self._last_store_status = \"unavailable\"\n"
        "            return {\n",
        "missing lock status",
    )
    text = replace_once(
        text,
        "            except _LedgerLockTimeout as exc:\n"
        "                return {\n",
        "            except _LedgerLockTimeout as exc:\n"
        "                self._last_store_status = \"unavailable\"\n"
        "                return {\n",
        "lock timeout status",
    )
    text = replace_once(
        text,
        "            except _LedgerLockUnavailable as exc:\n"
        "                return {\n",
        "            except _LedgerLockUnavailable as exc:\n"
        "                self._last_store_status = \"unavailable\"\n"
        "                return {\n",
        "lock unavailable status",
    )
    text = replace_once(
        text,
        "            except Exception as exc:\n"
        "                return {\n"
        "                    \"appended\": False,\n"
        "                    \"duplicate\": False,\n"
        "                    \"error\": \"LEDGER_APPEND_FAILED_CLOSED\",\n",
        "            except Exception as exc:\n"
        "                self._last_store_status = \"unavailable\"\n"
        "                return {\n"
        "                    \"appended\": False,\n"
        "                    \"duplicate\": False,\n"
        "                    \"error\": \"LEDGER_APPEND_FAILED_CLOSED\",\n",
        "generic append status",
    )
    text = replace_once(
        text,
        "        expected_prev = GENESIS_PREV\n\n"
        "        for i, e in enumerate(self._entries):\n"
        "            if e.get(\"seq\") != i:\n",
        "        retained = self._retention_anchor\n"
        "        expected_prev = (\n"
        "            str(retained[\"external_prev_digest\"]) if retained else GENESIS_PREV\n"
        "        )\n"
        "        first_seq = int(retained[\"first_seq\"]) if retained else 0\n\n"
        "        for i, e in enumerate(self._entries):\n"
        "            expected_seq = first_seq + i\n"
        "            if e.get(\"seq\") != expected_seq:\n",
        "retained verification base",
    )
    text = replace_once(
        text,
        '                        "reason": "seq is not contiguous and zero-based",\n',
        '                        "reason": "seq is not contiguous within the retained generation",\n',
        "sequence verdict wording",
    )
    text = replace_once(
        text,
        '            "genesis_prev": GENESIS_PREV,\n'
        '        }\n\n'
        '    # -- views',
        '            "genesis_prev": GENESIS_PREV,\n'
        '            "retention_anchor": retained,\n'
        '        }\n\n'
        '    # -- views',
        "retention verdict disclosure",
    )
    LEDGER.write_text(text, encoding="utf-8")

    tests = TESTS.read_text(encoding="utf-8")
    tests = replace_once(
        tests,
        '    assert verdict["first_break"]["reason"] == "seq is not contiguous and zero-based"\n',
        '    assert verdict["first_break"]["reason"] == "seq is not contiguous within the retained generation"\n',
        "sequence test wording",
    )
    addition = '''\n\ndef test_rotated_retention_uses_explicit_external_anchor(tmp_path: Path) -> None:\n    path = str(tmp_path / "energy.jsonl")\n    ledger = EnergyLedger(path=path)\n    ledger._store.max_bytes = 2048\n    ledger._store.backup_count = 2\n    ledger._store.fsync = False\n    for index in range(200):\n        assert ledger.append_job(job(index), now=NOW)["appended"] is True\n    verdict = ledger.verify()\n    assert verdict["ok"] is True, verdict\n    assert verdict["retention_anchor"] is not None\n    assert verdict["retention_anchor"]["evidence"] == "ROTATED_SEGMENTS_PRESENT"\n    assert ledger._store._counters.rotations > 0\n    assert ledger._store.total_bytes() <= ledger._store.max_total_bytes()\n'''
    if "test_rotated_retention_uses_explicit_external_anchor" in tests:
        raise RuntimeError("rotation test already present")
    TESTS.write_text(tests.rstrip() + addition + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
