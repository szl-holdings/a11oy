#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Canonical read-only observation of the pinned base's isolated stdlib SQLite.

This CLI pulls public image bytes and creates one disposable local container;
it never builds/publishes an image, loads application source, passes credentials
or mounts data, or reads/writes provider stores. The runtime imports only the
separate pure validator. A base observation is an expectation, not final-host
evidence. Any ambiguous create remains held even after bounded reconciliation.

Identity: pinned manifest/config -> explicit engine image ID -> container.Image.
https://github.com/opencontainers/image-spec/blob/main/image-index.md
https://github.com/opencontainers/image-spec/blob/main/config.md
https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gdw_durable_image as image


ROOT = Path(__file__).resolve().parents[1]
DOCKER = "/usr/bin/docker"
GIT = "/usr/bin/git"
DAEMON = "unix:///var/run/docker.sock"
MAX_SECONDS = 240
CLEANUP_SECONDS = 20
MAX_COMMANDS = 32
MAX_METADATA_BYTES = 256 * 1024
MAX_INPUT_BYTES = 256 * 1024
MAX_INSPECTION_BYTES = 64 * 1024
MAX_DOCKERFILE_BYTES = 128 * 1024
MAX_COMPRESSED_BYTES = 256 * 1024 * 1024
# Post-pull engine-reported Size acceptance bound, not a daemon disk quota.
MAX_IMAGE_BYTES = 512 * 1024 * 1024
OWNERSHIP_LABEL = "org.szl.gdw.base-probe"
WORKFLOW_REF = image.REPOSITORY + "/.github/workflows/hf-sync.yml@refs/heads/main"
_INDEX_TYPES = {"application/vnd.oci.image.index.v1+json",
                "application/vnd.docker.distribution.manifest.list.v2+json"}
_MANIFEST_TYPES = {"application/vnd.oci.image.manifest.v1+json",
                   "application/vnd.docker.distribution.manifest.v2+json"}
_CONFIG_TYPES = {"application/vnd.oci.image.config.v1+json",
                 "application/vnd.docker.container.image.v1+json"}
_LAYER_TYPES = {"application/vnd.oci.image.layer.v1.tar+gzip",
                "application/vnd.oci.image.layer.v1.tar+zstd",
                "application/vnd.oci.image.layer.v1.tar",
                "application/vnd.docker.image.rootfs.diff.tar.gzip"}

# This program is passed as a fixed -c argument, never mounted or interpolated.
# -I alone does not disable site initialization or bytecode; require all flags.
PROBE_CODE = r'''
import hashlib, json, platform, sqlite3, sys
def canonical(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")
try:
    if (sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 14)
            or sys.version_info.releaselevel != "final"
            or not sys.flags.isolated or not sys.flags.no_site
            or not sys.dont_write_bytecode or not sys.flags.ignore_environment
            or not sys.flags.safe_path or sys.executable != "/usr/local/bin/python"
            or platform.system() != "Linux" or platform.machine() != "x86_64"):
        raise ValueError()
    connection = sqlite3.connect(":memory:")
    try:
        version, source_id = connection.execute("SELECT sqlite_version(), sqlite_source_id()").fetchone()
        rows = connection.execute("PRAGMA compile_options").fetchmany(257)
    finally:
        connection.close()
    options = [row[0] for row in rows]
    if (not 1 <= len(options) <= 256 or len(set(options)) != len(options)
            or any(type(option) is not str or not option.isascii()
                   or not 1 <= len(option) <= 256
                   or any(ord(c) < 32 or ord(c) == 127 for c in option) for option in options)
            or version != sqlite3.sqlite_version):
        raise ValueError()
    report = {
        "interpreter": {"implementation": "cpython", "version": list(sys.version_info[:3]),
                        "executable": sys.executable, "isolation": "ISOLATED_NO_SITE_NO_BYTECODE",
                        "native_platform": "linux/amd64"},
        "sqlite": {"python_version": sqlite3.sqlite_version, "sql_version": version,
                   "source_id": source_id, "compile_options_count": len(options),
                   "compile_options_sha256": hashlib.sha256(canonical(sorted(options))).hexdigest()},
    }
    sys.stdout.buffer.write(canonical(report))
    sys.stdout.buffer.flush()
except BaseException:
    sys.stdout.write('{"state":"RUNTIME_BASE_NATIVE_PROBE_UNAVAILABLE"}\n')
    sys.stdout.flush()
    sys.exit(2)
'''
PROBE_ARGS = ["-I", "-B", "-S", "-c", PROBE_CODE]


class ProbeBlocked(image.RuntimeBaseBlocked):
    def __init__(self, code, cleanup_name=None):
        super().__init__(code)
        self.cleanup_name = cleanup_name


