#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic Docker/registry controls and native bounded-process negatives.

No test pulls/runs/builds an image. All Python 3.14/base observations here are
explicit synthetic fixtures; the workspace interpreter is never relabelled.
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

import gdw_durable_image as image
from scripts import probe_gdw_runtime_base as probe


SOURCE = "a" * 40
DOCKER_HASH = "b" * 64
MANIFEST = "c" * 64
CONFIG = "d" * 64
CONTAINER = "e" * 64
PRIVATE = "synthetic-private-content-must-not-escape"
EXECUTION = {"runner": "GITHUB_ACTIONS_CANONICAL_MAIN", "run_id": 42, "run_attempt": 1}
ENVIRONMENT = ["PATH=/usr/local/bin:/usr/bin:/bin", "LANG=C.UTF-8"]
MANIFEST_DESCRIPTOR = {"mediaType": "application/vnd.oci.image.manifest.v1+json",
                       "digest": "sha256:" + MANIFEST, "size": 512}


def fixture_report():
    return {
        "schema": image.SCHEMA, "state": "OBSERVED", "repository": image.REPOSITORY,
        "source_revision": SOURCE, "dockerfile_sha256": DOCKER_HASH,
        "scope": "PINNED_BASE_STDLIB_ONLY", "final_runtime": "FINAL_RUNTIME_NOT_OBSERVED",
        "execution": dict(EXECUTION),
        "base": {"reference": image.BASE_REFERENCE, "platform": "linux/amd64",
                 "manifest_sha256": MANIFEST, "config_sha256": CONFIG},
        "interpreter": {"implementation": "cpython", "version": [3, 14, 0],
                        "executable": "/usr/local/bin/python", "isolation": "ISOLATED_NO_SITE_NO_BYTECODE",
                        "native_platform": "linux/amd64"},
        "sqlite": {"python_version": "3.46.1", "sql_version": "3.46.1",
                   "source_id": "2024-08-13 09:16:08 " + "f" * 64,
                   "compile_options_count": 2,
                   "compile_options_sha256": hashlib.sha256(image.canonical(["THREADSAFE=1", "USE_URI"])).hexdigest()},
        "requirements": dict(image.REQUIREMENTS),
    }


def altered(path, value):
    report = fixture_report()
    current = report
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value
    return report


@pytest.fixture(autouse=True)
def no_docker_or_network(monkeypatch):
    original = subprocess.Popen

    def guarded(argv, *args, **kwargs):
        assert type(argv) is list and Path(argv[0]).name != "docker", "real Docker is forbidden in these tests"
        return original(argv, *args, **kwargs)

    def denied(*_args, **_kwargs):
        raise AssertionError("network forbidden in base observation tests")

    monkeypatch.setattr(subprocess, "Popen", guarded)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def test_validator_returns_detached_strict_base_only_expectation():
    original = fixture_report()
    result = image.validate_runtime_base_observation(original, SOURCE, DOCKER_HASH)
    assert result == original and result is not original
    result["interpreter"]["version"][2] = 99
    assert original["interpreter"]["version"] == [3, 14, 0]
    assert result["scope"] == "PINNED_BASE_STDLIB_ONLY"
    assert result["final_runtime"] == "FINAL_RUNTIME_NOT_OBSERVED"
    assert result["requirements"] == {
        "sqlite_equality": "REQUIRED_BEFORE_RESTORE_OR_CLAIM",
        "actual_host_ack": "REQUIRED_BEFORE_SERVE", "mismatch": "HELD_NO_LEARN_NO_RELAXATION",
    }


@pytest.mark.parametrize("path,value", [
    (("schema",), "unknown"), (("state",), "HELD"), (("scope",), "FINAL_HOST"),
    (("final_runtime",), "OBSERVED"), (("repository",), "other/a11oy"),
    (("source_revision",), "b" * 40), (("dockerfile_sha256",), "c" * 64),
    (("base", "reference"), "python:3.14-slim"), (("base", "platform"), "linux/arm64"),
    (("base", "manifest_sha256"), "0" * 64), (("base", "config_sha256"), "0" * 64),
    (("base", "config_sha256"), "D" * 64), (("base", "config_sha256"), True),
    (("execution", "runner"), "LOCAL"), (("execution", "run_id"), True),
    (("execution", "run_id"), 0), (("execution", "run_attempt"), 1001),
    (("interpreter", "version"), [3, 12, 14]), (("interpreter", "version"), [3, 14, True]),
    (("interpreter", "version"), [3, 14, -1]), (("interpreter", "version"), [3, 14, 0, 1]),
    (("interpreter", "implementation"), "pypy"), (("interpreter", "executable"), "/usr/bin/python"),
    (("interpreter", "isolation"), "ISOLATED"), (("interpreter", "native_platform"), "emulated/amd64"),
    (("sqlite", "python_version"), "3.046.1"), (("sqlite", "sql_version"), "3.45.1"),
    (("sqlite", "source_id"), PRIVATE), (("sqlite", "source_id"), "2024-02-31 09:16:08 " + "f" * 64),
    (("sqlite", "source_id"), "2024-08-13 09:16:08 " + "0" * 64),
    (("sqlite", "compile_options_count"), 0), (("sqlite", "compile_options_count"), True),
    (("sqlite", "compile_options_count"), 257), (("sqlite", "compile_options_sha256"), "0" * 64),
    (("requirements", "sqlite_equality"), "OPTIONAL"), (("requirements", "actual_host_ack"), "ALREADY_PASSED"),
    (("requirements", "mismatch"), "LEARN_ACTUAL_VERSION"),
])
def test_validator_rejects_tampered_types_identities_scope_and_expectations(path, value):
    with pytest.raises(image.RuntimeBaseBlocked):
        image.validate_runtime_base_observation(altered(path, value), SOURCE, DOCKER_HASH)


