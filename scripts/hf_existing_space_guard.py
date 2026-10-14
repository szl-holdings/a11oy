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

import inspect
import json
import sys
import urllib.parse
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
            f"provider identity mismatch for Space {repo_id}"
        )

    observed_private = getattr(info, "private", None)
    if requested_private is False and observed_private is True:
        raise SpaceGuardError(
            f"existing Space {repo_id} is private; this guard will not change visibility"
        )
    return info


def require_existing_public_space(
    repo_id: str, token: str, *, api_class: type[Any] = HfApi
) -> None:
    """Admit a selected writer only when its exact target is provably public."""
    _repo_id((), {"repo_id": repo_id})
    if not isinstance(token, str) or not token.strip():
        raise SpaceGuardError("Hugging Face writer token is unavailable")
    try:
        api = api_class(token=token)
        info = _observe_existing_space(
            api, repo_id=repo_id, token=token, requested_private=False
        )
    except SpaceGuardError:
        raise
    except Exception as exc:
        status = http_status(exc)
        cause = f"HTTP {status}" if status is not None else type(exc).__name__
        raise SpaceGuardError(
            f"unable to verify existing public Space {repo_id}: {cause}"
        ) from exc
    if info is None:
        raise SpaceGuardError(f"required existing public Space is absent: {repo_id}")
    if getattr(info, "private", None) is not False:
        raise SpaceGuardError(f"public visibility is unconfirmed for Space {repo_id}")


# hf-sync.yml is the only writer of the canonical A11oy Space. Publishers that
# install this guard write other Spaces, so the canonical Space is refused at
# two layers before any request leaves the process:
#
# * deny by default on the SDK class: every public HfApi method except the
#   reviewed read-only methods below refuses a call that names the canonical
#   Space in any argument, so an SDK mutator added later is refused unless it
#   is reviewed and listed here as a read. The module-level aliases
#   (``huggingface_hub.upload_file`` and the like, bound at import time) are
#   rebound to the refusing methods.
# * at the transport: every non-read HTTP request the SDK client sends whose
#   path names ``spaces/SZLHOLDINGS/a11oy``, or whose repository-management
#   body names it, is refused, whichever SDK entrypoint built the request.
CANONICAL_SPACE = "SZLHOLDINGS/a11oy"
CANONICAL_READ_METHODS = frozenset({
    "auth_check", "dataset_info", "fetch_space_logs", "file_exists", "get_dataset_leaderboard",
    "get_discussion_details", "get_full_repo_name", "get_paths_info", "get_repo_discussions",
    "get_safetensors_metadata", "get_space_runtime", "get_space_secrets", "get_space_variables",
    "hf_hub_download", "kernel_info", "list_accepted_access_requests",
    "list_dataset_parquet_files", "list_lfs_files", "list_pending_access_requests",
    "list_rejected_access_requests", "list_repo_commits", "list_repo_files", "list_repo_likers",
    "list_repo_refs", "list_repo_tree", "model_info", "parse_safetensors_file_metadata",
    "repo_exists", "repo_info", "resolve_revision", "revision_exists", "snapshot_download",
    "space_info", "verify_repo_checksums", "wait_for_space",
})
# Mutators known when the refusal was reviewed. Refusal does not depend on this
# list (it is deny by default); tests prove each of these is refused.
CANONICAL_WRITE_METHODS = (
    "add_space_secret", "add_space_variable", "create_branch", "create_commit",
    "create_pull_request", "create_repo", "create_tag", "delete_branch", "delete_file",
    "delete_files", "delete_folder", "delete_repo", "delete_space_secret",
    "delete_space_storage", "delete_space_variable", "delete_space_volumes", "delete_tag",
    "disable_space_dev_mode", "duplicate_repo", "duplicate_space", "enable_space_dev_mode",
    "merge_pull_request", "move_repo", "pause_space", "permanently_delete_lfs_files",
    "preupload_lfs_files", "request_space_hardware", "request_space_storage", "restart_space",
    "set_space_secret", "set_space_sleep_time", "set_space_variable", "set_space_volumes",
    "super_squash_history", "update_repo_settings", "update_repo_visibility", "upload_file",
    "upload_folder", "upload_large_folder",
)
_CANONICAL_MARKER = "__szl_canonical_space_refusal_v1__"
_READ_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_CANONICAL_PATH = "/spaces/" + CANONICAL_SPACE.casefold()
_TRANSPORT_STATE: dict[str, Any] = {"sync": "NOT_INSTALLED", "async": "NOT_INSTALLED",
                                    "refused_requests": 0}


