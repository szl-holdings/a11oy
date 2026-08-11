#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

SERVE_START = "# Immutable deployment identity. This endpoint is deliberately read-only and\n"
SERVE_END = "# Waqay Security Loop (wave 15): expose only the deterministic, read-only\n"

OLD_ROUTE = '''    @app.get("/api/build-info", tags=["runtime"], include_in_schema=True)
    async def _build_info():
        return _no_store_json(
            {
                "status": "OBSERVED",
                "service": ns,
                "build": build_identity,
                "runtime": {
                    "python": platform.python_version(),
                    "platform": sys.platform,
                },
                "receipt_minted": False,
            }
        )
'''

NEW_ROUTE = '''    @app.get("/api/build-info", tags=["runtime"], include_in_schema=True)
    async def _build_info():
        revision = str(build_identity.get("revision") or "")
        revision_source = str(build_identity.get("revision_source") or "")
        source_bound = bool(re.fullmatch(r"[0-9a-f]{40}", revision)) and revision_source in {
            "env:SZL_GIT_SHA",
            "env:A11OY_GIT_SHA",
        }
        if not source_bound:
            unavailable = dict(build_identity)
            unavailable["state"] = "UNAVAILABLE"
            unavailable["revision"] = None
            unavailable["revision_source"] = "UNAVAILABLE"
            field_evidence = dict(unavailable.get("field_evidence") or {})
            field_evidence["revision"] = "UNAVAILABLE"
            unavailable["field_evidence"] = field_evidence
            return _no_store_json(
                {
                    "status": "UNAVAILABLE",
                    "service": ns,
                    "build": unavailable,
                    "runtime": {
                        "python": platform.python_version(),
                        "platform": sys.platform,
                    },
                    "receipt_minted": False,
                },
                status_code=503,
            )
        return _no_store_json(
            {
                "status": "OBSERVED",
                "service": ns,
                "build": build_identity,
                "runtime": {
                    "python": platform.python_version(),
                    "platform": sys.platform,
                },
                "receipt_minted": False,
            }
        )
'''

TEST1_START = "def test_build_info_uses_allowlisted_sha_and_never_emits_environment(monkeypatch):\n"
TEST1_END = "def test_build_info_uses_hf_deployment_sha(monkeypatch):\n"
TEST1_NEW = '''def test_build_info_rejects_non_deployment_sha_and_never_emits_environment(monkeypatch):
    for name in contracts._ENV_SHA_NAMES:
        monkeypatch.delenv(name, raising=False)
    sha = "a" * 40
    monkeypatch.setenv("GITHUB_SHA", sha)
    monkeypatch.setenv("A11OY_VERSION", "2.1.0-test")
    monkeypatch.setenv("SECRET_TOKEN", "must-not-appear")
    response = TestClient(_app_with_catchall()).get("/api/build-info")
    body = response.json()
    rendered = str(body)
    assert response.status_code == 503
    assert body["status"] == "UNAVAILABLE"
    assert body["build"]["state"] == "UNAVAILABLE"
    assert body["build"]["revision"] is None
    assert body["build"]["revision_source"] == "UNAVAILABLE"
    assert body["build"]["version"] == "2.1.0-test"
    assert body["build"]["version_source"] == "env:A11OY_VERSION"
    assert body["build"]["field_evidence"]["revision"] == "UNAVAILABLE"
    assert "must-not-appear" not in rendered
    assert "SECRET_TOKEN" not in rendered


'''

TEST3_START = "def test_build_info_is_captured_once_and_get_never_spawns_git(monkeypatch):\n"
TEST3_END = "def test_build_info_preserves_unknowns_when_metadata_is_unobservable(monkeypatch):\n"
TEST3_NEW = '''def test_build_info_is_captured_once_and_get_never_spawns_git(monkeypatch):
    calls = []

    for name in contracts._ENV_SHA_NAMES:
        monkeypatch.delenv(name, raising=False)

    def fake_git(args):
        calls.append(tuple(args))
        if args == ["rev-parse", "HEAD"]:
            return type("Result", (), {"returncode": 0, "stdout": "b" * 40})()
        return type("Result", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(contracts, "_safe_git", fake_git)
    app = _app_with_catchall()
    startup_calls = list(calls)
    assert startup_calls == [("rev-parse", "HEAD"), ("status", "--porcelain", "--untracked-files=normal")]

    client = TestClient(app)
    first_response = client.get("/api/build-info")
    second_response = client.get("/api/build-info")
    first = first_response.json()
    second = second_response.json()
    assert first_response.status_code == 503
    assert second_response.status_code == 503
    assert first["build"] == second["build"]
    assert first["build"]["state"] == "UNAVAILABLE"
    assert first["build"]["revision"] is None
    assert first["build"]["working_tree"] == "CLEAN"
    assert first["build"]["working_tree_source"] == "git:status"
    assert first["build"]["field_evidence"]["working_tree"] == "OBSERVED"
    assert calls == startup_calls


'''

