#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One-shot, isolated acceptance rehearsal for the five required POST routes.

This is SIMULATED, declared-source-bound evidence. It cannot replace the canonical,
same-origin readiness probe or authorize a production effect.
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
MARKER = "SZL_EFFECT_ACCEPTANCE_JSON="
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
ROUTES = (
    "/api/a11oy/v1/policy/decide",
    "/api/a11oy/v1/operator/ask",
    "/api/a11oy/v1/eval/run",
    "/api/a11oy/v1/agentloop/run",
    "/api/a11oy/v1/policy/compliance",
)
FEED = "/api/a11oy/v1/policy/decisions/feed?limit=1"
FORUM = "/api/a11oy/v1/llm/forum?limit=1"


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _counts(client):
    feed = client.get(FEED)
    forum = client.get(FORUM)
    if feed.status_code != 200 or forum.status_code != 200:
        raise RuntimeError("readback_unavailable")
    f, m = feed.json(), forum.json()
    if type(f.get("total_buffered")) is not int or type(m.get("total_events")) is not int:
        raise RuntimeError("readback_contract_invalid")
    return {"policy_decisions": f["total_buffered"], "forum_events": m["total_events"]}, f


def _row(path, request, response, before, after, *, passed, reason, semantic=None):
    return {
        "path": path,
        "method": "POST",
        "evidenceClass": "SIMULATED" if passed else "UNAVAILABLE",
        "result": "PASS" if passed else "UNAVAILABLE",
        "reason": reason,
        "requestSha256": _digest(request),
        "statusCode": response.status_code,
        "responseSha256": _digest(response.json()),
        "before": before,
        "after": after,
        "semantic": semantic or {},
        "attempts": 1,
    }


def _post(client, path, payload, headers=None):
    return client.post(path, json=payload, headers=headers or {})


def rehearse(client, operator_token):
    """Run each route once; fail an unsafe or ambiguous observation closed."""
    rows = []
    plans = (
        (ROUTES[0], {"agent": "acceptance-rehearsal", "action": {"value": "noop"},
                     "request_id": "rehearsal-" + secrets.token_hex(8)}, {}),
        (ROUTES[1], {"question": "which formulas are proved?"}, {}),
        (ROUTES[4], {"framework": "NIST"}, {}),
        (ROUTES[2], {"suite": "core_honest_v1", "model_id": "__rehearsal_no_model__",
                     "execution_mode": "modeled"},
         {"Authorization": "Bearer " + operator_token}),
        # Agent-loop has no disposable tenant or no-effect execution mode. Only
        # its anonymous refusal can be observed safely in this bounded rehearsal.
        (ROUTES[3], {"task": "synthetic fixture: no execution"}, {}),
    )
    for path, payload, headers in plans:
        try:
            before, _ = _counts(client)
            response = _post(client, path, payload, headers)
            after, feed = _counts(client)
            body = response.json()
            if type(body) is not dict:
                raise RuntimeError("response_not_object")
            same = after == before
            if path == ROUTES[0]:
                top = (feed.get("verdicts") or [None])[0]
                passed = (response.status_code == 200
                          and body.get("decision") in ("allow", "deny")
                          and isinstance(body.get("receipt_hash"), str)
                          and bool(body["receipt_hash"])
                          and after["policy_decisions"] == min(before["policy_decisions"] + 1, 200)
                          and after["forum_events"] == before["forum_events"]
                          and type(top) is dict
                          and top.get("request_id") == payload["request_id"])
                semantic = {"decision": body.get("decision"),
                            "feedRequestMatched": type(top) is dict and top.get("request_id") == payload["request_id"]}
            elif path == ROUTES[1]:
                citations = body.get("citations") or []
                cited = citations[0].get("data") if citations and type(citations[0]) is dict else {}
                passed = (response.status_code == 200 and same
                          and body.get("topic") == "formulas"
                          and body.get("question") == payload["question"]
                          and type(body.get("citations")) is list
                          and type(cited) is dict and cited.get("count") == 8
                          and cited.get("proved") == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
                          and body.get("grounded") is True)
                semantic = {"topic": body.get("topic"), "citedCount": cited.get("count"),
                            "grounded": body.get("grounded")}
            elif path == ROUTES[4]:
                passed = (response.status_code == 200 and same
                          and body.get("status") == "REAL" and body.get("framework") == "NIST"
                          and type(body.get("covered")) is int
                          and type(body.get("total")) is int
                          and 0 <= body["covered"] <= body["total"])
                semantic = {"framework": body.get("framework"), "covered": body.get("covered"),
                            "total": body.get("total")}
            elif path == ROUTES[2]:
                aggregate = body.get("aggregate") or {}
                forum = body.get("forum_ingest") or {}
                signing = (body.get("receipt") or {}).get("signing") or {}
                passed = (response.status_code == 200
                          and body.get("execution_mode") == "modeled"
                          and body.get("honesty_label") == "MODELED"
                          and aggregate.get("n_evaluated") == 0
                          and aggregate.get("execution_complete") is False
                          and aggregate.get("model_qualified") is False
                          and forum.get("ingested") is True
                          and signing.get("mode") == "UNSIGNED-LOCAL"
                          and after["policy_decisions"] == before["policy_decisions"]
                          and after["forum_events"] == before["forum_events"] + 1)
                semantic = {"executionMode": body.get("execution_mode"),
                            "modelResponses": aggregate.get("n_evaluated"),
                            "signingMode": signing.get("mode"),
                            "forumIngested": forum.get("ingested")}
            else:
                # 401 is a refusal witness, never execution coverage.
                passed = False
                semantic = {"authorizationRefused": response.status_code == 401
                            and body.get("status") == "BLOCKED" and same}
            reason = ("isolated_route_and_state_contract_observed" if passed else
                      "agentloop_effect_not_executed" if path == ROUTES[3] and semantic.get("authorizationRefused") else
                      "route_or_state_contract_unavailable")
            rows.append(_row(path, payload, response, before, after,
                             passed=passed, reason=reason, semantic=semantic))
        except Exception as exc:
            rows.append({"path": path, "method": "POST", "evidenceClass": "UNAVAILABLE",
                         "result": "UNAVAILABLE", "reason": type(exc).__name__, "attempts": 1})
    return rows


