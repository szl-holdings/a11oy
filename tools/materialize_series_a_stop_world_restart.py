from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "scripts" / "prove_hf_series_a_restart.py"
TEST = ROOT / "scripts" / "test_prove_hf_series_a_restart.py"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise SystemExit(f"{label} target drifted: {old[:160]!r}")
    return source.replace(old, new, 1)


def patch_proof() -> None:
    source = PROOF.read_text(encoding="utf-8")
    anchor = """def _sleep_with_deadline(deadline: float, seconds: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RestartProofError("restart proof deadline exhausted")
    time.sleep(min(max(0.0, seconds), remaining))
    _check_deadline(deadline)
"""
    helpers = anchor + """


def _runtime_stage(value: Any) -> str:
    """Normalize huggingface_hub SpaceRuntime and SpaceInfo stage shapes."""

    candidate = value
    if isinstance(candidate, Mapping):
        candidate = candidate.get("runtime", candidate)
        stage = candidate.get("stage") if isinstance(candidate, Mapping) else None
    else:
        nested = getattr(candidate, "runtime", None)
        candidate = nested if nested is not None else candidate
        stage = getattr(candidate, "stage", None)
    stage = getattr(stage, "value", stage)
    return str(stage or "UNKNOWN").strip().upper()


def stop_the_world_restart(
    api: HfApi,
    *,
    repo_id: str,
    deadline: float,
    attempts: int,
    retry_seconds: int,
    phase: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pause to zero writers, confirm PAUSED, then start one replacement runtime.

    A direct restart may overlap a retiring and replacement replica. That is not
    admissible for a single-writer SQLite receipt chain on a mounted provider
    filesystem. This transition proves the old runtime is PAUSED before any new
    runtime is requested. If the restart response is lost, provider stage is
    inspected before a retry so an accepted request is never duplicated blindly.
    """

    if attempts < 1 or retry_seconds < 0:
        raise RestartProofError("stop-the-world polling bounds are invalid")
    record: dict[str, Any] = {
        "phase": phase,
        "pause_requested": False,
        "pause_confirmed": False,
        "pause_observations": [],
        "restart_requested": False,
        "restart_response_lost": False,
        "restart_retry_requested": False,
        "writer_overlap_prevented": False,
    }
    if evidence is not None:
        evidence[f"{phase}_restart_control"] = record

    _check_deadline(deadline)
    try:
        paused = api.pause_space(repo_id=repo_id)
    except Exception as exc:  # noqa: BLE001 - provider error is receipt evidence
        record["pause_error"] = {
            "type": type(exc).__name__,
            "message": str(exc)[:180],
        }
        raise RestartProofError(
            f"{phase} pause request failed: {type(exc).__name__}: {str(exc)[:180]}"
        ) from exc
    record["pause_requested"] = True
    pause_stage = _runtime_stage(paused)
    record["pause_response_stage"] = pause_stage
    confirmed = pause_stage == "PAUSED"
    last_stage = pause_stage

    for attempt in range(max(1, attempts)):
        if confirmed:
            break
        _check_deadline(deadline)
        try:
            runtime = api.get_space_runtime(repo_id=repo_id)
            last_stage = _runtime_stage(runtime)
            record["pause_observations"].append(
                {"attempt": attempt + 1, "stage": last_stage}
            )
            confirmed = last_stage == "PAUSED"
        except Exception as exc:  # noqa: BLE001 - bounded provider polling
            record["pause_observations"].append(
                {
                    "attempt": attempt + 1,
                    "stage": "UNAVAILABLE",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:180],
                }
            )
        if not confirmed and attempt + 1 < max(1, attempts):
            _sleep_with_deadline(deadline, retry_seconds)

    if not confirmed:
        raise RestartProofError(
            f"{phase} runtime did not reach PAUSED before replacement request; "
            f"last stage={last_stage}"
        )
    record["pause_confirmed"] = True
    record["confirmed_pause_stage"] = "PAUSED"
    _check_deadline(deadline)

    try:
        restarted = api.restart_space(repo_id=repo_id, factory_reboot=False)
        record["restart_requested"] = True
        restart_stage = _runtime_stage(restarted)
    except Exception as exc:  # noqa: BLE001 - recover availability without overlap
        record["restart_response_lost"] = True
        record["restart_error"] = {
            "type": type(exc).__name__,
            "message": str(exc)[:180],
        }
        _check_deadline(deadline)
        try:
            runtime = api.get_space_runtime(repo_id=repo_id)
            observed_stage = _runtime_stage(runtime)
        except Exception as runtime_exc:  # noqa: BLE001
            record["restart_failure_runtime_error"] = {
                "type": type(runtime_exc).__name__,
                "message": str(runtime_exc)[:180],
            }
            raise RestartProofError(
                f"{phase} restart response was lost and runtime state is unavailable"
            ) from runtime_exc
        record["restart_failure_runtime_stage"] = observed_stage
        if observed_stage == "PAUSED":
            record["restart_retry_requested"] = True
            try:
                restarted = api.restart_space(
                    repo_id=repo_id,
                    factory_reboot=False,
                )
            except Exception as retry_exc:  # noqa: BLE001
                raise RestartProofError(
                    f"{phase} restart failed after confirmed pause: "
                    f"{type(retry_exc).__name__}: {str(retry_exc)[:180]}"
                ) from retry_exc
            record["restart_requested"] = True
            restart_stage = _runtime_stage(restarted)
        else:
            # The provider no longer reports PAUSED, so the first request may
            # have been accepted. Do not issue a duplicate restart; the later
            # public boot-ID proof decides whether the transition completed.
            record["restart_requested"] = True
            restart_stage = observed_stage

    record["restart_response_stage"] = restart_stage
    record["writer_overlap_prevented"] = True
    _check_deadline(deadline)
    return record
