# SPDX-License-Identifier: Apache-2.0
"""Read-only public-data service. Cache writes are not decisions or signed receipts."""
import copy
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from . import feeds

API_PREFIX = "/api/a11oy/v1/civilian"
API_OPERATIONS = {
    "health", "overview", "refresh", "analyze", "observe/headers", "weather", "plan",
}


class ContractError(ValueError):
    pass


class BusyError(RuntimeError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def source_age(source, hours=24):
    value = copy.deepcopy(source)
    if value["status"] == "UNAVAILABLE":
        return value
    try:
        fetched = datetime.fromisoformat(value["fetched_at"].replace("Z", "+00:00")).timestamp()
        age = time.time() - fetched
    except (ValueError, TypeError, AttributeError, KeyError):
        age = float("inf")
    if age < -300 or age > hours * 3600:
        value.update(status="STALE", error=value.get("error") or "Snapshot is outside the configured freshness window.")
    return value


def rank(cves, snapshots):
    cves = sorted(set(cves))
    kev_ok = snapshots["kev"]["source"]["status"] != "UNAVAILABLE"
    epss_ok = snapshots["epss"]["source"]["status"] != "UNAVAILABLE"
    kev = {e["cveID"]: e for e in snapshots["kev"]["entries"]} if kev_ok else {}
    epss = {e["cve"]: e for e in snapshots["epss"]["entries"]} if epss_ok else {}
    rows = []
    for cve in cves:
        k, e = kev.get(cve), epss.get(cve)
        rows.append({
            "cve": cve, "kev_status": "LISTED" if k else "NOT_LISTED" if kev_ok else "UNKNOWN",
            "kev": k, "epss": e, "exposure": "UNKNOWN",
            "priority": "REVIEW_KNOWN_EXPLOITATION" if k else "REVIEW_ESTIMATE" if e else "INSUFFICIENT_DATA",
            "explanation": (
                "This CVE is listed in the available CISA known-exploited snapshot, so the advisory policy places it ahead of non-listed records. This does not establish that your systems are affected." if k else
                "This record is ordered using FIRST's EPSS estimate after KEV-listed records. EPSS is not your organization's attack probability; exposure and impact are unknown." if e else
                "Evidence is insufficient for a score-based ordering. Missing estimates are null, never zero, and lack of a KEV listing does not imply safety."
            ),
        })
    rows.sort(key=lambda r: (r["kev_status"] != "LISTED", -(r["epss"]["epss"] if r["epss"] else -1), r["cve"]))
    return {
        "analyzed_at": timestamp(), "policy_version": "kev-first-epss-second/1.0",
        "input": cves, "rows": rows, "sources": [snapshots["kev"]["source"], snapshots["epss"]["source"]],
        "asset_inventory_connected": False, "model_executed": False,
    }


def dry_run(scenario, approved):
    next_step = {
        "cyber": "Would draft an internal software-risk review item for an authorized analyst.",
        "weather": "Would draft a facilities review note linking to the official weather alert.",
        "research": "Would draft a literature-review task containing citations, not biological procedures.",
    }[scenario]
    return {
        "schema": "szl-observatory.dry-run.v1", "classification": "SIMULATED",
        "executed": False, "external_calls": 0, "scenario": scenario,
        "steps": [
            {"title": "Record a fictional observation", "state": "SIMULATED", "detail": "The scenario does not assert an incident, affected asset, patient result, or emergency."},
            {"title": "Preserve the human boundary", "state": "SIMULATED_APPROVAL" if approved else "REVIEW_REQUIRED", "detail": "This switch is a rehearsal input, not authentication or authorization."},
            {"title": "Preview the next step", "state": "WOULD_DRAFT" if approved else "HELD", "detail": next_step if approved else "The simulated plan stops before a draft response until the reviewer input is selected."},
            {"title": "Stop before external effects", "state": "NO_ADAPTER", "detail": "No ticket, alert, message, device command, network change, or laboratory action is executed."},
        ],
    }


def strict_params(params, required, optional=()):
    if not isinstance(params, dict) or set(params) - set(required) - set(optional) or not set(required).issubset(params):
        raise ContractError("Unexpected or missing query fields")
    if any(not isinstance(v, str) or len(v) > 1800 for v in params.values()):
        raise ContractError("Query fields must be bounded strings")


class PublicCache:
    """Bounded SQLite cache, shared process budgets and per-observation leases."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS snapshots(key TEXT PRIMARY KEY, payload TEXT NOT NULL, observed REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS observation_leases(key TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS starts(at REAL NOT NULL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def read(self, key):
        with self.connect() as db:
            row = db.execute("SELECT payload,observed FROM snapshots WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        return {"value": json.loads(row[0]), "observed": row[1]}

    def save(self, key, value):
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(payload.encode("utf-8")) > 6_000_000:
            raise ContractError("Cache record too large")
        with self.connect() as db:
            db.execute("INSERT INTO snapshots VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,observed=excluded.observed",
                       (key, payload, time.time()))
            # Bound cache growth; the two fixed feed records are retained.
            db.execute("DELETE FROM snapshots WHERE key NOT IN ('feeds','feed-attempt') AND key IN (SELECT key FROM snapshots WHERE key NOT IN ('feeds','feed-attempt') ORDER BY observed DESC LIMIT -1 OFFSET 96)")

    def acquire(self, key):
        owner = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            db.execute("DELETE FROM observation_leases WHERE expires<?", (now,))
            db.execute("DELETE FROM starts WHERE at<?", (now - 60,))
            if db.execute("SELECT 1 FROM observation_leases WHERE key=?", (key,)).fetchone():
                raise BusyError("This observation is already running")
            if db.execute("SELECT count(*) FROM observation_leases").fetchone()[0] >= 3:
                raise BusyError("Observation concurrency limit reached")
            if db.execute("SELECT count(*) FROM starts").fetchone()[0] >= 20:
                raise BusyError("Observation rate limit reached")
            db.execute("INSERT INTO starts VALUES(?)", (now,))
            # Expiration is crash recovery, not proof of network termination.
            db.execute("INSERT INTO observation_leases VALUES(?,?,?)", (key, owner, now + 120))
        return owner

    def release(self, key, owner):
        with self.connect() as db:
            db.execute("DELETE FROM observation_leases WHERE key=? AND owner=?", (key, owner))


def verify_package_manifest(root, manifest_path):
    root = Path(root).resolve()
    document = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if document.get("schema") != "szl.civilian.payload.v1" or not isinstance(document.get("files"), dict):
        raise ContractError("Unsupported payload manifest")
    if not document["files"]:
        raise ContractError("Empty payload manifest")
    present = {p.relative_to(root).as_posix() for p in root.rglob("*")
               if p.is_file() and "__pycache__" not in p.parts and p.name != "PAYLOAD_MANIFEST.json"}
    if present != set(document["files"]):
        raise ContractError("Payload manifest does not cover the exact package file set")
    for name, expected in document["files"].items():
        relative = Path(name)
        path = root / relative
        if relative.is_absolute() or ".." in relative.parts or path.is_symlink() or not path.is_file():
            raise ContractError("Manifest path is not an admitted regular file")
        if not path.resolve().is_relative_to(root):
            raise ContractError("Manifest path escaped its root")
        if not re.fullmatch(r"[0-9a-f]{64}", str(expected)):
            raise ContractError("Malformed file digest")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ContractError("Payload integrity mismatch")
    return document


class Observatory:
    def __init__(self, package_root, cache_path, provider=None):
        self.root = Path(package_root).resolve()
        self.provider = provider or feeds
        self.manifest = verify_package_manifest(self.root, self.root / "PAYLOAD_MANIFEST.json")
        self.cache = PublicCache(cache_path)
        self.estate = json.loads((self.root / "data/estate.json").read_text(encoding="utf-8"))
        repos = self.estate.get("repositories")
        if not isinstance(repos, list) or any(r.get("visibility") != "public" for r in repos):
            raise ContractError("Only public repository metadata is admitted")
        if len(repos) != self.estate.get("summary", {}).get("repo_count"):
            raise ContractError("Repository denominator mismatch")
        if self.cache.read("feeds") is None:
            self.cache.save("feeds", feeds.empty_feeds())

    def get_feeds(self):
        value = copy.deepcopy(self.cache.read("feeds")["value"])
        for name in ("kev", "epss"):
            value[name]["source"] = source_age(value[name]["source"])
        return value

    def refresh(self, force=False):
        current = self.cache.read("feeds")
        attempt = self.cache.read("feed-attempt")
        if attempt and time.time() - attempt["observed"] < 60:
            return self.get_feeds()
        if not force and current:
            try:
                fetched = current["value"]["kev"]["source"]["fetched_at"]
                age = time.time() - datetime.fromisoformat(fetched.replace("Z", "+00:00")).timestamp()
            except (KeyError, TypeError, ValueError, AttributeError):
                age = float("inf")
            if time.time() - current["observed"] < 3600 and 0 <= age < 3600:
                return self.get_feeds()
        try:
            lease_owner = self.cache.acquire("feeds")
        except BusyError:
            return self.get_feeds()
        try:
            self.cache.save("feed-attempt", {"attempted_at": timestamp()})
            previous = self.get_feeds()
            fresh = self.provider.get_feeds()
            for name in ("kev", "epss"):
                if fresh[name]["source"]["status"] == "UNAVAILABLE" and previous[name]["entries"]:
                    fresh[name] = previous[name]
                    fresh[name]["source"].update(status="STALE", error="Refresh failed. Showing the prior snapshot at its original fetch time.")
            self.cache.save("feeds", fresh)
            return self.get_feeds()
        except Exception:
            previous = self.get_feeds()
            for name in ("kev", "epss"):
                if previous[name]["source"]["status"] != "UNAVAILABLE":
                    previous[name]["source"].update(status="STALE", error="Refresh failed; prior observation retained, not remeasured.")
            self.cache.save("feeds", previous)
            return previous
        finally:
            self.cache.release("feeds", lease_owner)

    def observed(self, key, ttl, operation):
        prior = self.cache.read(key)
        if prior and time.time() - prior["observed"] < ttl:
            return prior["value"]
        lease_owner = self.cache.acquire(key)
        try:
            value = operation()
            self.cache.save(key, value)
            return value
        finally:
            self.cache.release(key, lease_owner)

    def handle(self, operation, params):
        if operation not in API_OPERATIONS:
            raise ContractError("Unknown operation")
        if operation in {"health", "overview", "refresh"}:
            strict_params(params, ())
        if operation == "health":
            # The canonical publisher binds SZL_GIT_SHA to GitHub, not the
            # independent image/HF revision or a build-time default.
            source_sha = os.environ.get("SZL_GIT_SHA", "")
            return {
                "status": "UP", "scope": "EXPERIMENTAL_SOFTWARE", "version": __version__,
                "model_loaded": False, "external_effectors": [], "time": timestamp(),
                "api_policy": "GET_ONLY_PUBLIC_OBSERVATIONS",
                "source_revision": source_sha if re.fullmatch(r"[0-9a-f]{40}", source_sha) else "UNKNOWN",
                "payload_manifest_sha256": hashlib.sha256((self.root / "PAYLOAD_MANIFEST.json").read_bytes()).hexdigest(),
                "receipt_trust": "UNSIGNED_SELF_ASSERTED",
                "cache_persistence": "REBUILDABLE_PUBLIC_CACHE",
                "source_states": {k: v["source"]["status"] for k, v in self.get_feeds().items() if k in ("kev", "epss")},
            }
        if operation in {"overview", "refresh"}:
            value = self.refresh(force=operation == "refresh")
            if operation == "refresh":
                return {"generated_at": value["generated_at"], "sources": [value["kev"]["source"], value["epss"]["source"]]}
            ids = [r["cveID"] for r in sorted(value["kev"]["entries"], key=lambda r: (r["dateAdded"], r["cveID"]), reverse=True)[:20]]
            view = copy.deepcopy(value)
            view["kev"]["catalog_count"] = len(value["kev"]["entries"])
            view["kev"]["entries"] = [e for e in value["kev"]["entries"] if e["cveID"] in ids]
            return {"estate": self.estate, "feeds": view, "analysis": rank(ids, value), "server_time": timestamp()}
        if operation == "analyze":
            strict_params(params, ("cves",))
            try:
                ids = feeds.valid_cves(params["cves"].split(","))
            except ValueError as exc:
                raise ContractError(str(exc)) from exc
            result = self.observed("epss:" + ",".join(ids), 3600, lambda: self.provider.get_epss(ids))
            result = copy.deepcopy(result)
            result["source"] = source_age(result["source"])
            current = self.get_feeds()
            current["epss"] = result
            return rank(ids, current)
        if operation == "observe/headers":
            strict_params(params, ("target",))
            if params["target"] not in feeds.TARGETS:
                raise ContractError("Target is outside the exact owner-scoped allowlist")
            return self.observed("headers:" + params["target"], 600, lambda: self.provider.get_headers(params["target"]))
        if operation == "weather":
            strict_params(params, (), ("area",))
            area = params.get("area", "NY")
            if area not in feeds.STATES:
                raise ContractError("Weather area is outside the admitted public scope")
            value = copy.deepcopy(self.observed("weather:" + area, 600, lambda: self.provider.get_weather(area)))
            value["source"] = source_age(value["source"], 1 / 6)
            return value
        if operation == "plan":
            strict_params(params, ("scenario", "simulatedApproval", "mode"))
            if params["scenario"] not in ("cyber", "weather", "research") or params["simulatedApproval"] not in ("true", "false") or params["mode"] != "dry-run":
                raise ContractError("Only known dry-run scenarios are supported")
            return dry_run(params["scenario"], params["simulatedApproval"] == "true")
        raise ContractError("Unknown operation")
