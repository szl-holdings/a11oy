#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Convergence planner and drift detector for the vertical flagship Spaces.

The vertical Spaces (Terra, Counsel, Sentra, Finance, Lyte) used to be
published only by an operator dispatch, so they drifted from main silently for
weeks. This tool decides, per target, whether the Space already serves what
main would publish:

* Generated shells (Terra, Counsel, Sentra, Finance): the publication is
  rendered offline from this checkout and compared file by file, by git blob
  id, with the Space's Hub tree. ``config.json`` is compared with its identity
  fields (``source_revision``, ``workflow_run_id``) taken from the served file,
  so an unrelated main commit is never drift while any changed byte is.
  Finance additionally proxies the canonical A11oy Space, which must report
  the same source revision as the Finance config.
  Finance's projection manifest is rendered from the served identity and
  compared too, and served identity fields that are not an exact revision and
  a positive run id are drift, never their own expected value.
* Lyte is source-owned: its Space must serve the qualified
  ``szl-holdings/lyte-services`` main revision, resolved (head and
  qualification) at plan time. While its runtime reports non-durable
  persistence the automatic writer excludes it: the release restarts the
  Space and a restart drops process-scoped data. That exclusion is the
  explicit UNPLANNED state, which names the qualified revision and alerts at
  once, because no automatic run will ever converge it.
* Every plan records every declared target, including the ones it does not
  assess (a superseded or deferred automatic run, an operator dispatch), so a
  target can never drop out of a plan receipt silently.
* A target is CONVERGED only while its running build is observed serving the
  expected bytes: an unreachable build-info or a Space stage other than RUNNING
  is RUNTIME_UNAVAILABLE, which alerts and keeps the tracker open.

Converged targets are no-ops. The tool never writes to Hugging Face; the
existing publisher performs and live-verifies every write. ``report`` also
dates each drift and ``issue`` keeps one tracking issue open while a drift
persists past a threshold and closes it once every target has converged.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
ORG = "SZLHOLDINGS"
REPOSITORY = "szl-holdings/a11oy"
LYTE_REPOSITORY = "szl-holdings/lyte-services"
A11OY_ORIGIN = "https://szlholdings-a11oy.hf.space"
HUB = "https://huggingface.co"
GITHUB_API = "https://api.github.com"
USER_AGENT = "SZLHOLDINGS-Vertical-Convergence/1.0"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
PLACEHOLDER_REVISION = "1" * 40

# Sentra is last: its admission may wait for the required checks of main, and
# the targets ahead of it should not wait behind that under the writer lock.
TARGETS = ("terra", "counsel", "finance", "lyte", "sentra")
GENERATED_TARGETS = ("terra", "counsel", "finance", "sentra")
IDENTITY_FIELDS = ("source_revision", "workflow_run_id")
PUBLISHED_FILES = ("app.py", "Dockerfile", "requirements.txt", "index.html", "panels.html", "README.md")
FINANCE_MANIFEST = "finance-projection-manifest.json"
# Space stages that serve a build, and stages in which a new build is expected
# to come up on its own (the RUNNING_* stages still serve the previous build).
RUNNING_STAGES = ("RUNNING", "RUNNING_BUILDING", "RUNNING_APP_STARTING")
STARTING_STAGES = ("BUILDING", "APP_STARTING", "RUNNING_BUILDING", "RUNNING_APP_STARTING")
# Lyte persistence that a release restart would lose (or that is not reported).
NON_DURABLE_PERSISTENCE = ("FILE_OR_PROCESS_SCOPED", "PROCESS_SCOPED", "EPHEMERAL")
DEFAULT_ALERT_HOURS = 6.0
TRACKER_MARKER = "<!-- szl:vertical-drift-tracker:v1 -->"

# Files whose bytes determine what the generated publisher renders. They are the
# files the renderer reads; tests/test_hf_vertical_convergence.py records the
# renderer's actual reads with an audit hook and fails if one is missing here
# or from the workflow push filter.
SHARED_RENDER_INPUTS = (
    "scripts/_hf_publish_vertical_flagships_v4_impl_base.py",
    "scripts/hf_publish_vertical_flagships_v4_impl.py",
    "scripts/hf_vertical_native_presentation.py",
    "scripts/hf_finance_functional_gate.py",
    "scripts/hf_finance_projection_manifest.py",
    "scripts/hf_finance_read_proxy.py",
    "scripts/hf_finance_research_workspace.py",
    "scripts/hf_finance_signed_workspace.py",
    "scripts/hf_finance_workspace.py",
    "scripts/hf_flagship_runtime_contract.py",
    "scripts/hf_sentra_upstream.py",
    "verticals/puriq-markets/runtime/components/finance_v2/source.json",
    "verticals/puriq-markets/runtime/components/puriq_verity/source.json",
)
NATIVE_PRESENTATION_INPUTS = (
    "console/assets/szl/SOURCE.json",
    "console/assets/szl/orbit-v2/UPSTREAM.json",
    "console/assets/szl/orbit-v2/szl-icon-32.svg",
    "console/assets/szl/szl-design-system.css",
    "scripts/hf_vertical_native.css",
)
TERRA_FORGE_INPUTS = (
    "deployments/vertical-forge/terra/build-receipt.json",
    "deployments/vertical-forge/terra/fleet-receipt.json",
    "deployments/vertical-forge/terra/index.html",
    "deployments/vertical-forge/terra/source-lock.json",
)
# Code that performs or gates a publication without changing the rendered
# bytes. A change here re-runs the plan; the plan is a no-op when converged.
PUBLISHER_INPUTS = (
    ".github/workflows/hf-publish-vertical-flagships.yml",
    "scripts/hf_existing_space_guard.py",
    "scripts/hf_publish_lyte_enterprise.py",
    "scripts/hf_publish_vertical_flagships_v4.py",
    "scripts/hf_vertical_convergence.py",
    "scripts/lyte_enterprise_live_contract.py",
    "scripts/szl_release_guard.py",
)
TARGET_RENDER_INPUTS: dict[str, tuple[str, ...]] = {
    "terra": SHARED_RENDER_INPUTS + NATIVE_PRESENTATION_INPUTS + TERRA_FORGE_INPUTS,
    "counsel": SHARED_RENDER_INPUTS + NATIVE_PRESENTATION_INPUTS,
    "sentra": SHARED_RENDER_INPUTS + NATIVE_PRESENTATION_INPUTS,
    "finance": SHARED_RENDER_INPUTS + NATIVE_PRESENTATION_INPUTS,
    # Lyte's bytes come from lyte-services; nothing in this repository is rendered.
    "lyte": (),
}