"""
    source = replace_once(source, anchor, helpers, "restart helper insertion")

    activation_old = """    activation_restart = api.restart_space(
        repo_id=repo_id,
        factory_reboot=False,
    )
    trace["activation_restart_requested"] = True
    _check_deadline(deadline)
    activation_stage = getattr(
        getattr(activation_restart, "runtime", None),
        "stage",
        None,
    )
    activation_stage = getattr(activation_stage, "value", activation_stage)
"""
    activation_new = """    activation_control = stop_the_world_restart(
        api,
        repo_id=repo_id,
        deadline=deadline,
        attempts=attempts,
        retry_seconds=retry_seconds,
        phase="activation",
        evidence=trace,
    )
    trace["activation_restart_requested"] = True
    activation_stage = activation_control["restart_response_stage"]
"""
    source = replace_once(
        source,
        activation_old,
        activation_new,
        "activation restart serialization",
    )

    durability_old = """    durability_restart = api.restart_space(
        repo_id=repo_id,
        factory_reboot=False,
    )
    trace["durability_restart_requested"] = True
    _check_deadline(deadline)
    durability_stage = getattr(
        getattr(durability_restart, "runtime", None),
        "stage",
        None,
    )
    durability_stage = getattr(
        durability_stage,
        "value",
        durability_stage,
    )
"""
    durability_new = """    durability_control = stop_the_world_restart(
        api,
        repo_id=repo_id,
        deadline=deadline,
        attempts=attempts,
        retry_seconds=retry_seconds,
        phase="durability",
        evidence=trace,
    )
    trace["durability_restart_requested"] = True
    durability_stage = durability_control["restart_response_stage"]
"""
    source = replace_once(
        source,
        durability_old,
        durability_new,
        "durability restart serialization",
    )

    source = replace_once(
        source,
        """        "activation_restart_requested": True,
        "activation_restart_response_stage": str(
            activation_stage or "UNKNOWN"
        ),
""",
        """        "activation_restart_requested": True,
        "activation_restart_response_stage": str(
            activation_stage or "UNKNOWN"
        ),
        "activation_pause_confirmed": activation_control["pause_confirmed"],
        "activation_writer_overlap_prevented": activation_control[
            "writer_overlap_prevented"
        ],
""",
        "activation result evidence",
    )
    source = replace_once(
        source,
        """        "durability_restart_response_stage": str(
            durability_stage or "UNKNOWN"
        ),
""",
        """        "durability_restart_response_stage": str(
            durability_stage or "UNKNOWN"
        ),
        "durability_pause_confirmed": durability_control["pause_confirmed"],
        "durability_writer_overlap_prevented": durability_control[
            "writer_overlap_prevented"
        ],
""",
        "durability result evidence",
    )
    source = replace_once(
        source,
        """            "pre_restart_chain_head_recovered": True,
        },
""",
        """            "pre_restart_chain_head_recovered": True,
            "activation_stop_the_world": True,
            "durability_stop_the_world": True,
            "writer_overlap_prevented": True,
        },
""",
        "proof result evidence",
    )
    PROOF.write_text(source, encoding="utf-8")


def patch_existing_tests() -> None:
    source = TEST.read_text(encoding="utf-8")
    old = """class Api:
    def __init__(self) -> None:
        self.calls = []

    def restart_space(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            runtime=SimpleNamespace(stage=SimpleNamespace(value="RESTARTING"))
        )
"""
    new = """class Api:
    def __init__(self) -> None:
        self.calls = []
        self.pause_calls = []
        self.runtime_calls = []

    def pause_space(self, **kwargs):
        self.pause_calls.append(kwargs)
        return SimpleNamespace(stage=SimpleNamespace(value="PAUSING"))

    def get_space_runtime(self, **kwargs):
        self.runtime_calls.append(kwargs)
        return SimpleNamespace(stage=SimpleNamespace(value="PAUSED"))

    def restart_space(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            runtime=SimpleNamespace(stage=SimpleNamespace(value="RESTARTING"))
        )
"""
    source = replace_once(source, old, new, "existing API test double")
    TEST.write_text(source, encoding="utf-8")


def main() -> int:
    patch_proof()
    patch_existing_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
