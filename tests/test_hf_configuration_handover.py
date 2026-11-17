#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Publication waits for the configuration restart, never the old HTTP process."""

import copy
from email.message import Message
import importlib.util
import io
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/await_hf_configuration_handover.py"
SPEC = importlib.util.spec_from_file_location("configuration_handover", SCRIPT)
barrier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(barrier)
SOURCE = "a" * 40
OLD_BOOT = "boot_" + "1" * 32
NEW_BOOT = "boot_" + "2" * 32


def runtime(*, epoch=277, boot=OLD_BOOT, source=SOURCE, claim="CLEAN"):
    kinds = {"gdw": "sqlite", "series_a": "sqlite", "khipu": "sqlite",
             "khipu_council": "sqlite", "unay": "sqlite",
             "khipu_lmdb": "lmdb", "khipu_repl": "lmdb"}
    return [
        {"build": {"revision": source}},
        {"schema": "szl.series-a-status/v1", "source_revision": source,
         "runtime_boot_id": boot},
        {"schema": "szl.a11oy-storage-status/v2", "mode": "FENCED", "role": "WRITER",
         "writable": True, "unfenced": False, "alert": False, "epoch": epoch,
         "claim": claim, "lease": {"state": "ACTIVE", "sequence": 22035,
                                    "heartbeat_age_s": 3.0},
         "pending_publish": [], "last_error": None, "active_errors": {},
         "stores": {name: {"kind": kind, "health": "OK", "blocked_code": None,
                           "last_error_code": None, "snapshot_failures": 0,
                           "integrity": "lmdb_read" if kind == "lmdb" else "quick_check",
                           "sha16": "a" * 16, "last_snapshot_age_s": 20.0,
                           "unsnapshotted_change_age_s": None}
                    for name, kind in kinds.items()}},
    ]


class Clock:
    def __init__(self):
        self.now, self.sleeps = 0.0, []

    def __call__(self):
        return self.now

    def wall(self):
        return 1000 + self.now

    def sleep(self, duration):
        self.sleeps.append(duration)
        self.now += duration


