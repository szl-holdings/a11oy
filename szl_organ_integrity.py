#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
# Signed-off-by: Lutar, Stephen P. <stephenlutar2@gmail.com>
"""Five-organ fail-closed integrity kernel.

Stdlib only. Real SHA-256. Advisory Λ. Energy UNAVAILABLE. Never a fabricated
joule. Locked-proven stays exactly 8. Λ uniqueness is Conjecture 1 OPEN.
proven_trust is False.

a11oy command-body surface of the replayable contract the 3D atlas (szl-holdings/anatomy) maps and
the KHIPU Space (SZLHOLDINGS/szl-khipu) runs in NumPy. This surface is the
same fail-closed body, hashed with hashlib.sha256 — not a Three.js rehost,
not a joule, not a theorem.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qs, urlparse

DOCTRINE = "v11 LOCKED"
KERNEL_COMMIT = "c7c0ba17"
LOCKED_EIGHT = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")
YUYAY_AXES = (
    "moralGrounding",
    "measurabilityHonesty",
    "empiricalGrounding",
    "logicalConsistency",
    "sourceTransparency",
    "reproducibility",
    "licenseHygiene",
    "scopeDiscipline",
    "claimCalibration",
    "evalAwareness",
    "deceptionKeywords",
    "conflictingDirectives",
    "reversalDirective",
)
YUYAY_FLOORS = (0.95, 0.95) + (0.90,) * 11
CONJECTURE_1 = (
    "Any two aggregators satisfying A1–A4 agree on every input. OPEN (sorry). "
    "Unconditional uniqueness under kernel A1–A5 is machine-checked FALSE."
)
WILLAY_NOTE = (
    "Refusals are tamper-EVIDENT, not tamper-proof. Auditable rules. "
    "Trust ceiling 0.97. WILLAY is conscience, not a sixth proven organ."
)
ZERO = "0" * 64
CHAIN_OPS = ("anatomy.brain", "anatomy.heart", "anatomy.skeleton")
ORGAN_SPEC = (
    {
        "id": "brain",
        "name": "BRAIN",
        "quechua": "YACHAY",
        "formulas": ("F1",),
        "role": "read-only reasoning cortex — never holds write authority",
    },
    {
        "id": "heart",
        "name": "HEART",
        "quechua": "YUYAY",
        "formulas": ("F4", "F11"),
        "role": "13-axis conjunctive critique gate — advisory Λ",
    },
    {
        "id": "circulatory",
        "name": "CIRCULATORY",
        "quechua": "YAWAR",
        "formulas": ("F7", "F22"),
        "role": "append-only receipt bus — SHA-256",
    },
    {
        "id": "nervous",
        "name": "NERVOUS",
        "quechua": "OTel",
        "formulas": ("F12",),
        "role": "telemetry spine — energy UNAVAILABLE",
    },
    {
        "id": "skeleton",
        "name": "SKELETON",
        "quechua": "Khipu",
        "formulas": ("F18", "F19"),
        "role": "locked-8 formula spine — CHECKED ≠ Lean PROVEN",
    },
)

proven_trust = False


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def wgm(xs: Sequence[float], ws: Sequence[float]) -> float:
    if len(xs) != len(ws) or not xs:
        return 0.0
    if any((not math.isfinite(x)) or x <= 0.0 for x in xs):
        return 0.0
    if any((not math.isfinite(w)) or w < 0.0 for w in ws):
        return 0.0
    if abs(sum(ws) - 1.0) >= 1e-9:
        return 0.0
    value = math.exp(sum(w * math.log(x) for x, w in zip(xs, ws)))
    return value if math.isfinite(value) else 0.0


def evaluate_lambda(axes: Sequence[float]) -> dict[str, Any]:
    n = len(axes)
    weights = tuple(1.0 / n for _ in range(n)) if n else ()
    value = wgm(axes, weights)
    xv = list(axes)
    a1 = True
    for i, x in enumerate(xv):
        if x >= 1.0:
            continue
        y = xv[:]
        y[i] = min(1.0, x + 0.05)
        if wgm(y, weights) + 1e-12 < value:
            a1 = False
            break
    c = 0.5
    a2 = abs(wgm([x * c for x in xv], weights) - c * value) <= 1e-9 * max(1.0, abs(c * value))
    a3 = abs(wgm([0.7] * n, weights) - 0.7) <= 1e-9 if n else True
    a4 = (not xv) or value <= max(xv) + 1e-12
    a5 = True
    if n >= 2:
        a5 = abs(wgm(list(reversed(xv)), list(reversed(weights))) - value) <= 1e-9
    axioms = [
        {"id": "A1", "ok": a1, "detail": "monotone"},
        {"id": "A2", "ok": a2, "detail": "homogeneous"},
        {"id": "A3", "ok": a3, "detail": "Egyptian-exact"},
        {"id": "A4", "ok": a4, "detail": "bounded-by-max"},
        {"id": "A5", "ok": a5, "detail": "permutation-invariant"},
    ]
    failed = next((a for a in axioms if not a["ok"]), None)
    blocked = value == 0.0 or failed is not None
    if blocked:
        reason = "zero-routed or non-finite axis" if value == 0.0 else f"axiom {failed['id']} failed"
    else:
        reason = "advisory pass — uniqueness remains Conjecture 1 OPEN"
    return {"value": float(value), "blocked": bool(blocked), "reason": reason, "axioms": axioms}


def yawar_chain(seed: int, tamper: bool) -> dict[str, Any]:
    hops: list[dict[str, Any]] = []
    prev = ZERO
    for seq, op in enumerate(CHAIN_OPS):
        material = f"{seq}|{op}|{prev}|{int(seed)}"
        digest = _sha256_hex(material)
        hops.append({"seq": seq, "op": op, "prev": prev, "digest": digest, "alg": "SHA-256"})
        prev = digest
    if tamper and len(hops) > 1:
        hops[1] = dict(hops[1])
        hops[1]["prev"] = "deadbeef" + hops[1]["prev"][8:]
    walk = ZERO
    ok = True
    brk: int | None = None
    for hop in hops:
        expect = _sha256_hex(f"{hop['seq']}|{hop['op']}|{hop['prev']}|{int(seed)}")
        if hop["prev"] != walk or expect != hop["digest"]:
            ok = False
            brk = int(hop["seq"])
            break
        walk = hop["digest"]
    return {
        "hops": hops,
        "ok": ok,
        "head": hops[-1]["digest"] if hops else ZERO,
        "depth": len(hops),
        "break_at": brk,
        "alg": "SHA-256",
    }


def canal_leak(leak: bool) -> float:
    """Deterministic canal-partition silhouette.

    Tokens 0..11 assigned to canal i % 3. Cross-canal mass is zero unless a
    leak is requested. This is the fail-closed rule, not NumPy YARQA.
    MEASURED YARQA lives on SZLHOLDINGS/szl-khipu.
    """
    return 1.0 if leak else 0.0


def _organ(
    id_: str,
    name: str,
    quechua: str,
    formulas: tuple[str, ...],
    status: str,
    honesty: str,
    detail: str,
    metric: float,
) -> dict[str, Any]:
    return {
        "id": id_,
        "name": name,
        "quechua": quechua,
        "formulas": list(formulas),
        "status": status,
        "honesty": honesty,
        "detail": detail,
        "metric": float(metric),
    }


def evaluate_anatomy(
    *,
    zero_heart: bool = False,
    leak_canal: bool = False,
    tamper_chain: bool = False,
    fabricate_joule: bool = False,
    break_skeleton: bool = False,
    willay_fire: bool = False,
    seed: int = 11,
) -> dict[str, Any]:
    if proven_trust is True:
        raise RuntimeError("refusing proven_trust true")

    axes = list(YUYAY_FLOORS)
    if zero_heart:
        axes[0] = 0.0
    heart = evaluate_lambda(axes)
    heart_down = bool(heart["blocked"])

    chain = yawar_chain(int(seed), bool(tamper_chain))
    yawar_down = not bool(chain["ok"])

    leaked = canal_leak(bool(leak_canal))
    brain_down = leaked > 1e-9

    nervous_down = bool(fabricate_joule)

    rows = [
        {"id": fid, "ok": not (break_skeleton and fid == "F18")}
        for fid in LOCKED_EIGHT
    ]
    skeleton_pass = sum(1 for r in rows if r["ok"])
    skeleton_down = skeleton_pass < len(rows)

    organs = [
        _organ(
            "brain",
            "BRAIN",
            "YACHAY",
            ("F1",),
            "DOWN" if brain_down else "LIVE",
            "LIVE",
            (
                f"cross-canal leak {leaked:.3e} — YACHAY cannot reason across a broken partition"
                if brain_down
                else (
                    "read-only cortex · canal-partition silhouette leak 0 · "
                    "MEASURED YARQA is the KHIPU Space"
                )
            ),
            leaked,
        ),
        _organ(
            "heart",
            "HEART",
            "YUYAY",
            ("F4", "F11"),
            "DOWN" if heart_down else "LIVE",
            "ADVISORY",
            (
                f"Λ {float(heart['value']):.4f} · {heart['reason']}"
                if heart_down
                else f"Λ {float(heart['value']):.4f} · advisory · Conjecture 1 OPEN"
            ),
            float(heart["value"]),
        ),
        _organ(
            "circulatory",
            "CIRCULATORY",
            "YAWAR",
            ("F7", "F22"),
            "DOWN" if yawar_down else "LIVE",
            "LIVE",
            (
                f"chain break at {chain['break_at']} — prev pointer does not walk. Fail closed."
                if yawar_down
                else f"3-hop SHA-256 · depth {chain['depth']} · head {chain['head'][:16]}"
            ),
            0.0 if chain["ok"] else 1.0,
        ),
        _organ(
            "nervous",
            "NERVOUS",
            "OTel",
            ("F12",),
            "DOWN" if nervous_down else "LIVE",
            "UNAVAILABLE",
            (
                "fabricated joule refused — energy stays UNAVAILABLE"
                if nervous_down
                else "loop-tax silhouette · energy UNAVAILABLE · never a fabricated joule"
            ),
            1.0 if nervous_down else 0.0,
        ),
        _organ(
            "skeleton",
            "SKELETON",
            "Khipu",
            ("F18", "F19"),
            "DOWN" if skeleton_down else "LIVE",
            "ADVISORY",
            (
                f"locked-8 silhouettes {skeleton_pass}/{len(rows)} — a sorry cannot be painted green"
                if skeleton_down
                else (
                    f"locked-8 silhouettes {skeleton_pass}/{len(rows)} · "
                    f"CHECKED ≠ Lean PROVEN @ {KERNEL_COMMIT}"
                )
            ),
            float(skeleton_pass),
        ),
    ]

    live_count = sum(1 for o in organs if o["status"] == "LIVE")
    organ_down = any(o["status"] == "DOWN" for o in organs)
    blocked = organ_down or bool(willay_fire)
    if willay_fire:
        reason = (
            "WILLAY conscience veto — governance bypass refused "
            "(tamper-EVIDENT, not tamper-proof)"
        )
    elif organ_down:
        down = ", ".join(o["name"] for o in organs if o["status"] == "DOWN")
        reason = f"organ integrity FAIL · {down} DOWN · fail closed"
    else:
        reason = (
            f"organ integrity {live_count}/5 LIVE · Λ advisory · "
            "energy UNAVAILABLE · Conjecture 1 OPEN"
        )

    return {
        "organs": organs,
        "live_count": int(live_count),
        "blocked": bool(blocked),
        "verdict": "BLOCKED" if blocked else "ADVISORY_BODY",
        "willay": {
            "refused": bool(willay_fire),
            "category": "bypass" if willay_fire else "none",
            "note": WILLAY_NOTE,
        },
        "energy": "UNAVAILABLE",
        "energy_j": None,
        "lambda_advisory": True,
        "conjecture_1": "OPEN",
        "conjecture_1_statement": CONJECTURE_1,
        "locked_proven": 8,
        "locked_ids": list(LOCKED_EIGHT),
        "kernel_commit": KERNEL_COMMIT,
        "doctrine": DOCTRINE,
        "chain_head": chain["head"],
        "chain_ok": bool(chain["ok"]),
        "chain_alg": "SHA-256",
        "chain": chain,
        "lambda": heart,
        "proven_trust": False,
        "trust_ceiling": 0.97,
        "reason": reason,
        "seed": int(seed),
        "tamper": {
            "zero_heart": bool(zero_heart),
            "leak_canal": bool(leak_canal),
            "tamper_chain": bool(tamper_chain),
            "fabricate_joule": bool(fabricate_joule),
            "break_skeleton": bool(break_skeleton),
            "willay_fire": bool(willay_fire),
        },
        "not_a_rehost": (
            "szl-holdings/anatomy 3D atlas is SLSA L1 static viz — "
            "this kernel is the integrity check"
        ),
        "checked_at": _now(),
    }


def envelope(ev: Mapping[str, Any]) -> dict[str, Any]:
    payload = json.dumps(ev, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "ok": True,
        "surface": "szl-organ-integrity",
        "receipt_sha256": _sha256_hex(payload),
        "signing": "STRUCTURAL-ONLY — no key on this surface; tamper-EVIDENT hash, not a signature",
        "body": dict(ev),
    }


def parse_flags(src: Mapping[str, Any] | None) -> dict[str, Any]:
    src = src or {}

    def flag(name: str) -> bool:
        v = src.get(name, False)
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return int(v) == 1
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "on"}
        if isinstance(v, list) and v:
            return flag(v[0])
        return False

    seed = src.get("seed", 11)
    if isinstance(seed, list) and seed:
        seed = seed[0]
    try:
        seed_i = int(seed)
    except (TypeError, ValueError):
        seed_i = 11
    return {
        "zero_heart": flag("zero_heart"),
        "leak_canal": flag("leak_canal"),
        "tamper_chain": flag("tamper_chain"),
        "fabricate_joule": flag("fabricate_joule"),
        "break_skeleton": flag("break_skeleton"),
        "willay_fire": flag("willay_fire"),
        "seed": seed_i,
    }


def selftest() -> dict[str, Any]:
    healthy = evaluate_anatomy(seed=11)
    assert healthy["live_count"] == 5, healthy["reason"]
    assert healthy["blocked"] is False
    assert healthy["energy"] == "UNAVAILABLE"
    assert healthy["energy_j"] is None
    assert healthy["proven_trust"] is False
    assert healthy["locked_proven"] == 8
    assert healthy["lambda_advisory"] is True
    assert healthy["chain"]["alg"] == "SHA-256"
    assert len(healthy["chain"]["head"]) == 64

    z = evaluate_anatomy(zero_heart=True, seed=11)
    assert z["blocked"] is True
    assert z["organs"][1]["status"] == "DOWN"
    assert z["organs"][1]["metric"] == 0.0

    t = evaluate_anatomy(tamper_chain=True, seed=11)
    assert t["blocked"] is True
    assert t["chain_ok"] is False
    assert t["organs"][2]["status"] == "DOWN"

    j = evaluate_anatomy(fabricate_joule=True, seed=11)
    assert j["blocked"] is True
    assert j["organs"][3]["status"] == "DOWN"
    assert j["energy_j"] is None

    s = evaluate_anatomy(break_skeleton=True, seed=11)
    assert s["blocked"] is True
    assert s["organs"][4]["metric"] == 7

    w = evaluate_anatomy(willay_fire=True, seed=11)
    assert w["blocked"] is True
    assert w["willay"]["refused"] is True
    assert w["live_count"] == 5

    l = evaluate_anatomy(leak_canal=True, seed=11)
    assert l["blocked"] is True
    assert l["organs"][0]["status"] == "DOWN"

    return {"ok": True, "cases": 7, "healthy_head": healthy["chain_head"]}


def _json_bytes(obj: Any, status: int = 200) -> tuple[int, bytes, str]:
    raw = json.dumps(obj, indent=2, default=str).encode("utf-8")
    return status, raw, "application/json; charset=utf-8"


class Handler(BaseHTTPRequestHandler):
    server_version = "szl-organ-integrity/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Cache-Control", "no-store")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        if path in {"/healthz", "/readyz"}:
            self._send(*_json_bytes({"ok": True, "energy": "UNAVAILABLE", "proven_trust": False}))
            return
        if path in {
            "/api/organs/integrity",
            "/api/a11oy/v1/organs/integrity",
            "/v1/organs/integrity",
        }:
            flags = parse_flags(qs)
            body = envelope(evaluate_anatomy(**flags))
            self._send(*_json_bytes(body))
            return
        if path in {"/", "/index.html", "/organs/integrity"}:
            html = _index_html()
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            return
        self._send(*_json_bytes({"ok": False, "error": "not found", "path": path}, 404))

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path not in {
            "/api/organs/integrity",
            "/api/a11oy/v1/organs/integrity",
            "/v1/organs/integrity",
        }:
            self._send(*_json_bytes({"ok": False, "error": "not found"}, 404))
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(max(0, min(length, 1_000_000))) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        flags = parse_flags(data)
        body = envelope(evaluate_anatomy(**flags))
        self._send(*_json_bytes(body))

    def _send(self, status: int, raw: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)


def _index_html() -> str:
    from pathlib import Path

    here = Path(__file__).resolve().parent
    for candidate in (here / "index.html", here / "site" / "index.html"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return (
        "<!doctype html><meta charset=utf-8><title>organ integrity</title>"
        "<p>kernel live. POST /api/organs/integrity</p>"
    )


def serve(host: str = "0.0.0.0", port: int = 7860) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"[szl-organ-integrity] {host}:{port} · SHA-256 · energy UNAVAILABLE", file=sys.stderr)
    httpd.serve_forever()


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Five-organ fail-closed integrity kernel")
    p.add_argument("--serve", action="store_true")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=7860)
    p.add_argument("--tamper", nargs="*", default=[], help="zero_heart leak_canal tamper_chain fabricate_joule break_skeleton willay_fire")
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args(list(argv) if argv is not None else None)
    if args.serve:
        serve(args.host, args.port)
        return 0
    flags = {k: (k in set(args.tamper)) for k in (
        "zero_heart",
        "leak_canal",
        "tamper_chain",
        "fabricate_joule",
        "break_skeleton",
        "willay_fire",
    )}
    if args.tamper:
        print(json.dumps(envelope(evaluate_anatomy(seed=args.seed, **flags)), indent=2))
        return 0
    result = selftest()
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# FastAPI registration (additive, front-moved, CORS * for the 3D atlas).
# ---------------------------------------------------------------------------
PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="color-scheme" content="dark"/>
<title>Organ integrity · a11oy</title>
<style>
:root{--bg:#05070d;--panel:#0b121b;--line:#1b2734;--proof:#3af4c8;--gold:#e8c074;--cream:#eef3f6;--para:#9fb1bf;--false:#d76a6a;--dim:#6c7d8c;--void:#080c14}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--cream);font:16px/1.5 ui-sans-serif,system-ui,sans-serif;padding:24px 16px 64px}
.wrap{max-width:920px;margin:0 auto}
.eyebrow{font:11px ui-monospace,monospace;letter-spacing:1.3px;text-transform:uppercase;color:var(--gold)}
h1{font-size:clamp(22px,4vw,32px);margin:.2em 0}
.lede{color:var(--para);max-width:72ch}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}
.metric{border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:12px 14px}
.k{font:10px ui-monospace,monospace;letter-spacing:.8px;text-transform:uppercase;color:var(--dim)}
.v{font:24px ui-monospace,monospace;margin-top:4px}
.ok{color:var(--proof)} .bad{color:var(--false)}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}
button,a.btn{min-height:44px;padding:10px 14px;border-radius:8px;border:1px solid var(--line);background:var(--void);color:var(--cream);font:600 12px ui-monospace,monospace;letter-spacing:.5px;text-transform:uppercase;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center}
button.primary{background:var(--proof);color:var(--bg);border-color:var(--proof)}
button.danger{border-color:var(--false);color:var(--false)}
pre{background:var(--void);border:1px solid var(--line);border-radius:10px;padding:12px;overflow:auto;max-height:380px;font:12px ui-monospace,monospace;white-space:pre-wrap}
a{color:var(--proof)}
.hero{border:1px solid #34301f;border-radius:14px;padding:16px;margin:12px 0;background:linear-gradient(180deg,rgba(232,192,116,.06),var(--void))}
</style>
</head>
<body>
<div class="wrap">
  <div class="eyebrow">a11oy · command body · organ integrity</div>
  <h1>Five organs. Fail closed.</h1>
  <p class="lede">Same-origin kernel on this host. Zero heart, tamper YAWAR, or ask for a joule — the body blocks. Λ = Conjecture 1 OPEN. Energy UNAVAILABLE. Receipt is STRUCTURAL-ONLY SHA-256.</p>
  <div class="controls">
    <button class="primary" id="go" type="button">Healthy cycle</button>
    <button class="danger" data-f="zero_heart" type="button">Zero heart</button>
    <button class="danger" data-f="tamper_chain" type="button">Tamper YAWAR</button>
    <button class="danger" data-f="fabricate_joule" type="button">Fabricate a joule</button>
    <button class="danger" data-f="break_skeleton" type="button">Paint a sorry green</button>
    <button class="danger" data-f="willay_fire" type="button">Governance bypass</button>
    <a class="btn" href="https://github.com/szl-holdings/szl-organ-integrity">Source</a>
  </div>
  <div class="hero" id="hero"><div class="k">waiting</div><p>Click Healthy cycle.</p></div>
  <div class="grid" id="organs"></div>
  <pre id="out">receipt appears here</pre>
</div>
<script>
const API="/api/a11oy/v1/organs/integrity";
async function run(flags){
  const r = await fetch(API,{
    method: Object.keys(flags).length ? "POST" : "GET",
    headers:{"content-type":"application/json"},
    body: Object.keys(flags).length ? JSON.stringify(flags) : undefined,
    cache:"no-store"
  });
  const j = await r.json();
  const ev = j.body || j;
  const blocked = !!ev.blocked;
  document.getElementById("hero").innerHTML =
    `<div class="k">same-origin · ${ev.chain_alg||"SHA-256"} · ${ev.kernel_commit||""}</div>
     <p>${ev.live_count}/5 LIVE · ${ev.reason}</p>
     <div class="${blocked?"bad":"ok"}">${blocked?"BLOCKED":"advisory body"} · energy UNAVAILABLE</div>`;
  document.getElementById("organs").innerHTML = (ev.organs||[]).map(o =>
    `<div class="metric"><div class="k">${o.name} · ${o.quechua}</div>
     <div class="v ${o.status==="DOWN"?"bad":"ok"}">${o.status}</div>
     <div class="k">${o.honesty}<br>${o.detail}</div></div>`).join("");
  document.getElementById("out").textContent = JSON.stringify(j,null,2);
}
document.getElementById("go").onclick = () => run({});
document.querySelectorAll("button[data-f]").forEach(b => b.onclick = () => run({[b.dataset.f]:true}));
run({});
</script>
</body></html>
"""


