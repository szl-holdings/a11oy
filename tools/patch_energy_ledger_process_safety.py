#!/usr/bin/env python3
"""Apply the bounded, forensic, cross-process EnergyLedger repair."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "szl_energy_ledger.py"
DOCKERFILE = ROOT / "Dockerfile"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    first = text.find(start)
    if first < 0:
        raise RuntimeError(f"{label}: start marker not found")
    second = text.find(end, first)
    if second < 0:
        raise RuntimeError(f"{label}: end marker not found")
    return text[:first] + replacement + text[second:]


def patch_ledger() -> None:
    text = LEDGER.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import json\nimport os\nimport threading\nimport time\n",
        "import json\nimport os\nimport threading\nimport time\n",
        "stdlib import anchor",
    )
    durable_anchor = '''try:
    from szl_durable_ledger import DurableStore as _DurableStore
except Exception:  # pragma: no cover — never let a missing helper break the ledger
    _DurableStore = None  # type: ignore
'''
    recovery_import = durable_anchor + '''
try:
    from szl_energy_ledger_recovery import (
        LedgerLockTimeout as _LedgerLockTimeout,
        LedgerLockUnavailable as _LedgerLockUnavailable,
        exclusive_writer_lock as _exclusive_writer_lock,
        quarantine_generation as _quarantine_generation,
        strict_read as _strict_read,
    )
except Exception:  # pragma: no cover - image COPY guard must prevent this in production
    _LedgerLockTimeout = RuntimeError  # type: ignore
    _LedgerLockUnavailable = RuntimeError  # type: ignore
    _exclusive_writer_lock = None  # type: ignore
    _quarantine_generation = None  # type: ignore
    _strict_read = None  # type: ignore
'''
    text = replace_once(text, durable_anchor, recovery_import, "recovery import")

    text = replace_once(
        text,
        'DEFAULT_PRICE_PER_KWH_CENTS = int(os.getenv("STRIPE_PRICE_PER_KWH_CENTS", "45"))\n',
        'DEFAULT_PRICE_PER_KWH_CENTS = int(os.getenv("STRIPE_PRICE_PER_KWH_CENTS", "45"))\n'
        'DEFAULT_WRITER_LOCK_TIMEOUT_S = float(os.getenv("SZL_ENERGY_WRITER_LOCK_TIMEOUT_S", "5"))\n'
        'DEFAULT_LEDGER_PAGE_LIMIT = 50\n'
        'MAX_LEDGER_PAGE_LIMIT = 100\n',
        "ledger limits",
    )

    old_signature = '''    def __init__(self, path: Optional[str] = None,
                 price_per_kwh_cents: int = DEFAULT_PRICE_PER_KWH_CENTS):
        self.path = path if path is not None else DEFAULT_LEDGER_PATH
        self.price_per_kwh_cents = price_per_kwh_cents
        self._entries: list[dict] = []
        self._idem_seen: set[str] = set()
        self._lock = threading.Lock()
'''
    new_signature = '''    def __init__(self, path: Optional[str] = None,
                 price_per_kwh_cents: int = DEFAULT_PRICE_PER_KWH_CENTS,
                 writer_lock_timeout_s: float = DEFAULT_WRITER_LOCK_TIMEOUT_S):
        self.path = path if path is not None else DEFAULT_LEDGER_PATH
        self.price_per_kwh_cents = price_per_kwh_cents
        self.writer_lock_timeout_s = max(0.01, float(writer_lock_timeout_s))
        self._entries: list[dict] = []
        self._idem_seen: set[str] = set()
        self._lock = threading.Lock()
        self._load_error: Optional[dict[str, Any]] = None
        self._recovery_info: Optional[dict[str, Any]] = None
'''
    text = replace_once(text, old_signature, new_signature, "constructor")

    load_replacement = '''    def _replace_memory(self, records: list[dict]) -> None:
        self._entries = list(records)
        self._idem_seen = {
            str(entry["idempotency_key"])
            for entry in self._entries
            if entry.get("idempotency_key")
        }
        self._recovery_info = None
        for entry in self._entries:
            decision = entry.get("receipt", {}).get("decision", {})
            if decision.get("schema") == "SZL.Energy.LedgerReset.v1":
                self._recovery_info = {
                    "state": "RECOVERED_GENERATION",
                    "prior_generation_sha256": decision.get("prior_generation_sha256"),
                    "prior_chain_ok": decision.get("prior_chain", {}).get("ok"),
                    "quarantine_manifest_sha256": decision.get("quarantine_manifest_sha256"),
                    "reset_at": decision.get("reset_at"),
                }

    def _build_reset_entry(self, quarantine: dict, prior_verdict: dict) -> dict:
        decision = {
            "schema": "SZL.Energy.LedgerReset.v1",
            "reason": "INVALID_PRIOR_GENERATION_QUARANTINED",
            "reset_at": datetime.now(timezone.utc).isoformat(),
            "prior_generation_sha256": quarantine["aggregate_sha256"],
            "quarantine_manifest_sha256": sha256_canon(
                {
                    key: quarantine[key]
                    for key in (
                        "schema", "created_at", "aggregate_sha256", "cause",
                        "files", "strict_errors", "prior_chain", "record_count_recovered",
                    )
                }
            ),
            "prior_chain": prior_verdict,
            "prior_files": quarantine["files"],
            "strict_errors": quarantine["strict_errors"],
            "authorization": "AUTOMATIC_FAIL_CLOSED_FORENSIC_RECOVERY",
            "billable": False,
            "sovereign": False,
            "lambda_status": "CONJECTURE_1_ADVISORY",
        }
        payload_digest = sha256_canon(decision)
        receipt = {
            "schema": "SZL.Energy.Receipt.v1",
            "decision": decision,
            "payload_digest": payload_digest,
        }
        idem = f"energy-ledger-reset:{quarantine['aggregate_sha256']}"
        return {
            "seq": 0,
            "prev_digest": GENESIS_PREV,
            "receipt": receipt,
            "job": {
                "node": "a11oy-energy-ledger",
                "tokens": 0,
                "wall_s": 0.0,
                "model": "forensic-generation-reset",
                "ts": decision["reset_at"],
                "nvml_age_s": None,
            },
            "billable": False,
            "reason": decision["reason"],
            "charge": {"status": "blocked", "reason": "forensic reset is not billable"},
            "idempotency_key": idem,
            "entry_digest": _entry_digest(0, GENESIS_PREV, payload_digest),
        }

    def _strict_reload_locked(self, recover: bool = True) -> None:
        if not self.path:
            self._replace_memory([])
            self._load_error = None
            return
        if _strict_read is None or _quarantine_generation is None:
            raise RuntimeError("energy ledger process-safety helper is unavailable")
        backup_count = int(getattr(self._store, "backup_count", 4) or 4)
        strict = _strict_read(self.path, backup_count)
        self._replace_memory(list(strict.records))
        verdict = self.verify()
        invalid = bool(strict.errors) or not verdict["ok"]
        if not invalid:
            self._load_error = None
            return
        if not recover:
            raise RuntimeError("ledger generation is malformed or forked")

        quarantine = _quarantine_generation(
            self.path,
            backup_count,
            strict,
            verdict,
            "strict-read-error" if strict.errors else "chain-verification-failed",
        )
        self._replace_memory([])
        if _DurableStore is not None:
            self._store = _DurableStore(self.path)
        reset = self._build_reset_entry(quarantine, verdict)
        persisted = self._persist_entry(reset)
        if not persisted["ok"]:
            raise RuntimeError(
                "quarantined invalid generation but reset receipt could not be persisted: "
                + str(persisted.get("error") or persisted.get("status"))
            )
        self._replace_memory([reset])
        self._load_error = None

    def _load(self) -> None:
        """Strictly load or quarantine an invalid durable generation under flock."""
        if not self.path:
            return
        if _exclusive_writer_lock is None:
            self._load_error = {
                "code": "INTERPROCESS_LOCK_UNAVAILABLE",
                "message": "process-safety helper is unavailable",
            }
            return
        try:
            with _exclusive_writer_lock(self.path, self.writer_lock_timeout_s):
                self._strict_reload_locked(recover=True)
        except (_LedgerLockTimeout, _LedgerLockUnavailable) as exc:
            self._replace_memory([])
            self._load_error = {"code": type(exc).__name__, "message": str(exc)}
        except Exception as exc:
            self._replace_memory([])
            self._load_error = {
                "code": "LEDGER_RECOVERY_FAILED",
                "message": f"{type(exc).__name__}: {exc}",
            }

'''
    text = replace_between(
        text,
        "    def _load(self) -> None:\n",
        "    def _persist_entry(self, entry: dict) -> None:\n",
        load_replacement,
        "strict load",
    )

    persist_replacement = '''    def _persist_entry(self, entry: dict) -> dict[str, Any]:
        """Persist one row and return an acknowledgement; never mutate memory first."""
        if self._store is not None:
            result = self._store.append(entry)
            self._last_store_status = result.status
            return {
                "ok": bool(result.ok),
                "status": result.status,
                "error": result.error,
                "bytes_written": result.bytes_written,
                "rotated": result.rotated,
            }
        if not self.path:
            return {"ok": False, "status": "unavailable", "error": "ledger path absent"}
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._last_store_status = "ok"
            return {"ok": True, "status": "ok", "error": None}
        except OSError as exc:
            self._last_store_status = "unavailable"
            return {
                "ok": False,
                "status": "unavailable",
                "error": f"{type(exc).__name__}: {exc}",
            }

'''
    text = replace_between(
        text,
        "    def _persist_entry(self, entry: dict) -> None:\n",
        "    # -- core append -------------------------------------------------------\n",
        persist_replacement,
        "durable acknowledgement",
    )

    start = text.find("    def append_job(self, job: JobRecord, now: Optional[float] = None) -> dict:\n")
    end = text.find("    # -- verification ------------------------------------------------------\n", start)
    if start < 0 or end < 0:
        raise RuntimeError("append_job block not found")
    old_block = text[start:end]
    with_marker = "        with self._lock:\n"
    split = old_block.find(with_marker)
    if split < 0:
        raise RuntimeError("append_job thread-lock marker not found")
    prefix = old_block[:split].replace("    def append_job(", "    def _append_job_after_refresh(", 1)
    body_lines = old_block[split + len(with_marker):].splitlines()
    if any(line and not line.startswith("            ") for line in body_lines):
        raise RuntimeError("append_job body indentation contract failed")
    dedented = "\n".join(line[4:] if line else "" for line in body_lines) + "\n"
    dedented = replace_once(
        dedented,
        '''        self._entries.append(entry)
        self._idem_seen.add(idem)
        self._persist_entry(entry)
        return {"appended": True, "duplicate": False,
                "idempotency_key": idem, "entry": entry}
''',
        '''        persisted = self._persist_entry(entry)
        if not persisted["ok"]:
            return {
                "appended": False,
                "duplicate": False,
                "error": "STORAGE_UNAVAILABLE",
                "storage": persisted,
                "idempotency_key": idem,
                "entry": None,
            }
        self._entries.append(entry)
        self._idem_seen.add(idem)
        return {"appended": True, "duplicate": False,
                "idempotency_key": idem, "entry": entry, "storage": persisted}
''',
        "persist-before-memory",
    )
    wrapper = '''    def append_job(self, job: JobRecord, now: Optional[float] = None) -> dict:
        """Serialize writers across processes, re-read the tail, then append once."""
        if not self.path or _exclusive_writer_lock is None:
            return {
                "appended": False,
                "duplicate": False,
                "error": "INTERPROCESS_LOCK_UNAVAILABLE",
                "entry": None,
            }
        with self._lock:
            try:
                with _exclusive_writer_lock(self.path, self.writer_lock_timeout_s) as lease:
                    self._strict_reload_locked(recover=True)
                    result = self._append_job_after_refresh(job, now=now)
                    result["writer_lease"] = lease
                    return result
            except _LedgerLockTimeout as exc:
                return {
                    "appended": False,
                    "duplicate": False,
                    "error": "WRITER_LOCK_TIMEOUT",
                    "message": str(exc),
                    "entry": None,
                }
            except _LedgerLockUnavailable as exc:
                return {
                    "appended": False,
                    "duplicate": False,
                    "error": "INTERPROCESS_LOCK_UNAVAILABLE",
                    "message": str(exc),
                    "entry": None,
                }
            except Exception as exc:
                return {
                    "appended": False,
                    "duplicate": False,
                    "error": "LEDGER_APPEND_FAILED_CLOSED",
                    "message": f"{type(exc).__name__}: {exc}",
                    "entry": None,
                }

'''
    text = text[:start] + wrapper + prefix + dedented + text[end:]

    text = replace_once(
        text,
        '''        for i, e in enumerate(self._entries):
            receipt = e.get("receipt", {})
''',
        '''        for i, e in enumerate(self._entries):
            if e.get("seq") != i:
                links_intact = False
                if first_break is None:
                    first_break = {
                        "index": i,
                        "reason": "seq is not contiguous and zero-based",
                    }
            receipt = e.get("receipt", {})
''',
        "sequence verification",
    )

    text = replace_once(
        text,
        '''        jobs = len(self._entries)
        joules_total = 0.0
''',
        '''        jobs = 0
        reset_records = 0
        joules_total = 0.0
''',
        "totals initialization",
    )
    text = replace_once(
        text,
        '''        for e in self._entries:
            d = e.get("receipt", {}).get("decision", {})
            joules_total += float(d.get("joules_measured", 0.0) or 0.0)
''',
        '''        for e in self._entries:
            d = e.get("receipt", {}).get("decision", {})
            if d.get("schema") == "SZL.Energy.LedgerReset.v1":
                reset_records += 1
                continue
            jobs += 1
            joules_total += float(d.get("joules_measured", 0.0) or 0.0)
''',
        "totals reset exclusion",
    )
    text = replace_once(
        text,
        '''            "jobs": jobs,
            "joules_total": round(joules_total, 6),
''',
        '''            "jobs": jobs,
            "ledger_records": len(self._entries),
            "reset_records": reset_records,
            "joules_total": round(joules_total, 6),
''',
        "totals shape",
    )

    summary_replacement = '''    def paged_entries(
        self,
        limit: int = DEFAULT_LEDGER_PAGE_LIMIT,
        before_seq: Optional[int] = None,
    ) -> tuple[list[dict], dict[str, Any]]:
        bounded = min(MAX_LEDGER_PAGE_LIMIT, max(1, int(limit)))
        total = len(self._entries)
        end = total if before_seq is None else min(total, max(0, int(before_seq)))
        start = max(0, end - bounded)
        page = list(self._entries[start:end])
        return page, {
            "limit": bounded,
            "total_records": total,
            "returned": len(page),
            "start_seq": page[0].get("seq") if page else None,
            "end_seq": page[-1].get("seq") if page else None,
            "next_before_seq": start if start > 0 else None,
            "complete": start == 0,
        }

    def summary(
        self,
        limit: int = DEFAULT_LEDGER_PAGE_LIMIT,
        before_seq: Optional[int] = None,
    ) -> dict:
        """Bounded public view; integrity and totals still cover the full generation."""
        receipts, page = self.paged_entries(limit=limit, before_seq=before_seq)
        chain = self.verify()
        return {
            "ok": bool(chain["ok"] and self._load_error is None),
            "receipts": receipts,
            "page": page,
            "chain": chain,
            "totals": self.totals(),
            "persistence": self.persistence_info(),
            "storage": self.storage_health(),
            "recovery": self._recovery_info,
            "load_error": self._load_error,
            "price_per_kwh_cents": self.price_per_kwh_cents,
            "stripe_mode": "live" if os.getenv("STRIPE_API_KEY") else "dry-run",
            "doctrine": DOCTRINE_NOTE,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }


'''
    text = replace_between(
        text,
        "    def summary(self) -> dict:\n",
        "\n\n# ---------------------------------------------------------------------------\n# Module-level singleton ledger",
        summary_replacement,
        "bounded summary",
    )

    text = replace_once(
        text,
        '''def handle_ledger() -> dict:
    return get_ledger().summary()
''',
        '''def handle_ledger(request: Optional[_Request] = None) -> dict:
    # Preserve the small offline contract while bounding every HTTP response.
    if request is None:
        return get_ledger().summary()
    params = request.query_params
    try:
        limit = int(params.get("limit", DEFAULT_LEDGER_PAGE_LIMIT))
    except (TypeError, ValueError):
        limit = DEFAULT_LEDGER_PAGE_LIMIT
    raw_before = params.get("before_seq")
    try:
        before_seq = None if raw_before in (None, "") else int(raw_before)
    except (TypeError, ValueError):
        before_seq = None
    return get_ledger().summary(limit=limit, before_seq=before_seq)
''',
        "bounded handler",
    )
    text = replace_once(
        text,
        "        return JSONResponse(handle_ledger())\n",
        "        return JSONResponse(handle_ledger(request))\n",
        "request-aware handler",
    )
    text = replace_once(
        text,
        '''        (f"{base}/ledger", _h_ledger),
        (f"{base}/receipt/{{idem}}", _h_receipt),
''',
        '''        (f"{base}/ledger", _h_ledger),
        (f"{base}/ledger/summary", _h_ledger),
        (f"{base}/receipt/{{idem}}", _h_receipt),
''',
        "summary route",
    )

    LEDGER.write_text(text, encoding="utf-8")


def patch_dockerfile() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "joule_billing.py szl_durable_ledger.py szl_energy_ledger.py szl_energy_operator.py",
        "joule_billing.py szl_durable_ledger.py szl_energy_ledger_recovery.py szl_energy_ledger.py szl_energy_operator.py",
        "runtime COPY closure",
    )
    DOCKERFILE.write_text(text, encoding="utf-8")


def main() -> int:
    patch_ledger()
    patch_dockerfile()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