class _CommandFailed(ProbeBlocked):
    """Private bounded stdout for the acquisition worker's strict decoder only.

    str/repr/args remain the fixed failure code. Stderr is never retained.
    No output is returned as success, and default callers never receive bytes.
    """
    def __init__(self, output):
        super().__init__("RUNTIME_BASE_COMMAND_FAILED")
        self._output = output


def _remaining(deadline):
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ProbeBlocked("RUNTIME_BASE_DEADLINE_INVALID")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProbeBlocked("RUNTIME_BASE_DEADLINE_EXHAUSTED")
    return remaining


def _run(argv, *, deadline, limit, env, cwd=None, input_bytes=None, _capture_failure=False):
    """Stream both pipes under one cap; kill the process group and reap on exit."""
    _remaining(deadline)
    if (type(_capture_failure) is not bool
            or type(argv) is not list or not 1 <= len(argv) <= 96
            or any(type(arg) is not str or "\0" in arg for arg in argv)
            or sum(len(arg.encode("utf-8")) for arg in argv) > 64 * 1024
            or type(limit) is not int or not 1 <= limit <= MAX_METADATA_BYTES
            or (input_bytes is not None and
                (type(input_bytes) is not bytes or len(input_bytes) > MAX_INPUT_BYTES))):
        raise ProbeBlocked("RUNTIME_BASE_COMMAND_INVALID")
    process = None
    selector = selectors.DefaultSelector()
    output, total, written = bytearray(), 0, 0
    try:
        process = subprocess.Popen(argv, stdin=(subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL),
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=env, cwd=cwd,
                                   start_new_session=True, close_fds=True)
        for stream in (process.stdout, process.stderr):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        if process.stdin is not None:
            if input_bytes:
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE)
            else:
                process.stdin.close()
        while selector.get_map() or process.poll() is None:
            remaining = _remaining(deadline)
            for event, _mask in selector.select(min(remaining, 0.05)):
                if event.fileobj is process.stdin:
                    try:
                        written += os.write(process.stdin.fileno(), input_bytes[written:written + 16 * 1024])
                    except BrokenPipeError:
                        raise ProbeBlocked("RUNTIME_BASE_COMMAND_INPUT_REJECTED") from None
                    if written == len(input_bytes):
                        selector.unregister(process.stdin)
                        process.stdin.close()
                    continue
                data = os.read(event.fileobj.fileno(), 16 * 1024)
                if not data:
                    selector.unregister(event.fileobj)
                    continue
                total += len(data)
                if total > limit:
                    raise ProbeBlocked("RUNTIME_BASE_OUTPUT_BOUND_EXCEEDED")
                if event.fileobj is process.stdout:
                    output.extend(data)
        _remaining(deadline)
        if process.returncode != 0:
            if _capture_failure and process.returncode == 2:
                raise _CommandFailed(bytes(output))
            raise ProbeBlocked("RUNTIME_BASE_COMMAND_FAILED")
        if input_bytes is not None and written != len(input_bytes):
            raise ProbeBlocked("RUNTIME_BASE_COMMAND_INPUT_REJECTED")
    except ProbeBlocked:
        raise
    except BaseException:
        raise ProbeBlocked("RUNTIME_BASE_COMMAND_UNAVAILABLE") from None
    finally:
        selector.close()
        if process is not None:
            cleanup_failed = False
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                cleanup_failed = True
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                cleanup_failed = True
            if cleanup_failed:
                raise ProbeBlocked("RUNTIME_BASE_PROCESS_CLEANUP_UNCONFIRMED") from None
    _remaining(deadline)
    return bytes(output)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProbeBlocked("RUNTIME_BASE_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _json(data):
    if type(data) is not bytes or not 1 <= len(data) <= MAX_METADATA_BYTES:
        raise ProbeBlocked("RUNTIME_BASE_METADATA_BOUND_INVALID")
    try:
        return json.loads(data, object_pairs_hook=_object,
                          parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()))
    except ProbeBlocked:
        raise
    except BaseException:
        raise ProbeBlocked("RUNTIME_BASE_METADATA_INVALID") from None


def _digest(value):
    if type(value) is not str or not value.startswith("sha256:"):
        raise ProbeBlocked("RUNTIME_BASE_DESCRIPTOR_INVALID")
    return image._hex(value[7:])


def _raw(data, expected_digest, expected_size=None):
    """Accept raw bytes or exactly one CLI-added LF only on a digest match."""
    image._hex(expected_digest)
    if type(data) is not bytes or not 1 <= len(data) <= MAX_METADATA_BYTES:
        raise ProbeBlocked("RUNTIME_BASE_METADATA_BOUND_INVALID")
    if hashlib.sha256(data).hexdigest() != expected_digest:
        if not data.endswith(b"\n") or hashlib.sha256(data[:-1]).hexdigest() != expected_digest:
            raise ProbeBlocked("RUNTIME_BASE_MANIFEST_DIGEST_MISMATCH")
        data = data[:-1]
    if expected_size is not None and (type(expected_size) is not int or len(data) != expected_size):
        raise ProbeBlocked("RUNTIME_BASE_MANIFEST_SIZE_MISMATCH")
    return data, _json(data)


