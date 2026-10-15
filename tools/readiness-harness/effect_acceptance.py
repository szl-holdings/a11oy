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
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path


ROOT = (Path("/app") if os.environ.get("SZL_EFFECT_REHEARSAL_CONTAINER") == "1"
        else Path(__file__).resolve().parents[2])
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
MAX_STDIO_BYTES = 1 << 20
MAX_REPORT_BYTES = 64 << 10
MAX_RECOVERY_EVENT_BYTES = 512


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


def _row(path, request, response, body, before, after, *, passed, reason, effect_state, semantic=None):
    return {
        "path": path,
        "method": "POST",
        "evidenceClass": "SIMULATED" if passed else "UNAVAILABLE",
        "result": "PASS" if passed else "UNAVAILABLE",
        "reason": reason,
        "effectState": effect_state,
        "requestSha256": _digest(request),
        "statusCode": response.status_code,
        "responseSha256": _digest(body),
        "before": before,
        "after": after,
        "semantic": semantic or {},
        "attempts": 1,
    }


def _unavailable_row(path, reason, *, attempts, before=None, after=None,
                     request=None, response=None, body=None):
    row = {"path": path, "method": "POST", "evidenceClass": "UNAVAILABLE",
           "result": "UNAVAILABLE", "reason": reason,
           "effectState": "UNKNOWN" if attempts else "NOT_ATTEMPTED",
           "attempts": attempts}
    if before is not None:
        row["before"] = before
    if after is not None:
        row["after"] = after
    if request is not None and attempts:
        row["requestSha256"] = _digest(request)
    if response is not None:
        row["statusCode"] = response.status_code
    if body is not None:
        row["responseSha256"] = _digest(body)
    return row


def _post(client, path, payload, headers=None):
    return client.post(path, json=payload, headers=headers or {})


