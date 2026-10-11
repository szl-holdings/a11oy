#!/usr/bin/env python3
"""Owner-only, fail-closed meter2 reader enrollment. No effect without --apply.

This is a proposed credential handoff, not a source or measurement attestation.
It never exports an existing DPAPI key. Synthetic tests model a fresh key being
added to the local verifier and sent only to the exact HF Space secret API.
The versioned HF secret write still has no provider-enforced create-only
condition, so real --apply remains blocked until a reviewed non-overwriting
activation protocol replaces it. Injectable synthetic tests exercise recovery.
"""

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request


AUDIENCE = "https://meter2.a-11-oy.com"
SPACE = "SZLHOLDINGS/a11oy"
SECRET_PREFIX = "SZL_METER_HMAC_TARGETS_V1_"
HF_HOST = "szlholdings-a11oy.hf.space"
PRODUCT_HOST = "a-11-oy.com"
LOCAL_PORT = 9471
SCHEMA = "szl.meter.private-config/v1"


class EnrollmentError(RuntimeError):
    pass


class PartialActivation(EnrollmentError):
    """Provider outcome could not be reversed; preserve the new local key."""


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _atomic_write(path: Path, data: bytes):
    temp = path.with_name(path.name + ".pending-" + secrets.token_hex(8))
    try:
        with temp.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _private_root():
    base = os.environ.get("LOCALAPPDATA")
    if os.name != "nt" or not base:
        raise EnrollmentError("Windows owner session and LOCALAPPDATA are required")
    return Path(base) / "SZL" / "Meter"


def _installation(root: Path):
    try:
        receipt = json.loads((root / "installation.json").read_text(encoding="utf-8-sig"))
        if (receipt["schema"] != "szl.meter.installation/v1"
                or receipt["audience"] != AUDIENCE
                or receipt["configuration_protection"] != "DPAPI_CURRENT_USER"):
            raise ValueError
        for name in ("omen_joule_exporter.py", "szl_meter_access.py", "run_meter_windows.ps1"):
            actual = hashlib.sha256((root / "program" / name).read_bytes()).hexdigest()
            if actual != receipt["files"][name]:
                raise ValueError
        return receipt
    except (OSError, ValueError, KeyError, TypeError):
        raise EnrollmentError("installed meter identity/source verification failed") from None


