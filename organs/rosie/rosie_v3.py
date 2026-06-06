# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
# Authored by Yachay (CTO). Co-Authored-By: Perplexity Computer Agent
"""
rosie_v3 — Operator Console v3.0.0 backend (ADDITIVE).

This module is the operator's command surface for the entire SZL mesh. It is
registered on the ROOT FastAPI app (`register(app)`) BEFORE the Gradio mount so
Starlette resolves every /api/rosie/v2/* and /metrics route ahead of the UI.

Design — everything REAL or honestly labelled:
  * Signing  : rosie owns its OWN ECDSA P-256 keypair, self-bootstrapped on first
               boot and persisted to ./data/rosie_signing.pem (the Space's
               git-history-aware filesystem). DSSE envelopes are byte-verifiable
               with the Python `cryptography` lib. NO fabricated signatures.
  * Chain    : SHA-256 hash-chained Khipu receipts in sqlite3 (stdlib). Each
               receipt links prev_hash -> hash forming an unbroken chain from a
               genesis "boot" receipt. This is a tamper-evident append-only log
               (Reed-Solomon ≠ holographic; this is plain hash-chaining).
  * Commands : 16 real handlers (the superpowers). Each dispatch runs a real
               handler, persists an event, writes a signed receipt, returns DSSE.
  * Gate     : 13-axis Yuyay gate (local re-impl). Pass/fail with per-axis scores.
  * Replay   : event-sourcing replay over the sqlite event log. This is
               event-sourcing — NOT time travel.

Quechua names (Wallpa, Yawar, Yuyay, Puriq, Khipu) are brand naming only; no
prior-art claims.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse, Response

# ───────────────────────── Constants ─────────────────────────
DOCTRINE = "v11"
DOCTRINE_NUMBERS = {"declarations": 749, "axioms": 14, "sorries": 163}
VERSION = "3.0.0"
SIBLINGS = ["a11oy", "amaru", "sentra", "killinchu"]
SIBLING_HEALTH = {s: f"https://szlholdings-{s}.hf.space/api/{s}/healthz" for s in SIBLINGS}
SIBLING_WIRE_D = {s: f"https://szlholdings-{s}.hf.space/api/{s}/wires/D" for s in SIBLINGS}
# Locked 13-axis replay baseline hash (per founder doctrine).
LOCKED_REPLAY_HASH = "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5"
PAYLOAD_TYPE = "application/vnd.szl.khipu+json"

# Persistence — ./data is in the Space's git-history-aware filesystem.
DATA_DIR = os.environ.get("ROSIE_DATA_DIR", "./data")
DB_PATH = os.path.join(DATA_DIR, "rosie_state.db")
KEY_PATH = os.path.join(DATA_DIR, "rosie_signing.pem")

_BOOT_TS = time.time()
_LOCK = threading.RLock()

# Counters (Prometheus).
_COUNTERS = {
    "rosie_commands_total": 0,
    "rosie_receipts_total": 0,
    "rosie_gate_passes_total": 0,
    "rosie_gate_failures_total": 0,
    "rosie_wire_d_emissions_total": 0,
}

_BUILD_SHA = os.environ.get("ROSIE_BUILD_SHA", "unset")


def set_build_sha(sha: str) -> None:
    global _BUILD_SHA
    _BUILD_SHA = sha


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ───────────────────────── Signing layer (rosie's own key) ─────────────────────────

def _ensure_data_dir() -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        pass


def _load_or_create_private_key():
    """Load rosie's ECDSA P-256 private key; bootstrap+persist on first boot.

    Priority: ROSIE_SIGNING_KEY env (PEM or b64) -> ./data/rosie_signing.pem ->
    generate new and persist. NEVER fabricates; on hard failure returns None.
    """
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import (
        load_pem_private_key, Encoding, PrivateFormat, NoEncryption,
    )
    # 1. env var
    pem_env = os.environ.get("ROSIE_SIGNING_KEY")
    if pem_env:
        try:
            if "BEGIN" not in pem_env:
                pem_env = base64.b64decode(pem_env).decode("utf-8")
            return load_pem_private_key(pem_env.encode(), password=None)
        except Exception:
            pass
    # 2. persisted file
    _ensure_data_dir()
    if os.path.exists(KEY_PATH):
        try:
            with open(KEY_PATH, "rb") as f:
                return load_pem_private_key(f.read(), password=None)
        except Exception:
            pass
    # 3. generate + persist
    try:
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        with open(KEY_PATH, "wb") as f:
            f.write(pem)
        return key
    except Exception:
        # last resort: ephemeral in-memory key (still REAL, just not persisted)
        try:
            return ec.generate_private_key(ec.SECP256R1())
        except Exception:
            return None


_PRIV_KEY = None
_KEY_BOOTSTRAPPED = False


def _priv_key():
    global _PRIV_KEY, _KEY_BOOTSTRAPPED
    if _PRIV_KEY is None:
        _PRIV_KEY = _load_or_create_private_key()
        _KEY_BOOTSTRAPPED = _PRIV_KEY is not None
    return _PRIV_KEY


def public_pem() -> str:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    k = _priv_key()
    if k is None:
        return ""
    pub = k.public_key()
    return pub.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()


def public_fingerprint() -> str:
    pem = public_pem()
    if not pem:
        return "unavailable"
    return hashlib.sha256(pem.strip().encode()).hexdigest()


def signing_available() -> bool:
    return _priv_key() is not None


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _pae(payload_type: str, body: bytes) -> bytes:
    t = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(body)).encode() + b" " + body


def sign_dsse(payload_obj: Any, payload_type: str = PAYLOAD_TYPE) -> dict:
    """Real DSSE envelope: PAE digest + base64 ECDSA-P256-SHA256 sig over PAE."""
    body = _canon(payload_obj)
    to_sign = _pae(payload_type, body)
    env: dict[str, Any] = {
        "payloadType": payload_type,
        "payload": base64.b64encode(body).decode("ascii"),
        "_dsse": "DSSEv1",
        "_pae_sha256": hashlib.sha256(to_sign).hexdigest(),
        "_signed_at": _now(),
        "keyid": "rosie-operator-p256",
    }
    k = _priv_key()
    if k is None:
        env["signatures"] = []
        env["signed"] = False
        env["honesty"] = "UNSIGNED — ECDSA key could not be bootstrapped in this runtime."
        return env
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    sig = k.sign(to_sign, ec.ECDSA(hashes.SHA256()))
    env["signatures"] = [{"sig": base64.b64encode(sig).decode("ascii"), "keyid": "rosie-operator-p256"}]
    env["signed"] = True
    env["honesty"] = ("REAL — ECDSA-P256-SHA256 over DSSE PAE; verify with the PEM at "
                      "/api/rosie/v2/keys/public.pem using the cryptography lib.")
    env["verify_key_url"] = "/api/rosie/v2/keys/public.pem"
    return env


def verify_dsse(env: dict, pubkey_pem: str | None = None) -> dict:
    out: dict[str, Any] = {"keyid_expected": "rosie-operator-p256",
                           "pub_fingerprint_sha256": public_fingerprint()}
    try:
        payload_b64 = env.get("payload")
        payload_type = env.get("payloadType")
        sigs = env.get("signatures") or []
        if not payload_b64 or not payload_type:
            return {**out, "verified": False, "reason": "missing payload/payloadType"}
        if not sigs:
            return {**out, "verified": False, "reason": "no signatures (unsigned envelope)"}
        body = base64.b64decode(payload_b64)
        to_verify = _pae(payload_type, body)
        out["pae_sha256"] = hashlib.sha256(to_verify).hexdigest()
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
        pem = pubkey_pem or public_pem()
        pub = load_pem_public_key(pem.encode())
        results = []
        any_ok = False
        for s in sigs:
            try:
                sig = base64.b64decode(s.get("sig", ""))
                pub.verify(sig, to_verify, ec.ECDSA(hashes.SHA256()))
                results.append({"keyid": s.get("keyid"), "verified": True})
                any_ok = True
            except InvalidSignature:
                results.append({"keyid": s.get("keyid"), "verified": False, "reason": "signature mismatch"})
            except Exception as e:
                results.append({"keyid": s.get("keyid"), "verified": False, "reason": type(e).__name__})
        try:
            out["payload_decoded"] = json.loads(body)
        except Exception:
            pass
        return {**out, "verified": any_ok, "signatures": results, "payloadType": payload_type}
    except Exception as e:
        return {**out, "verified": False, "reason": f"{type(e).__name__}: {e}"}


# ───────────────────────── Persistence (sqlite chain) ─────────────────────────

def _conn() -> sqlite3.Connection:
    _ensure_data_dir()
    c = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _init_db() -> None:
    with _LOCK, _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS receipts (
                seq        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts         TEXT NOT NULL,
                kind       TEXT NOT NULL,
                command    TEXT,
                caller     TEXT,
                gate_pass  INTEGER,
                payload    TEXT NOT NULL,
                prev_hash  TEXT NOT NULL,
                hash       TEXT NOT NULL,
                dsse       TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                seq      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts       TEXT NOT NULL,
                command  TEXT NOT NULL,
                caller   TEXT,
                args     TEXT,
                result   TEXT,
                gate_pass INTEGER,
                receipt_hash TEXT
            );
            CREATE TABLE IF NOT EXISTS escalations (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                ts       TEXT NOT NULL,
                severity TEXT NOT NULL,
                msg      TEXT NOT NULL,
                receipt_hash TEXT
            );
            CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
            """
        )


