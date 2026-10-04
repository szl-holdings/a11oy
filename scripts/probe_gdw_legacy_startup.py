#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Observe exact old-source rejection in the selected pinned Python base.

Only public source files are mounted. Public variable values and secret NAMES
travel over stdin; job credentials never enter Docker arguments, files or the
container environment. The result covers imports after interpreter startup,
not the final deployed image or unknown external writers.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import uuid

import gdw_durable_guard as guard
import gdw_durable_image as image
import probe_gdw_runtime_base as base

ROOT = Path(__file__).resolve().parents[1]
PROBE_CODE = r'''
import importlib.util,json,pathlib,sys,time
try:
    if sys.version_info[:2] != (3,14) or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
        raise ValueError()
    path=pathlib.Path('/probe/scripts/configure_hf_gdw_runtime.py')
    spec=importlib.util.spec_from_file_location('_native_legacy_probe',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    value=json.loads(sys.stdin.buffer.read(131073),object_pairs_hook=module._managed_object)
    if type(value) is not dict or set(value)!={'variables','secret_names'}:
        raise ValueError()
    result=module.legacy_guard_probe(pathlib.Path('/probe/deployed'),variables=value['variables'],
        secret_names=value['secret_names'],deadline=time.monotonic()+100)
    sys.stdout.buffer.write(module._managed_json(result))
except BaseException:
    sys.stdout.write('{"state":"LEGACY_NATIVE_GUARD_UNAVAILABLE"}\n')
    sys.exit(2)
'''
ARGS = ["-I", "-B", "-S", "-c", PROBE_CODE]


def _require(value, code="LEGACY_NATIVE_PROBE_UNQUALIFIED"):
    if value is not True:
        raise guard.GuardBlocked(code)


def _read(path: Path, expected=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= 2 * 1024 * 1024)
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(2 * 1024 * 1024 + 1)
        after = os.fstat(fd)
        stable = lambda item: tuple(getattr(item, name) for name in (
            "st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_gid", "st_size", "st_mtime_ns", "st_ctime_ns"))
        _require(len(data) == before.st_size and stable(after) == stable(before))
        _require(expected is None or hashlib.sha256(data).hexdigest() == expected)
        return data
    finally:
        os.close(fd)


def _container(value, *, name, nonce, manifest, config, installed, identifier, assembly, exited):
    kind = installed["image_id_kind"]
    _require(kind in {"CONFIG_DIGEST", "SELECTED_MANIFEST_DIGEST"})
    _require(installed["image_id"] == "sha256:" + (config if kind == "CONFIG_DIGEST" else manifest))
    base._owned(value, name, nonce, config, identifier, image_id=installed["image_id"])
    settings, host, state = value.get("Config", {}), value.get("HostConfig", {}), value.get("State", {})
    _require(type(settings) is dict and type(host) is dict and type(state) is dict)
    _require(value.get("Path") == image.EXECUTABLE and value.get("Args") == ARGS
        and settings.get("Image") == installed["image_id"]
        and settings.get("Labels") == dict(installed["labels"], **{base.OWNERSHIP_LABEL: nonce})
        and settings.get("Volumes") in (None, {})
        and settings.get("Entrypoint") == [image.EXECUTABLE] and settings.get("Cmd") == ARGS
        and settings.get("User") == "65534:65534" and settings.get("WorkingDir") == "/"
        and settings.get("Env") == installed["environment"] and settings.get("Healthcheck") == {"Test": ["NONE"]}
        and settings.get("OpenStdin") is True and settings.get("AttachStdin") is True
        and settings.get("StdinOnce") is True and settings.get("Tty") is False)
    _require(host.get("NetworkMode") == "none" and host.get("ReadonlyRootfs") is True
        and host.get("Privileged") is False and host.get("CapDrop") == ["ALL"]
        and host.get("SecurityOpt") == ["no-new-privileges"] and host.get("Memory") == 256 * 1024 * 1024
        and host.get("NanoCpus") == 1_000_000_000 and host.get("PidsLimit") == 32
        and host.get("IpcMode") == "none" and host.get("PublishAllPorts") is False
        and host.get("PidMode") == "" and host.get("AutoRemove") is False)
    _require(host.get("LogConfig") == {"Type": "none", "Config": {}}
        and host.get("RestartPolicy") == {"Name": "no", "MaximumRetryCount": 0})
    _require(host.get("Tmpfs") == {"/tmp": "rw,nosuid,nodev,noexec,size=67108864,mode=1777"})
    for key in ("Binds", "VolumesFrom", "Devices", "DeviceRequests", "PortBindings", "CapAdd"):
        _require(host.get(key) in (None, [], {}))
    mounts = value.get("Mounts")
    _require(type(mounts) is list and len(mounts) == 1)
    mount = mounts[0]
    _require(mount.get("Type") == "bind" and mount.get("Source") == str(assembly)
        and mount.get("Destination") == "/probe" and mount.get("RW") is False)
    descriptor = value.get("ImageManifestDescriptor")
    if descriptor is not None or kind == "SELECTED_MANIFEST_DIGEST":
        base._manifest_witness(descriptor, installed["manifest_descriptor"], platform_required=True)
    _require(state.get("Status") == ("exited" if exited else "created") and state.get("ExitCode") == 0
        and state.get("Pid") == 0 and state.get("Error") == ""
        and all(state.get(key) is False for key in ("Running", "Paused", "Restarting", "OOMKilled", "Dead")))