class Reader:
    def __init__(self, observations, *, bracketed=True):
        self.frames = [frame for value in observations for frame in (value, value)] \
            if bracketed else observations
        self.calls = []

    def __call__(self, path, deadline):
        index = len(self.calls)
        assert path == barrier.PATHS[index % 3]
        self.calls.append((path, deadline))
        frame = self.frames[min(index // 3, len(self.frames) - 1)]
        return copy.deepcopy(frame[index % 3])


def baseline(*, claim="CLEAN"):
    clock = Clock()
    return barrier.capture(Reader([runtime(claim=claim)]), clock=clock, wall_clock=clock.wall)


def reports(*, wrote=True):
    return [{"schema": "szl.hf-series-a-runtime-config/v1", "repo_id": barrier.SPACE,
             "credential_authority_state": "VERIFIED",
             "converged": True, "variables_changed": ["A11OY_STATE_PERIODIC_SECONDS"] if wrote else [],
             "volume_changed": False},
            {"schema": "szl.hf-gdw-runtime-config/v1", "repo_id": barrier.SPACE,
             "credential_authority_state": "VERIFIED",
             "converged": True, "variables_changed": []}]


def wait(reader, *, initial=None, configuration=None, timeout=60, clock=None):
    clock = clock or Clock()
    return barrier.await_handover(reader, baseline() if initial is None else initial,
                                 reports() if configuration is None else configuration,
                                 clock=clock, wall_clock=clock.wall, sleep=clock.sleep, timeout=timeout)


def test_capture_records_existing_unclean_claim_without_reclassifying_it():
    observed = baseline(claim="UNCLEAN_HANDOVER")
    assert observed["storage_claim"] == "UNCLEAN_HANDOVER"
    assert observed["storage_epoch"] == 277 and observed["runtime_boot_id"] == OLD_BOOT
    assert observed["provider_writes_performed"] is False
    assert observed["signature_status"] == "UNSIGNED"


@pytest.mark.parametrize("role,lease_state", [("RELEASED", "RELEASED"),
                                               ("HANDING_OVER", "HANDOVER_REQUESTED")])
def test_released_or_handing_over_baseline_is_truthful_and_no_change_does_not_wait(role, lease_state):
    released = runtime()
    released[2].update(role=role, writable=False)
    released[2]["lease"].update(state=lease_state, heartbeat_age_s=240)
    released[2]["stores"]["gdw"]["last_snapshot_age_s"] = 1800
    clock = Clock()
    initial = barrier.capture(Reader([released]), clock=clock, wall_clock=clock.wall)
    result = wait(lambda *_args: pytest.fail("no-change must not poll"),
                  initial=initial, configuration=reports(wrote=False), clock=clock)
    assert result["state"] == "NOT_REQUIRED" and result["waited"] is False
    assert result["baseline"]["storage_role"] == role
    assert result["baseline"]["storage_lease_state"] == lease_state
    assert result["baseline"]["storage_writable"] is False


def test_stale_baseline_does_not_prevent_configuration_repair_but_successor_must_be_healthy():
    stale = runtime(claim="UNCLEAN_HANDOVER")
    stale[2].update(alert=True, active_errors={"snapshot:gdw": {"code": "FAILED"}})
    stale[2]["lease"]["heartbeat_age_s"] = 180
    stale[2]["stores"]["gdw"]["last_snapshot_age_s"] = 1800
    clock = Clock()
    initial = barrier.capture(Reader([stale]), clock=clock, wall_clock=clock.wall)
    result = wait(Reader([runtime(epoch=278, boot=NEW_BOOT)]), initial=initial, clock=clock)
    assert result["state"] == "CONFIGURATION_HANDOVER_OBSERVED"
    assert result["baseline"]["storage_claim"] == "UNCLEAN_HANDOVER"
    assert result["observation"]["storage_claim"] == "CLEAN"


@pytest.mark.parametrize("old_state", ["RELEASED", "ACTIVE"])
def test_old_277_process_cannot_satisfy_barrier_even_when_source_still_serves(old_state):
    old = runtime()
    if old_state == "RELEASED":
        old[2].update(role="RELEASED", writable=False)
        old[2]["lease"]["state"] = "RELEASED"
    reader, clock = Reader([old]), Clock()
    initial = barrier.capture(Reader([old]), clock=clock, wall_clock=clock.wall)
    with pytest.raises(barrier.HandoverBlocked, match="CONFIGURATION_HANDOVER_NOT_OBSERVED"):
        wait(reader, initial=initial, clock=clock, timeout=30)
    assert clock.now == 30
    assert reader.calls and all(path in barrier.PATHS for path, _deadline in reader.calls)


def test_new_clean_278_writer_requires_three_stable_bracketed_observations():
    reader, clock = Reader([runtime(epoch=278, boot=NEW_BOOT)]), Clock()
    result = wait(reader, clock=clock)
    assert result["state"] == "CONFIGURATION_HANDOVER_OBSERVED"
    assert result["polls"] == 3 and len(reader.calls) == 18
    assert clock.sleeps == [10, 10]
    assert result["observation"]["storage_epoch"] == 278
    assert result["observation"]["runtime_boot_id"] == NEW_BOOT
    assert result["provider_writes_performed"] is False and result["publication_performed"] is False


@pytest.mark.parametrize("change", [
    {"claim": "UNCLEAN_HANDOVER"}, {"claim": "FIRST_BOOT"},
    {"source": "b" * 40}, {"boot": OLD_BOOT}, {"epoch": 277}, {"epoch": 276},
])
def test_new_process_must_be_clean_later_and_on_the_prepublication_source(change):
    arguments = {"epoch": 278, "boot": NEW_BOOT, **change}
    with pytest.raises(barrier.HandoverBlocked, match="CONFIGURATION_HANDOVER_NOT_OBSERVED"):
        wait(Reader([runtime(**arguments)]), timeout=1)


@pytest.mark.parametrize("mutation", [
    lambda state: state.update(mode="SNAPSHOT_ONLY_UNFENCED"),
    lambda state: state.update(unfenced=True),
    lambda state: state.update(writable=False),
    lambda state: state.update(alert=True),
    lambda state: state.update(active_errors={"snapshot:gdw": {"code": "FAILED"}}),
    lambda state: state.pop("active_errors"),
    lambda state: state.update(last_error={"code": "FAILED"}),
    lambda state: state.update(pending_publish=["gdw"]),
    lambda state: state["lease"].update(heartbeat_age_s=121),
    lambda state: state["stores"].pop("gdw"),
    lambda state: state["stores"]["gdw"].update(snapshot_failures=1),
    lambda state: state["stores"]["gdw"].update(last_snapshot_age_s=901),
])
def test_canonical_storage_invariants_remain_required(mutation):
    current = runtime(epoch=278, boot=NEW_BOOT)
    mutation(current[2])
    with pytest.raises(barrier.HandoverBlocked):
        wait(Reader([current]), timeout=1)


def test_epoch_or_process_bounce_resets_stable_streak():
    second = runtime(epoch=278, boot=NEW_BOOT)
    third = runtime(epoch=279, boot="boot_" + "3" * 32)
    reader = Reader([second, second, third, third, third])
    result = wait(reader)
    assert result["polls"] == 5 and result["observation"]["storage_epoch"] == 279


def test_identity_change_within_bracket_is_not_a_valid_observation():
    reader = Reader([runtime(), runtime(epoch=278, boot=NEW_BOOT)], bracketed=False)
    with pytest.raises(barrier.HandoverBlocked, match="RUNTIME_IDENTITY_CHANGED_DURING_READ"):
        barrier.observe(reader, 30)


def test_no_provider_change_performs_no_poll_or_sleep():
    clock = Clock()
    def forbidden_read(*_args):
        pytest.fail("no-change convergence must not wait for another process")
    result = wait(forbidden_read, configuration=reports(wrote=False), clock=clock)
    assert result["state"] == "NOT_REQUIRED" and result["waited"] is False
    assert result["polls"] == 0 and clock.sleeps == []


@pytest.mark.parametrize("mutation", [
    lambda values: values.pop(),
    lambda values: values.append(copy.deepcopy(values[0])),
    lambda values: values.__setitem__(1, copy.deepcopy(values[0])),
    lambda values: values[0].update(converged=False),
    lambda values: values[0].update(credential_authority_state="UNKNOWN"),
    lambda values: values[0].update(repo_id="SZLHOLDINGS/other"),
    lambda values: values[0].pop("variables_changed"),
    lambda values: values[0].update(variables_changed=""),
    lambda values: values[0].update(variables_changed=["PRIVATE\nDETAIL"]),
    lambda values: values[0].pop("volume_changed"),
    lambda values: values[0].update(volume_changed="false"),
])
def test_missing_or_malformed_reports_cannot_become_no_change_success(mutation):
    values = reports(wrote=False)
    mutation(values)
    with pytest.raises(barrier.HandoverBlocked, match="CONFIGURATION_REPORTS_INVALID"):
        wait(lambda *_args: pytest.fail("invalid reports must fail before GET"), configuration=values)


@pytest.mark.parametrize("mutation", [
    lambda value: value.pop("runtime_boot_id"),
    lambda value: value.update(runtime_boot_id="private-provider-detail"),
    lambda value: value.update(storage_epoch=True),
    lambda value: value.update(source_revision="a" * 39),
    lambda value: value.update(observed_at_unix=99),
    lambda value: value.update(observed_at_unix=1001),
    lambda value: value.update(origin="https://other.example"),
])
def test_invalid_baseline_holds_before_readback(mutation):
    value = baseline()
    mutation(value)
    with pytest.raises(barrier.HandoverBlocked, match="BASELINE_"):
        wait(lambda *_args: pytest.fail("invalid baseline must fail before GET"), initial=value)


class Response:
    def __init__(self, body=b'{"ok":true}', *, status=200, url=None, content_type="application/json"):
        self.stream = io.BytesIO(body)
        self.status = status
        self.url = url or barrier.ORIGIN + barrier.PATHS[0]
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.stream.close()

    def geturl(self):
        return self.url

    def read1(self, size):
        return self.stream.read1(size)


class Opener:
    def __init__(self, response):
        self.response, self.calls = response, []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_transport_has_only_fixed_origin_gets_and_no_credentials_or_redirects():
    opener = Opener(Response())
    transport = barrier.ReadOnlyTransport(barrier.ORIGIN, opener=opener, clock=lambda: 0)
    assert transport(barrier.PATHS[0], 30) == {"ok": True}
    request, timeout = opener.calls[0]
    assert request.method == "GET" and request.full_url == barrier.ORIGIN + barrier.PATHS[0]
    assert request.data is None and timeout == 5
    assert set(dict(request.header_items())) == {"Accept", "Accept-encoding", "Cache-control"}
    assert barrier._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example") is None
    with pytest.raises(barrier.HandoverBlocked, match="FIXED_READ_ROUTE_REQUIRED"):
        transport("https://other.example/", 30)
    assert len(opener.calls) == 1


@pytest.mark.parametrize("response", [
    Response(status=302), Response(url="https://other.example"), Response(content_type="text/html"),
    Response(body=b'x' * (barrier.MAX_BYTES + 1)), Response(body=b'{"x":1,"x":2}'),
    Response(body=b'{"x":NaN}'), OSError("private-provider-detail"),
])
def test_transport_refuses_unbounded_malformed_or_redirected_readback(response):
    transport = barrier.ReadOnlyTransport(barrier.ORIGIN, opener=Opener(response), clock=lambda: 0)
    with pytest.raises(barrier.HandoverBlocked) as error:
        transport(barrier.PATHS[0], 30)
    assert "private-provider-detail" not in str(error.value)


def test_body_stream_cannot_extend_the_overall_observation_deadline():
    clock = Clock()
    response = Response()
    original = response.read1
    def slow_read(size):
        clock.now += 6
        return original(size)
    response.read1 = slow_read
    transport = barrier.ReadOnlyTransport(barrier.ORIGIN, opener=Opener(response), clock=clock)
    with pytest.raises(barrier.HandoverBlocked, match="READ_DEADLINE_EXHAUSTED"):
        transport(barrier.PATHS[0], 5)


def test_cli_missing_baseline_returns_fixed_failed_receipt(tmp_path, capsys):
    output = tmp_path / "result.json"
    assert barrier.main(["wait", "--origin", barrier.ORIGIN, "--baseline",
                         str(tmp_path / "private-provider-detail"), "--output", str(output)]) == 1
    result = json.loads(output.read_text())
    assert result["state"] == "BLOCKED" and result["provider_writes_performed"] is False
    assert result["diagnostic_code"] == "LOCAL_OBSERVATION_DOCUMENT_INVALID"
    assert "private-provider-detail" not in capsys.readouterr().out


def test_cli_extra_baseline_field_is_rejected_without_echoing_it(tmp_path, capsys):
    initial = baseline()
    initial["private_extra"] = "private-baseline-sentinel"
    source, output = tmp_path / "baseline.json", tmp_path / "result.json"
    source.write_text(json.dumps(initial))
    assert barrier.main(["wait", "--origin", barrier.ORIGIN, "--baseline", str(source),
                         "--output", str(output)]) == 1
    rendered = output.read_text() + capsys.readouterr().out
    assert "private-baseline-sentinel" not in rendered and "private_extra" not in rendered
    assert json.loads(output.read_text())["diagnostic_code"] == "BASELINE_INVALID"


def test_workflow_barrier_precedes_convergence_and_fresh_publication_ownership():
    workflow = yaml.safe_load((ROOT / ".github/workflows/hf-sync.yml").read_text())
    steps = workflow["jobs"]["preflight"]["steps"]
    capture_index = next(i for i, step in enumerate(steps)
                         if "await_hf_configuration_handover.py capture" in step.get("run", ""))
    configure_index = next(i for i, step in enumerate(steps) if step.get("id") == "converge")
    owner_index = next(i for i, step in enumerate(steps) if step.get("id") == "owner")
    assert capture_index < configure_index < owner_index
    code = steps[configure_index]["run"]
    assert code.index("configure_hf_series_a_runtime.py") < code.index("configure_hf_gdw_runtime.py")
    assert code.index("configure_hf_gdw_runtime.py") < code.index("await_hf_configuration_handover.py wait")
    assert code.index("await_hf_configuration_handover.py wait") < code.index("echo 'converged=true'")
    assert "set -euo pipefail" in code and "continue-on-error" not in steps[configure_index]
    assert "steps.window.outputs.open == 'true'" in steps[capture_index]["if"]
    assert "steps.runtime.outputs.converge == 'true'" in steps[capture_index]["if"]
    assert "hf_exact_main_ownership.py" in steps[owner_index]["run"]
    assert workflow["jobs"]["deploy"]["needs"] == ["source-admission", "preflight"]
    assert "needs.preflight.result == 'success'" in workflow["jobs"]["deploy"]["if"]
    post = workflow["jobs"]["runtime-config"]["steps"]
    assert any("await_hf_runtime_serving.py" in step.get("run", "") for step in post)


def test_existing_ci_executes_the_new_tests_with_its_control_client_dependencies():
    workflow = (ROOT / ".github/workflows/series-a-live-control-plane.yml").read_text()
    assert ".github/requirements/ci-execution.txt" in workflow
    assert "python -B -m pytest -q -p no:cacheprovider tests/test_hf_configuration_handover.py" in workflow