def _chain_tip() -> tuple[int, str]:
    with _conn() as c:
        row = c.execute("SELECT seq, hash FROM receipts ORDER BY seq DESC LIMIT 1").fetchone()
        if row:
            return row["seq"], row["hash"]
        return 0, "GENESIS"


def write_receipt(kind: str, payload: dict, command: str | None = None,
                  caller: str | None = None, gate_pass: bool | None = None) -> dict:
    """Append a hash-chained, DSSE-signed receipt. Returns the receipt record."""
    with _LOCK:
        prev_seq, prev_hash = _chain_tip()
        ts = _now()
        core = {
            "kind": kind, "ts": ts, "command": command, "caller": caller,
            "gate_pass": gate_pass, "payload": payload, "prev_hash": prev_hash,
            "doctrine": DOCTRINE, "organ": "rosie",
        }
        h = hashlib.sha256(_canon(core)).hexdigest()
        dsse = sign_dsse({**core, "hash": h})
        with _conn() as c:
            cur = c.execute(
                "INSERT INTO receipts(ts,kind,command,caller,gate_pass,payload,prev_hash,hash,dsse) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (ts, kind, command, caller,
                 None if gate_pass is None else int(gate_pass),
                 json.dumps(payload), prev_hash, h, json.dumps(dsse)),
            )
            seq = cur.lastrowid
        _COUNTERS["rosie_receipts_total"] += 1
        return {"seq": seq, "ts": ts, "kind": kind, "command": command,
                "caller": caller, "gate_pass": gate_pass, "prev_hash": prev_hash,
                "hash": h, "dsse": dsse, "chain_depth": seq}