@pytest.mark.parametrize("field", list(fixture_report()))
def test_validator_rejects_missing_fields(field):
    value = fixture_report()
    del value[field]
    with pytest.raises(image.RuntimeBaseBlocked):
        image.validate_runtime_base_observation(value, SOURCE, DOCKER_HASH)


@pytest.mark.parametrize("field", (None, "base", "sqlite", "interpreter", "execution", "requirements"))
def test_validator_rejects_extra_fields_before_serializing_payload(field, monkeypatch):
    value = fixture_report()
    target = value if field is None else value[field]
    target["unknown"] = value
    monkeypatch.setattr(image, "canonical", lambda _value: pytest.fail("must reject structure before encoding"))
    with pytest.raises(image.RuntimeBaseBlocked):
        image.validate_runtime_base_observation(value, SOURCE, DOCKER_HASH)


@pytest.mark.parametrize("source,docker", [("0" * 40, DOCKER_HASH), (SOURCE, "0" * 64),
                                         (True, DOCKER_HASH), (SOURCE, None)])
def test_expected_identity_arguments_are_also_exact_nonzero(source, docker):
    with pytest.raises(image.RuntimeBaseBlocked):
        image.validate_runtime_base_observation(fixture_report(), source, docker)


@pytest.mark.parametrize("suffix", ("alt1", "alt2"))
def test_sqlite_modified_amalgamation_source_id_is_preserved_not_normalized(suffix):
    value = fixture_report()
    value["sqlite"]["source_id"] = "2024-08-13 09:16:08 " + "f" * 60 + suffix
    assert image.validate_runtime_base_observation(value, SOURCE, DOCKER_HASH)["sqlite"]["source_id"].endswith(suffix)
    value["sqlite"]["source_id"] += suffix
    with pytest.raises(image.RuntimeBaseBlocked):
        image.validate_runtime_base_observation(value, SOURCE, DOCKER_HASH)