TEST4_START = "def test_build_info_preserves_unknowns_when_metadata_is_unobservable(monkeypatch):\n"
TEST4_END = "def test_otel_separates_in_process_exporter_and_collector():\n"
TEST4_NEW = '''def test_build_info_fails_closed_when_metadata_is_unobservable(monkeypatch):
    for name in contracts._ENV_SHA_NAMES + contracts._ENV_VERSION_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(contracts, "_safe_git", lambda _args: None)

    response = TestClient(_app_with_catchall()).get("/api/build-info")
    body = response.json()
    build = body["build"]

    assert response.status_code == 503
    assert body["status"] == "UNAVAILABLE"
    assert body["receipt_minted"] is False
    assert build["state"] == "UNAVAILABLE"
    assert build["revision"] is None
    assert build["revision_source"] == "UNAVAILABLE"
    assert build["version"] is None
    assert build["version_source"] == "UNKNOWN"
    assert build["working_tree"] == "UNKNOWN"
    assert build["working_tree_source"] == "UNKNOWN"
    assert build["field_evidence"] == {
        "revision": "UNAVAILABLE",
        "version": "UNKNOWN",
        "working_tree": "UNKNOWN",
    }


'''

READINESS_OLD = '''    patched = patch(original)
    validate(patched)
    if not args.check:
        args.path.write_text(patched, encoding="utf-8")
    print(f"readiness soft revision contract PASS: {args.path}")
    return 0
'''
READINESS_NEW = '''    patched = patch(original)
    validate(patched)
    if args.check and patched != original:
        print(f"readiness soft revision contract FAIL_UNAPPLIED: {args.path}")
        return 1
    if not args.check:
        args.path.write_text(patched, encoding="utf-8")
    print(f"readiness soft revision contract PASS: {args.path}")
    return 0
'''


def replace_span(text: str, start: str, end: str, replacement: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError(f"ambiguous span: {start.strip()}")
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    return before + replacement + end + after


def main() -> int:
    serve = Path("serve.py")
    runtime = Path("szl_runtime_contracts.py")
    tests = Path("tests/test_runtime_contracts.py")
    readiness = Path("scripts/repair_readiness_soft_revision.py")

    serve_text = serve.read_text(encoding="utf-8")
    if SERVE_START in serve_text:
        if serve_text.count(SERVE_START) != 1 or serve_text.count(SERVE_END) != 1:
            raise RuntimeError("ambiguous duplicate build-info block in serve.py")
        prefix, rest = serve_text.split(SERVE_START, 1)
        _, suffix = rest.split(SERVE_END, 1)
        serve_text = prefix + SERVE_END + suffix
        serve.write_text(serve_text, encoding="utf-8")
    if '@app.get("/api/build-info", include_in_schema=False)' in serve_text:
        raise RuntimeError("duplicate serve.py build-info route remains")

    runtime_text = runtime.read_text(encoding="utf-8")
    if NEW_ROUTE not in runtime_text:
        if runtime_text.count(OLD_ROUTE) != 1:
            raise RuntimeError("canonical runtime build-info route anchor drifted")
        runtime_text = runtime_text.replace(OLD_ROUTE, NEW_ROUTE, 1)
        runtime.write_text(runtime_text, encoding="utf-8")
    if runtime_text.count(NEW_ROUTE) != 1:
        raise RuntimeError("canonical fail-closed build-info route must exist once")

    test_text = tests.read_text(encoding="utf-8")
    if TEST1_NEW not in test_text:
        test_text = replace_span(test_text, TEST1_START, TEST1_END, TEST1_NEW)
    if TEST3_NEW not in test_text:
        test_text = replace_span(test_text, TEST3_START, TEST3_END, TEST3_NEW)
    if TEST4_NEW not in test_text:
        test_text = replace_span(test_text, TEST4_START, TEST4_END, TEST4_NEW)
    tests.write_text(test_text, encoding="utf-8")

    readiness_text = readiness.read_text(encoding="utf-8")
    if READINESS_NEW not in readiness_text:
        if readiness_text.count(READINESS_OLD) != 1:
            raise RuntimeError("readiness check-mode anchor drifted")
        readiness_text = readiness_text.replace(READINESS_OLD, READINESS_NEW, 1)
        readiness.write_text(readiness_text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