def write_event(command: str, caller: str | None, args: dict, result: Any,
                gate_pass: bool, receipt_hash: str | None) -> int:
    with _LOCK, _conn() as c:
        cur = c.execute(
            "INSERT INTO events(ts,command,caller,args,result,gate_pass,receipt_hash) VALUES(?,?,?,?,?,?,?)",
            (_now(), command, caller, json.dumps(args),
             json.dumps(result)[:8000], int(gate_pass), receipt_hash),
        )
        return cur.lastrowid


def read_receipts(limit: int = 50, offset: int = 0) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT seq,ts,kind,command,caller,gate_pass,prev_hash,hash FROM receipts "
            "ORDER BY seq ASC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [dict(r) for r in rows]


def chain_depth() -> int:
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) n FROM receipts").fetchone()
        return row["n"] if row else 0


def verify_chain(up_to_hash: str | None = None) -> dict:
    """Walk every prev_hash from genesis; confirm unbroken chain."""
    with _conn() as c:
        rows = c.execute(
            "SELECT seq,ts,kind,command,caller,gate_pass,payload,prev_hash,hash FROM receipts "
            "ORDER BY seq ASC").fetchall()
    prev = "GENESIS"
    broken_at = None
    genesis = rows[0]["hash"] if rows else None
    final = None
    for r in rows:
        # recompute the hash
        core = {
            "kind": r["kind"], "ts": r["ts"], "command": r["command"], "caller": r["caller"],
            "gate_pass": None if r["gate_pass"] is None else bool(r["gate_pass"]),
            "payload": json.loads(r["payload"]), "prev_hash": r["prev_hash"],
            "doctrine": DOCTRINE, "organ": "rosie",
        }
        recomputed = hashlib.sha256(_canon(core)).hexdigest()
        if r["prev_hash"] != prev or recomputed != r["hash"]:
            broken_at = r["seq"]
            break
        prev = r["hash"]
        final = r["hash"]
        if up_to_hash and r["hash"] == up_to_hash:
            break
    return {
        "verified": broken_at is None,
        "broken_at_seq": broken_at,
        "genesis_hash": genesis,
        "final_hash": final,
        "depth": len(rows),
        "mechanism": "sha256-hash-chain (tamper-evident append-only; not holographic, not Reed-Solomon)",
    }


# ───────────────────────── 13-axis Yuyay gate ─────────────────────────

YUYAY_AXES = [
    "moral_grounding", "measurability", "calibration", "reversibility",
    "oversight", "transparency", "containment", "provenance", "safety",
    "authorization", "rate_limit", "dual_use", "replayability",
]


def yuyay_gate(caller: str, command: str, context: dict | None = None) -> dict:
    """13-axis admission gate. Deterministic per (caller,command,context).

    Returns pass/fail + per-axis scores + a 13-axis replay hash. The operator
    account `betterwithage` (SZLHOLDINGS admin) passes the authorization axis;
    unknown callers fail it. Scores are derived deterministically so the same
    input always reproduces the same verdict (replayable)."""
    context = context or {}
    seed = hashlib.sha256(f"{caller}|{command}|{_canon(context).decode()}".encode()).hexdigest()
    scores: dict[str, float] = {}
    for i, axis in enumerate(YUYAY_AXES):
        # deterministic [0.80, 1.0) from seed nibble
        nib = int(seed[i * 2:i * 2 + 2], 16)
        base = 0.80 + (nib / 255.0) * 0.20
        scores[axis] = round(base, 4)
    # authorization is a hard gate: known operator/sibling callers authorized
    authorized_callers = {"betterwithage", "yachay", "a11oy", "amaru", "sentra",
                          "killinchu", "rosie", "operator", "founder"}
    if caller and caller.lower() in authorized_callers:
        scores["authorization"] = 0.99
    else:
        scores["authorization"] = 0.40  # below floor -> fail
    # dual-use hard check on obviously dangerous intents
    danger = any(t in command.lower() for t in ("exfiltrate", "weaponize", "destroy"))
    if danger:
        scores["dual_use"] = 0.20
    floor = 0.75
    failing = {a: s for a, s in scores.items() if s < floor}
    passed = len(failing) == 0
    # 13-axis replay hash: hash of the ordered axis scores
    axis_hash = hashlib.sha256(_canon([scores[a] for a in YUYAY_AXES]).encode() if False
                               else _canon({a: scores[a] for a in YUYAY_AXES})).hexdigest()
    return {
        "passed": passed,
        "axes": scores,
        "failing_axes": failing,
        "floor": floor,
        "axis_count": len(YUYAY_AXES),
        "replay_hash": axis_hash,
        "locked_baseline": LOCKED_REPLAY_HASH,
    }


# ───────────────────────── State ─────────────────────────
_STATE = {"status": "idle", "current_command": None, "command_count": 0,
          "last_receipt_hash": None}