class WindowsDpapi:
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    def __init__(self):
        if os.name != "nt":
            raise EnrollmentError("Windows DPAPI is required")
        self.crypt = ctypes.WinDLL("crypt32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.crypt.CryptProtectData.argtypes = [ctypes.POINTER(self.Blob), wintypes.LPCWSTR,
                                                 ctypes.c_void_p, ctypes.c_void_p,
                                                 ctypes.c_void_p, wintypes.DWORD,
                                                 ctypes.POINTER(self.Blob)]
        self.crypt.CryptProtectData.restype = wintypes.BOOL
        self.crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(self.Blob), ctypes.c_void_p,
                                                   ctypes.c_void_p, ctypes.c_void_p,
                                                   ctypes.c_void_p, wintypes.DWORD,
                                                   ctypes.POINTER(self.Blob)]
        self.crypt.CryptUnprotectData.restype = wintypes.BOOL
        self.kernel.LocalFree.argtypes = [ctypes.c_void_p]

    def _run(self, payload: bytes, *, protect: bool):
        source = ctypes.create_string_buffer(payload)
        input_blob = self.Blob(len(payload), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
        output_blob = self.Blob()
        try:
            if protect:
                ok = self.crypt.CryptProtectData(ctypes.byref(input_blob), None, None, None,
                                                 None, 1, ctypes.byref(output_blob))
            else:
                ok = self.crypt.CryptUnprotectData(ctypes.byref(input_blob), None, None,
                                                   None, None, 1, ctypes.byref(output_blob))
            if not ok:
                raise EnrollmentError("DPAPI operation failed for current Windows user")
            try:
                return ctypes.string_at(output_blob.pbData, output_blob.cbData)
            finally:
                self.kernel.LocalFree(output_blob.pbData)
        finally:
            ctypes.memset(source, 0, len(source))

    def protect(self, data: bytes):
        return self._run(data, protect=True)

    def unprotect(self, data: bytes):
        return self._run(data, protect=False)


class ExporterSupervisor:
    """Restart only the installed loopback listener and its exact PowerShell parent."""

    def __init__(self, root: Path, receipt: dict):
        try:
            import psutil
        except ImportError:
            raise EnrollmentError("psutil is required for exact exporter identity") from None
        self.psutil = psutil
        self.root = root
        self.receipt = receipt
        self._launcher_exe = None

    def _identity(self):
        psutil = self.psutil
        matches = []
        for conn in psutil.net_connections(kind="tcp"):
            if (conn.status == psutil.CONN_LISTEN and conn.laddr
                    and conn.laddr.ip == "127.0.0.1" and conn.laddr.port == LOCAL_PORT
                    and conn.pid is not None):
                matches.append(psutil.Process(conn.pid))
        if len(matches) != 1:
            raise EnrollmentError("exact loopback exporter listener not found")
        child = matches[0]
        expected_py = Path(self.receipt["python"]).resolve()
        expected_source = (self.root / "program" / "omen_joule_exporter.py").resolve()
        args = child.cmdline()
        if (len(args) != 3 or Path(args[0]).resolve() != expected_py or args[1] != "-u"
                or Path(args[2]).resolve() != expected_source):
            raise EnrollmentError("listener is not the installed exporter")
        parent = child.parent()
        launcher = (self.root / "program" / "run_meter_windows.ps1").resolve()
        if parent is None:
            raise EnrollmentError("exporter supervisor is absent")
        parent_args = parent.cmdline()
        if (len(parent_args) != 5 or Path(parent_args[0]).name.lower() != "powershell.exe"
                or [s.lower() for s in parent_args[1:4]] !=
                   ["-noprofile", "-noninteractive", "-file"]
                or Path(parent_args[4]).resolve() != launcher):
            raise EnrollmentError("exporter supervisor identity changed")
        self._launcher_exe = parent.exe()
        return child, parent

    def restart(self):
        try:
            child, parent = self._identity()
        except EnrollmentError as exc:
            if str(exc) != "exact loopback exporter listener not found" or not self._launcher_exe:
                raise
        else:
            child.terminate()
            child.wait(timeout=8)
            if parent.is_running():
                parent.terminate()
                parent.wait(timeout=8)
        log = self.root / "meter-runtime.log"
        with log.open("ab") as stream:
            subprocess.Popen([self._launcher_exe, "-NoProfile", "-NonInteractive", "-File",
                              str(self.root / "program" / "run_meter_windows.ps1")],
                             stdin=subprocess.DEVNULL, stdout=stream,
                             stderr=subprocess.STDOUT, close_fds=True,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            try:
                self._identity()
                return
            except EnrollmentError:
                time.sleep(0.3)
        raise EnrollmentError("exporter did not return with exact identity")


class MeterProbe:
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, msg, headers, newurl):
            return None

    def _get(self, url: str, headers=None):
        request = urllib.request.Request(url, headers=headers or {}, method="GET")
        try:
            with urllib.request.build_opener(self.NoRedirect()).open(request, timeout=8) as response:
                return response.status, response.read(524288)
        except urllib.error.HTTPError as exc:
            return exc.code, b""

    @staticmethod
    def _headers(client_id: str, key_hex: str, *, local: bool):
        stamp, nonce = str(time.time_ns()), secrets.token_hex(16)
        fields = ("szl-meter-hmac-v1", "GET", "/metrics", AUDIENCE,
                  client_id, stamp, nonce)
        signature = hmac.new(bytes.fromhex(key_hex), "\n".join(fields).encode("ascii"),
                             hashlib.sha256).hexdigest()
        result = {"X-SZL-Meter-Client": client_id, "X-SZL-Meter-Time": stamp,
                  "X-SZL-Meter-Nonce": nonce, "X-SZL-Meter-Signature": signature}
        if local:
            result["Host"] = "meter2.a-11-oy.com"
        return result

    @staticmethod
    def _check_json(body):
        try:
            value = json.loads(body)
            if not isinstance(value, dict) or not isinstance(value.get("engines"), list):
                raise ValueError
        except (ValueError, TypeError):
            raise EnrollmentError("authenticated meter response schema invalid") from None

    def route_preflight(self):
        status, _ = self._get(AUDIENCE + "/metrics")
        if status != 403:
            raise EnrollmentError("public meter route is not fail-closed HTTP 403")

    def prove(self, client_id: str, key_hex: str):
        local_url = f"http://127.0.0.1:{LOCAL_PORT}/metrics"
        public_url = AUDIENCE + "/metrics"
        for local, url in ((True, local_url), (False, public_url)):
            unauth, _ = self._get(url, {"Host": "meter2.a-11-oy.com"} if local else None)
            if unauth != 403:
                raise EnrollmentError("anonymous meter request did not deny")
            headers = self._headers(client_id, key_hex, local=local)
            status, body = self._get(url, headers)
            if status != 200:
                raise EnrollmentError("new meter reader credential did not authenticate")
            self._check_json(body)
            replay, _ = self._get(url, headers)
            if replay != 403:
                raise EnrollmentError("meter replay was not rejected")

    def reject(self, client_id: str, key_hex: str):
        """Read back old-key retirement at the local verifier and public route."""
        for local, url in ((True, f"http://127.0.0.1:{LOCAL_PORT}/metrics"),
                           (False, AUDIENCE + "/metrics")):
            if self._get(url, self._headers(client_id, key_hex, local=local))[0] != 403:
                raise EnrollmentError("retired meter reader credential still authenticates")

    def source_preflight(self, source_revision: str):
        for host in (HF_HOST, PRODUCT_HOST):
            build_status, build_body = self._get(f"https://{host}/api/build-info")
            try:
                build = json.loads(build_body)
                observed = build["build"]["revision"]
            except (ValueError, KeyError, TypeError):
                raise EnrollmentError("product/HF build readback invalid") from None
            if build_status != 200 or observed != source_revision:
                raise EnrollmentError("product/HF source revision did not match")

    def live(self, source_revision: str, client_id: str):
        self.source_preflight(source_revision)
        for host in (HF_HOST, PRODUCT_HOST):
            live_status, live_body = self._get(f"https://{host}/api/a11oy/v1/energy/live")
            try:
                live = json.loads(live_body)
            except ValueError:
                raise EnrollmentError("energy/live readback invalid") from None
            if (live_status != 200 or live.get("meter_status") != "ok"
                    or live.get("meter_url") != AUDIENCE
                    or live.get("meter_request_client_id") != client_id):
                raise EnrollmentError("energy/live does not select the exact meter2 reader")
            # Authenticated connectivity alone does not qualify joules.
            if live.get("total_joules") is None and live.get("joules_label") == "MEASURED":
                raise EnrollmentError("energy/live mislabeled unavailable joules")

    def wait_live(self, source_revision: str, client_id: str):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                self.live(source_revision, client_id)
                return
            except EnrollmentError:
                time.sleep(3)
        raise EnrollmentError("product/HF live readback did not converge")


class HfSpace:
    def __init__(self):
        try:
            from huggingface_hub import HfApi
        except ImportError:
            raise EnrollmentError("huggingface_hub is required") from None
        self.api = HfApi()

    def preflight(self, expected_revision: str, secret_name: str):
        if not re.fullmatch(r"SZL_METER_HMAC_TARGETS_V1_[0-9A-F]{32}", secret_name):
            raise EnrollmentError("invalid versioned HF secret name")
        who = self.api.whoami()
        orgs = who.get("orgs") or []
        names = {o.get("name") for o in orgs if isinstance(o, dict)}
        if "SZLHOLDINGS" not in names:
            raise EnrollmentError("authenticated HF principal is not in SZLHOLDINGS")
        info = self.api.repo_info(repo_id=SPACE, repo_type="space")
        if info.sha != expected_revision:
            raise EnrollmentError("HF Space revision changed")
        if secret_name in self.api.get_space_secrets(repo_id=SPACE):
            raise EnrollmentError("HF meter secret already exists; write-only value cannot be rolled back")
        # The supported Hub operation is add-or-update. A fresh random name
        # sharply reduces accidental collision, but an absence check still
        # cannot stop another writer from creating this name before add().
        # Never risk clobbering or deleting another writer's write-only value.
        raise EnrollmentError("versioned HF secret add-or-update has no atomic create-only guard; apply blocked")

    def secret_exists(self, secret_name: str):
        return secret_name in self.api.get_space_secrets(repo_id=SPACE)

    def add(self, client_id: str, key_hex: str, secret_name: str):
        # This adapter intentionally has no write implementation until a
        # provider-enforced create-only operation (or equivalent fence) exists.
        # Synthetic FakeHub exercises the recoverable transaction separately.
        raise EnrollmentError("HF provider has no guarded create-only secret operation")

    def wait_running(self):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if self.api.get_space_runtime(repo_id=SPACE).stage == "RUNNING":
                return
            time.sleep(3)
        raise EnrollmentError("HF Space did not reach RUNNING after secret change")


def _read_config(root: Path, dpapi):
    original = (root / "settings.dpapi").read_bytes()
    try:
        config = json.loads(dpapi.unprotect(original))
        clients = config["clients"]
        if (config["schema"] != SCHEMA or config["audience"] != AUDIENCE
                or not isinstance(clients, dict) or "canonical-a11oy" not in clients
                or "local-healthcheck" not in clients or len(clients) > 14
                or any(not isinstance(v, str) or len(v) != 64
                       or any(c not in "0123456789abcdef" for c in v)
                       for v in clients.values())
                or len(set(clients.values())) != len(clients)):
            raise ValueError
        return original, config
    except (ValueError, KeyError, TypeError):
        raise EnrollmentError("private meter configuration invalid") from None


def _backup(root: Path, original: bytes, run_id: str):
    backup_dir = root / "backups"
    backup_dir.mkdir(exist_ok=True)
    path = backup_dir / f"meter-enroll-{run_id}.dpapi"
    with path.open("xb") as stream:
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def enroll(root: Path, *, dpapi, supervisor, probe, hub,
           source_revision: str, space_revision: str, maintenance_window: str,
           key_factory=secrets.token_hex):
    """Injectable transaction for synthetic tests. Never called by the dry-run path."""
    receipt = _installation(root)
    probe.route_preflight()
    probe.source_preflight(source_revision)
    run_id = secrets.token_hex(16)
    secret_name = SECRET_PREFIX + run_id.upper()
    hub.preflight(space_revision, secret_name)
    supervisor._identity()
    original, config = _read_config(root, dpapi)
    client_id = "canonical-a11oy-v2-" + run_id
    key_hex = key_factory(32)
    if (not isinstance(key_hex, str) or len(key_hex) != 64
            or any(c not in "0123456789abcdef" for c in key_hex)
            or key_hex in config["clients"].values()):
        raise EnrollmentError("new key generation failed")
    backup = _backup(root, original, run_id)
    staged = dict(config)
    staged["clients"] = {**config["clients"], client_id: key_hex}
    config_path = root / "settings.dpapi"
    receipt_path = root / f"meter-enrollment-{run_id}.json"
    result = {"status": "PREPARED", "evidence_class": "DECLARED",
              "audience": AUDIENCE, "space": SPACE, "secret_name": secret_name,
              "new_client_id": client_id,
              "installed_source_revision": receipt["source_revision"],
              "product_source_revision": source_revision, "hf_space_revision": space_revision,
              "maintenance_window": maintenance_window,
              "single_writer_window_evidence": "DECLARED",
              "encrypted_rollback_copy": str(backup), "secret_values_recorded": False}

    def record(status: str):
        next_state = {**result, "status": status}
        _atomic_write(receipt_path, _json_bytes(next_state))
        result.update(next_state)

    # A recoverable, non-secret state exists before the first verifier change.
    record("PREPARED")
    try:
        _atomic_write(config_path, dpapi.protect(_json_bytes(staged)))
        supervisor.restart()
        probe.prove(client_id, key_hex)
        record("LOCAL_KEY_ACTIVE")
    except Exception:
        try:
            _atomic_write(config_path, original)
            supervisor.restart()
            record("LOCAL_ROLLED_BACK")
        except Exception:
            try:
                record("PARTIAL_LOCAL_OUTCOME_UNCERTAIN")
            except Exception:
                pass  # PREPARED or LOCAL_KEY_ACTIVE remains as a durable warning.
            raise PartialActivation("local enrollment failed and rollback needs owner attention") from None
        raise EnrollmentError("local enrollment failed; encrypted configuration restored") from None

    try:
        record("HF_ADD_ATTEMPTED")
    except Exception:
        try:
            _atomic_write(config_path, original)
            supervisor.restart()
            record("LOCAL_ROLLED_BACK")
        except Exception:
            raise PartialActivation("HF write was not started; local rollback needs owner attention") from None
        raise EnrollmentError("HF write was not started; local configuration restored") from None

    try:
        hub.add(client_id, key_hex, secret_name)
        if not hub.secret_exists(secret_name):
            raise EnrollmentError("HF secret name readback absent after add attempt")
        hub.wait_running()
        probe.wait_live(source_revision, client_id)
        record("HF_METER2_LIVE")
    except Exception:
        # HF add is an add-or-update write, and an error or lagging name readback
        # cannot prove the write did not commit. Never revoke its local verifier
        # key or delete a potentially concurrent writer's secret automatically.
        try:
            record("PARTIAL_HF_OUTCOME_UNCERTAIN")
        except Exception:
            pass  # HF_ADD_ATTEMPTED remains as the last durable recovery state.
        raise PartialActivation("HF outcome uncertain; new local key retained") from None

    # Retire the prior canonical key only after both provider and live readback pass.
    retired = dict(staged)
    retired["clients"] = {k: v for k, v in staged["clients"].items()
                          if k != "canonical-a11oy"}
    try:
        record("OLD_KEY_RETIRE_ATTEMPTED")
        _atomic_write(config_path, dpapi.protect(_json_bytes(retired)))
        supervisor.restart()
        probe.prove(client_id, key_hex)
        probe.reject("canonical-a11oy", config["clients"]["canonical-a11oy"])
        probe.wait_live(source_revision, client_id)
        record("ENROLLED_AND_OLD_KEY_RETIRED")
    except Exception:
        try:
            _atomic_write(config_path, dpapi.protect(_json_bytes(staged)))
            supervisor.restart()
            record("PARTIAL_OVERLAP_RESTORED")
        except Exception:
            try:
                record("PARTIAL_RETIREMENT_OUTCOME_UNCERTAIN")
            except Exception:
                pass  # OLD_KEY_RETIRE_ATTEMPTED remains durable.
            raise PartialActivation("key retirement and local rollback need owner attention") from None
        raise PartialActivation("new HF reader live, but old-key retirement failed; overlap restored") from None
    return result


def _source_guard(repo: Path, expected: str):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    if (git("rev-parse", "HEAD") != expected or git("status", "--porcelain")
            or git("ls-remote", "origin", "refs/heads/main").split()[0] != expected):
        raise EnrollmentError("source checkout is not clean exact remote main")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform owner-approved enrollment")
    parser.add_argument("--expected-source-revision", help="exact current GitHub main SHA")
    parser.add_argument("--expected-space-revision", help="exact pre-change HF Space SHA")
    parser.add_argument("--maintenance-window-id", help="operator-attested approved window ID")
    parser.add_argument("--acknowledge-exporter-and-space-restarts", action="store_true")
    parser.add_argument("--acknowledge-single-writer-window", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = _private_root()
        receipt = _installation(root)
        if not args.apply:
            print(json.dumps({"status": "DRY_RUN", "audience": receipt["audience"],
                              "installed_source_revision": receipt["source_revision"],
                              "space": SPACE,
                              "secret_name_template": SECRET_PREFIX + "<fresh-128-bit-random>",
                              "effects": "NONE", "secret_values_recorded": False}))
            return 0
        if (not args.expected_source_revision or not args.expected_space_revision
                or not args.maintenance_window_id
                or not re.fullmatch(r"[A-Za-z0-9_-]{6,80}", args.maintenance_window_id)
                or not args.acknowledge_exporter_and_space_restarts
                or not args.acknowledge_single_writer_window):
            raise EnrollmentError("exact revisions and both operational acknowledgements required")
        _source_guard(Path(__file__).resolve().parent.parent, args.expected_source_revision)
        result = enroll(root, dpapi=WindowsDpapi(),
                        supervisor=ExporterSupervisor(root, receipt), probe=MeterProbe(),
                        hub=HfSpace(), source_revision=args.expected_source_revision,
                        space_revision=args.expected_space_revision,
                        maintenance_window=args.maintenance_window_id)
        print(json.dumps(result, sort_keys=True))
        return 0
    except EnrollmentError as exc:
        print(json.dumps({"status": "BLOCKED" if not isinstance(exc, PartialActivation) else "PARTIAL",
                          "reason": str(exc), "secret_values_recorded": False}), file=sys.stderr)
        return 2
    except Exception:
        print(json.dumps({"status": "BLOCKED", "reason": "unexpected enrollment failure; inspect local non-secret state",
                          "secret_values_recorded": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