def _descriptor(value, media_types, maximum):
    if type(value) is not dict or not {"mediaType", "digest", "size"} <= set(value):
        raise ProbeBlocked("RUNTIME_BASE_DESCRIPTOR_INVALID")
    if type(value["mediaType"]) is not str or value["mediaType"] not in media_types:
        raise ProbeBlocked("RUNTIME_BASE_DESCRIPTOR_INVALID")
    digest = _digest(value["digest"])
    image._number(value["size"], 1, maximum)
    if "urls" in value or "data" in value:
        raise ProbeBlocked("RUNTIME_BASE_ALTERNATE_BLOB_SOURCE_REJECTED")
    return digest


def _manifest(value):
    if (type(value) is not dict or type(value.get("schemaVersion")) is not int
            or value["schemaVersion"] != 2 or type(value.get("mediaType")) is not str
            or value["mediaType"] not in _MANIFEST_TYPES):
        raise ProbeBlocked("RUNTIME_BASE_MANIFEST_INVALID")
    config = _descriptor(value.get("config"), _CONFIG_TYPES, MAX_METADATA_BYTES)
    layers = value.get("layers")
    if type(layers) is not list or not 1 <= len(layers) <= 64:
        raise ProbeBlocked("RUNTIME_BASE_LAYERS_INVALID")
    total = 0
    for layer in layers:
        _descriptor(layer, _LAYER_TYPES, MAX_COMPRESSED_BYTES)
        total += layer["size"]
    if total > MAX_COMPRESSED_BYTES:
        raise ProbeBlocked("RUNTIME_BASE_IMAGE_BOUND_EXCEEDED")
    return config


def _manifest_witness(value, expected, *, platform_required=False):
    image._fixed(_descriptor(value, _MANIFEST_TYPES, MAX_METADATA_BYTES), _digest(expected["digest"]))
    for key in ("mediaType", "size"):
        image._fixed(value[key], expected[key])
    if platform_required or value.get("platform") is not None:
        image._fixed(value.get("platform"), {"os": "linux", "architecture": "amd64"})