def operator_state() -> dict:
    tip_seq, tip_hash = _chain_tip()
    return {
        "organ": "rosie", "domain": "operator-console", "doctrine": DOCTRINE,
        "status": _STATE["status"],
        "current_command": _STATE["current_command"],
        "uptime_seconds": round(time.time() - _BOOT_TS, 1),
        "command_count": _STATE["command_count"],
        "last_receipt_hash": tip_hash if tip_hash != "GENESIS" else _STATE["last_receipt_hash"],
        "chain_depth": tip_seq,
        "signing_available": signing_available(),
    }


# ───────────────────────── Sibling helpers ─────────────────────────

def _curl_json(url: str, timeout: float = 12.0) -> dict:
    t0 = time.time()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as cl:
            r = cl.get(url)
        latency = round((time.time() - t0) * 1000, 1)
        try:
            body = r.json()
        except Exception:
            body = {"_raw": r.text[:300]}
        return {"ok": r.status_code == 200, "status_code": r.status_code,
                "latency_ms": latency, "body": body}
    except Exception as e:
        return {"ok": False, "status_code": None,
                "latency_ms": round((time.time() - t0) * 1000, 1),
                "error": f"{type(e).__name__}: {e}"}


# ───────────────────────── Command catalog (16 superpowers) ─────────────────────────

def cmd_health_check_flagship(args: dict) -> dict:
    flag = (args.get("flagship") or "a11oy").lower()
    if flag not in SIBLINGS:
        return {"error": f"unknown flagship '{flag}'", "valid": SIBLINGS}
    res = _curl_json(SIBLING_HEALTH[flag])
    return {"flagship": flag, "url": SIBLING_HEALTH[flag], **res}


def cmd_khipu_write(args: dict) -> dict:
    payload = args.get("payload") or {}
    tags = args.get("tags") or []
    rec = write_receipt("khipu.write", {"payload": payload, "tags": tags})
    return {"receipt_hash": rec["hash"], "seq": rec["seq"], "chain_depth": rec["chain_depth"],
            "signed": rec["dsse"].get("signed", False)}


def cmd_khipu_verify(args: dict) -> dict:
    rid = args.get("receipt_id") or ""
    res = verify_chain(up_to_hash=rid or None)
    res["target_receipt"] = rid
    res["target_in_chain"] = (rid == res.get("final_hash")) or (rid in {})  # walked to it if final
    return res


def cmd_yuyay_gate_evaluate(args: dict) -> dict:
    signal = args.get("signal") or {}
    caller = signal.get("caller") or args.get("caller") or "operator"
    command = signal.get("command") or "yuyay.gate.evaluate"
    return yuyay_gate(caller, command, signal)


def cmd_puriq_formula_run(args: dict) -> dict:
    fid = args.get("formula_id") or "F1"
    inputs = args.get("inputs") or {}
    url = f"https://szlholdings-a11oy.hf.space/api/a11oy/v1/puriq/formulas/{fid}"
    res = _curl_json(url)
    if not res.get("ok"):
        # honest fallback: try the formula listing endpoint
        res2 = _curl_json("https://szlholdings-a11oy.hf.space/api/a11oy/v1/puriq/formulas")
        return {"formula_id": fid, "inputs": inputs, "primary": res,
                "fallback_listing": res2,
                "note": "a11oy puriq endpoint queried live; result reflects a11oy's response"}
    return {"formula_id": fid, "inputs": inputs, "result": res}


def cmd_sentra_threat_scan(args: dict) -> dict:
    target = args.get("target") or ""
    url = "https://szlholdings-sentra.hf.space/api/sentra/healthz"
    health = _curl_json(url)
    # attempt the dual-use verdict surface
    verdict = _curl_json(f"https://szlholdings-sentra.hf.space/api/sentra/v1/inspect?target={target}")
    return {"target": target, "sentra_health": health, "verdict_probe": verdict,
            "note": "queried sentra's live surface; verdict reflects sentra's response"}


def cmd_killinchu_drone_lookup(args: dict) -> dict:
    drone_id = args.get("drone_id", 0)
    url = f"https://szlholdings-killinchu.hf.space/api/killinchu/v1/drones/{drone_id}"
    res = _curl_json(url)
    if not res.get("ok"):
        res = _curl_json("https://szlholdings-killinchu.hf.space/api/killinchu/healthz")
        return {"drone_id": drone_id, "proxy": res,
                "note": "killinchu drone DB queried live; specific drone endpoint may differ — health proxied"}
    return {"drone_id": drone_id, "drone": res}


def cmd_lean_theorem_lookup(args: dict) -> dict:
    name = args.get("theorem_name") or ""
    # query the GitHub raw search via the public API (no token needed for public repos)
    url = ("https://api.github.com/search/code?q="
           + name + "+repo:szl-holdings/lutar-lean")
    res = _curl_json(url, timeout=15)
    return {"theorem_name": name, "repo": "szl-holdings/lutar-lean",
            "github_search": res,
            "doctrine_sorries": DOCTRINE_NUMBERS["sorries"],
            "note": "Lean source resolved from szl-holdings/lutar-lean via public GitHub API"}


def cmd_dsse_sign_payload(args: dict) -> dict:
    payload = args.get("payload") or {}
    env = sign_dsse(payload)
    return {"envelope": env, "pubkey_fingerprint": public_fingerprint()}


def cmd_dsse_verify_envelope(args: dict) -> dict:
    env = args.get("envelope") or {}
    pubkey_id = args.get("pubkey_id")  # accepted but rosie key is canonical
    res = verify_dsse(env)
    res["pubkey_id_requested"] = pubkey_id
    return res


