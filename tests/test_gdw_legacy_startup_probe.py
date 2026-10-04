#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic legacy-container readback and native bounded-file controls.

Run with PYTHONPATH=tests:scripts:. after integration. Docker, subprocess and
network execution are denied; every Python 3.14 report below is a fixture.
"""

import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
from types import SimpleNamespace

import pytest

import probe_gdw_legacy_startup as probe


MANIFEST = "c" * 64
CONFIG = "d" * 64
IDENTIFIER = "e" * 64
NONCE = "f" * 32
NAME = "gdw-legacy-probe-" + NONCE
ASSEMBLY = Path("/synthetic/public-source")
TMPFS = {"/tmp": "rw,nosuid,nodev,noexec,size=67108864,mode=1777"}
BLOCKED = (probe.guard.GuardBlocked, probe.image.RuntimeBaseBlocked)


@pytest.fixture(autouse=True)
def no_process_or_network(monkeypatch):
    def denied(*_args, **_kwargs):
        raise AssertionError("real process or network operation forbidden in synthetic legacy tests")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(probe.base.Docker, "command", denied)


def container_fixture(kind="CONFIG_DIGEST", exited=False, *, name=NAME, nonce=NONCE, assembly=ASSEMBLY):
    installed = {
        "environment": ["PATH=/usr/local/bin:/usr/bin:/bin", "LANG=C.UTF-8"],
        "labels": {"org.opencontainers.image.title": "synthetic-python-base"},
        "image_id": "sha256:" + (CONFIG if kind == "CONFIG_DIGEST" else MANIFEST),
        "image_id_kind": kind,
        "manifest_descriptor": {"mediaType": "application/vnd.oci.image.manifest.v1+json",
                                "digest": "sha256:" + MANIFEST, "size": 512},
    }
    value = {
        "Id": IDENTIFIER, "Name": "/" + name, "Image": installed["image_id"],
        "Path": "/usr/local/bin/python", "Args": list(probe.ARGS),
        "Config": {
            "Image": installed["image_id"], "Entrypoint": ["/usr/local/bin/python"],
            "Cmd": list(probe.ARGS), "User": "65534:65534", "WorkingDir": "/",
            "Env": list(installed["environment"]), "Healthcheck": {"Test": ["NONE"]},
            "Labels": {**installed["labels"], probe.base.OWNERSHIP_LABEL: nonce}, "Volumes": None,
            "OpenStdin": True, "AttachStdin": True, "StdinOnce": True, "Tty": False,
        },
        "HostConfig": {
            "NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
            "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges"], "Memory": 256 * 1024 * 1024,
            "NanoCpus": 1_000_000_000, "PidsLimit": 32, "IpcMode": "none", "PidMode": "",
            "PublishAllPorts": False, "AutoRemove": False,
            "LogConfig": {"Type": "none", "Config": {}},
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "Tmpfs": dict(TMPFS), "Binds": None, "VolumesFrom": None, "Devices": [],
            "DeviceRequests": None, "PortBindings": {}, "CapAdd": None,
            "Mounts": [{"Type": "bind", "Source": str(assembly), "Target": "/probe", "ReadOnly": True}],
        },
        # Legacy --tmpfs is in HostConfig.Tmpfs, not this mount-point array.
        "Mounts": [{"Type": "bind", "Source": str(assembly), "Destination": "/probe",
                    "Mode": "", "RW": False, "Propagation": "rprivate"}],
        "State": {"Status": "exited" if exited else "created", "ExitCode": 0, "Pid": 0, "Error": "",
                  "Running": False, "Paused": False, "Restarting": False, "OOMKilled": False, "Dead": False},
    }
    if kind == "SELECTED_MANIFEST_DIGEST":
        value["ImageManifestDescriptor"] = {
            **installed["manifest_descriptor"], "platform": {"os": "linux", "architecture": "amd64"},
        }
    parameters = dict(name=name, nonce=nonce, manifest=MANIFEST, config=CONFIG, installed=installed,
                      identifier=IDENTIFIER, assembly=assembly, exited=exited)
    return value, parameters


def replace(value, path, replacement):
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = copy.deepcopy(replacement)


@pytest.mark.parametrize("kind", ["CONFIG_DIGEST", "SELECTED_MANIFEST_DIGEST"])
@pytest.mark.parametrize("exited", [False, True], ids=["created", "exited"])
def test_classic_and_modern_native_mount_and_stdin_readback_pass(kind, exited):
    value, parameters = container_fixture(kind, exited)
    assert CONFIG != MANIFEST
    assert len(value["Mounts"]) == 1 and value["HostConfig"]["Tmpfs"] == TMPFS
    assert value["Config"]["StdinOnce"] is True
    probe._container(value, **parameters)


@pytest.mark.parametrize("exited", [False, True], ids=["created", "exited"])
def test_classic_engine_may_supply_a_matching_manifest_witness(exited):
    value, parameters = container_fixture(exited=exited)
    value["ImageManifestDescriptor"] = {
        **parameters["installed"]["manifest_descriptor"], "platform": {"os": "linux", "architecture": "amd64"},
    }
    probe._container(value, **parameters)


READBACK_DEFECTS = [
    (("Id",), "a" * 64), (("Name",), "/other-container"), (("Image",), "sha256:" + "a" * 64),
    (("Path",), "/bin/sh"), (("Args",), ["-c", "unexpected"]),
    (("Config", "Image"), "python:3.14-slim"), (("Config", "Entrypoint"), ["/bin/sh"]),
    (("Config", "Cmd"), ["-c", "unexpected"]), (("Config", "User"), "0:0"),
    (("Config", "WorkingDir"), "/probe"), (("Config", "Env"), ["UNEXPECTED=synthetic"]),
    (("Config", "Labels"), {probe.base.OWNERSHIP_LABEL: NONCE}),
    (("Config", "Labels", probe.base.OWNERSHIP_LABEL), "0" * 32),
    (("Config", "Volumes"), {"/unexpected": {}}),
    (("Config", "Healthcheck"), {"Test": ["CMD", "unexpected"]}),
    (("Config", "OpenStdin"), False), (("Config", "AttachStdin"), False),
    (("Config", "StdinOnce"), False), (("Config", "Tty"), True),
    (("Config", "OpenStdin"), 1), (("Config", "Tty"), 0),
    (("HostConfig", "NetworkMode"), "bridge"), (("HostConfig", "ReadonlyRootfs"), False),
    (("HostConfig", "Privileged"), True), (("HostConfig", "CapDrop"), []),
    (("HostConfig", "SecurityOpt"), []), (("HostConfig", "Memory"), 0),
    (("HostConfig", "NanoCpus"), 0), (("HostConfig", "PidsLimit"), -1),
    (("HostConfig", "IpcMode"), "host"), (("HostConfig", "PidMode"), "host"),
    (("HostConfig", "PublishAllPorts"), True), (("HostConfig", "AutoRemove"), True),
    (("HostConfig", "LogConfig"), {"Type": "json-file", "Config": {}}),
    (("HostConfig", "RestartPolicy"), {"Name": "always", "MaximumRetryCount": 0}),
    (("HostConfig", "Tmpfs"), {}),
    (("HostConfig", "Tmpfs"), {**TMPFS, "/unexpected": "rw"}),
    (("HostConfig", "Tmpfs"), {"/tmp": "rw,nodev,nosuid,noexec,size=67108864,mode=1777"}),
    (("HostConfig", "Binds"), ["/unexpected:/outside"]),
    (("HostConfig", "VolumesFrom"), ["other-container"]),
    (("HostConfig", "Devices"), [{"PathOnHost": "/dev/unexpected"}]),
    (("HostConfig", "DeviceRequests"), [{"Count": -1}]),
    (("HostConfig", "PortBindings"), {"80/tcp": [{"HostPort": "8080"}]}),
    (("HostConfig", "CapAdd"), ["SYS_ADMIN"]),
    (("Mounts",), []),
    (("Mounts",), [{"Type": "bind", "Source": str(ASSEMBLY), "Destination": "/probe", "RW": False},
                   {"Type": "tmpfs", "Destination": "/tmp", "RW": True}]),
    (("Mounts", 0, "Type"), "volume"), (("Mounts", 0, "Source"), "/other-source"),
    (("Mounts", 0, "Destination"), "/other-target"), (("Mounts", 0, "RW"), True),
    (("State", "Status"), "running"), (("State", "ExitCode"), 2), (("State", "Pid"), 42),
    (("State", "Error"), "synthetic-sensitive-error"), (("State", "Running"), True),
    (("State", "Paused"), True), (("State", "Restarting"), True),
    (("State", "OOMKilled"), True), (("State", "Dead"), True),
]


@pytest.mark.parametrize("path,replacement", READBACK_DEFECTS,
                         ids=["-".join(map(str, path)) + "-" + str(index)
                              for index, (path, _value) in enumerate(READBACK_DEFECTS)])
@pytest.mark.parametrize("exited", [False, True], ids=["created", "exited"])
def test_changed_native_identity_mount_isolation_stdin_or_state_rejected(path, replacement, exited):
    value, parameters = container_fixture("SELECTED_MANIFEST_DIGEST", exited)
    probe._container(value, **parameters)
    replace(value, path, replacement)
    with pytest.raises(BLOCKED) as failure:
        probe._container(value, **parameters)
    assert "synthetic-sensitive-error" not in str(failure.value)


@pytest.mark.parametrize("kind", ["CONFIG_DIGEST", "SELECTED_MANIFEST_DIGEST"])
@pytest.mark.parametrize("field,replacement", [
    ("digest", "sha256:" + "a" * 64), ("size", 513), ("size", True),
    ("mediaType", "application/vnd.oci.image.index.v1+json"),
    ("platform", {"os": "linux", "architecture": "arm64"}),
    ("platform", {"os": "linux", "architecture": "amd64", "variant": "v3"}),
    ("platform", None), ("urls", ["https://invalid.example/synthetic"]),
])
def test_exposed_manifest_witness_is_exact_for_both_engine_id_conventions(kind, field, replacement):
    value, parameters = container_fixture(kind)
    value["ImageManifestDescriptor"] = {
        **parameters["installed"]["manifest_descriptor"], "platform": {"os": "linux", "architecture": "amd64"},
    }
    probe._container(value, **parameters)
    value["ImageManifestDescriptor"][field] = replacement
    with pytest.raises(BLOCKED): probe._container(value, **parameters)


def test_modern_image_requires_a_manifest_witness():
    value, parameters = container_fixture("SELECTED_MANIFEST_DIGEST")
    probe._container(value, **parameters)
    del value["ImageManifestDescriptor"]
    with pytest.raises(BLOCKED): probe._container(value, **parameters)


@pytest.mark.parametrize("field,replacement", [
    ("image_id_kind", "UNOBSERVED"), ("image_id", "sha256:" + CONFIG),
])
def test_modern_installed_identity_cannot_be_relabelled_as_config(field, replacement):
    value, parameters = container_fixture("SELECTED_MANIFEST_DIGEST")
    probe._container(value, **parameters)
    parameters["installed"][field] = replacement
    if field == "image_id":
        value["Image"] = replacement
        value["Config"]["Image"] = replacement
    with pytest.raises(BLOCKED): probe._container(value, **parameters)


def edited_stat(metadata, field):
    value = {name: getattr(metadata, name) for name in dir(metadata) if name.startswith("st_")}
    value[field] += 1
    return SimpleNamespace(**value)


def second_fstat_change(monkeypatch, field):
    native = os.fstat
    seen = []

    def changed(descriptor):
        result = native(descriptor)
        seen.append(descriptor)
        return edited_stat(result, field) if len(seen) == 2 else result

    monkeypatch.setattr(probe.os, "fstat", changed)
    return native, seen


def assert_descriptor_closed(native, seen):
    assert len(seen) == 2 and seen[0] == seen[1]
    with pytest.raises(OSError) as failure: native(seen[0])
    assert failure.value.errno == errno.EBADF


def test_read_allows_atime_only_change_without_losing_hash_binding(tmp_path, monkeypatch):
    path = tmp_path / "public.py"
    body = b"# synthetic public source\n"
    path.write_bytes(body)
    native, seen = second_fstat_change(monkeypatch, "st_atime_ns")
    assert probe._read(path, hashlib.sha256(body).hexdigest()) == body
    assert_descriptor_closed(native, seen)


@pytest.mark.parametrize("field", ["st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_gid",
                                  "st_size", "st_mtime_ns", "st_ctime_ns"])
def test_read_rejects_each_stable_descriptor_change_and_closes_fd(tmp_path, monkeypatch, field):
    path = tmp_path / "public.py"
    body = b"# synthetic public source\n"
    path.write_bytes(body)
    native, seen = second_fstat_change(monkeypatch, field)
    with pytest.raises(probe.guard.GuardBlocked): probe._read(path, hashlib.sha256(body).hexdigest())
    assert_descriptor_closed(native, seen)


def test_read_checks_content_digest_even_when_metadata_is_stable(tmp_path):
    path = tmp_path / "public.py"
    path.write_bytes(b"# synthetic public source\n")
    assert probe._read(path) == path.read_bytes()
    with pytest.raises(probe.guard.GuardBlocked): probe._read(path, "a" * 64)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory", "fifo", "empty", "oversize"])
def test_read_rejects_nonregular_shared_empty_or_oversized_inputs_without_blocking(tmp_path, monkeypatch, kind):
    path = tmp_path / "public.py"
    if kind == "directory": path.mkdir()
    elif kind == "fifo": os.mkfifo(path)
    else:
        path.write_bytes(b"" if kind == "empty" else b"# synthetic public source\n")
        if kind == "hardlink": os.link(path, tmp_path / "other.py")
        elif kind == "symlink":
            path.rename(tmp_path / "target.py")
            path.symlink_to(tmp_path / "target.py")
        elif kind == "oversize":
            with path.open("r+b") as stream: stream.truncate(2 * 1024 * 1024 + 1)
    native = os.open
    calls = []

    def bounded_open(target, flags, *args, **kwargs):
        assert flags & os.O_NOFOLLOW and flags & os.O_NONBLOCK
        assert flags & os.O_ACCMODE == os.O_RDONLY
        calls.append(target)
        return native(target, flags, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(probe.os, "open", bounded_open)
        with pytest.raises((OSError, probe.guard.GuardBlocked)): probe._read(path)
    assert calls == [path]


@pytest.mark.parametrize("delta", [-1, 1], ids=["short-read", "extra-byte"])
def test_read_rejects_returned_length_that_disagrees_with_open_descriptor(tmp_path, monkeypatch, delta):
    path = tmp_path / "public.py"
    path.write_bytes(b"# synthetic public source\n")
    native = os.fdopen

    class Reader:
        def __init__(self, descriptor, *args, **kwargs): self.stream = native(descriptor, *args, **kwargs)
        def __enter__(self): return self
        def __exit__(self, *args): self.stream.close()
        def read(self, limit):
            assert limit == 2 * 1024 * 1024 + 1
            value = self.stream.read(limit)
            return value[:-1] if delta < 0 else value + b"!"

    monkeypatch.setattr(probe.os, "fdopen", Reader)
    with pytest.raises(probe.guard.GuardBlocked): probe._read(path)


def orchestration_fixture(monkeypatch, tmp_path, kind, *, defect=None, overall=500.0):
    clock = [100.0]
    monkeypatch.setattr(probe.time, "monotonic", lambda: clock[0])
    bodies = {"gdw_runtime.py": b"# synthetic old public runtime\n"}
    source_hashes = {name: hashlib.sha256(body).hexdigest() for name, body in bodies.items()}
    monkeypatch.setattr(probe.guard, "SOURCE_FILES", source_hashes)
    root = tmp_path / "canonical-source"
    (root / "scripts").mkdir(parents=True)
    (root / "gdw_durable_guard.py").write_bytes(b"# synthetic public guard\n")
    (root / "scripts/configure_hf_gdw_runtime.py").write_bytes(b"# synthetic public helper\n")
    monkeypatch.setattr(probe, "ROOT", root)
    report = {
        "schema": "szl.gdw-legacy-guard-probe/v1", "state": "PREWRITE_REJECTION_VERIFIED",
        "python_version": "3.14.0", "scope": probe.guard.PROBE_SCOPE,
        "source_files_sha256": source_hashes,
        "source_closure_sha256": hashlib.sha256(probe.guard.canonical(source_hashes)).hexdigest(),
        "cases": [{"name": case, "state": "PREWRITE_REJECTION_VERIFIED", "forbidden_effect_count": 0}
                  for case in probe.guard.CASES],
        "unguarded_control": "PREPARATION_WRITE_OBSERVED", "total_forbidden_effect_count": 0,
    }
    installed = container_fixture(kind)[1]["installed"]
    observation = {"space_revision": probe.guard.SPACE_REVISION, "stage": "PAUSED",
                   "variables": {"PUBLIC_SYNTHETIC_SETTING": "fixture-only"},
                   "secret_names": sorted(probe.guard.REQUIRED_SECRETS)}
    base_observation = {"base": {"manifest_sha256": MANIFEST, "config_sha256": CONFIG},
                        "interpreter": {"version": [3, 14, 0]}}
    calls, cleanup = [], []

    class API:
        def hf_hub_download(self, **kwargs):
            assert kwargs["repo_id"] == "SZLHOLDINGS/a11oy" and kwargs["repo_type"] == "space"
            assert kwargs["revision"] == probe.guard.SPACE_REVISION
            target = kwargs["local_dir"] / kwargs["filename"]
            target.write_bytes(bodies[kwargs["filename"]])
            return str(target)

    class Docker:
        def __init__(self, directory):
            self.directory = directory
            self.started = False
            self.name = self.nonce = self.assembly = None

        def native(self, deadline): assert deadline == min(overall - 20, 220.0)
        def identities(self, deadline): return MANIFEST, CONFIG
        def pull(self, manifest, config, deadline):
            assert (manifest, config) == (MANIFEST, CONFIG)
            return copy.deepcopy(installed)
        def named(self, name, deadline): return None

        def command(self, args, deadline, limit=None, *, input_bytes=None):
            calls.append(list(args))
            if args[:2] == ["container", "create"]:
                self.name = args[args.index("--name") + 1]
                self.nonce = args[args.index("--label") + 1].split("=", 1)[1]
                mount = args[args.index("--mount") + 1]
                self.assembly = self.directory.parent / "public-source"
                assert mount == f"type=bind,source={self.assembly},target=/probe,readonly"
                assert args[args.index("--tmpfs") + 1] == "/tmp:" + TMPFS["/tmp"]
                assert args[args.index("--entrypoint") + 1:] == ["/usr/local/bin/python", installed["image_id"], *probe.ARGS]
                assert input_bytes is None and "--interactive" in args and "--env" not in args
                assert "--pull=never" in args and "--read-only" in args
                assert args[args.index("--network") + 1] == "none"
                for path in (self.assembly, self.assembly / "deployed", self.assembly / "scripts"):
                    assert stat.S_IMODE(path.stat().st_mode) == 0o755
                assert stat.S_IMODE((self.assembly / "deployed/gdw_runtime.py").stat().st_mode) == 0o444
                if defect == "lost-create": raise probe.base.ProbeBlocked("SYNTHETIC_CREATE_OUTCOME_UNKNOWN")
                return (IDENTIFIER + "\n").encode("ascii")
            assert args == ["container", "start", "--attach", "--interactive", IDENTIFIER]
            assert limit == 16 * 1024
            assert json.loads(input_bytes) == {key: observation[key] for key in ("variables", "secret_names")}
            self.started = True
            clock[0] = 105.0
            if defect == "lost-start": raise probe.base.ProbeBlocked("SYNTHETIC_START_OUTCOME_UNKNOWN")
            return probe.guard.canonical(report)

        def inspect(self, identifier, deadline):
            assert identifier == (IDENTIFIER if self.started else self.name)
            value, _parameters = container_fixture(kind, self.started, name=self.name, nonce=self.nonce,
                                                   assembly=self.assembly)
            if defect == ("bad-exited" if self.started else "bad-created"):
                value["Mounts"].append({"Type": "bind", "Source": "/extra", "Destination": "/extra", "RW": True})
            return value

    def cleaned(docker, name, nonce, config, identifier, confirmed, deadline, *, image_id=None):
        cleanup.append({"name": name, "nonce": nonce, "config": config, "identifier": identifier,
                        "confirmed": confirmed, "deadline": deadline, "image_id": image_id})
        assert image_id == installed["image_id"]
        assert deadline == min(overall, clock[0] + 20)

    monkeypatch.setattr(probe.base, "Docker", Docker)
    monkeypatch.setattr(probe.base, "_cleanup", cleaned)
    invoke = lambda: probe.observe_legacy_guard(API(), base_observation, observation,
                                                deadline=overall, temporary_root=tmp_path)
    return invoke, calls, cleanup, report


@pytest.mark.parametrize("kind", ["CONFIG_DIGEST", "SELECTED_MANIFEST_DIGEST"])
@pytest.mark.parametrize("overall", [500.0, 126.0])
def test_orchestration_uses_exact_selected_image_public_stdin_and_twenty_second_cleanup(monkeypatch, tmp_path, kind, overall):
    invoke, calls, cleanup, report = orchestration_fixture(monkeypatch, tmp_path, kind, overall=overall)
    assert invoke() == report
    assert [call[:2] for call in calls] == [["container", "create"], ["container", "start"]]
    assert len(cleanup) == 1 and cleanup[0]["confirmed"] is True
    assert not list(tmp_path.glob("gdw-legacy-native-*"))


@pytest.mark.parametrize("defect,started,confirmed", [
    ("bad-created", False, False), ("bad-exited", True, True),
    ("lost-create", False, False), ("lost-start", True, True),
])
def test_failed_or_uncertain_orchestration_cleans_up_without_retry_or_success(monkeypatch, tmp_path, defect, started, confirmed):
    invoke, calls, cleanup, _report = orchestration_fixture(monkeypatch, tmp_path, "SELECTED_MANIFEST_DIGEST", defect=defect)
    with pytest.raises(BLOCKED): invoke()
    assert sum(call[:2] == ["container", "create"] for call in calls) == 1
    assert sum(call[:2] == ["container", "start"] for call in calls) == int(started)
    assert len(cleanup) == 1 and cleanup[0]["confirmed"] is confirmed
    assert not list(tmp_path.glob("gdw-legacy-native-*"))