class Docker:
    def __init__(self, config):
        self.config = config
        self.commands = 0
        self._selected = None
        self.env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                    "HOME": str(config),
                    "DOCKER_CONFIG": str(config), "DOCKER_HOST": DAEMON}

    def command(self, args, deadline, limit=MAX_INSPECTION_BYTES, *, input_bytes=None):
        self.commands += 1
        if self.commands > MAX_COMMANDS:
            raise ProbeBlocked("RUNTIME_BASE_COMMAND_BOUND_EXCEEDED")
        return _run([DOCKER, "--config", str(self.config), "--host", DAEMON, *args],
                    deadline=deadline, limit=limit, env=self.env, input_bytes=input_bytes)

    def native(self, deadline):
        if platform.system() != "Linux" or platform.machine() != "x86_64":
            raise ProbeBlocked("RUNTIME_BASE_NATIVE_PLATFORM_UNAVAILABLE")
        value = _json(self.command([
            "info", "--format", '{"os":{{json .OSType}},"architecture":{{json .Architecture}}}',
        ], deadline))
        image._shape(value, {"os", "architecture"})
        if value["os"] != "linux" or value["architecture"] not in ("amd64", "x86_64"):
            raise ProbeBlocked("RUNTIME_BASE_NATIVE_PLATFORM_UNAVAILABLE")

    def identities(self, deadline):
        self._selected = None
        raw, value = _raw(self.command([
            "buildx", "imagetools", "inspect", "--raw", image.BASE_REFERENCE,
        ], deadline, MAX_METADATA_BYTES), image.BASE_SHA256)
        if (type(value) is dict and type(value.get("mediaType")) is str
                and value["mediaType"] in _MANIFEST_TYPES):
            config = _manifest(value)
            self._selected = {
                "manifest": image.BASE_SHA256, "config": config,
                "descriptor": {"mediaType": value["mediaType"], "digest": "sha256:" + image.BASE_SHA256,
                               "size": len(raw)},
            }
            return image.BASE_SHA256, config
        if (type(value) is not dict or type(value.get("schemaVersion")) is not int
                or value["schemaVersion"] != 2 or type(value.get("mediaType")) is not str
                or value["mediaType"] not in _INDEX_TYPES):
            raise ProbeBlocked("RUNTIME_BASE_INDEX_INVALID")
        entries = value.get("manifests")
        if type(entries) is not list or not 1 <= len(entries) <= 64:
            raise ProbeBlocked("RUNTIME_BASE_INDEX_BOUND_INVALID")
        selected = []
        for entry in entries:
            _descriptor(entry, _MANIFEST_TYPES, MAX_METADATA_BYTES)
            selected_platform = entry.get("platform")
            if type(selected_platform) is not dict:
                raise ProbeBlocked("RUNTIME_BASE_PLATFORM_INVALID")
            if (selected_platform.get("os") == "linux"
                    and selected_platform.get("architecture") == "amd64"):
                if selected_platform != {"os": "linux", "architecture": "amd64"}:
                    raise ProbeBlocked("RUNTIME_BASE_PLATFORM_AMBIGUOUS")
                selected.append(entry)
        if len(selected) != 1:
            raise ProbeBlocked("RUNTIME_BASE_PLATFORM_AMBIGUOUS")
        descriptor = selected[0]
        digest = _digest(descriptor["digest"])
        raw_bytes, manifest = _raw(self.command([
            "buildx", "imagetools", "inspect", "--raw", "docker.io/library/python@sha256:" + digest,
        ], deadline, MAX_METADATA_BYTES), digest, descriptor["size"])
        config = _manifest(manifest)
        self._selected = {
            "manifest": digest, "config": config,
            "descriptor": {"mediaType": manifest["mediaType"], "digest": "sha256:" + digest,
                           "size": len(raw_bytes)},
        }
        return digest, config

    def pull(self, manifest, config, deadline):
        if (self._selected is None or self._selected["manifest"] != manifest
                or self._selected["config"] != config):
            raise ProbeBlocked("RUNTIME_BASE_IMAGE_SELECTION_UNBOUND")
        reference = "docker.io/library/python@sha256:" + manifest
        self.command(["image", "pull", "--platform", image.PLATFORM, "--quiet", reference], deadline)
        value = _json(self.command(["image", "inspect", "--format", "{{json .}}", reference], deadline))
        if type(value) is not dict:
            raise ProbeBlocked("RUNTIME_BASE_IMAGE_INVALID")
        descriptor = self._selected["descriptor"]
        if value.get("Id") == "sha256:" + config:
            identity_kind = "CONFIG_DIGEST"
            if value.get("Descriptor") is not None:
                _manifest_witness(value["Descriptor"], descriptor)
        elif value.get("Id") == "sha256:" + manifest:
            # Moby's containerd store uses the target manifest as ImageID.
            # Require its explicit witness; this is not an interchangeable ID.
            # https://github.com/moby/moby/blob/v28.5.2/daemon/containerd/image_inspect.go
            identity_kind = "SELECTED_MANIFEST_DIGEST"
            _manifest_witness(value.get("Descriptor"), descriptor)
        else:
            raise ProbeBlocked("RUNTIME_BASE_IMAGE_ID_UNBOUND")
        image._fixed(value.get("Os"), "linux")
        image._fixed(value.get("Architecture"), "amd64")
        if value.get("Variant") not in (None, ""):
            raise ProbeBlocked("RUNTIME_BASE_PLATFORM_AMBIGUOUS")
        image._number(value.get("Size"), 1, MAX_IMAGE_BYTES)
        digests = value.get("RepoDigests")
        aliases = {prefix + "@sha256:" + manifest for prefix in
                   ("python", "library/python", "docker.io/library/python")}
        if (type(digests) is not list or len(digests) > 64
                or any(type(item) is not str for item in digests) or not aliases.intersection(digests)):
            raise ProbeBlocked("RUNTIME_BASE_IMAGE_MANIFEST_UNBOUND")
        settings = value.get("Config")
        if type(settings) is not dict or settings.get("Volumes") not in (None, {}):
            raise ProbeBlocked("RUNTIME_BASE_IMAGE_MOUNTS_REJECTED")
        environment = settings.get("Env")
        if (type(environment) is not list or len(environment) > 64
                or any(type(item) is not str or len(item) > 4096 for item in environment)):
            raise ProbeBlocked("RUNTIME_BASE_IMAGE_ENVIRONMENT_INVALID")
        labels = {} if settings.get("Labels") is None else settings["Labels"]
        if type(labels) is not dict or OWNERSHIP_LABEL in labels:
            raise ProbeBlocked("RUNTIME_BASE_IMAGE_LABEL_INVALID")
        return {"environment": environment, "labels": labels, "image_id": value["Id"],
                "image_id_kind": identity_kind, "manifest_descriptor": dict(descriptor)}

    def named(self, name, deadline):
        raw = self.command(["container", "ls", "--all", "--no-trunc", "--filter", "name=^/" + name + "$",
                            "--format", "{{.ID}}"], deadline)
        entries = raw.splitlines()
        if len(entries) > 1:
            raise ProbeBlocked("RUNTIME_BASE_CONTAINER_ID_AMBIGUOUS")
        if not entries:
            return None
        try:
            return image._hex(entries[0].decode("ascii"))
        except (UnicodeError, image.RuntimeBaseBlocked):
            raise ProbeBlocked("RUNTIME_BASE_CONTAINER_ID_INVALID") from None

    def inspect(self, identifier, deadline):
        return _json(self.command(["container", "inspect", "--format", "{{json .}}", identifier], deadline))