def inside():
    if os.environ.get("SZL_EFFECT_REHEARSAL_CONTAINER") != "1":
        raise RuntimeError("inside_requires_isolated_container")
    source = os.environ.get("SZL_EFFECT_REHEARSAL_SOURCE", "")
    image = os.environ.get("SZL_EFFECT_REHEARSAL_IMAGE", "")
    if not SHA40.fullmatch(source) or not image.startswith("sha256:"):
        raise RuntimeError("source_or_image_identity_unavailable")
    # -I excludes the working directory from sys.path. The immutable image owns
    # /app/serve.py; the read-only bind-mounted driver lives outside that tree.
    sys.path.insert(0, "/app")
    # These four routes can be exercised without provider credentials. The only
    # credential below is generated in this disposable process for the local gate.
    for name in ("HF_TOKEN", "HF_ORG_TOKEN", "SZL_COSIGN_PRIVATE_PEM",
                 "SZL_COSIGN_PRIVATE_KEY_PEM", "szlcosig", "szlcosig1",
                 "SZLCOSIG", "SZLCOSIG1", "A11OY_CODE_SECOND_APPROVER_KEY"):
        if os.environ.get(name):
            raise RuntimeError("unexpected_provider_or_signing_credential")
    token = secrets.token_urlsafe(32)
    os.environ["A11OY_CODE_ADMIN_KEY"] = token
    os.environ["A11OY_CODE_SECOND_APPROVER_KEY"] = ""
    os.environ["A11OY_ORG_RAG_AUTOSTART"] = "0"
    os.environ["A11OY_FEED_WARM_ENABLED"] = "0"
    os.environ["A11OY_EVAL_AUTORUN_INTERVAL_SEC"] = "0"

    import szl_dsse
    if szl_dsse.signing_available():
        raise RuntimeError("signing_key_present_in_isolated_image")

    from fastapi.testclient import TestClient
    import serve

    client = TestClient(serve.app)  # no lifespan startup/background writers
    rows = rehearse(client, token)
    report = {
        "schema": "szl.a11oy-effect-acceptance/v1",
        "evidenceClass": "SIMULATED",
        "scope": "one_shot_declared_source_isolated_container",
        "sourceRevision": source,
        "imageId": image,
        "sourceBinding": "DECLARED_IMAGE_REVISION_LABEL",
        "network": "docker_none",
        "checkedAt": _stamp(),
        "results": rows,
        "summary": {"total": len(ROUTES), "pass": sum(r["result"] == "PASS" for r in rows),
                    "unavailable": sum(r["result"] == "UNAVAILABLE" for r in rows)},
        "productionReadiness": "UNAVAILABLE",
    }
    print(MARKER + json.dumps(report, sort_keys=True, separators=(",", ":")))