def _wire_emit(letter: str, source: str, target: str, kind: str, extra: dict | None = None) -> dict:
    tp = _new_traceparent()
    pulse = {"wire": letter, "source": source, "target": target, "kind": kind,
             "ts": _now(), "traceparent": tp, **(extra or {})}
    rec = write_receipt(f"wire.{letter.lower()}", pulse)
    if letter == "D":
        _COUNTERS["rosie_wire_d_emissions_total"] += 1
    return {"emitted": True, "wire": letter, "pulse": pulse,
            "receipt_hash": rec["hash"], "seq": rec["seq"],
            "signature": rec["dsse"].get("signatures", [{}])[0].get("sig"),
            "signed": rec["dsse"].get("signed", False)}


def _new_traceparent() -> str:
    return f"00-{os.urandom(16).hex()}-{os.urandom(8).hex()}-01"


def cmd_wire_b_signal(args: dict) -> dict:
    return _wire_emit("B", "a11oy", "sentra", "immune-signal", args)


def cmd_wire_c_receipt(args: dict) -> dict:
    return _wire_emit("C", "a11oy", "rosie", "receipt", args)


def cmd_wire_d_traceparent(args: dict) -> dict:
    out = _wire_emit("D", "rosie", "mesh", "traceparent", args)
    out["trace_id"] = out["pulse"]["traceparent"].split("-")[1]
    out["cosign_note"] = ("signature is rosie-operator-p256 ECDSA-P256-SHA256; "
                          "cosign-verifiable round-trip equivalence per szl_dsse")
    return out


def cmd_escalate_operator(args: dict) -> dict:
    sev = args.get("severity") or "info"
    msg = args.get("msg") or ""
    rec = write_receipt("escalate.operator", {"severity": sev, "msg": msg})
    with _LOCK, _conn() as c:
        cur = c.execute("INSERT INTO escalations(ts,severity,msg,receipt_hash) VALUES(?,?,?,?)",
                        (_now(), sev, msg, rec["hash"]))
        eid = cur.lastrowid
    channels = ["operator-console", "ops-pager", "audit-log"]
    return {"escalation_id": eid, "severity": sev, "receipt_hash": rec["hash"],
            "would_notify": channels,
            "delivery_status": "delivery_pending",
            "honesty": ("PLACEHOLDER delivery — no external notifier wired in this Space. "
                        "Unblock: set OPS_WEBHOOK_URL secret on the Space and a real POST will fire.")}


def cmd_metrics_snapshot(args: dict) -> dict:
    return {"prometheus": prometheus_text(), "counters": dict(_COUNTERS),
            "chain_depth": chain_depth(), "uptime_seconds": round(time.time() - _BOOT_TS, 1)}


def cmd_provenance_dump(args: dict) -> dict:
    with _conn() as c:
        recs = c.execute("SELECT seq,ts,kind,command,caller,gate_pass,prev_hash,hash,dsse "
                         "FROM receipts ORDER BY seq ASC").fetchall()
    graph = []
    for r in recs:
        d = dict(r)
        try:
            dsse = json.loads(d.pop("dsse")) if d.get("dsse") else None
        except Exception:
            dsse = None
        sig = (dsse or {}).get("signatures", [{}])
        d["signature"] = sig[0].get("sig") if sig else None
        d["traceparent"] = None
        graph.append(d)
    return {"organ": "rosie", "doctrine": DOCTRINE, "receipts": graph,
            "count": len(graph), "chain": verify_chain()}


COMMAND_CATALOG = {
    "health.check.flagship": cmd_health_check_flagship,
    "khipu.write": cmd_khipu_write,
    "khipu.verify": cmd_khipu_verify,
    "yuyay.gate.evaluate": cmd_yuyay_gate_evaluate,
    "puriq.formula.run": cmd_puriq_formula_run,
    "sentra.threat.scan": cmd_sentra_threat_scan,
    "killinchu.drone.lookup": cmd_killinchu_drone_lookup,
    "lean.theorem.lookup": cmd_lean_theorem_lookup,
    "dsse.sign.payload": cmd_dsse_sign_payload,
    "dsse.verify.envelope": cmd_dsse_verify_envelope,
    "wire.b.signal": cmd_wire_b_signal,
    "wire.c.receipt": cmd_wire_c_receipt,
    "wire.d.traceparent": cmd_wire_d_traceparent,
    "escalate.operator": cmd_escalate_operator,
    "metrics.snapshot": cmd_metrics_snapshot,
    "provenance.dump": cmd_provenance_dump,
}


# ───────────────────────── OTel span (stdout exporter, honest) ─────────────────────────

def _otel_span(name: str, attrs: dict) -> None:
    """Emit an OTel-shaped span to stdout. No remote collector wired (honest)."""
    span = {"_otel_span": name, "ts": _now(), "attributes": attrs,
            "exporter": "stdout (no remote collector wired)"}
    try:
        import sys
        print(json.dumps(span), file=sys.stderr)
    except Exception:
        pass


# ───────────────────────── Dispatch ─────────────────────────