def _owned(value, name, nonce, config, identifier=None, *, image_id=None):
    if type(value) is not dict or type(value.get("Config")) is not dict:
        raise ProbeBlocked("RUNTIME_BASE_CONTAINER_OWNERSHIP_UNCONFIRMED")
    actual_id = image._hex(value.get("Id"))
    if identifier is not None:
        image._fixed(actual_id, identifier)
    image._fixed(value.get("Name"), "/" + name)
    image_id = "sha256:" + config if image_id is None else image_id
    _digest(image_id)
    image._fixed(value.get("Image"), image_id)
    labels = value["Config"].get("Labels")
    if type(labels) is not dict or labels.get(OWNERSHIP_LABEL) != nonce:
        raise ProbeBlocked("RUNTIME_BASE_CONTAINER_OWNERSHIP_UNCONFIRMED")
    return actual_id


def _container(value, name, nonce, manifest, config, installed, identifier, *, exited):
    kind = installed["image_id_kind"]
    if kind not in ("CONFIG_DIGEST", "SELECTED_MANIFEST_DIGEST"):
        raise ProbeBlocked("RUNTIME_BASE_IMAGE_ID_UNBOUND")
    image._fixed(installed["image_id"], "sha256:" + (config if kind == "CONFIG_DIGEST" else manifest))
    _owned(value, name, nonce, config, identifier, image_id=installed["image_id"])
    image._fixed(value.get("Path"), image.EXECUTABLE)
    image._fixed(value.get("Args"), PROBE_ARGS)
    image._fixed(value.get("Mounts"), [])
    settings = value["Config"]
    for key, expected in (("Image", installed["image_id"]), ("User", "65534:65534"), ("WorkingDir", "/"),
                          ("Entrypoint", [image.EXECUTABLE]), ("Cmd", PROBE_ARGS),
                          ("Env", installed["environment"]),
                          ("Labels", dict(installed["labels"], **{OWNERSHIP_LABEL: nonce}))):
        image._fixed(settings.get(key), expected)
    if settings.get("Volumes") not in (None, {}):
        raise ProbeBlocked("RUNTIME_BASE_CONTAINER_MOUNTS_REJECTED")
    image._fixed(settings.get("Healthcheck"), {"Test": ["NONE"]})
    image._fixed(settings.get("OpenStdin"), False)
    image._fixed(settings.get("Tty"), False)
    host = value.get("HostConfig")
    if type(host) is not dict:
        raise ProbeBlocked("RUNTIME_BASE_CONTAINER_ISOLATION_INVALID")
    for key, expected in (("NetworkMode", "none"), ("ReadonlyRootfs", True), ("Privileged", False),
                          ("CapDrop", ["ALL"]), ("SecurityOpt", ["no-new-privileges"]),
                          ("Memory", 128 * 1024 * 1024), ("NanoCpus", 1_000_000_000),
                          ("PidsLimit", 16), ("IpcMode", "none"), ("PidMode", ""),
                          ("PublishAllPorts", False), ("AutoRemove", False)):
        image._fixed(host.get(key), expected)
    for key in ("Binds", "Mounts", "Tmpfs", "VolumesFrom", "Devices", "DeviceRequests", "PortBindings", "CapAdd"):
        if host.get(key) not in (None, [], {}):
            raise ProbeBlocked("RUNTIME_BASE_CONTAINER_ISOLATION_INVALID")
    image._fixed(host.get("LogConfig"), {"Type": "none", "Config": {}})
    image._fixed(host.get("RestartPolicy"), {"Name": "no", "MaximumRetryCount": 0})
    descriptor = value.get("ImageManifestDescriptor")
    if descriptor is not None or kind == "SELECTED_MANIFEST_DIGEST":
        _manifest_witness(descriptor, installed["manifest_descriptor"], platform_required=True)
    state = value.get("State")
    if type(state) is not dict:
        raise ProbeBlocked("RUNTIME_BASE_CONTAINER_STATE_INVALID")
    for key in ("Running", "Paused", "Restarting", "OOMKilled", "Dead"):
        image._fixed(state.get(key), False)
    image._fixed(state.get("Pid"), 0)
    image._fixed(state.get("ExitCode"), 0)
    image._fixed(state.get("Error"), "")
    image._fixed(state.get("Status"), "exited" if exited else "created")