def rehearse(client, operator_token):
    """Run each route once; fail an unsafe or ambiguous observation closed."""
    rows = []
    plans = (
        (ROUTES[0], {"agent": "acceptance-rehearsal", "action": {"value": "noop"},
                     "request_id": "rehearsal-" + secrets.token_hex(8)}, {}),
        (ROUTES[1], {"question": "which formulas are proved?"}, {}),
        (ROUTES[2], {"suite": "core_honest_v1", "model_id": "__rehearsal_no_model__",
                     "execution_mode": "modeled"},
         {"Authorization": "Bearer " + operator_token}),
        # Agent-loop has no disposable tenant or no-effect execution mode. Only
        # its anonymous refusal can be observed safely in this bounded rehearsal.
        (ROUTES[3], {"task": "synthetic fixture: no execution"}, {}),
        (ROUTES[4], {"framework": "NIST"}, {}),
    )
    for index, (path, payload, headers) in enumerate(plans):
        try:
            before, _ = _counts(client)
        except Exception:
            rows.append(_unavailable_row(path, "pre_post_readback_unavailable",
                                         attempts=0))
            continue
        response = body = after = None
        try:
            response = _post(client, path, payload, headers)
            body = response.json()
            if type(body) is not dict:
                raise RuntimeError("response_not_object")
            after, feed = _counts(client)
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
                          and top.get("request_id") == payload["request_id"]
                          and top.get("decision") == body.get("decision")
                          and top.get("receipt_hash") == body.get("receipt_hash"))
                semantic = {"decision": body.get("decision"),
                            "feedRequestMatched": type(top) is dict and top.get("request_id") == payload["request_id"],
                            "feedDecisionMatched": type(top) is dict and top.get("decision") == body.get("decision"),
                            "feedReceiptMatched": type(top) is dict and top.get("receipt_hash") == body.get("receipt_hash")}
            elif path == ROUTES[1]:
                citations = body.get("citations") or []
                cited = citations[0].get("data") if citations and type(citations[0]) is dict else {}
                passed = (response.status_code == 200 and same
                          and body.get("topic") == "formulas"
                          and body.get("question") == payload["question"]
                          and type(body.get("citations")) is list
                          and bool(citations)
                          and citations[0].get("endpoint") == "szl_brain.CANONICAL"
                          and type(cited) is dict and cited.get("count") == 8
                          and cited.get("proved") == ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
                          and body.get("grounded") is True)
                semantic = {"topic": body.get("topic"), "citationEndpoint": citations[0].get("endpoint") if citations else None,
                            "citedCount": cited.get("count"),
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
            if passed:
                effect_state = ("OBSERVED_LOCAL_STATE" if path in (ROUTES[0], ROUTES[2])
                                else "RESPONSE_OBSERVED_NO_TRACKED_STATE_DELTA")
                rows.append(_row(path, payload, response, body, before, after,
                                 passed=True, reason="isolated_route_and_state_contract_observed",
                                 effect_state=effect_state, semantic=semantic))
                continue
            if path == ROUTES[3] and semantic.get("authorizationRefused"):
                rows.append(_row(path, payload, response, body, before, after,
                                 passed=False, reason="agentloop_effect_not_executed",
                                 effect_state="REFUSED_BEFORE_ROUTE", semantic=semantic))
                continue
            rows.append(_unavailable_row(path, "effect_unknown_contract_mismatch",
                                         attempts=1, before=before, after=after,
                                         request=payload, response=response, body=body))
        except Exception:
            # The call may have reached the route even when the transport raises.
            # An unreadable response or post-effect readback is never safe to retry.
            rows.append(_unavailable_row(path, "effect_unknown_after_post",
                                         attempts=1, before=before, after=after,
                                         request=payload, response=response, body=body))
        for remaining_path, _, _ in plans[index + 1:]:
            rows.append(_unavailable_row(remaining_path, "stopped_after_unknown_effect",
                                         attempts=0))
        break
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
    os.environ["A11OY_NVD_CVSS_DELAY_SEC"] = "0"

    import szl_dsse
    if szl_dsse.signing_available():
        raise RuntimeError("signing_key_present_in_isolated_image")

    import serve

    client = _isolated_client(serve.app)  # no lifespan startup; import-time cache probes remain disposable
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


def _isolated_client(app):
    from fastapi.testclient import TestClient
    return TestClient(app, follow_redirects=False)


def _git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def _blocked_report(source, reason, *, container_attempted=False,
                    cleanup_verified=False):
    # Once Docker has been invoked, a failed/malformed child marker cannot tell
    # us which POSTs reached the route. Zero attempts would be a false claim.
    attempts = "UNKNOWN" if container_attempted else 0
    effect_state = "UNKNOWN" if container_attempted else "NOT_ATTEMPTED"
    return {"schema": "szl.a11oy-effect-acceptance/v1", "evidenceClass": "UNAVAILABLE",
            "scope": "one_shot_declared_source_isolated_container", "sourceRevision": source,
            "containerRunInvoked": container_attempted,
            "containerStarted": "UNKNOWN" if container_attempted else False,
            "containerCleanupVerified": cleanup_verified,
            "checkedAt": _stamp(), "results": [
                {"path": p, "method": "POST", "evidenceClass": "UNAVAILABLE",
                 "result": "UNAVAILABLE", "reason": reason,
                 "effectState": effect_state, "attempts": attempts} for p in ROUTES],
            "summary": {"total": len(ROUTES), "pass": 0, "unavailable": len(ROUTES)},
            "productionReadiness": "UNAVAILABLE"}


def _write_report(output, report):
    # A failed first attempt is evidence. Never erase it with a later run.
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")


def _valid_cidfile_id(cidfile):
    """Return only a bounded, syntactically valid Docker CID file value."""
    try:
        if not cidfile.exists() or cidfile.stat().st_size > 128:
            return None
        identifier = cidfile.read_text(encoding="ascii").strip()
        return identifier if re.fullmatch(r"[0-9a-f]{64}", identifier) else None
    except (OSError, UnicodeError):
        return None


def _record_recovery(stream, phase, *, source=None, image=None, name=None,
                     nonce=None, container_id=None, cleanup_verified=None):
    """Fsync an allowlisted local recovery event before accepting any run."""
    event = {"schema": "szl.a11oy-effect-recovery/v1", "phase": phase,
             "checkedAt": _stamp()}
    if phase == "prepared":
        if (not SHA40.fullmatch(source or "")
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", image or "")
                or not re.fullmatch(r"[0-9a-f]{24}", nonce or "")
                or name != "szl-effect-rehearsal-" + nonce):
            raise ValueError("recovery_identity_invalid")
        event.update({"sourceRevision": source, "imageId": image,
                      "containerName": name, "nonce": nonce})
    elif phase == "cidfile":
        if container_id is not None and not re.fullmatch(r"[0-9a-f]{64}", container_id):
            raise ValueError("recovery_cid_invalid")
        event.update({"containerId": container_id or "UNKNOWN",
                      "idEvidence": "FORMAT_VALIDATED_DOCKER_CIDFILE" if container_id
                      else "UNAVAILABLE"})
    elif phase == "cleanup":
        if type(cleanup_verified) is not bool:
            raise ValueError("recovery_cleanup_invalid")
        event["containerCleanupVerified"] = cleanup_verified
    else:
        raise ValueError("recovery_phase_invalid")
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
    if len(encoded.encode("utf-8")) > MAX_RECOVERY_EVENT_BYTES:
        raise ValueError("recovery_event_too_large")
    stream.write(encoded)
    stream.flush()
    os.fsync(stream.fileno())


def _run_bounded(command, *, timeout):
    """Capture bounded Docker output without risking unbounded host memory use."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = bytearray()
    exceeded = threading.Event()

    def drain(pipe, keep):
        size = 0
        try:
            while chunk := pipe.read(8192):
                size += len(chunk)
                if size > MAX_STDIO_BYTES:
                    exceeded.set()
                    try:
                        process.kill()
                    except OSError:
                        pass
                    break
                if keep:
                    stdout.extend(chunk)
        finally:
            pipe.close()

    readers = (threading.Thread(target=drain, args=(process.stdout, True), daemon=True),
               threading.Thread(target=drain, args=(process.stderr, False), daemon=True))
    for reader in readers:
        reader.start()
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
        raise
    finally:
        for reader in readers:
            reader.join(timeout=10)
    if exceeded.is_set() or any(reader.is_alive() for reader in readers):
        raise RuntimeError("subprocess_output_unavailable")
    return code, stdout.decode("utf-8", errors="replace")


def _docker_metadata(raw):
    parsed = json.loads(raw)
    if type(parsed) is not list or len(parsed) != 1 or type(parsed[0]) is not dict:
        raise ValueError("docker_inspect_shape_invalid")
    metadata = parsed[0]
    config = metadata.get("Config")
    if type(config) is not dict or type(config.get("Labels")) is not dict:
        raise ValueError("docker_inspect_labels_invalid")
    return metadata, config["Labels"]


def _cleanup_own_container(name, nonce, image, cidfile):
    """Touch only the one container identified by this invocation's nonce."""
    selector = "label=szl.effect.rehearsal.run=" + nonce
    listing = ["docker", "container", "ls", "-a", "--filter", selector,
               "--format", "{{.ID}}"]
    try:
        code, output = _run_bounded(listing, timeout=10)
        if code:
            return False
        identifiers = output.splitlines()
        if not identifiers:
            return True  # daemon confirms no container with our nonce remains
        if len(identifiers) != 1 or not re.fullmatch(r"[0-9a-f]{12,64}", identifiers[0]):
            return False
        identifier = identifiers[0]
        code, raw = _run_bounded(["docker", "container", "inspect", identifier], timeout=10)
        if code:
            return False
        metadata, labels = _docker_metadata(raw)
        full_id = metadata.get("Id", "")
        if (type(full_id) is not str or not re.fullmatch(r"[0-9a-f]{64}", full_id)
                or not full_id.startswith(identifier)
                or metadata.get("Name") != "/" + name
                or metadata.get("Image") != image
                or labels.get("szl.effect.rehearsal.run") != nonce):
            return False
        if cidfile.exists():
            if _valid_cidfile_id(cidfile) != full_id:
                return False
        try:
            _run_bounded(["docker", "container", "stop", "--time", "2", full_id], timeout=10)
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            pass  # still try forced removal, then verify the nonce is absent
        try:
            _run_bounded(["docker", "container", "rm", "--force", full_id], timeout=10)
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            pass
        code, output = _run_bounded(listing, timeout=10)
        return code == 0 and not output.strip()
    except (OSError, ValueError, TypeError, IndexError, subprocess.TimeoutExpired, RuntimeError):
        return False


def _valid_counts(value):
    return (type(value) is dict and set(value) == {"policy_decisions", "forum_events"}
            and all(type(item) is int and item >= 0 for item in value.values()))


def _valid_hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _validate_child_report(report, source, image):
    """Reject malformed or overclaiming child markers before retaining evidence."""
    _require(type(report) is dict, "report_not_object")
    _require(set(report) == {"schema", "evidenceClass", "scope", "sourceRevision",
                             "imageId", "sourceBinding", "network", "checkedAt",
                             "results", "summary", "productionReadiness"},
             "report_keys_invalid")
    for key, expected in (("schema", "szl.a11oy-effect-acceptance/v1"),
                          ("evidenceClass", "SIMULATED"),
                          ("scope", "one_shot_declared_source_isolated_container"),
                          ("sourceRevision", source), ("imageId", image),
                          ("sourceBinding", "DECLARED_IMAGE_REVISION_LABEL"),
                          ("network", "docker_none"),
                          ("productionReadiness", "UNAVAILABLE")):
        _require(report.get(key) == expected, "report_identity_or_boundary_invalid")
    stamp = report.get("checkedAt")
    _require(type(stamp) is str and len(stamp) <= 35 and stamp.endswith("Z"),
             "report_timestamp_invalid")
    try:
        observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("report_timestamp_invalid") from exc
    age_seconds = (datetime.now(timezone.utc) - observed).total_seconds()
    _require(observed.tzinfo is not None and -5 <= age_seconds <= 300,
             "report_timestamp_not_fresh")
    rows = report.get("results")
    _require(type(rows) is list and len(rows) == len(ROUTES), "report_rows_incomplete")
    _require([r.get("path") if type(r) is dict else None for r in rows] == list(ROUTES),
             "report_paths_invalid")
    unknown_seen = False
    passes = 0
    for row, path in zip(rows, ROUTES):
        required = {"path", "method", "evidenceClass", "result", "reason",
                    "effectState", "attempts"}
        optional = {"requestSha256", "statusCode", "responseSha256", "before",
                    "after", "semantic"}
        _require(required <= set(row) <= required | optional, "row_keys_invalid")
        _require(row.get("method") == "POST" and row.get("result") in ("PASS", "UNAVAILABLE"),
                 "row_method_or_result_invalid")
        attempts = row.get("attempts")
        _require(type(attempts) is int and attempts in (0, 1), "row_attempts_invalid")
        if unknown_seen:
            _require(attempts == 0 and row.get("reason") == "stopped_after_unknown_effect",
                     "post_after_unknown_effect")
        if attempts == 0:
            _require(row.get("result") == "UNAVAILABLE"
                     and row.get("evidenceClass") == "UNAVAILABLE"
                     and row.get("effectState") == "NOT_ATTEMPTED"
                     and row.get("reason") in ("pre_post_readback_unavailable",
                                               "stopped_after_unknown_effect")
                     and not any(key in row for key in ("before", "after", "statusCode",
                                                         "requestSha256", "responseSha256")),
                     "unattempted_row_invalid")
            _require(row["reason"] != "stopped_after_unknown_effect" or unknown_seen,
                     "stopped_without_unknown_effect")
            continue
        _require(_valid_hash(row.get("requestSha256")) and _valid_counts(row.get("before")),
                 "attempted_row_missing_request_or_baseline")
        if "statusCode" in row:
            _require(type(row["statusCode"]) is int and 100 <= row["statusCode"] <= 599,
                     "attempted_status_invalid")
        if "responseSha256" in row:
            _require(_valid_hash(row["responseSha256"]), "attempted_response_hash_invalid")
        if "after" in row:
            _require(_valid_counts(row["after"]), "attempted_after_invalid")
        if row["result"] == "UNAVAILABLE":
            if path == ROUTES[3] and row.get("effectState") == "REFUSED_BEFORE_ROUTE":
                _require(row.get("reason") == "agentloop_effect_not_executed"
                         and row.get("statusCode") == 401
                         and _valid_hash(row.get("responseSha256"))
                         and row.get("after") == row["before"]
                         and row.get("semantic") == {"authorizationRefused": True},
                         "agentloop_refusal_invalid")
            else:
                _require(row.get("effectState") == "UNKNOWN"
                         and row.get("reason") in ("effect_unknown_after_post",
                                                   "effect_unknown_contract_mismatch")
                         and "semantic" not in row,
                         "unknown_effect_row_invalid")
                unknown_seen = True
            _require(row.get("evidenceClass") == "UNAVAILABLE", "unavailable_evidence_invalid")
            continue
        passes += 1
        _require(path != ROUTES[3] and row.get("evidenceClass") == "SIMULATED"
                 and row.get("reason") == "isolated_route_and_state_contract_observed"
                 and row.get("statusCode") == 200
                 and _valid_hash(row.get("responseSha256"))
                 and _valid_counts(row.get("after")), "pass_row_invalid")
        before, after, semantic = row["before"], row["after"], row.get("semantic")
        _require(type(semantic) is dict, "pass_semantic_invalid")
        if path == ROUTES[0]:
            _require(set(semantic) == {"decision", "feedRequestMatched",
                                       "feedDecisionMatched", "feedReceiptMatched"},
                     "policy_semantic_keys_invalid")
            _require(row.get("effectState") == "OBSERVED_LOCAL_STATE"
                     and semantic.get("decision") in ("allow", "deny")
                     and semantic.get("feedRequestMatched") is True
                     and semantic.get("feedDecisionMatched") is True
                     and semantic.get("feedReceiptMatched") is True
                     and after["policy_decisions"] == min(before["policy_decisions"] + 1, 200)
                     and after["forum_events"] == before["forum_events"],
                     "policy_effect_invalid")
        elif path == ROUTES[2]:
            _require(set(semantic) == {"executionMode", "modelResponses",
                                       "signingMode", "forumIngested"},
                     "eval_semantic_keys_invalid")
            _require(row.get("effectState") == "OBSERVED_LOCAL_STATE"
                     and semantic.get("executionMode") == "modeled"
                     and semantic.get("modelResponses") == 0
                     and semantic.get("signingMode") == "UNSIGNED-LOCAL"
                     and semantic.get("forumIngested") is True
                     and after["policy_decisions"] == before["policy_decisions"]
                     and after["forum_events"] == before["forum_events"] + 1,
                     "eval_effect_invalid")
        else:
            _require(row.get("effectState") == "RESPONSE_OBSERVED_NO_TRACKED_STATE_DELTA"
                     and after == before, "response_only_state_invalid")
            if path == ROUTES[1]:
                _require(set(semantic) == {"topic", "citationEndpoint", "citedCount",
                                           "grounded"}, "operator_semantic_keys_invalid")
                _require(semantic.get("topic") == "formulas"
                         and semantic.get("citationEndpoint") == "szl_brain.CANONICAL"
                         and semantic.get("citedCount") == 8
                         and semantic.get("grounded") is True, "operator_semantic_invalid")
            else:
                _require(set(semantic) == {"framework", "covered", "total"},
                         "compliance_semantic_keys_invalid")
                _require(semantic.get("framework") == "NIST"
                         and type(semantic.get("covered")) is int
                         and type(semantic.get("total")) is int
                         and 0 <= semantic["covered"] <= semantic["total"],
                         "compliance_semantic_invalid")
    summary = report.get("summary")
    _require(type(summary) is dict and set(summary) == {"total", "pass", "unavailable"}
             and all(type(value) is int for value in summary.values())
             and summary == {"total": len(ROUTES), "pass": passes,
                             "unavailable": len(ROUTES) - passes}
             and passes <= len(ROUTES) - 1,
             "report_summary_invalid")


def launch(output, image):
    if output.exists():
        raise FileExistsError(output)
    recovery_path = output.with_name(output.name + ".recovery.jsonl")
    if recovery_path.exists():
        raise FileExistsError(recovery_path)
    source = _git("rev-parse", "HEAD")
    if not SHA40.fullmatch(source):
        raise RuntimeError("head_not_exact_sha")
    if _git("status", "--porcelain=v1"):
        report = _blocked_report(source, "working_tree_not_clean")
        _write_report(output, report)
        return 2
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image or ""):
        report = _blocked_report(source, "exact_image_id_not_supplied")
        _write_report(output, report)
        return 2
    container_attempted = False
    cleanup_verified = False
    try:
        inspect_code, inspect_stdout = _run_bounded(["docker", "image", "inspect", image],
                                                    timeout=30)
        if inspect_code:
            raise RuntimeError("image_inspect_unavailable")
        metadata, labels = _docker_metadata(inspect_stdout)
        if metadata.get("Id") != image or labels.get("org.opencontainers.image.revision") != source:
            raise RuntimeError("image_source_identity_mismatch")
        with tempfile.TemporaryDirectory(prefix="szl-effect-rehearsal-") as temporary:
            temp_path = Path(temporary).resolve()
            if temp_path.is_relative_to(ROOT):
                raise RuntimeError("cidfile_location_not_isolated")
            nonce = secrets.token_hex(12)
            name = "szl-effect-rehearsal-" + nonce
            cidfile = temp_path / "container.cid"
            command = ["docker", "run", "--rm", "--network", "none", "--read-only",
                       "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                       "--pids-limit", "128", "--memory", "2g",
                       "--name", name, "--cidfile", str(cidfile),
                       "--label", "szl.effect.rehearsal.run=" + nonce,
                       "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m",
                       "--tmpfs", "/app/data:rw,nosuid,nodev,size=128m",
                       "--mount", f"type=bind,source={SELF},target=/rehearsal/effect_acceptance.py,readonly",
                       "--env", "SZL_EFFECT_REHEARSAL_CONTAINER=1",
                       "--env", "SZL_EFFECT_REHEARSAL_SOURCE=" + source,
                       "--env", "SZL_EFFECT_REHEARSAL_IMAGE=" + image,
                       "--env", "A11OY_ORG_RAG_AUTOSTART=0",
                       "--env", "A11OY_FEED_WARM_ENABLED=0",
                       "--env", "A11OY_EVAL_AUTORUN_INTERVAL_SEC=0",
                       "--env", "A11OY_NVD_CVSS_DELAY_SEC=0",
                       "--env", "HF_TOKEN=", "--env", "HF_ORG_TOKEN=",
                       "--env", "SZL_COSIGN_PRIVATE_PEM=", "--env", "SZL_COSIGN_PRIVATE_KEY_PEM=",
                       "--entrypoint", "python", image, "-I", "-B",
                       "/rehearsal/effect_acceptance.py", "--inside"]
            # Keep this outside TemporaryDirectory: the Docker CLI may time out
            # while its daemon container survives. A fsynced name and nonce let
            # an operator identify only this invocation even if report write fails.
            with recovery_path.open("x", encoding="utf-8") as recovery:
                _record_recovery(recovery, "prepared", source=source, image=image,
                                 name=name, nonce=nonce)
                container_attempted = True
                try:
                    run_code, run_stdout = _run_bounded(command, timeout=180)
                finally:
                    record_failed = False
                    try:
                        _record_recovery(recovery, "cidfile",
                                         container_id=_valid_cidfile_id(cidfile))
                    except (OSError, ValueError):
                        record_failed = True
                    cleanup_verified = _cleanup_own_container(name, nonce, image, cidfile)
                    try:
                        _record_recovery(recovery, "cleanup",
                                         cleanup_verified=cleanup_verified)
                    except (OSError, ValueError):
                        record_failed = True
                    if record_failed:
                        raise RuntimeError("recovery_event_write_unavailable")
        if not cleanup_verified:
            raise RuntimeError("container_cleanup_unverified")
        lines = [line[len(MARKER):] for line in run_stdout.splitlines() if line.startswith(MARKER)]
        if run_code or len(lines) != 1 or len(lines[0].encode("utf-8")) > MAX_REPORT_BYTES:
            report = _blocked_report(source, "isolated_rehearsal_unavailable",
                                     container_attempted=True, cleanup_verified=True)
        else:
            report = json.loads(lines[0])
            try:
                _validate_child_report(report, source, image)
                report["containerCleanupVerified"] = True
            except ValueError:
                report = _blocked_report(source, "isolated_report_invalid",
                                         container_attempted=True, cleanup_verified=True)
    except (OSError, ValueError, TypeError, IndexError, subprocess.TimeoutExpired, RuntimeError):
        report = _blocked_report(source, "local_image_or_isolated_rehearsal_unavailable",
                                 container_attempted=container_attempted,
                                 cleanup_verified=cleanup_verified)
    _write_report(output, report)
    return 2  # agent-loop execution remains unobserved even in a valid report


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