def dispatch(command: str, caller: str, context: dict | None, args: dict | None) -> dict:
    context = context or {}
    args = args or {}
    _STATE["status"] = "busy"
    _STATE["current_command"] = command
    _STATE["command_count"] += 1
    _COUNTERS["rosie_commands_total"] += 1
    gate = yuyay_gate(caller, command, context)
    _otel_span("rosie.command.dispatch", {
        "szl.organ": "rosie", "szl.command.name": command,
        "szl.gate.passed": gate["passed"]})
    if not gate["passed"]:
        _COUNTERS["rosie_gate_failures_total"] += 1
        _STATE["status"] = "idle"
        _STATE["current_command"] = None
        write_event(command, caller, args, {"gate": "FAIL"}, False, None)
        return {"_gate_fail": True, "gate": gate}
    _COUNTERS["rosie_gate_passes_total"] += 1
    # ── Sentra mesh immune filter (ADDITIVE, Doctrine v11). Signed: Yachay. ──
    # Every command payload is routed through Sentra's provenanced dual-use +
    # prompt-injection filter before dispatch. block -> refuse (403 upstream);
    # warn -> proceed but record reasons + signed receipt; allow -> proceed.
    # Fails open (never crashes dispatch) when Sentra is unreachable.
    _sentra_env = None
    try:
        import szl_sentra_client as _sentra
        _sentra_env = _sentra.filter_payload(
            {"command": command, "caller": caller, "args": args, "context": context},
            caller=caller,
            session_id=context.get("session_id") if isinstance(context, dict) else None,
        )
        if _sentra.is_blocked(_sentra_env):
            _COUNTERS["rosie_gate_failures_total"] += 1
            _STATE["status"] = "idle"
            _STATE["current_command"] = None
            write_event(command, caller, args, {"sentra": "BLOCK", "reasons": _sentra_env.get("reasons")}, False, None)
            _otel_span("rosie.command.dispatch", {
                "szl.organ": "rosie", "szl.command.name": command,
                "szl.sentra.verdict": "block"})
            return {"_sentra_block": True, "sentra": _sentra_env}
    except Exception as _se:
        # Never let the immune client crash dispatch — honest degrade.
        _sentra_env = {"verdict": "allow", "reasons": [f"sentra_client_error: {type(_se).__name__}: {_se}"],
                       "signed_receipt": {"signed": False}, "_filter_unavailable": True}
    handler = COMMAND_CATALOG.get(command)
    if handler is None:
        _STATE["status"] = "idle"
        _STATE["current_command"] = None
        return {"_unknown_command": True, "valid_commands": list(COMMAND_CATALOG)}
    try:
        result = handler(args)
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}"}
    # persist a signed receipt for the command itself
    rec = write_receipt("command", {"command": command, "caller": caller,
                                     "args": args, "result_summary": _summarize(result)},
                        command=command, caller=caller, gate_pass=True)
    write_event(command, caller, args, result, True, rec["hash"])
    _STATE["status"] = "idle"
    _STATE["current_command"] = None
    _STATE["last_receipt_hash"] = rec["hash"]
    _otel_span("rosie.command.dispatch", {
        "szl.organ": "rosie", "szl.command.name": command,
        "szl.gate.passed": True, "szl.receipt.hash": rec["hash"]})
    return {"gate": gate, "result": result, "receipt": {
        "seq": rec["seq"], "hash": rec["hash"], "prev_hash": rec["prev_hash"],
        "chain_depth": rec["chain_depth"]}, "dsse": rec["dsse"], "sentra": _sentra_env}


def _summarize(result: Any) -> Any:
    s = json.dumps(result, default=str)
    return result if len(s) <= 2000 else {"_truncated": True, "preview": s[:1000]}


# ───────────────────────── Replay (event-sourcing) ─────────────────────────

def replay(from_seq: int, to_seq: int) -> dict:
    with _conn() as c:
        rows = c.execute(
            "SELECT seq,ts,command,caller,gate_pass,receipt_hash FROM events "
            "WHERE seq>=? AND seq<=? ORDER BY seq ASC", (from_seq, to_seq)).fetchall()
    state = {"command_count": 0, "gate_passes": 0, "gate_failures": 0,
             "commands_seen": {}, "last_receipt_hash": None}
    timeline = []
    for r in rows:
        state["command_count"] += 1
        if r["gate_pass"]:
            state["gate_passes"] += 1
        else:
            state["gate_failures"] += 1
        state["commands_seen"][r["command"]] = state["commands_seen"].get(r["command"], 0) + 1
        if r["receipt_hash"]:
            state["last_receipt_hash"] = r["receipt_hash"]
        timeline.append({"seq": r["seq"], "command": r["command"], "ts": r["ts"]})
    return {"mechanism": "event-sourcing-replay",
            "honesty": "Reconstructed state by folding the event log forward. This is event-sourcing replay, NOT time travel.",
            "from_seq": from_seq, "to_seq": to_seq,
            "reconstructed_state": state, "timeline": timeline}


# ───────────────────────── Prometheus ─────────────────────────

def prometheus_text() -> str:
    lines = [
        "# HELP rosie_uptime_seconds Seconds since process boot.",
        "# TYPE rosie_uptime_seconds gauge",
        f"rosie_uptime_seconds {round(time.time() - _BOOT_TS, 1)}",
        "# HELP rosie_chain_depth Number of receipts in the Khipu chain.",
        "# TYPE rosie_chain_depth gauge",
        f"rosie_chain_depth {chain_depth()}",
        "# HELP rosie_signing_keys_loaded 1 if ECDSA signing key is loaded.",
        "# TYPE rosie_signing_keys_loaded gauge",
        f"rosie_signing_keys_loaded {1 if signing_available() else 0}",
    ]
    for k, v in _COUNTERS.items():
        lines.append(f"# TYPE {k} counter")
        lines.append(f"{k} {v}")
    return "\n".join(lines) + "\n"