def workflow_push_paths() -> tuple[str, ...]:
    """The exact push filter the publisher workflow must declare."""
    paths = set(PUBLISHER_INPUTS)
    for inputs in TARGET_RENDER_INPUTS.values():
        paths.update(inputs)
    return tuple(sorted(paths))


# --------------------------------------------------------------------------- io


class Unavailable(RuntimeError):
    """A provider read did not return usable evidence."""


def _request(url: str, *, headers: dict[str, str] | None = None, attempts: int = 4,
             timeout: int = 20, limit: int = 4 * 1024 * 1024) -> bytes:
    merged = {"User-Agent": USER_AGENT, "Cache-Control": "no-cache"}
    merged.update(headers or {})
    delay = 5.0
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers=merged)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read(limit + 1)
            if len(body) > limit:
                raise Unavailable(f"response exceeded {limit} bytes: {url}")
            return body
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or exc.code >= 500
            if not retryable or attempt == attempts:
                raise Unavailable(f"HTTP {exc.code}: {url}") from exc
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            # A truncated or malformed response (IncompleteRead, BadStatusLine,
            # LineTooLong) is an HTTPException, not an OSError. It is a
            # transient read like a reset socket, so it degrades this one
            # target to UNOBSERVABLE instead of failing the whole estate plan.
            if attempt == attempts:
                raise Unavailable(f"{type(exc).__name__}: {url}") from exc
        time.sleep(delay)
        delay *= 3
    raise Unavailable(url)


def get_json(url: str, **kwargs: Any) -> Any:
    try:
        return json.loads(_request(url, **kwargs))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Unavailable(f"invalid JSON: {url}") from exc


def github_json(path: str) -> Any:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return get_json(GITHUB_API + path, headers=headers)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
                          text=True).stdout.strip()


def git_blob_id(content: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(content) + content).hexdigest()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(value: dt.datetime | None) -> str | None:
    return None if value is None else value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------- expectations


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_renderer() -> ModuleType:
    return _load("szl_vertical_convergence_renderer", ROOT / "scripts/hf_publish_vertical_flagships_v4_impl.py")