def observe_legacy_guard(api, base_observation: dict, observation: dict, *, deadline: float,
                         temporary_root: Path) -> dict:
    guard.validate_environment(observation["variables"], observation["secret_names"])
    _require(observation["space_revision"] == guard.SPACE_REVISION
        and observation["stage"] in {"PAUSED", "RUNTIME_ERROR"})
    work_deadline = min(deadline - 20, time.monotonic() + 120)
    _require(time.monotonic() < work_deadline)
    with tempfile.TemporaryDirectory(prefix="gdw-legacy-native-", dir=temporary_root) as temporary:
        directory = Path(temporary)
        assembly = directory / "public-source"; assembly.mkdir(mode=0o755)
        deployed = assembly / "deployed"; deployed.mkdir(mode=0o755)
        scripts = assembly / "scripts"; scripts.mkdir(mode=0o755)
        downloads = directory / "downloads"; downloads.mkdir(mode=0o700)
        for name, expected in guard.SOURCE_FILES.items():
            result = api.hf_hub_download(repo_id="SZLHOLDINGS/a11oy", repo_type="space", revision=guard.SPACE_REVISION,
                filename=name, local_dir=downloads, cache_dir=directory / "cache")
            _require(type(result) is str and Path(result) == downloads / name)
            body = _read(Path(result), expected)
            target = deployed / name; target.write_bytes(body); target.chmod(0o444)
        for name in ("gdw_durable_guard.py", "scripts/configure_hf_gdw_runtime.py"):
            target = assembly / name; target.write_bytes(_read(ROOT / name)); target.chmod(0o444)
        # umask077 may narrow mkdir's public-source mode; only public source
        # assembly is traversable by the deliberately unprivileged container.
        for path in (assembly, deployed, scripts): path.chmod(0o755)
        docker_dir = directory / "docker"; docker_dir.mkdir(mode=0o700)
        docker = base.Docker(docker_dir)
        docker.native(work_deadline)
        manifest, config = docker.identities(work_deadline)
        _require(manifest == base_observation["base"]["manifest_sha256"]
            and config == base_observation["base"]["config_sha256"])
        installed = docker.pull(manifest, config, work_deadline)
        nonce = uuid.uuid4().hex; name = "gdw-legacy-probe-" + nonce
        _require(docker.named(name, work_deadline) is None)
        identifier, confirmed = None, False
        try:
            raw = docker.command(["container", "create", "--pull=never", "--platform", image.PLATFORM,
                "--name", name, "--label", base.OWNERSHIP_LABEL + "=" + nonce,
                "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--user", "65534:65534", "--pids-limit", "32", "--memory", "256m", "--cpus", "1", "--ipc", "none",
                "--no-healthcheck", "--log-driver", "none", "--interactive", "--workdir", "/",
                "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=67108864,mode=1777",
                "--mount", f"type=bind,source={assembly},target=/probe,readonly",
                "--entrypoint", image.EXECUTABLE, installed["image_id"], *ARGS], work_deadline)
            identifier = image._hex(raw.decode("ascii").removesuffix("\n"))
            parameters = dict(name=name, nonce=nonce, manifest=manifest, config=config, installed=installed,
                identifier=identifier, assembly=assembly)
            _container(docker.inspect(name, work_deadline), **parameters, exited=False)
            confirmed = True
            raw = docker.command(["container", "start", "--attach", "--interactive", identifier], work_deadline,
                limit=16 * 1024, input_bytes=guard.canonical({key: observation[key] for key in ("variables", "secret_names")}))
            _container(docker.inspect(identifier, work_deadline), **parameters, exited=True)
            report = json.loads(raw)
            _require(report.get("python_version") == ".".join(str(n) for n in base_observation["interpreter"]["version"])
                and report.get("source_files_sha256") == guard.SOURCE_FILES)
        finally:
            base._cleanup(docker, name, nonce, config, identifier, confirmed,
                min(deadline, time.monotonic() + base.CLEANUP_SECONDS), image_id=installed["image_id"])
    _require(time.monotonic() < deadline)
    return report