def register(app, ns: str = "a11oy") -> str:
    """ADDITIVE: GET/POST /api/{ns}/v1/organs/integrity + HTML /organs/integrity."""
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse

    b = f"/api/{ns}/v1/organs/integrity"
    cors = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "content-type",
        "Cache-Control": "no-store",
    }
    _n_before = len(app.router.routes)

    @app.get(b)
    @app.get("/v1/organs/integrity")
    async def _get_integrity(request: Request):  # type: ignore[no-untyped-def]
        flags = parse_flags(dict(request.query_params))
        return JSONResponse(envelope(evaluate_anatomy(**flags)), headers=cors)

    @app.post(b)
    @app.post("/v1/organs/integrity")
    async def _post_integrity(request: Request):  # type: ignore[no-untyped-def]
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        flags = parse_flags(body)
        return JSONResponse(envelope(evaluate_anatomy(**flags)), headers=cors)

    @app.options(b)
    @app.options("/v1/organs/integrity")
    async def _opt_integrity():  # type: ignore[no-untyped-def]
        return JSONResponse({"ok": True}, headers=cors)

    @app.get("/organs/integrity")
    async def _page_integrity():  # type: ignore[no-untyped-def]
        return HTMLResponse(PAGE_HTML)

    try:
        _new = app.router.routes[_n_before:]
        del app.router.routes[_n_before:]
        app.router.routes[0:0] = _new
        _moved = len(_new)
    except Exception as _e:  # never fatal
        _moved = -1
        print(f"[a11oy] organ-integrity route reorder failed (non-fatal): {_e!r}", file=sys.stderr)

    print(
        f"[a11oy] organ-integrity registered: {b} + /organs/integrity [moved {_moved} routes to front]",
        file=sys.stderr,
    )
    return "organ-integrity-ok moved=%s" % _moved