def _cleanup(docker, name, nonce, config, identifier, confirmed, deadline, *, image_id=None):
    """Reconcile only the exact nonce-owned container; never retry creation."""
    try:
        current = docker.named(name, deadline)
        if current is None:
            if not confirmed:
                # The daemon might still complete a lost create after this read.
                raise ProbeBlocked("RUNTIME_BASE_CLEANUP_UNCONFIRMED", name)
            if identifier is not None:
                raw = docker.command(["container", "ls", "--all", "--no-trunc", "--filter", "id=" + identifier,
                                      "--format", "{{.ID}}"], deadline)
                if raw:
                    raise ProbeBlocked("RUNTIME_BASE_CLEANUP_UNCONFIRMED", name)
            return
        value = docker.inspect(current, deadline)
        _owned(value, name, nonce, config, current, image_id=image_id)
        if confirmed and identifier is not None and current != identifier:
            raise ProbeBlocked("RUNTIME_BASE_CLEANUP_UNCONFIRMED", name)
        try:
            returned = docker.command(["container", "rm", "--force", current], deadline)
            if returned != (current + "\n").encode("ascii"):
                raise ProbeBlocked("RUNTIME_BASE_CLEANUP_UNCONFIRMED", name)
        except image.RuntimeBaseBlocked:
            # An accepted remove can lose its reply; exact absence is read back.
            pass
        if docker.named(name, deadline) is not None:
            raise ProbeBlocked("RUNTIME_BASE_CLEANUP_UNCONFIRMED", name)
        remaining = docker.command(["container", "ls", "--all", "--no-trunc", "--filter", "id=" + current,
                                    "--format", "{{.ID}}"], deadline)
        if remaining:
            raise ProbeBlocked("RUNTIME_BASE_CLEANUP_UNCONFIRMED", name)
        _remaining(deadline)
    except BaseException:
        raise ProbeBlocked("RUNTIME_BASE_CLEANUP_UNCONFIRMED", name) from None


def observe_runtime_base(source_revision, dockerfile_sha256, execution, *, deadline=None, temporary_root=None):
    """Native operation for the canonical CLI; tests replace the Docker boundary."""
    image._hex(source_revision, 40)
    image._hex(dockerfile_sha256)
    image._shape(execution, {"runner", "run_id", "run_attempt"})
    image._fixed(execution["runner"], "GITHUB_ACTIONS_CANONICAL_MAIN")
    image._number(execution["run_id"], 1, 2**63 - 1)
    image._number(execution["run_attempt"], 1, 1000)
    now = time.monotonic()
    deadline = now + MAX_SECONDS if deadline is None else deadline
    _remaining(deadline)
    deadline = min(deadline, now + MAX_SECONDS)
    work_deadline = deadline - CLEANUP_SECONDS
    _remaining(work_deadline)
    report = None
    with tempfile.TemporaryDirectory(prefix="gdw-base-probe-", dir=temporary_root) as directory:
        docker = Docker(Path(directory))
        docker.native(work_deadline)
        manifest, config = docker.identities(work_deadline)
        installed = docker.pull(manifest, config, work_deadline)
        nonce = uuid.uuid4().hex
        name = "gdw-base-probe-" + nonce
        if docker.named(name, work_deadline) is not None:
            raise ProbeBlocked("RUNTIME_BASE_CONTAINER_NAME_COLLISION")
        identifier, confirmed = None, False
        try:
            # Mark this boundary before dispatch: an error is not proof of no create.
            raw = docker.command([
                "container", "create", "--pull=never", "--platform", image.PLATFORM,
                "--name", name, "--label", OWNERSHIP_LABEL + "=" + nonce,
                "--network", "none", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--user", "65534:65534",
                "--pids-limit", "16", "--memory", "128m", "--cpus", "1",
                "--ipc", "none", "--no-healthcheck", "--log-driver", "none",
                "--workdir", "/", "--entrypoint", image.EXECUTABLE,
                installed["image_id"], *PROBE_ARGS,
            ], work_deadline)
            try:
                identifier = image._hex(raw.decode("ascii").removesuffix("\n"))
            except (UnicodeError, image.RuntimeBaseBlocked):
                raise ProbeBlocked("RUNTIME_BASE_CONTAINER_ID_INVALID") from None
            value = docker.inspect(name, work_deadline)
            _container(value, name, nonce, manifest, config, installed, identifier, exited=False)
            confirmed = True
            payload = _json(docker.command(["container", "start", "--attach", identifier],
                                          work_deadline, image.MAX_OBSERVATION_BYTES))
            _container(docker.inspect(identifier, work_deadline), name, nonce, manifest, config,
                       installed, identifier, exited=True)
            image._shape(payload, {"interpreter", "sqlite"})
            report = image.validate_runtime_base_observation({
                "schema": image.SCHEMA, "state": "OBSERVED", "repository": image.REPOSITORY,
                "source_revision": source_revision, "dockerfile_sha256": dockerfile_sha256,
                "scope": "PINNED_BASE_STDLIB_ONLY", "final_runtime": "FINAL_RUNTIME_NOT_OBSERVED",
                "execution": execution,
                "base": {"reference": image.BASE_REFERENCE, "platform": image.PLATFORM,
                         "manifest_sha256": manifest, "config_sha256": config},
                **payload, "requirements": dict(image.REQUIREMENTS),
            }, source_revision, dockerfile_sha256)
        finally:
            _cleanup(docker, name, nonce, config, identifier, confirmed,
                     min(deadline, time.monotonic() + CLEANUP_SECONDS), image_id=installed["image_id"])
    result = image.validate_runtime_base_observation(report, source_revision, dockerfile_sha256)
    _remaining(deadline)
    return result


