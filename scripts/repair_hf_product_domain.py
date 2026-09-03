#!/usr/bin/env python3
"""Repair and prove the canonical Hugging Face custom domain for A11oy.

Authority is deliberately narrow: this controller may mutate only the single
custom-domain attachment on ``SZLHOLDINGS/a11oy``. It removes a wrong current
claim only when the authenticated Space metadata proves that claim belongs to
this Space, submits ``a-11-oy.com``, and then requires both provider metadata
and uncached public HTTP evidence before reporting success.

No DNS, repository contents, visibility, hardware, secrets, models, datasets,
other Spaces, or Cloudflare resources are changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HF_BASE = "https://huggingface.co"
SPACE_ID = "SZLHOLDINGS/a11oy"
SPACE_API = f"{HF_BASE}/api/spaces/{SPACE_ID}"
DOMAIN_API = f"{SPACE_API}/custom-domain"
WHOAMI_API = f"{HF_BASE}/api/whoami-v2"
DESIRED_DOMAIN = "a-11-oy.com"
KNOWN_WRONG_DOMAIN = "www.a-11-oy.com"
READY_STATES = frozenset({"READY", "ACTIVE", "VERIFIED"})
TOKEN_KEYS = (
    "HF_ORG_TOKEN",
    "HF_TOKEN",
    "HUGGINGFACEHUB_API_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
)


class DomainRepairError(RuntimeError):
    """Fail-closed provider or public-proof error."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):  # type: ignore[no-untyped-def]
        return None


def token() -> str:
    for key in TOKEN_KEYS:
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return ""


def safe_error(error: BaseException, bearer: str) -> str:
    try:
        text = str(error)
    except Exception:
        text = "<unprintable>"
    if bearer:
        text = text.replace(bearer, "<redacted>")
    return " ".join(text.split())[:2000] or "<empty>"


