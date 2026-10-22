#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline local ASGI contract checks; never production acceptance evidence.

This developer-only runner uses Python audit guards, not an OS sandbox. It does
not open a listener, inherit service credentials, invoke Docker, or publish.
"""

import argparse
import asyncio
import base64
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "/api/a11oy/v1/"
ROUTES = ("policy/decide", "operator/ask", "eval/run", "agentloop/run", "policy/compliance")
MAX_LOG_BYTES = 2 << 20
MAX_REPORT_BYTES = 2 << 20
MAX_SOURCE_COMMAND_BYTES = 4 << 20
MAX_SOURCE_FILE_BYTES = 2 << 20
MAX_SOURCE_TOTAL_BYTES = 8 << 20
MAX_SOURCE_FILES = 256


def bounded_git_output(command, *, timeout):
    """Bound parent-side source capture as well as the later ASGI child."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    chunks = []
    failed = threading.Event()

    def drain():
        total = 0
        try:
            while chunk := process.stdout.read(8192):
                total += len(chunk)
                if total > MAX_SOURCE_COMMAND_BYTES:
                    failed.set()
                    process.kill()
                    break
                chunks.append(chunk)
        except OSError:
            failed.set()
        finally:
            process.stdout.close()

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)
        failed.set()
        code = 124
    reader.join(timeout=10)
    if failed.is_set() or reader.is_alive() or code != 0:
        raise RuntimeError("source_command_failed_or_limit_exceeded")
    return b"".join(chunks)


def child_environment(scratch):
    env = {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "COMSPEC") if name in os.environ}
    env.update({"PATH": str(Path(sys.executable).parent), "TEMP": str(scratch), "TMP": str(scratch),
                "HOME": str(scratch), "USERPROFILE": str(scratch), "APPDATA": str(scratch),
                "LOCALAPPDATA": str(scratch), "PYTHONIOENCODING": "utf-8"})
    return env