def expected_generated(renderer: ModuleType, slug: str) -> dict[str, Any]:
    """Render one generated target offline exactly as its writer publishes it."""
    if slug not in GENERATED_TARGETS:
        raise ValueError(f"not a generated target: {slug}")
    renderer._sync_contract()
    if slug == "finance":
        files = renderer.render_finance_payloads(PLACEHOLDER_REVISION, 1)
    elif slug == "sentra":
        files, _ = renderer.render_sentra_payload(PLACEHOLDER_REVISION, 1)
    else:
        items = [row for row in renderer.FLAGSHIPS if row["slug"] == slug]
        if len(items) != 1:
            raise RuntimeError(f"renderer inventory is ambiguous for {slug}")
        item = items[0]
        panels = renderer.html(item)
        page, forge = renderer.load_terra_native_landing() if slug == "terra" else (panels, None)
        card = renderer.readme(item)
        forge_payload = json.dumps(forge, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        config = {
            "slug": slug, "title": item["title"], "vertical": item["vertical"],
            "product_source": item["source"],
            "source_repository": renderer.DEPLOYMENT_SOURCE_REPOSITORY,
            "source_revision": PLACEHOLDER_REVISION, "workflow_run_id": 1,
            "hf_repository": f"{renderer.ORG}/{slug}",
            "artifact_set_sha256": renderer.artifact_digest(
                renderer.APP, renderer.DOCKER, renderer.REQ, page, panels, card, forge_payload),
            "landing_sha256": hashlib.sha256(page.encode("utf-8")).hexdigest(),
            "panels_sha256": hashlib.sha256(panels.encode("utf-8")).hexdigest(),
            "forge": forge, "upstream": item["upstream"],
            "public_experience": renderer.PUBLIC_EXPERIENCE_VERSION,
        }
        files = {path: content.encode("utf-8") for path, content in (
            ("app.py", renderer.APP), ("Dockerfile", renderer.DOCKER),
            ("requirements.txt", renderer.REQ),
            ("config.json", json.dumps(config, indent=2, sort_keys=True) + "\n"),
            ("index.html", page), ("panels.html", panels), ("README.md", card),
        )}
    config = json.loads(files["config.json"])
    return {
        "files": {path: git_blob_id(files[path]) for path in PUBLISHED_FILES},
        "config": {key: value for key, value in config.items() if key not in IDENTITY_FIELDS},
        "artifact_set_sha256": config["artifact_set_sha256"],
    }


def finance_binds_canonical_revision(renderer: ModuleType) -> bool:
    """Whether the emitted Finance projection requires A11oy's exact revision.

    While the projection answers CANONICAL_REVISION_MISMATCH for any canonical
    response whose source_revision differs from its own config, Finance is only
    current when it binds the revision the canonical Space serves, and its
    publisher preflight only admits main while that Space serves main. A
    contract-versioned projection drops that coupling and is then planned like
    every other generated target.
    """
    return "CANONICAL_REVISION_MISMATCH" in renderer.APP


def expected_config_bytes(core: dict[str, Any], served: dict[str, Any]) -> bytes:
    merged = dict(core)
    for field in IDENTITY_FIELDS:
        merged[field] = served.get(field)
    return (json.dumps(merged, indent=2, sort_keys=True) + "\n").encode("utf-8")


def valid_identity(served: dict[str, Any]) -> bool:
    """The identity a publisher writes: an exact nonzero revision and a positive run id."""
    revision, run_id = served.get("source_revision"), served.get("workflow_run_id")
    return (isinstance(revision, str) and SHA40.fullmatch(revision) is not None
            and revision != "0" * 40 and type(run_id) is int and run_id > 0)


def expected_finance_manifest_blob(renderer: ModuleType, served: dict[str, Any]) -> str:
    """The projection manifest Finance's writer uploads for the served identity."""
    revision, run_id = served["source_revision"], served["workflow_run_id"]
    files = renderer.render_finance_payloads(revision, run_id)
    return git_blob_id(renderer.finance_projection_manifest_bytes(files, revision, run_id))


# --------------------------------------------------------------- observations


def hub_tree(slug: str) -> dict[str, str]:
    rows = get_json(f"{HUB}/api/spaces/{ORG}/{slug}/tree/main")
    if not isinstance(rows, list):
        raise Unavailable(f"Hub tree is not a list for {slug}")
    return {row["path"]: row["oid"] for row in rows
            if isinstance(row, dict) and row.get("type") == "file"
            and isinstance(row.get("path"), str) and isinstance(row.get("oid"), str)}


def hub_config(slug: str) -> tuple[dict[str, Any], bytes]:
    raw = _request(f"{HUB}/spaces/{ORG}/{slug}/resolve/main/config.json")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Unavailable(f"served config.json is not JSON for {slug}") from exc
    if not isinstance(value, dict):
        raise Unavailable(f"served config.json is not an object for {slug}")
    return value, raw


def space_info(slug: str) -> dict[str, Any]:
    value = get_json(f"{HUB}/api/spaces/{ORG}/{slug}")
    if not isinstance(value, dict):
        raise Unavailable(f"Space info is not an object for {slug}")
    runtime = value.get("runtime") if isinstance(value.get("runtime"), dict) else {}
    return {"sha": value.get("sha"), "last_modified": value.get("lastModified"),
            "stage": runtime.get("stage")}


def live_build_info(slug: str) -> dict[str, Any]:
    value = get_json(f"https://szlholdings-{slug}.hf.space/api/build-info", attempts=3)
    if not isinstance(value, dict):
        raise Unavailable(f"live build-info is not an object for {slug}")
    return value


def a11oy_served_revision() -> str:
    value = get_json(f"{A11OY_ORIGIN}/api/build-info", attempts=3)
    build = value.get("build") if isinstance(value, dict) else None
    revision = build.get("revision") if isinstance(build, dict) else None
    if not isinstance(revision, str) or SHA40.fullmatch(revision) is None:
        raise Unavailable("canonical A11oy build-info has no exact revision")
    return revision


def lyte_expected_revision() -> tuple[str, dict[str, Any]]:
    module = _load_lyte_publisher()
    return module.resolve_verified_source_tip()


def _load_lyte_publisher() -> ModuleType:
    entrypoint = _load("szl_vertical_convergence_entrypoint", ROOT / "scripts/hf_publish_vertical_flagships_v4.py")
    return entrypoint.load_module("szl_vertical_convergence_lyte", entrypoint.LYTE_IMPL)


# --------------------------------------------------------------------- dating


def commit_time(revision: str | None) -> dt.datetime | None:
    if not isinstance(revision, str) or SHA40.fullmatch(revision) is None:
        return None
    try:
        return parse_time(git("show", "-s", "--format=%cI", revision))
    except subprocess.CalledProcessError:
        return None


def first_input_change_after(revision: str, inputs: tuple[str, ...]) -> dt.datetime | None:
    """Commit time of the oldest main commit after ``revision`` touching ``inputs``."""
    if not inputs or SHA40.fullmatch(revision or "") is None:
        return None
    try:
        out = git("log", "--reverse", "--format=%cI", f"{revision}..HEAD", "--", *inputs)
    except subprocess.CalledProcessError:
        return None
    first = out.splitlines()[0] if out else ""
    return parse_time(first)


# ---------------------------------------------------------------------- state


def _row(slug: str, **values: Any) -> dict[str, Any]:
    row = {"target": slug, "space": f"{ORG}/{slug}", "state": "UNKNOWN", "publish": False,
           "reason": None, "served_revision": None, "drift_since": None,
           "drift_since_basis": None, "differing_files": []}
    row.update(values)
    return row


def assess_generated(slug: str, renderer: ModuleType, *, head: str,
                     a11oy_revision: Callable[[], str] = a11oy_served_revision) -> dict[str, Any]:
    expected = expected_generated(renderer, slug)
    try:
        tree = hub_tree(slug)
        served, served_raw = hub_config(slug)
    except Unavailable as exc:
        return _row(slug, state="UNOBSERVABLE", reason=str(exc))
    served_revision = served.get("source_revision")
    differing = [path for path in PUBLISHED_FILES if tree.get(path) != expected["files"][path]]
    # The identity fields are taken from the served file only when they are an
    # identity a publisher can have written; anything else is drift itself.
    identity_valid = valid_identity(served)
    if not identity_valid or served_raw != expected_config_bytes(expected["config"], served):
        differing.append("config.json")
    if slug == "finance" and (not identity_valid or tree.get(FINANCE_MANIFEST)
                              != expected_finance_manifest_blob(renderer, served)):
        differing.append(FINANCE_MANIFEST)
    row = _row(slug, served_revision=served_revision, differing_files=differing,
               served_workflow_run_id=served.get("workflow_run_id"),
               served_identity_valid=identity_valid,
               expected_artifact_set_sha256=expected["artifact_set_sha256"],
               served_artifact_set_sha256=served.get("artifact_set_sha256"))
    try:
        info = space_info(slug)
        row.update(space_stage=info["stage"], space_last_modified=info["last_modified"])
    except Unavailable as exc:
        info = {"last_modified": None, "stage": None}
        row["space_info_error"] = str(exc)

    canonical = None
    coupled = slug == "finance" and finance_binds_canonical_revision(renderer)
    row["canonical_revision_bound"] = coupled
    if coupled:
        try:
            canonical = a11oy_revision()
        except Unavailable as exc:
            row.update(state="UNOBSERVABLE", reason=f"canonical A11oy revision: {exc}")
            return row
        row["canonical_a11oy_revision"] = canonical

    if differing:
        since = first_input_change_after(str(served_revision if identity_valid else ""),
                                         TARGET_RENDER_INPUTS[slug])
        basis = "first input change after the served revision"
        if since is None:
            # Bytes differ but no listed input changed: the input table is
            # incomplete or the Space was edited outside this publisher.
            since = commit_time(served_revision) or parse_time(info.get("last_modified"))
            basis = "served revision (no listed input changed; unexplained drift)"
            row["unexplained_drift"] = True
        reason = "published bytes differ from main: " + ", ".join(differing)
        if not identity_valid:
            reason += "; the served source identity is not an exact revision and positive run id"
        row.update(state="DRIFT", reason=reason, drift_since=iso(since), drift_since_basis=basis)
    elif coupled and served_revision != canonical:
        times = [value for value in (commit_time(canonical), commit_time(served_revision)) if value]
        row.update(state="DRIFT",
                   reason=f"Finance binds {served_revision} but the canonical A11oy Space serves {canonical}",
                   drift_since=iso(max(times)) if times else None,
                   drift_since_basis="later commit of the two mismatched revisions (deploys follow commits)")
    else:
        row.update(state="CONVERGED")
        return _with_runtime(row, slug, stage=info.get("stage"))

    if coupled and canonical != head:
        row.update(state="BLOCKED", reason=row["reason"] + (
            f"; Finance can only publish main while the canonical A11oy Space serves it "
            f"(A11oy serves {canonical}, main is {head})"))
    else:
        row["publish"] = True
    return row


def _runtime_unavailable(row: dict[str, Any], *, stage: Any, reason: str) -> dict[str, Any]:
    """The Hub tree may be current, but no running build is observed serving it.

    A Space that is still building or starting is dated from its last commit,
    so only a build that stays down past the threshold alerts. A crashed,
    errored or unreachable runtime has no datable start and alerts at once. A
    sleeping Space wakes on request; it is not converged but does not alert.
    """
    if stage == "SLEEPING":
        row.update(state="RUNTIME_SLEEPING", publish=False, reason=reason)
        return row
    starting = stage in STARTING_STAGES
    row.update(state="RUNTIME_UNAVAILABLE", publish=False, reason=reason,
               drift_since=row.get("space_last_modified") if starting else None,
               drift_since_basis=("Space last modified (build or start in progress)" if starting
                                  else "undatable: no running build is observed"))
    return row


def _with_runtime(row: dict[str, Any], slug: str, *, stage: Any = None) -> dict[str, Any]:
    """A converged Hub tree is CONVERGED only while its running build serves it."""
    try:
        live = live_build_info(slug)
    except Unavailable as exc:
        row["runtime"] = {"state": "UNOBSERVABLE", "stage": stage, "reason": str(exc)}
        return _runtime_unavailable(row, stage=stage, reason=(
            f"the Hub files are current but the running build is not observable (stage {stage}): {exc}"))
    current = (live.get("source_revision") == row["served_revision"]
               and live.get("artifact_set_sha256") == row["expected_artifact_set_sha256"])
    row["runtime"] = {"state": "CURRENT" if current else "LAGGING", "stage": stage,
                      "source_revision": live.get("source_revision"),
                      "artifact_set_sha256": live.get("artifact_set_sha256")}
    if stage is not None and stage not in RUNNING_STAGES:
        return _runtime_unavailable(row, stage=stage, reason=(
            f"the Space stage is {stage}, not RUNNING"))
    if not current:
        row.update(state="RUNTIME_DRIFT",
                   reason="the Hub files are current but the running build serves older bytes",
                   drift_since=row.get("space_last_modified"),
                   drift_since_basis="Space last modified")
    return row


def _lyte_drift_since(served: Any, tip: str) -> dt.datetime | None:
    if not isinstance(served, str) or SHA40.fullmatch(served) is None:
        return None
    try:
        compare = github_json(f"/repos/{LYTE_REPOSITORY}/compare/{served}...{tip}")
    except Unavailable:
        return None
    commits = compare.get("commits") if isinstance(compare, dict) else None
    if not commits or not isinstance(commits[0], dict):
        return None
    return parse_time(commits[0].get("commit", {}).get("committer", {}).get("date"))


def lyte_persistence_durability(live: dict[str, Any]) -> Any:
    persistence = live.get("persistence")
    return persistence.get("durability") if isinstance(persistence, dict) else None


def assess_lyte(*, resolve: Callable[[], tuple[str, dict[str, Any]]] | None = None,
                source_tip: Callable[[], Any] | None = None) -> dict[str, Any]:
    # Both the lyte-services head and its qualification are read now, on every
    # plan: nothing here pins a revision.
    try:
        head = (source_tip or (lambda: github_json(f"/repos/{LYTE_REPOSITORY}/commits/main")))()
    except Unavailable as exc:
        return _row("lyte", state="UNOBSERVABLE", reason=f"lyte-services main: {exc}")
    tip = head.get("sha") if isinstance(head, dict) else None
    if not isinstance(tip, str) or SHA40.fullmatch(tip) is None:
        return _row("lyte", state="UNOBSERVABLE", reason="lyte-services main has no exact revision")
    try:
        info = space_info("lyte")
    except Unavailable as exc:
        info = {"stage": None, "last_modified": None, "error": str(exc)}
    try:
        live = live_build_info("lyte")
    except Unavailable as exc:
        # A Lyte Space that is down is not converged and alerts. It is not
        # republished automatically: a failed build would only be restarted
        # into the same failure every hour.
        row = _row("lyte", source_repository=LYTE_REPOSITORY, source_tip=tip,
                   space_stage=info.get("stage"), space_last_modified=info.get("last_modified"),
                   runtime={"state": "UNOBSERVABLE", "stage": info.get("stage"), "reason": str(exc)})
        return _runtime_unavailable(row, stage=info.get("stage"), reason=(
            f"the Lyte runtime is not observable (stage {info.get('stage')}): {exc}"))
    served = live.get("source_revision")
    durability = lyte_persistence_durability(live)
    row = _row("lyte", served_revision=served, source_repository=LYTE_REPOSITORY,
               source_tip=tip, runtime_source_revision=live.get("runtime_source_revision"),
               space_stage=info.get("stage"), space_last_modified=info.get("last_modified"),
               persistence_durability=durability)
    if info.get("stage") is not None and info.get("stage") not in RUNNING_STAGES:
        return _runtime_unavailable(row, stage=info.get("stage"),
                                    reason=f"the Lyte Space stage is {info.get('stage')}, not RUNNING")
    if served == tip and live.get("runtime_source_revision") == tip:
        row["state"] = "CONVERGED"
        return row
    row.update(drift_since=iso(_lyte_drift_since(served, tip)),
               drift_since_basis="first lyte-services commit after the served revision")
    try:
        expected, _ = (resolve or lyte_expected_revision)()
    except Exception as exc:  # the Lyte publisher's own source qualification refused
        row.update(state="BLOCKED", reason=(
            f"Lyte serves {served}; lyte-services main {tip} is not qualified: "
            f"{type(exc).__name__}: {exc}"))
        return row
    row["expected_revision"] = expected
    if not isinstance(durability, str) or durability in NON_DURABLE_PERSISTENCE:
        # The Lyte release restarts the Space. With process- or file-scoped
        # persistence that restart drops every acknowledged ingest, so an
        # automatic republish is withheld; an operator dispatch (scope lyte)
        # stays the explicit path that accepts that loss.
        row.update(state="UNPLANNED", automatic_writer="EXCLUDED",
                   unplanned_reason="NON_DURABLE_PERSISTENCE",
                   operator_action="dispatch hf-publish-vertical-flagships.yml with scope lyte",
                   reason=(
            f"Lyte serves {served}; qualified lyte-services main is {expected}, but the runtime "
            f"reports persistence durability {durability!r}: the release restarts the Space and "
            "would drop its stored data, so the automatic writer excludes Lyte until persistence "
            "is durable (dispatch scope lyte to accept the restart)"))
        return row
    row.update(state="DRIFT", publish=True,
               reason=f"Lyte serves {served}; qualified lyte-services main is {expected}")
    return row


def assess(targets: tuple[str, ...], *, head: str) -> list[dict[str, Any]]:
    renderer = load_renderer() if any(t in GENERATED_TARGETS for t in targets) else None
    rows = []
    for slug in targets:
        if slug == "lyte":
            rows.append(assess_lyte())
        else:
            rows.append(assess_generated(slug, renderer, head=head))
    return rows


def current_main() -> str:
    out = git("ls-remote", "origin", "refs/heads/main")
    revision = out.split()[0] if out else ""
    if SHA40.fullmatch(revision) is None:
        raise Unavailable("origin main did not resolve to an exact revision")
    return revision


# ----------------------------------------------------------------------- plan


# Every workflow whose dispatch can write a vertical Space. They all hold the
# one vertical writer group, where a newly queued job cancels the pending one,
# so an automatic run must not queue behind (and displace) a dispatched writer.
DISPATCHED_WRITER_WORKFLOWS = ("hf-publish-vertical-flagships.yml", "hf-sync.yml")


def active_dispatched_writers(*, own_run_id: str | None = None,
                              read: Callable[[str], Any] = github_json) -> list[dict[str, Any]]:
    active = []
    for workflow in DISPATCHED_WRITER_WORKFLOWS:
        payload = read(f"/repos/{REPOSITORY}/actions/workflows/{workflow}/runs"
                       "?event=workflow_dispatch&per_page=30")
        runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
        if not isinstance(runs, list):
            raise Unavailable(f"workflow run listing for {workflow} is not a list")
        for run in runs:
            if (isinstance(run, dict) and run.get("status") != "completed"
                    and str(run.get("id")) != str(own_run_id)):
                active.append({"workflow": workflow, "run_id": run.get("id"),
                               "status": run.get("status")})
    return active


def _unassessed(state: str, reason: str, targets: tuple[str, ...] = TARGETS) -> list[dict[str, Any]]:
    """Rows for targets this plan records but deliberately does not assess."""
    return [_row(slug, state=state, reason=reason, assessed=False) for slug in targets]


def require_full_coverage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A plan row for every declared target, exactly once, in declaration order.

    A target missing from a plan receipt is indistinguishable from a target
    nobody evaluated, which is how Lyte's drift could look silent; an
    incomplete assessment therefore fails the plan instead.
    """
    observed = [row.get("target") for row in rows]
    if observed != list(TARGETS):
        raise RuntimeError(f"plan does not cover the declared vertical estate {list(TARGETS)}: {observed}")
    return rows


def plan(*, event: str, scope: str, head: str, main_tip: str,
         assess_fn: Callable[..., list[dict[str, Any]]] = assess,
         dispatched_writers: Callable[[], list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"schema": "szl.vertical-convergence-plan/v3", "event": event,
                              "scope": scope, "head": head, "main": main_tip,
                              "declared_targets": list(TARGETS),
                              "observed_at": iso(utc_now()), "targets": [], "matrix": []}
    if event == "workflow_dispatch":
        if scope == "estate":
            result["mode"] = "ESTATE_DISPATCH"
            result["targets"] = _unassessed(
                "FORCED", "operator estate dispatch publishes every flagship target (and the combined "
                "SZLHOLDINGS/vertical-services runtime, whose drift szl-holdings/vertical-services owns)")
            return result
        if scope not in TARGETS:
            raise ValueError(f"unknown dispatch scope: {scope}")
        # An explicit targeted repair publishes regardless of convergence.
        result["mode"] = "TARGETED_REPAIR"
        result["matrix"] = [{"target": scope, "forced": True}]
        result["targets"] = [
            _row(slug, assessed=False, **(
                {"state": "FORCED", "reason": "operator targeted repair publishes regardless of convergence"}
                if slug == scope else
                {"state": "OUT_OF_SCOPE", "reason": f"operator dispatch scope is {scope}; this Space is preserved"}))
            for slug in TARGETS]
        return result
    result["mode"] = "CONVERGENCE"
    if head != main_tip:
        result["superseded_by"] = main_tip
        # Rendering a stale checkout would compare the Spaces with bytes main
        # no longer publishes; the newer main's run assesses them.
        result["targets"] = _unassessed("SUPERSEDED", (
            f"main moved to {main_tip}; that revision's run or the next hourly plan assesses this target"))
        return result
    if dispatched_writers is not None:
        active = dispatched_writers()
        if active:
            # The dispatched writer owns the vertical writer group; the next
            # hourly plan re-checks every target after it finishes. A Space
            # it is writing is not assessed mid-write.
            result["deferred_to"] = active
            result["targets"] = _unassessed("DEFERRED", "a dispatched vertical writer run is active: " + ", ".join(
                f"{row['workflow']} {row['run_id']}" for row in active))
            return result
    # Every automatic event assesses the full estate. A completed canonical
    # deploy mainly changes what Finance must bind, but planning only Finance
    # there left the other targets (Lyte among them) out of that receipt.
    rows = require_full_coverage(assess_fn(TARGETS, head=head))
    result["targets"] = rows
    result["matrix"] = [{"target": row["target"], "forced": False} for row in rows if row["publish"]]
    return result


def plan_target_lines(result: dict[str, Any]) -> list[str]:
    """The writer job's work list: one ``target forced`` line per planned entry."""
    lines = []
    for entry in result.get("matrix", []):
        target, forced = entry.get("target"), entry.get("forced")
        if target not in TARGETS or type(forced) is not bool:
            raise ValueError(f"invalid plan entry: {entry!r}")
        lines.append(f"{target} {'true' if forced else 'false'}")
    return lines


# -------------------------------------------------------------------- sentra


def wait_for_sentra_admission(timeout_s: float, *, interval_s: float = 60.0,
                              sleep: Callable[[float], None] = time.sleep,
                              clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """Wait until Sentra's exact-source admission can pass, without publishing.

    Sentra admits only the protected main tip whose required checks completed
    successfully. A push run starts while those checks still run, so it waits
    for them; a moved main is supersession and a failed check is a block.
    """
    entrypoint = _load("szl_vertical_convergence_sentra", ROOT / "scripts/hf_publish_vertical_flagships_v4.py")
    deadline = clock() + timeout_s
    while True:
        try:
            revision = entrypoint._sentra_source_admission()
            return {"state": "ADMISSIBLE", "revision": revision}
        except entrypoint.SentraSourceSuperseded as exc:
            return {"state": "SUPERSEDED", "reason": str(exc)}
        except entrypoint.SentraChecksPending as exc:
            if clock() >= deadline:
                return {"state": "BLOCKED", "reason": f"{exc} after waiting {int(timeout_s)} s"}
        except entrypoint.SentraPublicationError as exc:
            # A failed check, a bad signature or a policy defect is a block. A
            # transient GitHub read (5xx, 429, rate-limited 403) is retried.
            status = getattr(exc, "http_status", None)
            if not (isinstance(status, int) and (status >= 500 or status in (403, 429))):
                return {"state": "BLOCKED", "reason": str(exc)}
            if clock() >= deadline:
                return {"state": "BLOCKED", "reason": (
                    f"GitHub source evidence stayed unavailable (HTTP {status}) for {int(timeout_s)} s")}
        except (OSError, ValueError) as exc:  # URLError, timeouts, truncated JSON
            if clock() >= deadline:
                return {"state": "BLOCKED", "reason": (
                    f"GitHub source evidence stayed unreadable ({type(exc).__name__}) "
                    f"for {int(timeout_s)} s")}
        sleep(interval_s)


# --------------------------------------------------------------------- report


def drift_age_hours(row: dict[str, Any], now: dt.datetime) -> float | None:
    since = parse_time(row.get("drift_since"))
    if since is None:
        return None
    return max(0.0, (now - since).total_seconds() / 3600.0)


# States that alert once they persist past the threshold (or at once when
# undatable). UNOBSERVABLE (a Hub or GitHub read failed) and RUNTIME_SLEEPING
# never count as converged, so they keep an open tracker open, but a provider
# read failure alone does not open one.
DRIFT_STATES = ("DRIFT", "BLOCKED", "RUNTIME_DRIFT", "RUNTIME_UNAVAILABLE", "UNPLANNED")
# A drift the automatic writer is excluded from never converges on its own, so
# waiting out the threshold would only delay the operator action it needs.
IMMEDIATE_ALERT_STATES = ("UNPLANNED",)


def report(rows: list[dict[str, Any]], *, head: str, threshold_hours: float,
           now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or utc_now()
    alerting = []
    for row in rows:
        age = drift_age_hours(row, now) if row["state"] in DRIFT_STATES else None
        row["drift_age_hours"] = None if age is None else round(age, 2)
        # A drift without a datable start is reported as persistent: an
        # undatable drift must not stay silent forever.
        row["alert"] = row["state"] in DRIFT_STATES and (
            row["state"] in IMMEDIATE_ALERT_STATES or age is None or age >= threshold_hours)
        if row["alert"]:
            alerting.append(row["target"])
    return {
        "schema": "szl.vertical-drift-report/v1", "observed_at": iso(now), "main": head,
        "threshold_hours": threshold_hours, "targets": rows, "alerting": alerting,
        "converged": all(row["state"] == "CONVERGED" for row in rows),
        "unobservable": [row["target"] for row in rows
                         if row["state"] in ("UNOBSERVABLE", "RUNTIME_SLEEPING")],
    }


def render_issue(result: dict[str, Any], *, run_url: str | None) -> tuple[str, str]:
    alerting = result["alerting"]
    states = {row["target"]: row["state"] for row in result["targets"]}
    needs_operator = [t for t in alerting if states.get(t) in IMMEDIATE_ALERT_STATES]
    persistent = [t for t in alerting if t not in needs_operator]
    parts = ([f"{', '.join(needs_operator)} needs an operator publish"] if needs_operator else []) + (
        [f"{', '.join(persistent)} beyond {result['threshold_hours']:g} h"] if persistent else [])
    title = ("Vertical Space drift: " + "; ".join(parts)
             if alerting else "Vertical Space drift: below alert threshold")
    lines = [TRACKER_MARKER, "",
             "Automated by `.github/workflows/hf-vertical-drift.yml` "
             "(`scripts/hf_vertical_convergence.py report`). This issue stays open while any "
             "vertical Space differs from what main would publish and closes when all converge.",
             "", f"- Observed: `{result['observed_at']}`", f"- main: `{result['main']}`",
             f"- Alert threshold: {result['threshold_hours']:g} h"]
    if run_url:
        lines.append(f"- Run: {run_url}")
    lines += ["", "| Target | State | Served revision | Drift since | Age (h) | Reason |",
              "|---|---|---|---|---|---|"]
    for row in result["targets"]:
        served = row.get("served_revision")
        served = f"`{served[:12]}`" if isinstance(served, str) and served else "-"
        age = row.get("drift_age_hours")
        reason = " ".join(str(row.get("reason") or "").split()).replace("|", "\\|")[:600]
        lines.append(f"| {row['target']} | {row['state']}{' (alert)' if row.get('alert') else ''} | "
                     f"{served} | {row.get('drift_since') or '-'} | {'-' if age is None else age} | {reason} |")
    lines += ["", "Convergence runs hourly and on every main push that changes a publisher "
              "input (`.github/workflows/hf-publish-vertical-flagships.yml`). A target "
              "marked BLOCKED or RUNTIME_UNAVAILABLE is not repaired by an automatic "
              "publish; its reason names the precondition or the observed runtime state. "
              "A target marked UNPLANNED is excluded from the automatic writer and alerts "
              "at once; its reason names why and the operator dispatch that publishes it."]
    return title, "\n".join(lines) + "\n"


def _github_write(method: str, path: str, payload: dict[str, Any]) -> Any:
    token = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to maintain the drift tracker")
    request = urllib.request.Request(
        GITHUB_API + path, method=method, data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                 "Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read() or b"null")


def find_tracker(repository: str, *, read: Callable[[str], Any] = github_json) -> dict[str, Any] | None:
    creator = urllib.parse.quote("github-actions[bot]")
    for page in range(1, 6):
        rows = read(f"/repos/{repository}/issues?state=open&creator={creator}&per_page=100&page={page}")
        if not isinstance(rows, list):
            raise Unavailable("issue listing is not a list")
        for row in rows:
            if (isinstance(row, dict) and "pull_request" not in row
                    and TRACKER_MARKER in str(row.get("body") or "")):
                return row
        if len(rows) < 100:
            return None
    return None


def sync_issue(result: dict[str, Any], repository: str, *, run_url: str | None = None,
               read: Callable[[str], Any] = github_json,
               write: Callable[[str, str, dict[str, Any]], Any] = _github_write) -> dict[str, Any]:
    tracker = find_tracker(repository, read=read)
    title, body = render_issue(result, run_url=run_url)
    if result["alerting"]:
        if tracker is None:
            created = write("POST", f"/repos/{repository}/issues", {"title": title, "body": body})
            return {"action": "opened", "number": (created or {}).get("number")}
        write("PATCH", f"/repos/{repository}/issues/{tracker['number']}", {"title": title, "body": body})
        return {"action": "updated", "number": tracker["number"]}
    if tracker is None:
        return {"action": "none"}
    if result["converged"]:
        write("POST", f"/repos/{repository}/issues/{tracker['number']}/comments",
              {"body": f"All vertical Spaces converged with main `{result['main']}` at "
                       f"`{result['observed_at']}`. Closing."})
        write("PATCH", f"/repos/{repository}/issues/{tracker['number']}",
              {"state": "closed", "state_reason": "completed", "body": body})
        return {"action": "closed", "number": tracker["number"]}
    # Drift remains below the threshold (or a target is unobservable): keep the
    # issue open with current evidence instead of flapping it closed.
    write("PATCH", f"/repos/{repository}/issues/{tracker['number']}", {"title": title, "body": body})
    return {"action": "updated", "number": tracker["number"]}


# ------------------------------------------------------------------------ cli


def _github_output(values: dict[str, str]) -> None:
    path = os.getenv("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def _summary(text: str) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")


def _head() -> str:
    head = (os.getenv("GITHUB_SHA") or git("rev-parse", "HEAD")).strip().lower()
    if SHA40.fullmatch(head) is None:
        raise RuntimeError("an exact head revision is required")
    return head


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--event", default=os.getenv("GITHUB_EVENT_NAME", "schedule"))
    p_plan.add_argument("--scope", default=os.getenv("SZL_FLAGSHIP_SCOPE", ""))
    p_plan.add_argument("--output", default="hf-vertical-convergence-plan.json")
    p_plan.add_argument("--defer-to-dispatched-writers", action="store_true",
                        help="publish nothing while a dispatched vertical writer run is active")
    p_targets = sub.add_parser("targets", help="print a plan's targets as 'target forced' lines")
    p_targets.add_argument("--plan", required=True)
    p_check = sub.add_parser("check")
    p_check.add_argument("--target", required=True, choices=TARGETS)
    p_wait = sub.add_parser("wait-sentra")
    p_wait.add_argument("--timeout", type=float, default=2400.0)
    p_report = sub.add_parser("report")
    p_report.add_argument("--output", default="hf-vertical-drift-report.json")
    p_report.add_argument("--threshold-hours", type=float, default=DEFAULT_ALERT_HOURS)
    p_report.add_argument("--sync-issue", action="store_true")
    args = parser.parse_args(argv)
    # This tool never writes. It loads the publishers' renderers, so it runs
    # under the same in-process refusal of canonical-Space writes as they do.
    _load("szl_vertical_convergence_space_guard",
          ROOT / "scripts/hf_existing_space_guard.py").refuse_canonical_space_writes()

    if args.command == "plan":
        own_run = os.getenv("GITHUB_RUN_ID")
        result = plan(event=args.event, scope=args.scope, head=_head(),
                      main_tip=current_main() if args.event != "workflow_dispatch" else _head(),
                      dispatched_writers=(lambda: active_dispatched_writers(own_run_id=own_run))
                      if args.defer_to_dispatched_writers else None)
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        if result.get("superseded_by"):
            print(f"::notice::main moved to {result['superseded_by']}; that revision's run "
                  "or the hourly convergence owns publication")
        if result.get("deferred_to"):
            print("::notice::a dispatched vertical writer run is active ("
                  + ", ".join(f"{row['workflow']} {row['run_id']}" for row in result["deferred_to"])
                  + "); it owns the vertical writer group and the next hourly plan re-checks")
        for row in result["targets"]:
            _summary(f"- {row['target']}: {row['state']} - {row.get('reason') or 'converged'}")
            if row["state"] in ("BLOCKED", "UNPLANNED"):
                print(f"::warning::{row['target']} is {row['state']}: {row['reason']}")
        estate = result.get("mode") == "ESTATE_DISPATCH"
        _github_output({"mode": result["mode"],
                        "publish": "true" if result["matrix"] else "false",
                        "estate": "true" if estate else "false"})
        return 0
    if args.command == "targets":
        for line in plan_target_lines(json.loads(Path(args.plan).read_text(encoding="utf-8"))):
            print(line)
        return 0
    if args.command == "check":
        head = _head()
        if head != current_main():
            print("::notice::main moved; this convergence job is superseded")
            _github_output({"publish": "false", "state": "SUPERSEDED"})
            return 0
        row = assess((args.target,), head=head)[0]
        print(json.dumps(row, indent=2, sort_keys=True))
        _github_output({"publish": "true" if row["publish"] else "false", "state": row["state"]})
        if row["state"] in ("BLOCKED", "UNPLANNED"):
            print(f"::warning::{args.target} is {row['state']}: {row['reason']}")
        return 0
    if args.command == "wait-sentra":
        outcome = wait_for_sentra_admission(args.timeout)
        print(json.dumps(outcome, indent=2, sort_keys=True))
        _github_output({"state": outcome["state"]})
        return 0
    head = _head()
    result = report(require_full_coverage(assess(TARGETS, head=head)), head=head,
                    threshold_hours=args.threshold_hours)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    run_url = None
    if os.getenv("GITHUB_RUN_ID") and os.getenv("GITHUB_REPOSITORY"):
        run_url = (f"{os.getenv('GITHUB_SERVER_URL', 'https://github.com')}/"
                   f"{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}")
    _summary(render_issue(result, run_url=run_url)[1])
    if args.sync_issue:
        outcome = sync_issue(result, os.getenv("GITHUB_REPOSITORY", REPOSITORY), run_url=run_url)
        print(json.dumps({"tracker": outcome}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