def registry_fixture():
    config = {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": "sha256:" + CONFIG, "size": 512}
    manifest = {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json", "config": config,
                "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                            "digest": "sha256:" + "1" * 64, "size": 1024}]}
    manifest_bytes = image.canonical(manifest)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    descriptor = {"mediaType": manifest["mediaType"], "digest": "sha256:" + manifest_sha,
                  "size": len(manifest_bytes), "platform": {"os": "linux", "architecture": "amd64"}}
    index = {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json", "manifests": [descriptor]}
    return index, manifest, manifest_bytes, manifest_sha


def metadata_docker(monkeypatch, tmp_path, index, manifest_bytes, *, raw_suffix=b""):
    raw_index = image.canonical(index)
    # Synthetic OCI documents have their own explicitly derived test digest.
    monkeypatch.setattr(image, "BASE_SHA256", hashlib.sha256(raw_index).hexdigest())
    docker = probe.Docker(tmp_path)
    calls = []

    def command(args, deadline, limit=probe.MAX_INSPECTION_BYTES, **_kwargs):
        calls.append(args)
        return (raw_index if len(calls) == 1 else manifest_bytes) + raw_suffix

    monkeypatch.setattr(docker, "command", command)
    return docker, calls


def test_raw_index_child_size_and_config_chain_match_without_reserializing(monkeypatch, tmp_path):
    index, _manifest, raw, digest = registry_fixture()
    docker, calls = metadata_docker(monkeypatch, tmp_path, index, raw)
    assert docker.identities(time.monotonic() + 2) == (digest, CONFIG)
    assert calls[1][-1] == "docker.io/library/python@sha256:" + digest


def test_only_one_terminal_cli_lf_is_tolerated_on_an_exact_hash_match(monkeypatch, tmp_path):
    index, _manifest, raw, digest = registry_fixture()
    docker, _calls = metadata_docker(monkeypatch, tmp_path, index, raw, raw_suffix=b"\n")
    assert docker.identities(time.monotonic() + 2) == (digest, CONFIG)
    with pytest.raises(image.RuntimeBaseBlocked):
        probe._raw(raw + b"\n\n", digest)
    with pytest.raises(image.RuntimeBaseBlocked):
        probe._raw(b" " + raw, digest)


@pytest.mark.parametrize("mutation", ("duplicate", "absent", "variant", "size", "digest", "zero", "alternate_url"))
def test_index_platform_and_child_binding_negative_controls(monkeypatch, tmp_path, mutation):
    index, _manifest, raw, _digest = registry_fixture()
    descriptor = index["manifests"][0]
    if mutation == "duplicate":
        index["manifests"].append(copy.deepcopy(descriptor))
    elif mutation == "absent":
        descriptor["platform"]["architecture"] = "arm64"
    elif mutation == "variant":
        descriptor["platform"]["variant"] = "v3"
    elif mutation == "size":
        descriptor["size"] += 1
    elif mutation == "digest":
        descriptor["digest"] = "sha256:" + MANIFEST
    elif mutation == "zero":
        descriptor["digest"] = "sha256:" + "0" * 64
    else:
        descriptor["urls"] = ["https://unowned.invalid/blob"]
    docker, calls = metadata_docker(monkeypatch, tmp_path, index, raw)
    with pytest.raises(image.RuntimeBaseBlocked):
        docker.identities(time.monotonic() + 2)
    assert all("pull" not in args and "create" not in args for args in calls)


@pytest.mark.parametrize("data", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{', b''])
def test_registry_json_rejects_duplicate_keys_constants_and_malformed_input(data):
    with pytest.raises(image.RuntimeBaseBlocked):
        probe._json(data)


@pytest.mark.parametrize("mutation", ("layer_total", "layer_count", "zero_config", "config_url", "media_type_list"))
def test_manifest_metadata_is_bounded_and_typed(mutation):
    _index, manifest, _raw, _digest = registry_fixture()
    if mutation == "layer_total":
        manifest["layers"] *= 2
        manifest["layers"][0]["size"] = probe.MAX_COMPRESSED_BYTES
    elif mutation == "layer_count":
        manifest["layers"] *= 65
    elif mutation == "zero_config":
        manifest["config"]["digest"] = "sha256:" + "0" * 64
    elif mutation == "config_url":
        manifest["config"]["urls"] = ["https://unowned.invalid/config"]
    else:
        manifest["mediaType"] = []
    with pytest.raises(image.RuntimeBaseBlocked):
        probe._manifest(manifest)


def image_inspection():
    return {"Id": "sha256:" + CONFIG, "Os": "linux", "Architecture": "amd64", "Size": 4096,
            "RepoDigests": ["python@sha256:" + MANIFEST],
            "Config": {"Env": list(ENVIRONMENT), "Labels": None, "Volumes": None}}


@pytest.mark.parametrize("modern", (False, True))
def test_pulled_classic_and_modern_identity_branches_remain_explicit(monkeypatch, tmp_path, modern):
    value = image_inspection()
    if modern:
        value["Id"] = "sha256:" + MANIFEST
        value["Descriptor"] = dict(MANIFEST_DESCRIPTOR)
    docker = probe.Docker(tmp_path)
    docker._selected = {"manifest": MANIFEST, "config": CONFIG, "descriptor": dict(MANIFEST_DESCRIPTOR)}
    monkeypatch.setattr(docker, "command", lambda args, *_args, **_kwargs:
                        b"" if args[:2] == ["image", "pull"] else image.canonical(value))
    result = docker.pull(MANIFEST, CONFIG, time.monotonic() + 2)
    assert result["image_id"] == "sha256:" + (MANIFEST if modern else CONFIG)
    assert result["image_id_kind"] == ("SELECTED_MANIFEST_DIGEST" if modern else "CONFIG_DIGEST")
    assert result["manifest_descriptor"] == MANIFEST_DESCRIPTOR


@pytest.mark.parametrize("mutation", ("missing", "index", "size", "media_type"))
def test_modern_image_requires_verified_child_descriptor(monkeypatch, tmp_path, mutation):
    value = image_inspection()
    value["Id"] = "sha256:" + MANIFEST
    value["Descriptor"] = dict(MANIFEST_DESCRIPTOR)
    if mutation == "missing":
        del value["Descriptor"]
    elif mutation == "index":
        value["Descriptor"]["digest"] = "sha256:" + image.BASE_SHA256
    elif mutation == "size":
        value["Descriptor"]["size"] += 1
    else:
        value["Descriptor"]["mediaType"] = "application/vnd.oci.image.index.v1+json"
    docker = probe.Docker(tmp_path)
    docker._selected = {"manifest": MANIFEST, "config": CONFIG, "descriptor": dict(MANIFEST_DESCRIPTOR)}
    monkeypatch.setattr(docker, "command", lambda args, *_args, **_kwargs:
                        b"" if args[:2] == ["image", "pull"] else image.canonical(value))
    with pytest.raises(image.RuntimeBaseBlocked):
        docker.pull(MANIFEST, CONFIG, time.monotonic() + 2)


def test_unselected_image_never_reaches_pull(monkeypatch, tmp_path):
    docker = probe.Docker(tmp_path)
    monkeypatch.setattr(docker, "command", lambda *_args, **_kwargs: pytest.fail("must not pull"))
    with pytest.raises(probe.ProbeBlocked, match="SELECTION_UNBOUND"):
        docker.pull(MANIFEST, CONFIG, time.monotonic() + 2)


@pytest.mark.parametrize("path,value", [((), None), (("Id",), "sha256:" + "1" * 64),
    (("Architecture",), "arm64"), (("Variant",), "v3"), (("RepoDigests",), []),
    (("Size",), probe.MAX_IMAGE_BYTES + 1), (("Config", "Volumes"), {"/data": {}}),
    (("Config", "Labels"), []), (("Config", "Labels"), {probe.OWNERSHIP_LABEL: "unowned"}),
    (("Config", "Env"), [True])])
def test_pulled_image_must_be_exact_and_cannot_declare_implicit_mounts(monkeypatch, tmp_path, path, value):
    inspection = image_inspection()
    if not path:
        inspection = value
    else:
        current = inspection
        for key in path[:-1]:
            current = current[key]
        current[path[-1]] = value
    docker = probe.Docker(tmp_path)
    docker._selected = {"manifest": MANIFEST, "config": CONFIG, "descriptor": dict(MANIFEST_DESCRIPTOR)}
    calls = []

    def command(args, *_args, **_kwargs):
        calls.append(args)
        return b"" if len(calls) == 1 else image.canonical(inspection)

    monkeypatch.setattr(docker, "command", command)
    with pytest.raises(image.RuntimeBaseBlocked):
        docker.pull(MANIFEST, CONFIG, time.monotonic() + 2)
    assert calls[0] == ["image", "pull", "--platform", "linux/amd64", "--quiet",
                        "docker.io/library/python@sha256:" + MANIFEST]


class FakeDocker:
    """Synthetic daemon: accepted effects and lost client replies are distinct."""
    def __init__(self, directory, *, fault=None, mutate=None, modern=False):
        self.directory = directory
        self.fault = fault
        self.mutate = mutate
        self.created = False
        self.exited = False
        self.calls = []
        self.name = None
        self.nonce = None
        self.removed = False
        self.modern = modern

    def native(self, _deadline):
        pass

    def identities(self, _deadline):
        return MANIFEST, CONFIG

    def pull(self, *_args):
        return {"environment": list(ENVIRONMENT), "labels": {},
                "image_id": "sha256:" + (MANIFEST if self.modern else CONFIG),
                "image_id_kind": "SELECTED_MANIFEST_DIGEST" if self.modern else "CONFIG_DIGEST",
                "manifest_descriptor": dict(MANIFEST_DESCRIPTOR)}

    def named(self, name, _deadline):
        self.calls.append(["named", name])
        if self.fault == "collision" and not self.name:
            return "f" * 64
        return CONTAINER if self.created else None

    def inspect(self, _identifier, _deadline):
        self.calls.append(["inspect", _identifier])
        result = {
            "Id": CONTAINER, "Name": "/" + self.name, "Image": "sha256:" + CONFIG,
            "Path": "/usr/local/bin/python", "Args": list(probe.PROBE_ARGS), "Mounts": [],
            "Config": {"Image": "sha256:" + CONFIG, "User": "65534:65534", "WorkingDir": "/",
                       "Entrypoint": ["/usr/local/bin/python"], "Cmd": list(probe.PROBE_ARGS),
                       "Env": list(ENVIRONMENT), "Labels": {probe.OWNERSHIP_LABEL: self.nonce},
                       "Volumes": None, "Healthcheck": {"Test": ["NONE"]}, "OpenStdin": False, "Tty": False},
            "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False,
                           "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges"],
                           "Memory": 128 * 1024 * 1024, "NanoCpus": 1_000_000_000, "PidsLimit": 16,
                           "IpcMode": "none", "PidMode": "", "PublishAllPorts": False, "AutoRemove": False,
                           "LogConfig": {"Type": "none", "Config": {}},
                           "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0}},
            "State": {"Running": False, "Paused": False, "Restarting": False, "OOMKilled": False,
                      "Dead": False, "Pid": 0, "ExitCode": 0, "Error": "",
                      "Status": "exited" if self.exited else "created"},
        }
        if self.modern:
            result["Image"] = result["Config"]["Image"] = "sha256:" + MANIFEST
            result["ImageManifestDescriptor"] = dict(MANIFEST_DESCRIPTOR, platform={"os": "linux", "architecture": "amd64"})
        if self.fault == "wrong_owner":
            result["Config"]["Labels"][probe.OWNERSHIP_LABEL] = "unowned"
        if self.mutate is not None:
            self.mutate(result)
        return result

    def command(self, args, _deadline, _limit=probe.MAX_INSPECTION_BYTES, **_kwargs):
        self.calls.append(list(args))
        if args[:2] == ["container", "create"]:
            self.name = args[args.index("--name") + 1]
            self.nonce = args[args.index("--label") + 1].split("=", 1)[1]
            if self.fault == "late_create":
                raise probe.ProbeBlocked("RUNTIME_BASE_COMMAND_FAILED")
            self.created = True
            if self.fault == "create_lost":
                raise probe.ProbeBlocked(PRIVATE)
            if self.fault == "malformed_id":
                return b"unexpected container id\n"
            if self.fault == "wrong_id":
                return ("f" * 64 + "\n").encode()
            return (CONTAINER + "\n").encode()
        if args[:2] == ["container", "start"]:
            assert args == ["container", "start", "--attach", CONTAINER]
            self.exited = True
            if self.fault == "start_timeout":
                raise probe.ProbeBlocked("RUNTIME_BASE_DEADLINE_EXHAUSTED")
            report = fixture_report()
            if self.fault == "payload_tamper":
                report["sqlite"]["sql_version"] = "3.45.1"
            return image.canonical({key: report[key] for key in ("interpreter", "sqlite")})
        if args[:2] == ["container", "rm"]:
            assert args == ["container", "rm", "--force", CONTAINER]
            if self.fault != "remove_failed":
                self.created = False
                self.removed = True
            if self.fault in ("remove_lost", "remove_failed"):
                raise probe.ProbeBlocked(PRIVATE)
            return (CONTAINER + "\n").encode()
        if args[:2] == ["container", "ls"]:
            assert "id=" + CONTAINER in args
            return (CONTAINER + "\n").encode() if self.created else b""
        raise AssertionError("unexpected Docker operation")


def engine(monkeypatch, tmp_path, *, fault=None, mutate=None, modern=False):
    instance = FakeDocker(tmp_path, fault=fault, mutate=mutate, modern=modern)
    monkeypatch.setattr(probe, "Docker", lambda directory: instance)
    return instance


def observe(tmp_path):
    return probe.observe_runtime_base(SOURCE, DOCKER_HASH, dict(EXECUTION), temporary_root=tmp_path)


def test_full_synthetic_observation_requires_exact_fixed_container_and_cleanup(monkeypatch, tmp_path):
    daemon = engine(monkeypatch, tmp_path)
    result = observe(tmp_path)
    assert result == fixture_report() and daemon.removed and not daemon.created
    create = next(args for args in daemon.calls if args[:2] == ["container", "create"])
    for flag, expected in (("--platform", "linux/amd64"), ("--network", "none"), ("--user", "65534:65534"),
                           ("--entrypoint", "/usr/local/bin/python"), ("--workdir", "/")):
        assert create[create.index(flag) + 1] == expected
    assert "--pull=never" in create and "--read-only" in create
    assert create[-len(probe.PROBE_ARGS)-1] == "sha256:" + CONFIG
    assert create[-len(probe.PROBE_ARGS):] == ["-I", "-B", "-S", "-c", probe.PROBE_CODE]
    assert all(arg not in create for arg in ("--mount", "--volume", "-v", "--env", "-e", "--env-file"))
    assert not list(tmp_path.iterdir())


def test_modern_target_manifest_identity_has_its_own_exact_container_route(monkeypatch, tmp_path):
    daemon = engine(monkeypatch, tmp_path, modern=True)
    assert observe(tmp_path) == fixture_report() and daemon.removed
    create = next(args for args in daemon.calls if args[:2] == ["container", "create"])
    assert create[-len(probe.PROBE_ARGS)-1] == "sha256:" + MANIFEST


@pytest.mark.parametrize("mutation", ("missing", "index", "size", "platform", "config_id"))
def test_modern_container_requires_full_selected_manifest_witness(monkeypatch, tmp_path, mutation):
    def mutate(document):
        descriptor = document["ImageManifestDescriptor"]
        if mutation == "missing":
            del document["ImageManifestDescriptor"]
        elif mutation == "index":
            descriptor["digest"] = "sha256:" + image.BASE_SHA256
        elif mutation == "size":
            descriptor["size"] += 1
        elif mutation == "platform":
            descriptor["platform"]["architecture"] = "arm64"
        else:
            document["Image"] = "sha256:" + CONFIG

    daemon = engine(monkeypatch, tmp_path, modern=True, mutate=mutate)
    with pytest.raises(image.RuntimeBaseBlocked):
        observe(tmp_path)
    if mutation != "config_id":
        assert daemon.removed
    assert not any(args[:2] == ["container", "start"] for args in daemon.calls)


@pytest.mark.parametrize("fault", ("create_lost", "malformed_id", "wrong_id", "start_timeout", "payload_tamper"))
def test_accepted_effect_lost_reply_or_invalid_evidence_never_becomes_observed(monkeypatch, tmp_path, fault):
    daemon = engine(monkeypatch, tmp_path, fault=fault)
    with pytest.raises(image.RuntimeBaseBlocked):
        observe(tmp_path)
    assert daemon.removed and not daemon.created
    assert sum(args[:2] == ["container", "create"] for args in daemon.calls) == 1


def test_accepted_remove_with_lost_reply_is_resolved_by_exact_absence(monkeypatch, tmp_path):
    daemon = engine(monkeypatch, tmp_path, fault="remove_lost")
    assert observe(tmp_path)["state"] == "OBSERVED"
    assert daemon.removed and any("id=" + CONTAINER in args for args in daemon.calls)


@pytest.mark.parametrize("fault", ("late_create", "wrong_owner", "remove_failed"))
def test_uncertain_cleanup_is_held_and_preserves_exact_cleanup_name(monkeypatch, tmp_path, fault):
    daemon = engine(monkeypatch, tmp_path, fault=fault)
    with pytest.raises(probe.ProbeBlocked, match="RUNTIME_BASE_CLEANUP_UNCONFIRMED") as caught:
        observe(tmp_path)
    assert caught.value.cleanup_name == daemon.name
    if fault == "wrong_owner":
        assert not any(args[:2] == ["container", "rm"] for args in daemon.calls)


def test_existing_unowned_name_is_never_created_started_or_removed(monkeypatch, tmp_path):
    daemon = engine(monkeypatch, tmp_path, fault="collision")
    with pytest.raises(probe.ProbeBlocked, match="NAME_COLLISION"):
        observe(tmp_path)
    assert all(args[0] == "named" for args in daemon.calls)


@pytest.mark.parametrize("path,value", [
    (("Mounts",), [{"Source": "/private"}]), (("Path",), "/bin/sh"),
    (("Args",), ["-c", PRIVATE]), (("Config", "Env"), ENVIRONMENT + ["HF_TOKEN=" + PRIVATE]),
    (("Config", "User"), "0"), (("Config", "Volumes"), {"/data": {}}),
    (("HostConfig", "Privileged"), True), (("HostConfig", "ReadonlyRootfs"), False),
    (("HostConfig", "NetworkMode"), "host"), (("HostConfig", "Binds"), ["/private:/private"]),
    (("HostConfig", "CapAdd"), ["SYS_ADMIN"]), (("HostConfig", "SecurityOpt"), []),
    (("HostConfig", "Memory"), True), (("HostConfig", "PidsLimit"), -1),
    (("HostConfig", "LogConfig"), {"Type": "syslog", "Config": {}}),
    (("HostConfig", "RestartPolicy"), {"Name": "always", "MaximumRetryCount": 0}),
    (("Config", "Tty"), True), (("Config", "OpenStdin"), True),
    (("State", "OOMKilled"), True), (("State", "ExitCode"), 1),
    (("ImageManifestDescriptor",), {"mediaType": "application/vnd.oci.image.manifest.v1+json",
         "digest": "sha256:" + "1" * 64, "size": 1, "platform": {"os": "linux", "architecture": "amd64"}}),
])
def test_container_readback_rejects_injected_inputs_wrong_identity_and_isolation(monkeypatch, tmp_path, path, value):
    def mutate(document):
        target = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    daemon = engine(monkeypatch, tmp_path, mutate=mutate)
    with pytest.raises(image.RuntimeBaseBlocked):
        observe(tmp_path)
    assert daemon.removed
    assert not any(args[:2] == ["container", "start"] for args in daemon.calls)


def test_final_deadline_after_cleanup_is_authoritative(monkeypatch, tmp_path):
    daemon = engine(monkeypatch, tmp_path)
    real_cleanup = probe._cleanup
    clock = [10.0]
    monkeypatch.setattr(probe.time, "monotonic", lambda: clock[0])

    def cleanup(*args, **kwargs):
        real_cleanup(*args, **kwargs)
        clock[0] = 251.0

    monkeypatch.setattr(probe, "_cleanup", cleanup)
    with pytest.raises(probe.ProbeBlocked, match="DEADLINE_EXHAUSTED"):
        probe.observe_runtime_base(SOURCE, DOCKER_HASH, EXECUTION, deadline=250.0, temporary_root=tmp_path)
    assert daemon.removed


def test_final_validator_cannot_return_success_after_authoritative_deadline(monkeypatch, tmp_path):
    daemon = engine(monkeypatch, tmp_path)
    clock = [10.0]
    monkeypatch.setattr(probe.time, "monotonic", lambda: clock[0])
    validate = image.validate_runtime_base_observation
    count = [0]

    def late(*args):
        result = validate(*args)
        count[0] += 1
        if count[0] == 2:
            clock[0] = 251.0
        return result

    monkeypatch.setattr(image, "validate_runtime_base_observation", late)
    with pytest.raises(probe.ProbeBlocked, match="DEADLINE_EXHAUSTED"):
        probe.observe_runtime_base(SOURCE, DOCKER_HASH, EXECUTION, deadline=250.0, temporary_root=tmp_path)
    assert daemon.removed and count[0] == 2


def test_docker_wrapper_strips_credentials_context_proxy_and_uses_private_home(monkeypatch, tmp_path):
    for key in ("HF_TOKEN", "GH_TOKEN", "DOCKER_AUTH_CONFIG", "DOCKER_CONTEXT", "HTTP_PROXY", "PYTHONPATH"):
        monkeypatch.setenv(key, PRIVATE)
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return b"safe"

    monkeypatch.setattr(probe, "_run", run)
    docker = probe.Docker(tmp_path)
    assert docker.command(["version"], time.monotonic() + 2, input_bytes=b"{}") == b"safe"
    argv, args = calls[0]
    assert argv[:6] == ["/usr/bin/docker", "--config", str(tmp_path), "--host", probe.DAEMON, "version"]
    assert args["env"]["HOME"] == args["env"]["DOCKER_CONFIG"] == str(tmp_path)
    assert PRIVATE not in repr(args) and args["input_bytes"] == b"{}"
    assert "DOCKER_CONTEXT" not in args["env"] and "HTTP_PROXY" not in args["env"]


def run_python(code, *args, deadline=None, limit=probe.MAX_METADATA_BYTES, input_bytes=None):
    return probe._run([sys.executable, "-I", "-B", "-c", code, *map(str, args)],
                      deadline=time.monotonic() + 3 if deadline is None else deadline,
                      limit=limit, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, input_bytes=input_bytes)


def test_native_concurrent_stdin_and_both_output_pipes_cannot_deadlock():
    data = b"owned synthetic input" * 10000
    code = "import hashlib,os,sys;os.write(1,b'x'*100000);os.write(2,b'y'*1024);data=sys.stdin.buffer.read();print(hashlib.sha256(data).hexdigest())"
    result = run_python(code, input_bytes=data)
    assert result == b"x" * 100000 + hashlib.sha256(data).hexdigest().encode() + b"\n"


@pytest.mark.parametrize("descriptor", (1, 2))
def test_native_either_output_pipe_is_capped_without_leaking_content(descriptor):
    started = time.monotonic()
    with pytest.raises(probe.ProbeBlocked, match="OUTPUT_BOUND_EXCEEDED") as caught:
        run_python("import os;os.write(" + str(descriptor) + ",b'x'*100000)", limit=1024)
    assert time.monotonic() - started < 2 and PRIVATE not in str(caught.value)


def test_native_stderr_and_exception_text_are_redacted():
    with pytest.raises(probe.ProbeBlocked, match="COMMAND_FAILED") as caught:
        run_python("import sys;sys.stderr.write(sys.argv[1]);sys.exit(2)", PRIVATE)
    assert PRIVATE not in str(caught.value)


def test_native_late_success_is_killed_and_never_returned():
    started = time.monotonic()
    with pytest.raises(probe.ProbeBlocked, match="DEADLINE_EXHAUSTED"):
        run_python("import time;time.sleep(2);print('late success')", deadline=started + 0.1)
    assert time.monotonic() - started < 1


def test_native_deadline_is_rechecked_after_process_cleanup(monkeypatch):
    clock = [10.0]
    original = subprocess.Popen

    def launch(*args, **kwargs):
        process = original(*args, **kwargs)
        wait = process.wait

        def cleanup_wait(*wait_args, **wait_kwargs):
            result = wait(*wait_args, **wait_kwargs)
            clock[0] = 31.0
            return result

        process.wait = cleanup_wait
        return process

    monkeypatch.setattr(subprocess, "Popen", launch)
    monkeypatch.setattr(probe.time, "monotonic", lambda: clock[0])
    with pytest.raises(probe.ProbeBlocked, match="DEADLINE_EXHAUSTED"):
        run_python("print('complete before cleanup')", deadline=30.0)


def _not_running(identifier):
    path = Path("/proc") / str(identifier) / "stat"
    try:
        return path.read_text().rsplit(")", 1)[1].split()[0] == "Z"
    except FileNotFoundError:
        return True


@pytest.mark.parametrize("close_pipes", (False, True))
def test_native_descendant_cleanup_after_parent_exit(tmp_path, close_pipes):
    child_path = tmp_path / "owned-child.pid"
    code = '''import os,signal,sys,time
child = os.fork()
if child == 0:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    with open(sys.argv[1], "w") as stream:
        stream.write(str(os.getpid()))
    if sys.argv[2] == "yes":
        os.close(1); os.close(2)
    time.sleep(20)
else:
    while not os.path.exists(sys.argv[1]):
        time.sleep(0.005)
'''
    if close_pipes:
        assert run_python(code, child_path, "yes", deadline=time.monotonic() + 1) == b""
    else:
        with pytest.raises(probe.ProbeBlocked, match="DEADLINE_EXHAUSTED"):
            run_python(code, child_path, "no", deadline=time.monotonic() + 0.3)
    child = int(child_path.read_text())
    end = time.monotonic() + 1
    while not _not_running(child) and time.monotonic() < end:
        time.sleep(0.01)
    assert _not_running(child)


@pytest.mark.parametrize("input_bytes", ("text", b"x" * (probe.MAX_INPUT_BYTES + 1)))
def test_invalid_or_oversized_stdin_never_starts_a_process(monkeypatch, input_bytes):
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("must not launch"))
    with pytest.raises(probe.ProbeBlocked):
        run_python("pass", input_bytes=input_bytes)


@pytest.mark.parametrize("deadline", (float("nan"), float("inf"), 0, True))
def test_invalid_deadline_never_starts_a_process(monkeypatch, deadline):
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("must not launch"))
    with pytest.raises(probe.ProbeBlocked):
        run_python("pass", deadline=deadline)


def test_current_native_interpreter_cannot_be_relabelled_as_the_base():
    if sys.version_info[:2] == (3, 14) and sys.executable == image.EXECUTABLE:
        # Still not the digest-bound Docker observation; use a conflicting flag.
        args = [sys.executable, "-I", "-B", "-c", probe.PROBE_CODE]
    else:
        args = [sys.executable, "-I", "-B", "-S", "-c", probe.PROBE_CODE]
    with pytest.raises(probe.ProbeBlocked, match="COMMAND_FAILED"):
        probe._run(args, deadline=time.monotonic() + 2, limit=4096, env={"PATH": "/usr/bin:/bin"})


def context_environment():
    return {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": image.REPOSITORY,
            "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": SOURCE,
            "GITHUB_WORKFLOW_REF": probe.WORKFLOW_REF, "GITHUB_EVENT_NAME": "push",
            "GITHUB_RUN_ID": "42", "GITHUB_RUN_ATTEMPT": "1"}


def context_fixture(monkeypatch, tmp_path, *, docker=None, git_docker=None):
    data = ("FROM python:3.14-slim@sha256:" + image.BASE_SHA256 + " AS runtime\n\nWORKDIR /app\n").encode()
    if docker is not None:
        data = docker
    (tmp_path / "Dockerfile").write_bytes(data)
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return (SOURCE + "\n").encode() if argv[-2:] == ["rev-parse", "HEAD"] else (data if git_docker is None else git_docker)

    monkeypatch.setattr(probe, "_run", run)
    return data, calls


def test_canonical_context_binds_checked_out_bytes_without_git_lazy_fetch(monkeypatch, tmp_path):
    data, calls = context_fixture(monkeypatch, tmp_path)
    digest, execution = probe.canonical_context(SOURCE, environment=context_environment(), root=tmp_path,
                                                deadline=time.monotonic() + 2)
    assert digest == hashlib.sha256(data).hexdigest() and execution == EXECUTION
    assert all(call[1]["env"]["GIT_NO_LAZY_FETCH"] == "1" and call[1]["env"]["GIT_ALLOW_PROTOCOL"] == "" for call in calls)


@pytest.mark.parametrize("key,value", [("GITHUB_REF", "refs/pull/1/merge"), ("GITHUB_REPOSITORY", "other/a11oy"),
    ("GITHUB_SHA", "b" * 40), ("GITHUB_ACTIONS", "false"), ("GITHUB_WORKFLOW_REF", "other/workflow@main"),
    ("GITHUB_EVENT_NAME", "pull_request"), ("GITHUB_RUN_ID", "042"), ("GITHUB_RUN_ATTEMPT", "1001")])
def test_noncanonical_context_does_not_reach_git_or_docker(monkeypatch, tmp_path, key, value):
    _data, calls = context_fixture(monkeypatch, tmp_path)
    environment = context_environment()
    environment[key] = value
    with pytest.raises(image.RuntimeBaseBlocked):
        probe.canonical_context(SOURCE, environment=environment, root=tmp_path, deadline=time.monotonic() + 2)
    assert calls == []


@pytest.mark.parametrize("kind", ("changed", "mutable", "duplicate"))
def test_docker_source_change_or_unqualified_runtime_base_is_held(monkeypatch, tmp_path, kind):
    if kind == "changed":
        context_fixture(monkeypatch, tmp_path, git_docker=b"different immutable source")
    elif kind == "mutable":
        context_fixture(monkeypatch, tmp_path, docker=b"FROM python:3.14-slim AS runtime\n")
    else:
        data = ("FROM python:3.14-slim@sha256:" + image.BASE_SHA256 + " AS runtime\n") * 2
        context_fixture(monkeypatch, tmp_path, docker=data.encode())
    with pytest.raises(image.RuntimeBaseBlocked):
        probe.canonical_context(SOURCE, environment=context_environment(), root=tmp_path, deadline=time.monotonic() + 2)


def test_actual_source_dockerfile_uses_the_qualified_final_runtime_declaration():
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    probe._require_runtime_base(dockerfile.read_text())


@pytest.mark.parametrize("suffix", ("FROM python:3.12 AS final\n", "RUN echo \" <<'END'\"\n",
                                    "RUN python3 <<'END'\nunterminated\n", "# escape=`\n"))
def test_later_stages_or_ambiguous_heredoc_syntax_cannot_hide_a_different_runtime(suffix):
    text = "FROM python:3.14-slim@sha256:" + image.BASE_SHA256 + " AS runtime\n" + suffix
    with pytest.raises(probe.ProbeBlocked):
        probe._require_runtime_base(text)


def test_literal_runtime_from_inside_heredoc_cannot_qualify_the_actual_base():
    text = ("FROM python:3.12-slim AS \\\n runtime\nRUN <<'END'\ncat <<'TEXT'\n"
            "FROM python:3.14-slim@sha256:" + image.BASE_SHA256 + " AS runtime\nTEXT\nEND\n")
    with pytest.raises(probe.ProbeBlocked):
        probe._require_runtime_base(text)


def test_simple_python_heredoc_data_cannot_add_or_replace_from_declarations():
    text = ("FROM python:3.14-slim AS builder\nRUN python3 <<'DATA'\nvalue = '''\n"
            "FROM python:3.12 AS runtime\n'''\nDATA\nFROM python:3.14-slim@sha256:"
            + image.BASE_SHA256 + " AS runtime\n")
    probe._require_runtime_base(text)


@pytest.mark.parametrize("kind", ("fifo", "symlink", "hardlink", "directory", "oversize"))
def test_dockerfile_reader_rejects_nonregular_aliases_and_bounds_without_blocking(tmp_path, kind):
    path = tmp_path / "Dockerfile"
    if kind == "fifo":
        os.mkfifo(path)
    elif kind == "symlink":
        (tmp_path / "original").write_text("source")
        path.symlink_to(tmp_path / "original")
    elif kind == "hardlink":
        (tmp_path / "original").write_text("source")
        os.link(tmp_path / "original", path)
    elif kind == "directory":
        path.mkdir()
    else:
        path.write_bytes(b"x" * (probe.MAX_DOCKERFILE_BYTES + 1))
    started = time.monotonic()
    with pytest.raises(image.RuntimeBaseBlocked):
        probe._read_dockerfile(path)
    assert time.monotonic() - started < 0.5


def test_cli_failure_is_safe_fixed_metadata_and_not_an_admission(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(probe, "canonical_context", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(PRIVATE)))
    output = tmp_path / "gdw-runtime-base-observation.json"
    assert probe.main(["--source-sha", SOURCE, "--output", str(output)]) == 2
    raw = output.read_bytes()
    assert PRIVATE.encode() not in raw and PRIVATE not in capsys.readouterr().out
    assert json.loads(raw)["state"] == "HELD"
    with pytest.raises(image.RuntimeBaseBlocked):
        image.validate_runtime_base_observation(json.loads(raw), SOURCE, DOCKER_HASH)


def test_cli_does_not_overwrite_or_follow_existing_output(monkeypatch, tmp_path):
    output = tmp_path / "gdw-runtime-base-observation.json"
    original = tmp_path / "original"
    original.write_bytes(b"owned original bytes")
    output.symlink_to(original)
    with pytest.raises(probe.ProbeBlocked):
        probe._write_output(output, fixture_report())
    assert original.read_bytes() == b"owned original bytes"


def test_cli_success_serializes_the_exact_detached_observation(monkeypatch, tmp_path):
    monkeypatch.setattr(probe, "canonical_context", lambda *_args, **_kwargs: (DOCKER_HASH, dict(EXECUTION)))
    monkeypatch.setattr(probe, "observe_runtime_base", lambda *_args, **_kwargs: fixture_report())
    output = tmp_path / "gdw-runtime-base-observation.json"
    assert probe.main(["--source-sha", SOURCE, "--output", str(output)]) == 0
    assert output.read_bytes() == image.canonical(fixture_report())


def test_late_output_fsync_cannot_leave_an_observed_artifact(monkeypatch, tmp_path):
    clock = [10.0]
    fsync = os.fsync

    def late(descriptor):
        fsync(descriptor)
        clock[0] = 21.0

    monkeypatch.setattr(probe.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(probe.os, "fsync", late)
    output = tmp_path / "gdw-runtime-base-observation.json"
    with pytest.raises(probe.ProbeBlocked, match="OUTPUT_UNAVAILABLE"):
        probe._write_output(output, fixture_report(), deadline=20.0)
    assert not output.exists()


def test_cli_final_deadline_replaces_only_its_owned_observation_with_held(monkeypatch, tmp_path):
    clock = [10.0]
    monkeypatch.setattr(probe.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(probe, "canonical_context", lambda *_args, **_kwargs: (DOCKER_HASH, dict(EXECUTION)))
    monkeypatch.setattr(probe, "observe_runtime_base", lambda *_args, **_kwargs: fixture_report())
    write = probe._write_output

    def late(*args, **kwargs):
        result = write(*args, **kwargs)
        clock[0] = 251.0
        return result

    monkeypatch.setattr(probe, "_write_output", late)
    output = tmp_path / "gdw-runtime-base-observation.json"
    assert probe.main(["--source-sha", SOURCE, "--output", str(output)]) == 2
    assert json.loads(output.read_bytes())["state"] == "HELD"


def test_cli_argument_errors_do_not_echo_arbitrary_input(capsys):
    assert probe.main(["--unexpected", PRIVATE]) == 2
    captured = capsys.readouterr()
    assert PRIVATE not in captured.out + captured.err


def test_command_count_is_bounded_before_spawning(monkeypatch, tmp_path):
    docker = probe.Docker(tmp_path)
    docker.commands = probe.MAX_COMMANDS
    monkeypatch.setattr(probe, "_run", lambda *_args, **_kwargs: pytest.fail("must not spawn"))
    with pytest.raises(probe.ProbeBlocked, match="COMMAND_BOUND_EXCEEDED"):
        docker.command(["version"], time.monotonic() + 2)