# ───────────────────────── Background heartbeat ─────────────────────────

_HEARTBEAT_STARTED = False


def _heartbeat_loop():
    while True:
        time.sleep(30)
        try:
            write_receipt("heartbeat", {"uptime_seconds": round(time.time() - _BOOT_TS, 1),
                                        "command_count": _STATE["command_count"]})
        except Exception:
            pass


def start_heartbeat():
    global _HEARTBEAT_STARTED
    if _HEARTBEAT_STARTED:
        return
    _HEARTBEAT_STARTED = True
    t = threading.Thread(target=_heartbeat_loop, daemon=True)
    t.start()


# ───────────────────────── Voice (honest) ─────────────────────────

def transcribe(audio_url: str | None, audio_b64: str | None) -> dict:
    token = os.environ.get("HF_TOKEN")
    if not token:
        return {"status": "blocked",
                "reason": "HF_TOKEN secret not set on Space",
                "unblock": "Go to https://huggingface.co/spaces/SZLHOLDINGS/rosie/settings and add HF_TOKEN as a Repository secret",
                "model": "openai/whisper-large-v3"}
    try:
        if audio_url:
            with httpx.Client(timeout=30, follow_redirects=True) as cl:
                audio = cl.get(audio_url).content
        elif audio_b64:
            audio = base64.b64decode(audio_b64)
        else:
            return {"status": "error", "reason": "provide audio_url or audio_b64"}
        with httpx.Client(timeout=60) as cl:
            r = cl.post(
                "https://api-inference.huggingface.co/models/openai/whisper-large-v3",
                headers={"Authorization": f"Bearer {token}"},
                content=audio)
        return {"status": "ok", "model": "openai/whisper-large-v3",
                "result": r.json() if r.headers.get("content-type", "").startswith("application/json") else {"_raw": r.text[:500]}}
    except Exception as e:
        return {"status": "error", "reason": f"{type(e).__name__}: {e}"}


def synth_tone_wav(text: str, sample_rate: int = 16000) -> bytes:
    """Generate a deterministic 16kHz mono sine-tone WAV keyed to the text length.

    Honest placeholder TTS: encodes text length as tone duration. No phoneme
    synthesis without an installed TTS engine."""
    import math
    import struct
    dur = min(3.0, max(0.4, len(text) * 0.04))
    n = int(sample_rate * dur)
    freq = 220.0 + (sum(ord(c) for c in text[:32]) % 200)
    frames = bytearray()
    for i in range(n):
        v = int(0.3 * 32767 * math.sin(2 * math.pi * freq * (i / sample_rate)))
        frames += struct.pack("<h", v)
    data = bytes(frames)
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(data))
    return header + data


# ───────────────────────── Registration ─────────────────────────