def output_directory(path):
    resolved = path.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise ValueError("output_root_must_be_outside_source_checkout")
    return resolved


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def source_manifest():
    """Bind the protected base and every local change, never call dirty bytes HEAD."""
    def git(*args):
        return bounded_git_output(["git", "-C", str(ROOT), *args], timeout=30)

    base = git("rev-parse", "HEAD").decode().strip()
    patch = git("diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD", "--")
    paths = set(git("diff", "--name-only", "-z", "HEAD").decode().split("\0"))
    paths.update(git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0"))
    paths.discard("")
    if len(paths) > MAX_SOURCE_FILES:
        raise RuntimeError("source_file_count_limit_exceeded")
    files = {}
    total = 0
    for name in sorted(paths):
        path = ROOT / name
        if path.is_symlink() or ROOT not in path.resolve().parents:
            raise RuntimeError("source_path_not_ordinary")
        if not path.exists():
            files[name] = "DELETED"
            continue
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError("source_path_not_ordinary")
        limit = min(MAX_SOURCE_FILE_BYTES, MAX_SOURCE_TOTAL_BYTES - total)
        if info.st_size > limit:
            raise RuntimeError("source_file_byte_limit_exceeded")
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        total += len(data)
        if len(data) > limit:
            raise RuntimeError("source_file_byte_limit_exceeded")
        files[name] = hashlib.sha256(data).hexdigest()
    value = {"baseRevision": base, "binding": "LOCAL_CANDIDATE_BASE_PLUS_PATCH_AND_FILE_HASHES",
             "trackedPatchSha256": hashlib.sha256(patch).hexdigest(), "changedFiles": files}
    return {**value, "candidateSha256": digest(value)}


def baseline_passed(rows):
    if (type(rows) is not list or any(type(row) is not dict for row in rows)
            or [row.get("path") for row in rows] != [PREFIX + path for path in ROUTES]):
        return False
    for index, row in enumerate(rows):
        if index == 3:
            if not (row.get("statusCode") == 401 and row.get("result") == "UNAVAILABLE"
                    and row.get("effectState") == "REFUSED_BEFORE_ROUTE"
                    and type(row.get("semantic")) is dict
                    and row["semantic"].get("authorizationRefused") is True
                    and row.get("before") == row.get("after")):
                return False
        elif row.get("result") != "PASS" or row.get("statusCode") != 200:
            return False
    return True


def offline_loop_passed(status, body, before, after, payload):
    """Assert actual offline orchestration; never count this as model execution."""
    try:
        return _offline_loop_contract(status, body, before, after, payload)
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def _offline_loop_contract(status, body, before, after, payload):
    completion = body.get("completion") or {}
    steps = body.get("steps") or []
    if not (status == 200 and body.get("orchestration_complete") is True
            and body.get("ok") is False and body.get("task") == payload["task"]
            and isinstance(body.get("run_id"), str) and bool(body["run_id"].strip())
            and body.get("mode") == "chat" and body.get("brain_consulted") is False
            and body.get("energy_allocated") is False and len(steps) == 2
            and completion.get("state") == "UNAVAILABLE"
            and completion.get("requested_model_id") == payload["model_id"]
            and completion.get("complete") is False and completion.get("model_qualified") is False
            and completion.get("n_complete_steps") == 0
            and set(completion.get("reasons", [])) == {
                "SELECTED_MODEL_GENERATION_NOT_OBSERVED", "SELF_EVAL_INCOMPLETE_OR_UNAVAILABLE"}
            and before["policy_decisions"] == after["policy_decisions"]
            and after["forum_events"] == before["forum_events"] + 3
            and body.get("forum_ingest", {}).get("ingested") is True):
        return False
    for step in steps:
        engine = step.get("final", {}).get("engine", {})
        evaluation = step.get("final", {}).get("eval", {})
        aggregate = evaluation.get("evidence", {}).get("aggregate", {})
        if not (step.get("mode") == "chat" and step.get("sandbox") is False
                and step.get("state_changing") is False and step.get("retries") == 0
                and len(step.get("attempts", [])) == 1
                and engine.get("executed") is False and engine.get("execution_status") == "NOT_REQUESTED"
                and engine.get("backend") == {"backend": "local-deterministic", "configured": False, "offline": True}
                and evaluation.get("honesty_label") == "UNAVAILABLE"
                and evaluation.get("accuracy") is None and evaluation.get("receipt_signed") is False
                and aggregate.get("n_evaluated") == 0 and aggregate.get("accuracy") is None
                and aggregate.get("model_qualified") is False
                and aggregate.get("execution_complete") is False):
            return False
    receipt = body.get("composite_receipt", {}).get("body", {})
    return (receipt.get("task") == payload["task"] and receipt.get("model_id") == payload["model_id"]
            and receipt.get("run_id") == body.get("run_id") and receipt.get("completion") == completion)


def verify_ephemeral_receipt(composite, pem):
    """Verify actual DSSE bytes; this key has same-process trust only."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    public = serialization.load_pem_public_key(pem)
    if not isinstance(public, ec.EllipticCurvePublicKey) or not isinstance(public.curve, ec.SECP256R1):
        raise ValueError("unexpected_local_key_type")
    envelope = composite["dsse"]
    if envelope.get("signed") is not True or envelope.get("payloadType") != "application/vnd.szl.receipt+json":
        raise ValueError("unexpected_local_envelope")
    signatures = envelope["signatures"]
    if type(signatures) is not list or len(signatures) != 1:
        raise ValueError("unexpected_local_signatures")
    payload = base64.b64decode(envelope["payload"], validate=True)
    signature = base64.b64decode(signatures[0]["sig"], validate=True)
    typ = envelope["payloadType"].encode("utf-8")
    pae = b"DSSEv1 " + str(len(typ)).encode() + b" " + typ + b" " + str(len(payload)).encode() + b" " + payload
    public.verify(signature, pae, ec.ECDSA(hashes.SHA256()))

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_signed_field")
            result[key] = value
        return result

    decoded = json.loads(payload.decode("utf-8", errors="strict"), object_pairs_hook=unique,
                         parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    identity = decoded.pop("_signing_identity")
    fingerprint = hashlib.sha256(pem.strip()).hexdigest()
    expected = {"keyid": fingerprint, "key_fingerprint_sha256": fingerprint,
                "key_scope": "PROCESS_BOOT_EPHEMERAL", "key_lifetime": "UNTIL_PROCESS_RESTART",
                "key_source": "ephemeral", "verify_key_url": "/api/a11oy/cosign.pub"}
    if identity != expected or decoded != composite["body"]:
        raise ValueError("local_signed_payload_mismatch")
    if (signatures[0].get("keyid") != fingerprint
            or envelope.get("key_fingerprint_sha256") != fingerprint
            or envelope.get("key_scope") != expected["key_scope"]
            or envelope.get("key_lifetime") != expected["key_lifetime"]
            or envelope.get("_pae_sha256") != hashlib.sha256(pae).hexdigest()
            or composite["signing"].get("pae_sha256") != hashlib.sha256(pae).hexdigest()):
        raise ValueError("local_envelope_binding_mismatch")
    return {"evidenceClass": "MEASURED", "signatureVerified": True,
            "keyScope": "PROCESS_BOOT_EPHEMERAL", "keyTrust": "SAME_LOCAL_PROCESS_ONLY",
            "publicKeySha256": fingerprint, "paeSha256": hashlib.sha256(pae).hexdigest()}


def signature_controls(composite, pem):
    measured = verify_ephemeral_receipt(composite, pem)
    controls = {}
    for field in ("payload", "signature", "outer_body", "fingerprint"):
        changed = copy.deepcopy(composite)
        if field == "payload":
            raw = base64.b64decode(changed["dsse"]["payload"], validate=True) + b" "
            changed["dsse"]["payload"] = base64.b64encode(raw).decode("ascii")
        elif field == "signature":
            raw = bytearray(base64.b64decode(changed["dsse"]["signatures"][0]["sig"], validate=True))
            raw[-1] ^= 1
            changed["dsse"]["signatures"][0]["sig"] = base64.b64encode(raw).decode("ascii")
        elif field == "outer_body":
            changed["body"]["task"] += " tampered"
        else:
            changed["dsse"]["key_fingerprint_sha256"] = "0" * 64
        try:
            verify_ephemeral_receipt(changed, pem)
            controls[field] = False
        except Exception:
            controls[field] = True
    return {**measured, "tamperRejected": controls, "contractPassed": all(controls.values())}


def install_guards(scratch):
    """Deny Python network/process effects and out-of-scratch file writes."""
    denied = []
    read_roots = (ROOT, scratch, Path(sys.base_prefix).resolve())
    windows = Path(os.environ.get("SystemRoot", "C:/Windows")).resolve()

    def within(path, roots):
        try:
            resolved = Path(os.fsdecode(path)).resolve()
            return any(resolved == root or root in resolved.parents for root in roots)
        except (TypeError, ValueError, OSError):
            return False

    def reject(kind):
        if len(denied) < 1000:
            denied.append(kind)
        raise PermissionError("local_acceptance_denied:" + kind)

    def audit(event, args):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname",
                     "socket.gethostbyaddr", "socket.sendto", "socket.bind"):
            reject("network:" + event)
        if event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn",
                     "os.spawn", "os.startfile", "os.startfile/2", "pty.spawn"):
            reject("process:" + event)
        if event == "open" and not isinstance(args[0], int):
            path, mode, flags = args
            write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or bool(
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if write and not within(path, (scratch,)):
                reject("filesystem:write")
            if not write and not within(path, read_roots + (windows,)):
                reject("filesystem:read")
        if event == "sqlite3.connect" and args[0] != ":memory:" and not within(args[0], (scratch,)):
            reject("filesystem:sqlite")
        if event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate"):
            if not isinstance(args[0], int) and not within(args[0], (scratch,)):
                reject("filesystem:" + event)
        if event in ("os.rename", "os.link", "os.symlink"):
            if not all(within(path, (scratch,)) for path in args[:2]):
                reject("filesystem:" + event)

    sys.addaudithook(audit)
    return denied


def child(scratch, source):
    scratch = Path(scratch).resolve()
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("local_child_requires_isolated_no_site_no_bytecode")
    # Also sanitize at the entry point: --child must not inherit a caller's
    # credentials even when invoked directly rather than through main().
    env = child_environment(scratch)
    os.environ.clear()
    os.environ.update(env)
    binding = json.loads((scratch / "source-manifest.json").read_text(encoding="utf-8"))
    # -S avoids processing site startup hooks. Dependencies are read from the
    # existing interpreter installation, without installation or mutation.
    sys.path.insert(0, sysconfig.get_paths()["purelib"])
    sys.path.insert(0, str(ROOT))
    token = secrets.token_urlsafe(32)
    tenant = "local-acceptance-" + secrets.token_hex(16)
    os.environ.update({
        "A11OY_CODE_ADMIN_KEY": token,
        "A11OY_CODE_TENANT": tenant,
        "A11OY_ORG_RAG_AUTOSTART": "0", "A11OY_FEED_WARM_ENABLED": "0",
        "A11OY_ENERGY_AUTOSTART": "0",
        "A11OY_EVAL_AUTORUN_INTERVAL_SEC": "0", "A11OY_NVD_CVSS_DELAY_SEC": "0",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
        "A11OY_AGENT_REFLECT_DB": str(scratch / "reflect.sqlite"),
        "A11OY_CODE_DB": str(scratch / "code.sqlite"),
        "A11OY_CODE_SANDBOX": str(scratch / "sandbox"),
        "A11OY_REACT_DB": str(scratch / "react.sqlite"),
        "SZL_ENERGY_LEDGER_PATH": str(scratch / "energy.jsonl"),
        "SZL_GIT_SHA": source,
    })
    # Create the event-loop self-pipe before denying all socket operations.
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)
    denied = install_guards(scratch)
    # Prove guards fire before importing application code.
    import socket
    guard_checks = {}
    for name, reason, attempt in (
        ("egress", "network:socket.getaddrinfo", lambda: socket.getaddrinfo("example.invalid", 443)),
        ("subprocess", "process:subprocess.Popen", lambda: subprocess.run([sys.executable, "-V"])),
        ("outside_write", "filesystem:write", lambda: (ROOT / "local-acceptance-write-canary").write_text("must not exist")),
    ):
        try:
            attempt()
            guard_checks[name] = False
        except PermissionError as error:
            guard_checks[name] = str(error) == "local_acceptance_denied:" + reason
    if not all(guard_checks.values()):
        raise RuntimeError("isolation_self_test_failed")

    import httpx
    import serve
    import szl_dsse
    if szl_dsse.signing_available():
        raise RuntimeError("unexpected_signing_authority")
    print("LOCAL_ACCEPTANCE_APP_IMPORTED", flush=True)
    spec = importlib.util.spec_from_file_location("local_existing_effect_driver", ROOT / "tools/readiness-harness/effect_acceptance.py")
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    transport = httpx.ASGITransport(app=serve.app, raise_app_exceptions=False)
    client = httpx.AsyncClient(transport=transport, base_url="http://isolated-local.invalid", follow_redirects=False)

    class SyncASGI:
        def get(self, path):
            return loop.run_until_complete(client.get(path))

        def post(self, path, json, headers):
            # httpx json=None means no body; serialize explicitly to test JSON null.
            return loop.run_until_complete(client.post(path, content=__import__("json").dumps(json),
                                                       headers={**headers, "Content-Type": "application/json"}))

        def raw_post(self, path, content, headers):
            return loop.run_until_complete(client.post(path, content=content,
                                                       headers={**headers, "Content-Type": "application/json"}))

    local = SyncASGI()
    rows = driver.rehearse(local, token)
    print("LOCAL_ACCEPTANCE_BASELINE_COMPLETE", flush=True)
    additional = []

    def observe(name, path, payload, headers, expected, *, raw=False):
        before, _ = driver._counts(local)
        result = (local.raw_post if raw else local.post)(PREFIX + path, payload, headers)
        try:
            body = result.json()
        except ValueError:
            body = {"non_json": True}
        after, _ = driver._counts(local)
        passed = type(body) is dict and expected(result.status_code, body, before, after)
        additional.append({"name": name, "path": PREFIX + path, "method": "POST",
                           "request": payload, "statusCode": result.status_code,
                           "body": body, "before": before, "after": after,
                           "contractPassed": bool(passed), "responseSha256": digest(body)})
        print("LOCAL_ACCEPTANCE_CASE " + name + " " + str(result.status_code), flush=True)

    headers = {"Authorization": "Bearer " + token, "X-A11oy-Tenant": tenant}
    for path in ("eval/run", "agentloop/run"):
        observe("anonymous_" + path, path, {}, {},
                lambda status, body, before, after: status == 401 and body.get("status") == "BLOCKED" and before == after)
        observe("wrong_bearer_" + path, path, {}, {"Authorization": "Bearer local-invalid"},
                lambda status, body, before, after: status == 401 and body.get("status") == "BLOCKED" and before == after)
    for name, tenant_headers in (
        ("missing_tenant", {"Authorization": "Bearer " + token}),
        ("wrong_tenant", {"Authorization": "Bearer " + token, "X-A11oy-Tenant": "wrong-local-tenant"}),
    ):
        observe(name + "_agentloop", "agentloop/run", '{"broken":', tenant_headers,
                lambda status, body, before, after: status == 403 and body.get("status") == "BLOCKED" and before == after,
                raw=True)
    payload = {"task": "Describe the local test boundary.", "mode": "chat",
               "model_id": "__rehearsal_no_model__", "max_retries": 0,
               "sandbox": False, "consult_brain": False, "allocate_energy": False}
    observe("authenticated_offline_agentloop", "agentloop/run", payload, headers,
            lambda status, body, before, after: offline_loop_passed(status, body, before, after, payload))
    before_key, _ = driver._counts(local)
    public_key = local.get("/api/a11oy/cosign.pub")
    after_key, _ = driver._counts(local)
    signature = {"contractPassed": False, "reason": "local_signature_unavailable"}
    if public_key.status_code == 200 and before_key == after_key:
        try:
            signature = signature_controls(additional[-1]["body"]["composite_receipt"], public_key.content)
            signature["publicKeyGetTrackedStateUnchanged"] = True
        except Exception as error:
            signature["reason"] = type(error).__name__ + ":" + str(error)[:160]
    for path in ROUTES:
        for name, invalid in (("array", []), ("null", None), ("boolean", False),
                              ("number", 0), ("string", "invalid")):
            observe(name + "_" + path, path, invalid, headers,
                    lambda status, body, before, after: status in (400, 422) and before == after)
        observe("malformed_" + path, path, '{"broken":', headers,
                lambda status, body, before, after: status in (400, 422) and before == after, raw=True)
    loop.run_until_complete(client.aclose())
    loop.close()
    report = {"schema": "szl.local-post-acceptance/v1", "evidenceClass": "SIMULATED",
              "source": binding, "python": sys.version, "scope": "isolated_python_asgi_no_lifespan",
              "dependencies": {name: importlib.metadata.version(name) for name in
                               ("fastapi", "starlette", "httpx", "pydantic", "cryptography")},
              "isolation": {"mechanism": "python_audit_hooks_not_os_sandbox", "guardChecks": guard_checks,
                            "inheritedServiceCredentials": False, "listenerOpened": False,
                            "paidServicesUsed": False, "deniedEvents": denied},
              "baseline": rows, "baselineContractPassed": baseline_passed(rows), "additional": additional,
              "ephemeralSignature": signature,
              "productionReadiness": "UNAVAILABLE"}
    encoded = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if len(encoded.encode("utf-8")) > MAX_REPORT_BYTES:
        raise RuntimeError("report_byte_limit_exceeded")
    (scratch / "report.json").write_text(encoded, encoding="utf-8")
    return 0 if (baseline_passed(rows) and signature["contractPassed"]
                 and all(item["contractPassed"] for item in additional)) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--child", type=Path)
    parser.add_argument("--source")
    args = parser.parse_args()
    if args.child:
        return child(args.child, args.source)
    if args.output_root is None or not 10 <= args.timeout <= 300:
        parser.error("--output-root and timeout 10..300 required")
    try:
        output = output_directory(args.output_root)
    except ValueError as error:
        parser.error(str(error))
    binding = source_manifest()
    source = binding["baseRevision"]
    output.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="local-post-", dir=output))
    (scratch / "source-manifest.json").write_text(json.dumps(binding, indent=2) + "\n", encoding="utf-8")
    env = child_environment(scratch)
    command = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
               "--child", str(scratch), "--source", source]
    start = time.monotonic()
    exceeded = threading.Event()
    with (scratch / "child.log").open("wb") as log:
        process = subprocess.Popen(command, cwd=scratch, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def drain():
            total = 0
            while chunk := process.stdout.read(8192):
                keep = max(0, MAX_LOG_BYTES - total)
                log.write(chunk[:keep])
                total += len(chunk)
                if total > MAX_LOG_BYTES:
                    exceeded.set()
                    process.kill()
                    break
            process.stdout.close()

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
            code = 124
        reader.join(timeout=10)
        if exceeded.is_set() or reader.is_alive():
            code = 125
    unchanged = binding == source_manifest()
    if not unchanged:
        code = 126
    summary = {"source": binding, "sourceUnchangedAfterRun": unchanged,
               "exitCode": code, "elapsedSeconds": round(time.monotonic() - start, 3),
               "report": str(scratch / "report.json"), "log": str(scratch / "child.log"),
               "processTerminated": process.poll() is not None, "productionTouched": False}
    (scratch / "launch.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