def _request(
    method: str,
    url: str,
    *,
    bearer: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
    follow_redirects: bool = True,
) -> tuple[int, dict[str, str], bytes]:
    body = None
    headers = {
        "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
        "User-Agent": "SZL-HF-product-domain-repair/1.0",
        "Cache-Control": "no-cache, no-store",
        "Pragma": "no-cache",
    }
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    opener = (
        urllib.request.build_opener()
        if follow_redirects
        else urllib.request.build_opener(NoRedirect())
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            return (
                int(response.status),
                {key.lower(): value for key, value in response.headers.items()},
                response.read(262144),
            )
    except urllib.error.HTTPError as exc:
        return (
            int(exc.code),
            {key.lower(): value for key, value in exc.headers.items()},
            exc.read(262144),
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DomainRepairError(f"transport failure for {url}: {type(exc).__name__}") from exc


def _json(body: bytes) -> Any:
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def response_summary(status: int, headers: dict[str, str], body: bytes) -> dict[str, Any]:
    """Return bounded non-credential response evidence."""
    parsed = _json(body)
    summary: dict[str, Any] = {
        "status": status,
        "content_type": headers.get("content-type"),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body_bytes": len(body),
    }
    safe_keys = (
        "domain",
        "hostname",
        "host",
        "status",
        "stage",
        "state",
        "message",
        "error",
        "detail",
        "cname",
    )
    if isinstance(parsed, dict):
        for key in safe_keys:
            value = parsed.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                if key in parsed:
                    summary[key] = value
    return summary


def _normalize_domain(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().lower().rstrip(".")
    if not text:
        return None
    if "://" in text:
        try:
            text = (urllib.parse.urlsplit(text).hostname or "").lower().rstrip(".")
        except ValueError:
            return None
    return text or None


def domain_states(space: Any) -> dict[str, str]:
    """Normalize the Hub's runtime.domains response across known shapes."""
    if not isinstance(space, dict):
        return {}
    runtime = space.get("runtime")
    candidates: Any = runtime.get("domains") if isinstance(runtime, dict) else None
    if candidates is None:
        candidates = space.get("domains")
    if isinstance(candidates, dict):
        candidates = [
            {"domain": name, "stage": state}
            for name, state in candidates.items()
        ]
    if not isinstance(candidates, list):
        return {}

    result: dict[str, str] = {}
    for item in candidates:
        if isinstance(item, str):
            name = _normalize_domain(item)
            state = "UNKNOWN"
        elif isinstance(item, dict):
            name = None
            for key in ("domain", "hostname", "host", "name", "url"):
                name = _normalize_domain(item.get(key))
                if name:
                    break
            raw_state = next(
                (
                    item.get(key)
                    for key in ("stage", "status", "state")
                    if item.get(key) is not None
                ),
                "UNKNOWN",
            )
            state = str(raw_state).strip().upper() or "UNKNOWN"
        else:
            continue
        if name:
            result[name] = state
    return result


def custom_domains(states: dict[str, str]) -> dict[str, str]:
    return {
        name: state
        for name, state in states.items()
        if not name.endswith(".hf.space")
    }


def authenticated_space(bearer: str) -> tuple[dict[str, Any], dict[str, Any]]:
    status, headers, body = _request("GET", SPACE_API, bearer=bearer)
    if status != 200:
        raise DomainRepairError(
            "Space metadata request failed: "
            + json.dumps(response_summary(status, headers, body), sort_keys=True)
        )
    value = _json(body)
    if not isinstance(value, dict):
        raise DomainRepairError("Space metadata response was not a JSON object")
    if str(value.get("id") or "").lower() != SPACE_ID.lower():
        raise DomainRepairError(
            f"Space metadata identity mismatch: {value.get('id')!r}"
        )
    return value, response_summary(status, headers, body)


def authenticated_actor(bearer: str) -> dict[str, Any]:
    status, headers, body = _request("GET", WHOAMI_API, bearer=bearer)
    if status != 200:
        raise DomainRepairError(
            "HF token verification failed: "
            + json.dumps(response_summary(status, headers, body), sort_keys=True)
        )
    value = _json(body)
    if not isinstance(value, dict):
        raise DomainRepairError("HF whoami response was not a JSON object")
    actor = str(value.get("name") or "").strip()
    if not actor:
        raise DomainRepairError("HF whoami response did not identify an actor")
    org_names: list[str] = []
    for item in value.get("orgs") or []:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            org_names.append(item["name"])
        elif isinstance(item, str):
            org_names.append(item)
    if "szlholdings" not in {name.lower() for name in org_names}:
        raise DomainRepairError(
            "Authenticated HF actor is not listed in the SZLHOLDINGS organization"
        )
    return {"name": actor, "organizations": sorted(set(org_names))}


def delete_current_domain(bearer: str) -> dict[str, Any]:
    status, headers, body = _request("DELETE", DOMAIN_API, bearer=bearer)
    summary = response_summary(status, headers, body)
    if status not in {200, 202, 204, 404}:
        raise DomainRepairError(
            "HF custom-domain delete failed: " + json.dumps(summary, sort_keys=True)
        )
    return summary


def submit_domain(bearer: str, domain: str) -> dict[str, Any]:
    status, headers, body = _request(
        "POST",
        DOMAIN_API,
        bearer=bearer,
        payload={"domain": domain},
    )
    summary = response_summary(status, headers, body)
    if status not in {200, 201, 202, 204, 409}:
        raise DomainRepairError(
            "HF custom-domain submission failed: " + json.dumps(summary, sort_keys=True)
        )
    return summary


def mutation_plan(states: dict[str, str]) -> list[str]:
    current = custom_domains(states)
    if DESIRED_DOMAIN in current:
        return []
    if not current:
        return ["submit-desired-domain"]
    if set(current) == {KNOWN_WRONG_DOMAIN}:
        return ["delete-known-wrong-domain", "submit-desired-domain"]
    raise DomainRepairError(
        "Unexpected custom-domain attachment(s) on the target Space: "
        + ",".join(sorted(current))
    )


def public_root_probe() -> dict[str, Any]:
    nonce = secrets.token_hex(8)
    url = f"https://{DESIRED_DOMAIN}/?__szl_hf_domain_probe__={nonce}"
    status, headers, body = _request("GET", url, follow_redirects=False, timeout=30)
    text = body[:131072].decode("utf-8", "replace").lower()
    location = headers.get("location")
    final_ok = (
        status == 200
        and location is None
        and ("a11oy" in text or "szl holdings" in text or "szlholdings" in text)
    )
    return {
        "status": status,
        "location": location,
        "content_type": headers.get("content-type"),
        "server": headers.get("server"),
        "x_szl_space": headers.get("x-szl-space"),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body_bytes": len(body),
        "verified": final_ok,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=90)
    parser.add_argument("--interval", type=float, default=10.0)
    args = parser.parse_args()
    if args.attempts < 1 or args.interval < 0:
        parser.error("attempts must be positive and interval must be non-negative")

    bearer = token()
    report: dict[str, Any] = {
        "schema": "szl.hf-product-domain-repair/v1",
        "space": SPACE_ID,
        "desired_domain": DESIRED_DOMAIN,
        "known_wrong_domain": KNOWN_WRONG_DOMAIN,
        "authority": "single-space-custom-domain-only",
        "dns_mutated": False,
        "cloudflare_mutated": False,
        "repo_mutated": False,
        "visibility_mutated": False,
        "hardware_mutated": False,
        "token_recorded": False,
        "status": "BLOCKED",
    }
    if not bearer:
        report["status"] = "UNAVAILABLE"
        report["error"] = "No supported Hugging Face organization token is configured."
        write_report(args.report, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    try:
        report["actor"] = authenticated_actor(bearer)
        before, before_summary = authenticated_space(bearer)
        before_states = domain_states(before)
        report["metadata_before"] = before_summary
        report["domains_before"] = before_states
        plan = mutation_plan(before_states)
        report["plan"] = plan
        actions: list[dict[str, Any]] = []

        for action in plan:
            if action == "delete-known-wrong-domain":
                actions.append({"action": action, "response": delete_current_domain(bearer)})
                for _ in range(12):
                    current, _summary = authenticated_space(bearer)
                    if not custom_domains(domain_states(current)):
                        break
                    time.sleep(2)
                else:
                    raise DomainRepairError(
                        "The known wrong custom domain did not detach from the target Space"
                    )
            elif action == "submit-desired-domain":
                actions.append(
                    {
                        "action": action,
                        "response": submit_domain(bearer, DESIRED_DOMAIN),
                    }
                )
            else:
                raise DomainRepairError(f"Unsupported mutation action: {action}")
        report["actions"] = actions

        last: dict[str, Any] = {}
        for attempt in range(1, args.attempts + 1):
            space, metadata_summary = authenticated_space(bearer)
            states = domain_states(space)
            root = public_root_probe()
            desired_state = states.get(DESIRED_DOMAIN)
            last = {
                "attempt": attempt,
                "metadata": metadata_summary,
                "domains": states,
                "desired_state": desired_state,
                "root": root,
            }
            if root["verified"] and (desired_state or "").upper() in READY_STATES:
                report["status"] = "LIVE_READY"
                report["proof"] = last
                write_report(args.report, report)
                print(json.dumps(report, indent=2, sort_keys=True))
                return 0
            if attempt < args.attempts:
                time.sleep(args.interval)

        report["proof"] = last
        if (last.get("root") or {}).get("verified"):
            report["status"] = "SERVING_PENDING"
            report["error"] = "The apex serves, but Hugging Face has not reported READY."
        else:
            report["status"] = "BLOCKED"
            report["error"] = "The desired custom domain did not reach provider-ready HTTP 200."
        write_report(args.report, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2
    except DomainRepairError as exc:
        report["error"] = safe_error(exc, bearer)
        write_report(args.report, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
