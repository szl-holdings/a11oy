#!/usr/bin/env python3
"""five_space_estate_finish.py — honest probe for Grok Terminal.

Usage:
  python3 scripts/five_space_estate_finish.py --check
  python3 scripts/five_space_estate_finish.py --publish-space

Never prints LIVE / RUNNING / PASS unless a probe actually returned it.
Never writes the Hub without HF_TOKEN, and even then refuses a silent push.
Never mints SZLHOLDINGS/five-space.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

PRODUCT = "https://a-11-oy.com"
PROOF = "https://a11oy.net"
NEVER = "https://a11oy.com"

PROBES = [
    ("product_five_space", f"{PRODUCT}/five-space"),
    ("product_status", f"{PRODUCT}/api/a11oy/v1/five-space/status"),
    ("product_healthz", f"{PRODUCT}/api/a11oy/v1/five-space/healthz"),
    ("product_home", f"{PRODUCT}/"),
    ("product_console", f"{PRODUCT}/console"),
    ("proof_five_space", f"{PROOF}/five-space/"),
    ("hub_org", "https://huggingface.co/SZLHOLDINGS"),
    ("hub_a11oy", "https://huggingface.co/spaces/SZLHOLDINGS/a11oy"),
    ("hub_lyte", "https://huggingface.co/spaces/SZLHOLDINGS/lyte-lattice"),
]

OPEN_BLOCKED = [
    "a11oy#1764 make every Space public — blocked-external",
    "a11oy#1836 flagship Space allowlist — blocked-external",
    "a11oy#1282 HF ecosystem drift — blocked-external",
    "a11oy#541 alert channel OFF",
    "szl-hf-frontier#1 C1-C6 / L1-L3 metal — BLOCKED_NO_METAL",
    "szl-forge#124 Codex GPU/eval estate ticket",
]

DONE = [
    "a11oy#1480 five-space route BIND",
    "a11oy#1887 anatomy 302 + source_count 7 allowlist",
    "a11oy#1888 Bound-packages cite restore",
    "a11oy-net#76 RECORD honesty BIND",
    "a11oy-net#133 stalled cut",
    "szl-ouroboros#18 Codex source_count=7",
]


def probe(url: str, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "SZL-GrokTerminal/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read()
            code = getattr(res, "status", 200)
            text = raw.decode("utf-8", "replace")
            out = {"url": url, "http": code, "bytes": len(raw)}
            if "status" in url or url.endswith("healthz"):
                try:
                    out["json"] = json.loads(text)
                except Exception:
                    out["json"] = None
            if url.rstrip("/") == PRODUCT:
                out["cites_five_space"] = (
                    "bind-five-space" in text or "/five-space" in text
                )
                out["honesty_live"] = "Honesty LIVE" in text
            if "five-space" in url and "a11oy.net" not in url and "api/" not in url:
                low = text.lower()
                out["first_paint_connecting"] = "connecting" in low
                out["claims_live"] = ("operator · live" in low) or ("hub running" in low)
            return out
    except Exception as err:
        return {"url": url, "http": None, "state": "UNAVAILABLE", "detail": str(err)}


def check() -> dict:
    token = bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"))
    probes = {name: probe(url) for name, url in PROBES}
    status = (probes.get("product_status") or {}).get("json") or {}
    home = probes.get("product_home") or {}
    page = probes.get("product_five_space") or {}
    honesty = status.get("honesty") or {}
    product = status.get("product") or {}
    accept = {
        "five_space_http_200": probes["product_five_space"].get("http") == 200,
        "status_bind": status.get("state") == "BIND",
        "not_certified": honesty.get("certified") is False
        or product.get("certified") is False,
        "proof_200": probes["proof_five_space"].get("http") == 200,
        "home_cites_package": bool(home.get("cites_five_space")),
        "no_honesty_live": home.get("honesty_live") is not True,
        "no_live_paint": page.get("claims_live") is not True,
    }
    return {
        "bind": "BIND_AS_A11OY_PACKAGE",
        "lambda": "Conjecture 1",
        "doctrine": "v11 LOCKED",
        "signer": "UNSIGNED-honest",
        "proven_trust": False,
        "product_certified": False,
        "hub_write": False,
        "placement": {
            "product": f"{PRODUCT}/five-space",
            "proof": f"{PROOF}/five-space/",
            "hub": "SZLHOLDINGS/a11oy",
            "new_space_refused": "SZLHOLDINGS/five-space",
        },
        "hf_token_present": token,
        "never_origin": NEVER,
        "probes": probes,
        "accept": accept,
        "accept_all": all(accept.values()),
        "done_do_not_redo": DONE,
        "still_open_blocked_external": OPEN_BLOCKED,
        "publish": "UNAVAILABLE" if not token else "TOKEN_PRESENT_NOT_PUBLISHED",
        "next": (
            "Jobs 1–4 on GitHub. Job 5 only if hf_token_present. "
            "Do not create SZLHOLDINGS/five-space. "
            "Do not close blocked-external issues without a token or owner decision."
        ),
    }


def publish() -> dict:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        return {
            "ok": False,
            "state": "UNAVAILABLE",
            "reason": "HF_TOKEN missing. Hub write refused. Space not mocked as RUNNING.",
            "refused_space": "SZLHOLDINGS/five-space",
        }
    return {
        "ok": False,
        "state": "BLOCKED",
        "reason": (
            "Protected publisher only. Refuse a silent Hub write even with a token. "
            "Hand the exact git tip to Sync and Relock Canonical Hugging Face Space "
            "and wait for commit readback before saying RUNNING. "
            "Target SZLHOLDINGS/a11oy only. Never create SZLHOLDINGS/five-space."
        ),
        "space": "SZLHOLDINGS/a11oy",
        "source": "szl-holdings/a11oy",
        "cite": "SZLHOLDINGS/lyte-lattice stays UNAVAILABLE if Hub listing is 401.",
        "refused_space": "SZLHOLDINGS/five-space",
    }


def main(argv: list[str]) -> int:
    out = publish() if "--publish-space" in argv else check()
    print(json.dumps(out, indent=2))
    if "accept_all" in out:
        return 0 if out["accept_all"] else 2
    return 0 if out.get("state") == "UNAVAILABLE" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