def _git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def _blocked_report(source, reason):
    return {"schema": "szl.a11oy-effect-acceptance/v1", "evidenceClass": "UNAVAILABLE",
            "scope": "one_shot_declared_source_isolated_container", "sourceRevision": source,
            "checkedAt": _stamp(), "results": [
                {"path": p, "method": "POST", "evidenceClass": "UNAVAILABLE",
                 "result": "UNAVAILABLE", "reason": reason, "attempts": 0} for p in ROUTES],
            "summary": {"total": len(ROUTES), "pass": 0, "unavailable": len(ROUTES)},
            "productionReadiness": "UNAVAILABLE"}


def launch(output, image):
    source = _git("rev-parse", "HEAD")
    if not SHA40.fullmatch(source):
        raise RuntimeError("head_not_exact_sha")
    if _git("status", "--porcelain=v1"):
        report = _blocked_report(source, "working_tree_not_clean")
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 2
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image or ""):
        report = _blocked_report(source, "exact_image_id_not_supplied")
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 2
    try:
        inspect = subprocess.run(["docker", "image", "inspect", image],
                                 capture_output=True, text=True, timeout=30, check=False)
        metadata = json.loads(inspect.stdout)[0] if inspect.returncode == 0 else {}
        labels = (metadata.get("Config") or {}).get("Labels") or {}
        if metadata.get("Id") != image or labels.get("org.opencontainers.image.revision") != source:
            raise RuntimeError("image_source_identity_mismatch")
        command = ["docker", "run", "--rm", "--network", "none", "--read-only",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--pids-limit", "128", "--memory", "2g",
                   "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m",
                   "--tmpfs", "/app/data:rw,nosuid,nodev,size=128m",
                   "--mount", f"type=bind,source={SELF},target=/rehearsal/effect_acceptance.py,readonly",
                   "--env", "SZL_EFFECT_REHEARSAL_CONTAINER=1",
                   "--env", "SZL_EFFECT_REHEARSAL_SOURCE=" + source,
                   "--env", "SZL_EFFECT_REHEARSAL_IMAGE=" + image,
                   "--env", "A11OY_ORG_RAG_AUTOSTART=0",
                   "--env", "A11OY_FEED_WARM_ENABLED=0",
                   "--env", "A11OY_EVAL_AUTORUN_INTERVAL_SEC=0",
                   "--env", "HF_TOKEN=", "--env", "HF_ORG_TOKEN=",
                   "--env", "SZL_COSIGN_PRIVATE_PEM=", "--env", "SZL_COSIGN_PRIVATE_KEY_PEM=",
                   image, "python", "-I", "-B", "/rehearsal/effect_acceptance.py", "--inside"]
        run = subprocess.run(command, capture_output=True, text=True, timeout=180,
                             check=False)
        lines = [line[len(MARKER):] for line in run.stdout.splitlines() if line.startswith(MARKER)]
        if run.returncode or len(lines) != 1:
            report = _blocked_report(source, "isolated_rehearsal_unavailable")
        else:
            report = json.loads(lines[0])
            if report.get("sourceRevision") != source or report.get("imageId") != image:
                report = _blocked_report(source, "isolated_identity_mismatch")
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired, RuntimeError):
        report = _blocked_report(source, "local_image_or_isolated_rehearsal_unavailable")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["summary"]["unavailable"] == 0 else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help="Local secret-free report path")
    parser.add_argument("--image", help="Already-local immutable image ID (sha256:...)")
    args = parser.parse_args()
    if args.inside:
        inside()
        return 0
    if args.out is None:
        parser.error("--out is required")
    if args.out.resolve().is_relative_to(ROOT):
        parser.error("--out must be outside the source checkout")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    return launch(args.out, args.image)


if __name__ == "__main__":
    sys.exit(main())