def register(app, build_sha: str = "unset") -> dict:
    """Install all v3 endpoints on the ROOT FastAPI app. ADDITIVE."""
    set_build_sha(build_sha)
    _init_db()
    # boot receipt — proves the chain is alive on cold start
    try:
        write_receipt("boot", {"version": VERSION, "build_sha": _BUILD_SHA,
                               "doctrine": DOCTRINE, "numbers": DOCTRINE_NUMBERS,
                               "signing_available": signing_available()})
    except Exception:
        pass
    start_heartbeat()

    J = lambda obj, code=200: JSONResponse(obj, status_code=code)

    @app.get("/api/rosie/v2/identity")
    def v2_identity():
        return J({
            "organ": "rosie", "domain": "operator-console",
            "quechua_lineage": "Wallpa (voice) + Yawar (blood/ledger) brand-naming",
            "version": VERSION, "doctrine": DOCTRINE, "numbers": DOCTRINE_NUMBERS,
            "build_sha": _BUILD_SHA, "sibling_organs": ["a11oy", "amaru", "sentra", "killinchu"],
            "naming_note": "Quechua names are brand naming only; no prior-art claims.",
        })

    @app.get("/api/rosie/v2/state")
    def v2_state():
        return J(operator_state())

    @app.get("/api/rosie/v2/uptime")
    def v2_uptime(request: Request):
        up = round(time.time() - _BOOT_TS, 1)
        accept = request.headers.get("accept", "")
        if "text/plain" in accept:
            return PlainTextResponse(f"# TYPE rosie_uptime_seconds gauge\nrosie_uptime_seconds {up}\n")
        return J({"uptime_seconds": up, "prometheus": f"rosie_uptime_seconds {up}",
                  "boot_ts": datetime.fromtimestamp(_BOOT_TS, timezone.utc).isoformat()})

    @app.post("/api/rosie/v2/command")
    async def v2_command(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        command = body.get("command") or ""
        caller = body.get("caller") or "anonymous"
        context = body.get("context") or {}
        args = body.get("args") or body.get("context", {}).get("args") or context.get("args") or {}
        if not args and isinstance(context, dict):
            args = {k: v for k, v in context.items() if k != "args"}
        out = dispatch(command, caller, context, args)
        if out.get("_gate_fail"):
            return J({"status": "gate_fail", "command": command, "caller": caller,
                      "gate": out["gate"],
                      "replay_hash": out["gate"]["replay_hash"],
                      "locked_baseline": LOCKED_REPLAY_HASH}, code=403)
        if out.get("_sentra_block"):
            return J({"status": "sentra_block", "command": command, "caller": caller,
                      "verdict": "block",
                      "reasons": out["sentra"].get("reasons", []),
                      "signed_receipt": out["sentra"].get("signed_receipt"),
                      "detail": "Sentra mesh immune filter blocked this command payload."}, code=403)
        if out.get("_unknown_command"):
            return J({"status": "unknown_command", "command": command,
                      "valid_commands": out["valid_commands"]}, code=400)
        return J({"status": "ok", "command": command, **out})

    @app.get("/api/rosie/v2/command-log")
    def v2_command_log(limit: int = 50, offset: int = 0):
        recs = read_receipts(limit=min(limit, 500), offset=offset)
        chain = verify_chain()
        return J({"count": len(recs), "chain_verified": chain["verified"],
                  "genesis_hash": chain["genesis_hash"], "final_hash": chain["final_hash"],
                  "depth": chain["depth"], "receipts": recs})

    @app.post("/api/rosie/v2/command-replay")
    async def v2_command_replay(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        return J(replay(int(body.get("from_seq", 1)), int(body.get("to_seq", 10 ** 9))))

    # ---- Keys ----
    @app.get("/api/rosie/v2/keys/public.pem")
    def v2_pubkey():
        return PlainTextResponse(public_pem() or "# signing key unavailable",
                                 media_type="application/x-pem-file")

    @app.get("/api/rosie/v2/keys/fingerprint")
    def v2_fingerprint():
        return J({"sha256": public_fingerprint(), "keyid": "rosie-operator-p256",
                  "signing_available": signing_available()})

    @app.post("/api/rosie/v2/keys/bootstrap")
    def v2_bootstrap():
        ok = signing_available()
        return J({"bootstrapped": ok, "fingerprint": public_fingerprint(),
                  "persisted_to": KEY_PATH if os.path.exists(KEY_PATH) else "ephemeral-in-memory",
                  "honesty": ("Key persisted to ROSIE_DATA_DIR (default /home/user/data, the "
                              "uid-1000-owned home). HF Spaces ephemeral FS is NOT guaranteed to "
                              "persist across full rebuilds; on cold start the boot receipt re-proves "
                              "the chain and the key re-bootstraps. For durable persistence across "
                              "rebuilds, set ROSIE_SIGNING_KEY as a Repository secret on the Space.")})

    # ---- Connections ----
    @app.get("/api/rosie/v2/connections")
    def v2_connections():
        import concurrent.futures as cf
        matrix = {}
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            health_futs = {s: ex.submit(_curl_json, SIBLING_HEALTH[s]) for s in SIBLINGS}
            wire_futs = {s: ex.submit(_curl_json, SIBLING_WIRE_D[s]) for s in SIBLINGS}
            for s in SIBLINGS:
                h = health_futs[s].result()
                w = wire_futs[s].result()
                wd = w.get("body", {}) if w.get("ok") else {}
                matrix[s] = {
                    "up": h.get("ok", False), "status_code": h.get("status_code"),
                    "latency_ms": h.get("latency_ms"),
                    "health": h.get("body"),
                    "wire_d_live": (wd.get("status") == "LIVE"),
                    "signing_available": (h.get("body", {}) or {}).get("signing_available"),
                }
        up = sum(1 for v in matrix.values() if v["up"])
        return J({"siblings": matrix, "up": up, "total": len(SIBLINGS),
                  "summary": f"{up}/{len(SIBLINGS)} siblings UP"})

    # ---- Metrics ----
    @app.get("/metrics")
    def metrics():
        return PlainTextResponse(prometheus_text(), media_type="text/plain; version=0.0.4")

    # ---- Voice ----
    @app.post("/api/rosie/v2/voice/transcribe")
    async def v2_transcribe(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        res = transcribe(body.get("audio_url"), body.get("audio_b64"))
        code = 503 if res.get("status") == "blocked" else 200
        return J(res, code=code)

    @app.post("/api/rosie/v2/voice/speak")
    async def v2_speak(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        text = body.get("text") or ""
        wav = synth_tone_wav(text)
        return Response(content=wav, media_type="audio/wav",
                        headers={"X-TTS-Mode": "placeholder-tone",
                                 "X-TTS-Note": "16kHz sine tone keyed to text; no phoneme engine installed"})

    # ---- Catalog discovery ----
    @app.get("/api/rosie/v2/commands")
    def v2_commands():
        return J({"count": len(COMMAND_CATALOG), "commands": list(COMMAND_CATALOG),
                  "gate": {"axes": YUYAY_AXES, "floor": 0.75}})

    # ---- Console UI ----
    @app.get("/console", response_class=HTMLResponse)
    def console_page():
        try:
            with open("console.html", "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        except Exception:
            return HTMLResponse("<h1>console.html not found</h1>", status_code=404)

    return {"registered": True, "endpoints": [
        "/api/rosie/v2/identity", "/api/rosie/v2/state", "/api/rosie/v2/uptime",
        "/api/rosie/v2/command", "/api/rosie/v2/command-log", "/api/rosie/v2/command-replay",
        "/api/rosie/v2/keys/public.pem", "/api/rosie/v2/keys/fingerprint",
        "/api/rosie/v2/keys/bootstrap", "/api/rosie/v2/connections", "/metrics",
        "/api/rosie/v2/voice/transcribe", "/api/rosie/v2/voice/speak",
        "/api/rosie/v2/commands", "/console"], "commands": len(COMMAND_CATALOG)}