class CanonicalSpaceWriteRefused(SpaceGuardError):
    """A non-canonical publisher attempted to mutate the canonical Space."""


def _names_canonical(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip().casefold()
    for prefix in ("https://huggingface.co/", "http://huggingface.co/", "spaces/"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.rstrip("/") == CANONICAL_SPACE.casefold()


def _refusing(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(original)
    def refusing(self: Any, *args: Any, **kwargs: Any) -> Any:
        if any(_names_canonical(value) for value in (*args, *kwargs.values())):
            raise CanonicalSpaceWriteRefused(
                f"{name} refused: only hf-sync.yml writes {CANONICAL_SPACE}"
            )
        return original(self, *args, **kwargs)

    setattr(refusing, _CANONICAL_MARKER, True)
    return refusing


def _refusable_methods(api_class: type[Any]) -> list[str]:
    names = []
    for name in dir(api_class):
        if name.startswith("_") or name in CANONICAL_READ_METHODS:
            continue
        static = inspect.getattr_static(api_class, name, None)
        if inspect.isfunction(static):
            names.append(name)
    return sorted(names)


def _rebind_module_aliases(api_class: type[Any]) -> int:
    """Point import-time aliases such as ``huggingface_hub.upload_file`` at the refusal."""
    rebound = 0
    for module_name in ("huggingface_hub.hf_api", "huggingface_hub"):
        module = sys.modules.get(module_name)
        if module is None:
            continue
        for alias, value in list(vars(module).items()):
            owner = getattr(value, "__self__", None)
            if not inspect.ismethod(value) or not isinstance(owner, api_class):
                continue
            current = getattr(owner, value.__func__.__name__, None)
            if (getattr(getattr(current, "__func__", None), _CANONICAL_MARKER, False)
                    and not getattr(value.__func__, _CANONICAL_MARKER, False)):
                setattr(module, alias, current)
                rebound += 1
    return rebound


def _request_names_canonical(method: str, url: Any, content: Callable[[], bytes]) -> bool:
    if str(method).upper() in _READ_HTTP_METHODS:
        return False
    path = urllib.parse.unquote(urllib.parse.urlsplit(str(url)).path).casefold()
    start = path.find(_CANONICAL_PATH)
    while start != -1:
        following = path[start + len(_CANONICAL_PATH):start + len(_CANONICAL_PATH) + 1]
        if following in ("", "/", "."):
            return True
        start = path.find(_CANONICAL_PATH, start + 1)
    if not path.startswith("/api/repos/"):
        return False
    # Repository create, delete, move and settings name the target in the body.
    try:
        body = json.loads(content() or b"null")
    except Exception:
        return False
    if not isinstance(body, dict):
        return False
    if any(_names_canonical(value) for value in body.values()):
        return True
    organization, name = body.get("organization"), body.get("name")
    return (isinstance(organization, str) and isinstance(name, str)
            and _names_canonical(f"{organization}/{name}"))


def _refuse_request(request: Any) -> None:
    def content() -> bytes:
        return bytes(request.content)

    if _request_names_canonical(request.method, request.url, content):
        with _COUNTER_LOCK:
            _TRANSPORT_STATE["refused_requests"] += 1
        raise CanonicalSpaceWriteRefused(
            f"{request.method} request refused: only hf-sync.yml writes {CANONICAL_SPACE}"
        )


async def _refuse_request_async(request: Any) -> None:
    _refuse_request(request)


def install_canonical_transport_refusal() -> dict[str, Any]:
    """Refuse canonical-Space mutations in every SDK HTTP client created from now on."""
    try:
        from huggingface_hub.utils import _http
    except Exception:  # a stand-in or pre-httpx SDK: the class layer still refuses
        return dict(_TRANSPORT_STATE)
    for kind, factory_name, setter_name, hook in (
        ("sync", "_GLOBAL_CLIENT_FACTORY", "set_client_factory", _refuse_request),
        ("async", "_GLOBAL_ASYNC_CLIENT_FACTORY", "set_async_client_factory", _refuse_request_async),
    ):
        current = getattr(_http, factory_name, None)
        setter = getattr(_http, setter_name, None)
        if not callable(current) or not callable(setter):
            _TRANSPORT_STATE[kind] = "UNAVAILABLE"
            continue
        if getattr(current, _CANONICAL_MARKER, False):
            _TRANSPORT_STATE[kind] = "INSTALLED"
            continue

        def factory(_current: Callable[[], Any] = current, _hook: Callable[..., Any] = hook) -> Any:
            client = _current()
            hooks = dict(client.event_hooks)
            hooks["request"] = [*hooks.get("request", []), _hook]
            client.event_hooks = hooks
            return client

        setattr(factory, _CANONICAL_MARKER, True)
        setter(factory)
        _TRANSPORT_STATE[kind] = "INSTALLED"
    return dict(_TRANSPORT_STATE)


def refuse_canonical_space_writes(api_class: type[Any] = HfApi) -> tuple[str, ...]:
    """Refuse every non-read use of the canonical Space, deny by default.

    Wraps every public method of ``api_class`` except ``CANONICAL_READ_METHODS``
    so that a call naming the canonical Space in any argument is refused,
    rebinds the SDK's import-time module aliases, and installs the transport
    refusal for the SDK HTTP clients. Returns the method names that now
    refuse; installation is idempotent.
    """

    refused: list[str] = []
    with _INSTALL_LOCK:
        for name in _refusable_methods(api_class):
            current = getattr(api_class, name)
            if not getattr(current, _CANONICAL_MARKER, False):
                setattr(api_class, name, _refusing(name, current))
            refused.append(name)
        _rebind_module_aliases(api_class)
    install_canonical_transport_refusal()
    return tuple(refused)


def canonical_refusal_report(api_class: type[Any] = HfApi) -> dict[str, Any]:
    with _COUNTER_LOCK:
        transport = dict(_TRANSPORT_STATE)
    return {"canonical_space": CANONICAL_SPACE, "policy": "DENY_BY_DEFAULT_EXCEPT_REVIEWED_READS",
            "class_methods_refusing": sum(
                1 for name in _refusable_methods(api_class)
                if getattr(getattr(api_class, name), _CANONICAL_MARKER, False)),
            "transport": transport}


def install_existing_space_guard(
    api_class: type[Any] = HfApi, *, require_existing: bool = False
) -> dict[str, Any]:
    """Install a process-local create guard on one Hugging Face API class.

    By default, only calls that explicitly request ``repo_type='space'`` and
    ``exist_ok=True`` are intercepted; other SDK calls remain untouched.
    ``require_existing=True`` blocks missing Spaces and unexpected create calls.
    Installation also refuses every mutation of the canonical A11oy Space.
    """

    refuse_canonical_space_writes(api_class)
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
    "CANONICAL_READ_METHODS",
    "CANONICAL_SPACE",
    "CANONICAL_WRITE_METHODS",
    "CanonicalSpaceWriteRefused",
    "SpaceGuardError",
    "canonical_refusal_report",
    "guard_report",
    "http_status",
    "install_canonical_transport_refusal",
    "install_existing_space_guard",
    "refuse_canonical_space_writes",
    "require_existing_public_space",
]