def _read_dockerfile(path):
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        before = os.fstat(descriptor)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or not 1 <= before.st_size <= MAX_DOCKERFILE_BYTES):
            raise ProbeBlocked("RUNTIME_BASE_DOCKERFILE_INVALID")
        data = bytearray()
        while len(data) <= MAX_DOCKERFILE_BYTES:
            chunk = os.read(descriptor, min(16 * 1024, MAX_DOCKERFILE_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        after = os.fstat(descriptor)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
                                  value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if identity(before) != identity(after) or len(data) != before.st_size:
            raise ProbeBlocked("RUNTIME_BASE_DOCKERFILE_CHANGED")
        return bytes(data)
    except image.RuntimeBaseBlocked:
        raise
    except BaseException:
        raise ProbeBlocked("RUNTIME_BASE_DOCKERFILE_INVALID") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _require_runtime_base(text):
    """Read top-level FROM only; reject unsupported escape/continuation syntax.

    This is a narrow declaration check, not a second COPY parser or publisher.
    Heredoc contents are data and cannot contribute a runtime FROM declaration.
    """
    runtime = []
    stages = []
    pending = []
    heredoc = None
    for line in text.splitlines():
        if heredoc is not None:
            delimiter, tabs = heredoc
            if (line.lstrip("\t") if tabs else line) == delimiter:
                heredoc = None
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if re.match(r"(?i)^#[ \t]*escape[ \t]*=", stripped):
                raise ProbeBlocked("RUNTIME_BASE_DOCKERFILE_SYNTAX_UNQUALIFIED")
            continue
        pending.append(line)
        if line.rstrip().endswith("\\"):
            continue
        continued = len(pending) > 1
        logical = " ".join(part.rstrip().removesuffix("\\") for part in pending).strip()
        pending = []
        keyword = logical.split(None, 1)[0].upper()
        if keyword not in {"FROM", "RUN", "COPY", "ADD", "ARG", "ENV", "LABEL", "WORKDIR", "CMD",
                           "ENTRYPOINT", "EXPOSE", "VOLUME", "USER", "HEALTHCHECK", "SHELL", "STOPSIGNAL"}:
            raise ProbeBlocked("RUNTIME_BASE_DOCKERFILE_SYNTAX_UNQUALIFIED")
        if keyword == "FROM":
            if continued:
                raise ProbeBlocked("RUNTIME_BASE_DOCKERFILE_SYNTAX_UNQUALIFIED")
            stages.append(logical)
            if re.search(r"(?i)[ \t]AS[ \t]+runtime[ \t]*$", logical):
                runtime.append(logical)
        if "<<" in logical:
            # Accept the simple native-Python heredocs used in this source;
            # quoted shell strings cannot masquerade as a delimiter declaration.
            match = re.fullmatch(r"RUN[ \t]+python3[ \t]+<<(-?)'([A-Za-z_][A-Za-z0-9_]*)'", logical)
            if continued or match is None:
                raise ProbeBlocked("RUNTIME_BASE_DOCKERFILE_SYNTAX_UNQUALIFIED")
            heredoc = (match[2], bool(match[1]))
    if pending or heredoc is not None:
        raise ProbeBlocked("RUNTIME_BASE_DOCKERFILE_SYNTAX_UNQUALIFIED")
    expected = "FROM python:3.14-slim@sha256:" + image.BASE_SHA256 + " AS runtime"
    if runtime != [expected] or not stages or stages[-1] != expected:
        raise ProbeBlocked("RUNTIME_BASE_DOCKERFILE_BASE_UNQUALIFIED")


def canonical_context(source_revision, *, environment=None, root=ROOT, deadline):
    environment = os.environ if environment is None else environment
    image._hex(source_revision, 40)
    for key, expected in (("GITHUB_ACTIONS", "true"), ("GITHUB_REPOSITORY", image.REPOSITORY),
                          ("GITHUB_REF", "refs/heads/main"), ("GITHUB_SHA", source_revision),
                          ("GITHUB_WORKFLOW_REF", WORKFLOW_REF)):
        image._fixed(environment.get(key), expected)
    if environment.get("GITHUB_EVENT_NAME") not in ("push", "workflow_dispatch"):
        raise ProbeBlocked("RUNTIME_BASE_CANONICAL_CONTEXT_INVALID")
    numbers = {}
    for key, maximum in (("GITHUB_RUN_ID", 2**63 - 1), ("GITHUB_RUN_ATTEMPT", 1000)):
        value = environment.get(key)
        if type(value) is not str or re.fullmatch(r"[1-9][0-9]{0,18}", value) is None:
            raise ProbeBlocked("RUNTIME_BASE_CANONICAL_CONTEXT_INVALID")
        numbers[key] = int(value)
        image._number(numbers[key], 1, maximum)
    git_env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_NO_LAZY_FETCH": "1", "GIT_ALLOW_PROTOCOL": "", "GIT_TERMINAL_PROMPT": "0"}
    head = _run([GIT, "-C", str(root), "rev-parse", "HEAD"], deadline=deadline,
                limit=1024, env=git_env)
    image._fixed(head, (source_revision + "\n").encode("ascii"))
    data = _read_dockerfile(root / "Dockerfile")
    original = _run([GIT, "-C", str(root), "show", source_revision + ":Dockerfile"],
                    deadline=deadline, limit=MAX_DOCKERFILE_BYTES, env=git_env)
    image._fixed(original, data)
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        raise ProbeBlocked("RUNTIME_BASE_DOCKERFILE_INVALID") from None
    _require_runtime_base(text)
    _remaining(deadline)
    return hashlib.sha256(data).hexdigest(), {
        "runner": "GITHUB_ACTIONS_CANONICAL_MAIN", "run_id": numbers["GITHUB_RUN_ID"],
        "run_attempt": numbers["GITHUB_RUN_ATTEMPT"],
    }


def _unlink_owned_output(path, identity):
    try:
        observed = os.lstat(path)
        if (observed.st_dev, observed.st_ino) == identity and stat.S_ISREG(observed.st_mode):
            os.unlink(path)
    except FileNotFoundError:
        pass


def _write_output(path, value, *, deadline=None):
    data = image.canonical(value)
    if len(data) > image.MAX_OBSERVATION_BYTES:
        raise ProbeBlocked("RUNTIME_BASE_OUTPUT_BOUND_EXCEEDED")
    path = Path(path)
    if not path.is_absolute() or path.name != "gdw-runtime-base-observation.json" or ".." in path.parts:
        raise ProbeBlocked("RUNTIME_BASE_OUTPUT_PATH_INVALID")
    descriptor = None
    identity = None
    try:
        if deadline is not None:
            _remaining(deadline)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        metadata = os.fstat(descriptor)
        identity = metadata.st_dev, metadata.st_ino
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if deadline is not None:
            _remaining(deadline)
    except BaseException:
        if identity is not None:
            _unlink_owned_output(path, identity)
        raise ProbeBlocked("RUNTIME_BASE_OUTPUT_UNAVAILABLE") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return identity


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise ProbeBlocked("RUNTIME_BASE_ARGUMENTS_INVALID")


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True)
    output = None
    output_identity = None
    try:
        args = parser.parse_args(argv)
        output = args.output
        deadline = time.monotonic() + MAX_SECONDS
        digest, execution = canonical_context(args.source_sha, deadline=deadline - CLEANUP_SECONDS)
        value = observe_runtime_base(args.source_sha, digest, execution, deadline=deadline,
                                     temporary_root=os.environ.get("RUNNER_TEMP"))
        _remaining(deadline)
        output_identity = _write_output(output, value, deadline=deadline)
        _remaining(deadline)
        return 0
    except Exception as exc:
        value = {"schema": image.SCHEMA, "state": "HELD", "scope": "PINNED_BASE_STDLIB_ONLY",
                 "final_runtime": "FINAL_RUNTIME_NOT_OBSERVED", "reason": "RUNTIME_BASE_OBSERVATION_UNAVAILABLE"}
        name = getattr(exc, "cleanup_name", None)
        if type(name) is str and re.fullmatch(r"gdw-base-probe-[0-9a-f]{32}", name):
            value["reason"] = "RUNTIME_BASE_CLEANUP_UNCONFIRMED"
            value["cleanup_container_name"] = name
        if output is not None:
            try:
                if output_identity is not None:
                    _unlink_owned_output(output, output_identity)
                _write_output(output, value)
            except Exception:
                pass
        sys.stdout.buffer.write(image.canonical(value))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
