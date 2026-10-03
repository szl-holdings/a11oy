#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prevent idempotent publishers from consuming Hugging Face Space-create quota.

``HfApi.create_repo(..., repo_type="space", exist_ok=True)`` still calls the
provider's Space-creation endpoint. Repeated publications can therefore exhaust
the daily create limit even when every target already exists. This process-local
guard observes the exact Space first and returns the existing repository metadata
when present. By default, it delegates to the original SDK only after an exact
404; selected publications can require an existing target instead.

The observation is an admission gate, not a readiness claim: successful repository
lookup does not prove that the Space is running, current, healthy, or source-bound.
Selected single-target publications require an existing Space and block an exact
404 instead of delegating creation. Authentication, rate-limit, transport, and
server errors never become absence. The guard does not change visibility,
hardware, storage, variables, secrets, or repository contents.
"""
from __future__ import annotations

from functools import wraps
from threading import Lock
from typing import Any, Callable

from huggingface_hub import HfApi

_MARKER = "__szl_existing_space_guard_v1__"
_INSTALL_LOCK = Lock()
_COUNTER_LOCK = Lock()


class SpaceGuardError(RuntimeError):
    """Raised when repository identity or visibility cannot be proven safely."""


def http_status(exc: BaseException) -> int | None:
    """Extract a provider HTTP status without depending on one SDK exception type."""

    response = getattr(exc, "response", None)
    for value in (
        getattr(response, "status_code", None),
        getattr(response, "status", None),
        getattr(exc, "status_code", None),
        getattr(exc, "code", None),
    ):
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _repo_id(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    value = kwargs.get("repo_id")
    if value is None and args:
        value = args[0]
    if not isinstance(value, str) or "/" not in value or value != value.strip():
        raise SpaceGuardError("repo_id must be an exact namespace/name string")
    return value


def _increment(state: dict[str, Any], key: str) -> None:
    with _COUNTER_LOCK:
        state[key] += 1


def _observe_existing_space(
    api: Any,
    *,
    repo_id: str,
    token: Any,
    requested_private: Any,
) -> Any | None:
    try:
        info = api.repo_info(repo_id=repo_id, repo_type="space", token=token)
    except Exception as exc:  # SDK exception classes vary between pinned clients.
        if http_status(exc) == 404:
            return None
        raise

    observed_id = getattr(info, "id", None) or getattr(info, "repo_id", None)
    if not isinstance(observed_id, str) or observed_id.casefold() != repo_id.casefold():
        raise SpaceGuardError(
            f"provider identity mismatch: expected {repo_id}, observed {observed_id!r}"
        )

    observed_private = getattr(info, "private", None)
    if requested_private is False and observed_private is True:
        raise SpaceGuardError(
            f"existing Space {repo_id} is private; this guard will not change visibility"
        )
    return info


def install_existing_space_guard(
    api_class: type[Any] = HfApi, *, require_existing: bool = False
) -> dict[str, Any]:
    """Install a process-local create guard on one Hugging Face API class.

    By default, only calls that explicitly request ``repo_type='space'`` and
    ``exist_ok=True`` are intercepted; other SDK calls remain untouched.
    ``require_existing=True`` blocks missing Spaces and unexpected create calls.
    """

    with _INSTALL_LOCK:
        current = api_class.create_repo
        if getattr(current, _MARKER, False):
            if require_existing:
                with _COUNTER_LOCK:
                    current.__szl_guard_state__["require_existing"] = True
            return guard_report(api_class)

        original: Callable[..., Any] = current
        state = {
            "schema": "szl.hf-existing-space-guard/v1",
            "installed": True,
            "existing_spaces_reused": 0,
            "missing_spaces_delegated_to_create": 0,
            "missing_spaces_blocked": 0,
            "non_space_or_strict_calls_delegated": 0,
            "absence_policy": "EXACT_HTTP_404_ONLY",
            "require_existing": require_existing,
            "secret_values_recorded": False,
        }

        @wraps(original)
        def guarded(self: Any, *args: Any, **kwargs: Any) -> Any:
            repo_type = kwargs.get("repo_type")
            exist_ok = kwargs.get("exist_ok", False)
            if state["require_existing"] and (repo_type != "space" or exist_ok is not True):
                raise SpaceGuardError("selected publisher cannot create a new repository")
            if repo_type != "space" or exist_ok is not True:
                _increment(state, "non_space_or_strict_calls_delegated")
                return original(self, *args, **kwargs)

            repo_id = _repo_id(args, kwargs)
            info = _observe_existing_space(
                self,
                repo_id=repo_id,
                token=kwargs.get("token"),
                requested_private=kwargs.get("private"),
            )
            if info is not None:
                _increment(state, "existing_spaces_reused")
                return info

            if state["require_existing"]:
                _increment(state, "missing_spaces_blocked")
                raise SpaceGuardError(f"required existing Space is absent: {repo_id}")

            _increment(state, "missing_spaces_delegated_to_create")
            return original(self, *args, **kwargs)

        setattr(guarded, _MARKER, True)
        setattr(guarded, "__szl_guard_state__", state)
        setattr(guarded, "__szl_original_create_repo__", original)
        api_class.create_repo = guarded
        return dict(state)


def guard_report(api_class: type[Any] = HfApi) -> dict[str, Any]:
    current = api_class.create_repo
    state = getattr(current, "__szl_guard_state__", None)
    if not isinstance(state, dict):
        return {
            "schema": "szl.hf-existing-space-guard/v1",
            "installed": False,
            "existing_spaces_reused": 0,
            "missing_spaces_delegated_to_create": 0,
            "missing_spaces_blocked": 0,
            "non_space_or_strict_calls_delegated": 0,
            "absence_policy": "EXACT_HTTP_404_ONLY",
            "require_existing": False,
            "secret_values_recorded": False,
        }
    with _COUNTER_LOCK:
        return dict(state)


__all__ = [
    "SpaceGuardError",
    "guard_report",
    "http_status",
    "install_existing_space_guard",
]
