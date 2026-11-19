# SPDX-License-Identifier: Apache-2.0
"""Regression guard for Docker daemon import depth on PR image builds."""

import hashlib
import json
from pathlib import Path
import shlex

from scripts.build_gdw_installed_source_manifest import _instructions


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
BUILD_WORKFLOW = ROOT / ".github" / "workflows" / "docker-build.yml"
# Prior admitted af0026 has 110 COPY + 7 RUN instructions in runtime.
# The readiness verdict validator needs one dedicated COPY: relocating its
# Python source fails the installed-source provenance guard. The native image
# build passed with this additional instruction; keep its increase explicit.
RUNTIME_LAYER_BUDGET = 118
# Exact base 5ec5b66 has 579 explicit COPY sources with SHA-256
# aa11d167572da80452e1247815b1a0e08bbd9ba206f4d859b0b26f8d84ffc48e.
# Steward adds only its four named adapter/reader/projection/lock files, batched
# into one COPY; no original source is removed and the layer budget is unchanged.
# The civilian services surface adds exactly its registrar and package directory.
# The public HF inventory repair adds exactly three reviewed docs sources; the
# prior 585-source allowlist remains pinned separately below.
# Model support adds only its runtime reader and source catalog. Each baseline
# below excludes those two named additions so its historical digest is retained.
# The GDW orphan-page repair adds exactly its one module next to gdw_runtime.py;
# every baseline below also excludes it, so no historical count/digest moves.
# Meter2 Access adds exactly one runtime helper; historical baselines exclude it.
# The run-loop journey witness is one module copied beside a11oy_code_runloop.py.
# Historical baselines exclude it, so their counts and digests stay put.
# Action identity is one module copied beside that journey witness.
# Historical baselines exclude it, so their counts and digests stay put.
# The A11oy wake-receipt route is one module batched into an existing root COPY.
# Historical baselines exclude it, so their counts and digests stay put.
# Org-RAG reference auth is one module batched beside szl_meter_access.py.
# Historical baselines exclude it, so their counts and digests stay put.
# The a11oy state store (ADR-0001) is one module copied into the existing GDW
# COPY instruction; historical baselines exclude it and the budget is unchanged.
# The Python command-centre projection adds only its canonical public binding,
# batched with existing shared assets; historical counts and digests stay put.
# Readiness artifact reading adds its one module and the canonical pure verdict
# validator. The latter keeps its source path with a dedicated COPY instruction.
# Historical baselines exclude these exact sources.
# Preserve every prior source and the unchanged layer budget, not a broad COPY.
RUNTIME_IDENTITY_COPY_ADDITIONS = {".szl-runtime-marker.json", "szl_runtime_identity.py", ".github/workflows/hf-sync.yml"}
# One adapter and one canonical package, with adjacent root COPY lines batched
# to retain the existing layer ceiling and every previous source identity.
REPLICATION_COPY_ADDITIONS = {"szl_khipu_delivery_routes.py", "khipu_lmdb/"}
# Shared passive signer observation adds one provenance module to the existing
# runtime-identity COPY. All three historical counts and digests stay unchanged.
SIGNING_STATE_COPY_ADDITIONS = {"szl_signing_state.py"}
# The master implementation workcell adds one module to the root COPY batch and
# one DAG artifact to the genome data COPY. All three historical counts and
# digests stay unchanged.
MASTER_WORKCELL_COPY_ADDITIONS = {
    "szl_master_workcell.py",
    "data/master_workcell_dag_20261027.json",
}

# The RAG synthesis controller is imported by a11oy_code_orchestrator and copied
# on that same root COPY line. Historical allowlist counts and digests stay put.
RAG_SYNTHESIS_CONTROLLER_COPY_ADDITIONS = {"a11oy_rag_synthesis_controller.py"}

# The generated x402 price manifest is batched into the existing security.txt COPY
# (same destination directory), so the layer budget is unchanged. Historical
# allowlist counts and digests exclude it.
X402_MANIFEST_COPY_ADDITIONS = {".well-known/x402-pricing.json"}

# One opt-in health-read registrar, batched into the existing origin-admission
# COPY. Every historical source count/digest and layer ceiling stays unchanged.
BUILD_ENV_FANOUT_COPY_ADDITIONS = {"a11oy_build_env_fanout.py"}
# The CEG registrar, offline reader/catalog and inspector assets are batched
# into existing root/shared COPY instructions. Historical source digests and
# the layer ceiling remain unchanged; only these exact additions are excluded.
EVIDENCE_GRAPH_COPY_ADDITIONS = {
    "szl_evidence_graph.py", "szl_evidence_discovery.py",
    "szl_evidence_receipts.py", "evidence_graph_receipts.json",
    "static/shared/ceg-explorer.js", "static/shared/ceg-explorer.css",
}
# One explicit telemetry module; prior source digests and layer budget stay fixed.
TRACE_OBSERVATION_COPY_ADDITIONS = {"vsp_otel/trace_ir.py"}

# The bounded ORO evidence package uses the layer saved by batching two
# adjacent root COPY instructions. Every historical source digest stays intact.
ORO_EVIDENCE_COPY_ADDITIONS = {"oro/"}
# The governed CPU lab uses one pure contract adapter in the existing root COPY.
# Exclude only that named addition from each frozen historical source set.
CPU_LAB_CONTRACT_COPY_ADDITIONS = {"a11oy_cpu_lab_contract.py"}
# One bounded numerical research kernel is batched beside the existing qbio
# module. Freeze every historical source digest by excluding this exact source.
FLAVIN_SPIN_COPY_ADDITIONS = {"szl_flavin_spin_research.py"}

# One pool-receipt ingestion surface, batched into the existing root COPY beside
# the compute-pool contract it reuses; every historical source digest and count
# stays frozen by excluding this exact addition below.
POOL_RECEIPT_INGEST_COPY_ADDITIONS = {"szl_pool_receipt_ingest.py"}

COPY_SOURCE_ALLOWLIST_COUNT = 589
COPY_SOURCE_ALLOWLIST_SHA256 = (
    "4f4d797eac48f0cd845f4fce9869aa9a25aabc6ab321cf3dd48934be07d2c8b1"
)
PRE_CIVILIAN_ALLOWLIST_COUNT = 587
PRE_CIVILIAN_ALLOWLIST_SHA256 = (
    "5acdb5896a48c2e6d347d74c295893d8bd59d1a4c844519222ed6e2168eadec1"
)
PRE_HF_DOCS_ALLOWLIST_COUNT = 586
PRE_HF_DOCS_ALLOWLIST_SHA256 = (
    "0de3b7f1c6ef5dcf60e9d54f8988b32760a1d16e296fb9f1b584481e6f05656c"
)
HF_DOCS_COPY_ADDITIONS = {
    "docs/huggingface-ecosystem-manifest.json",
    "docs/huggingface-ecosystem-manifest.schema.json",
    "docs/huggingface.md",
}
CIVILIAN_COPY_ADDITIONS = {
    "a11oy_civilian_observatory.py",
    "civilian_observatory/",
}
MODEL_SUPPORT_COPY_ADDITIONS = {
    "a11oy_model_support.py",
    "docs/model-inference-support.json",
}
X402_ORIGIN_COPY_ADDITIONS = {
    "a11oy_x402_admission.py",
    "szl_trust_x402_payment_context.py",
}

# Exact acquisition additions. Keep all historical source counts/digests below;
# requirements-runtime.txt was already present and is not an addition.
GDW_ACQUISITION_COPY_ADDITIONS = {
    "gdw_durable_runtime.py", "gdw_durable_artifacts.py",
    "gdw_durable_startup.py", "gdw_durable_storage.py",
    "gdw_durable_source.py", "gdw_durable_guard.py", "gdw_durable_image.py",
    "Dockerfile", "scripts/verify_installed_authority.py",
}
# Exact orphan-page repair addition (imported by gdw_runtime.py).
GDW_ORPHAN_REPAIR_COPY_ADDITIONS = {"gdw_sqlite_repair.py"}
METER_ACCESS_COPY_ADDITIONS = {"szl_meter_access.py"}
# One pure model authentication helper shares that COPY without adding a layer.
MODEL_ACCESS_COPY_ADDITIONS = {"szl_model_access.py"}
RUNLOOP_JOURNEY_COPY_ADDITIONS = {"a11oy_code_runloop_journey.py"}
ACTION_IDENTITY_COPY_ADDITIONS = {"szl_action_identity.py"}
WAKE_ROUTE_COPY_ADDITIONS = {"szl_kernels_organ.py"}
RAG_REFERENCE_AUTH_COPY_ADDITIONS = {"a11oy_rag_reference_auth.py"}
STATE_STORE_COPY_ADDITIONS = {"a11oy_state_store.py"}
PUBLIC_ESTATE_COPY_ADDITIONS = {"static/shared/public-estate-contract.v1.json"}
# Exact observer/native-adapter/consumer additions; prior source pins stay intact.
# Consolidating two adjacent root COPY instructions pays for the parser's own
# exact tools/ path without increasing the 118-layer ceiling.
EXECUTION_OBSERVER_COPY_ADDITIONS = {
    "observer_runtime.py", "observer_adapters.py", "native_readbacks.py",
    "szl_execution_readiness.py", "tools/execution_acceptance.py", "tools/__init__.py",
}
READINESS_READER_COPY_ADDITIONS = {
    "szl_readiness_artifact.py", ".github/scripts/publish_readiness_verdict.py",
}


def _logical_instructions() -> list[tuple[int, str]]:
    # Reuse the reviewed, bounded Docker parser: RUN heredoc bodies can contain
    # Python strings beginning with FROM/COPY and must not alter stage counting.
    _text, instructions = _instructions(DOCKERFILE.read_bytes())
    return [(index, line) for index, (_kind, _arguments, line)
            in enumerate(instructions, 1)]


def _runtime_filesystem_instructions() -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    in_runtime = False
    for line_number, line in _logical_instructions():
        if line.upper().startswith("FROM "):
            in_runtime = line.upper().endswith(" AS RUNTIME")
            continue
        if not in_runtime:
            continue
        instruction = line.split(maxsplit=1)[0].upper()
        if instruction in {"RUN", "COPY", "ADD"}:
            rows.append((line_number, instruction))
    return rows


def _copy_sources(instruction: str) -> list[str]:
    payload = instruction.split(maxsplit=1)[1].strip()
    if payload.startswith("["):
        values = json.loads(payload)
        return values[:-1]
    values = shlex.split(payload)
    while values and values[0].startswith("--"):
        values.pop(0)
    return values[:-1]


def test_runtime_image_stays_below_docker_layer_depth_budget() -> None:
    """Preserve the prior admitted source depth and the real PR image-load gate."""
    rows = _runtime_filesystem_instructions()
    assert len(rows) <= RUNTIME_LAYER_BUDGET, (
        f"runtime stage has {len(rows)} filesystem instructions; "
        f"budget is {RUNTIME_LAYER_BUDGET}. Batch explicit COPY sources instead "
        "of disabling the PR image load and smoke test."
    )


def test_layer_batching_keeps_the_explicit_source_allowlist() -> None:
    workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
    copy_sources = {
        source
        for _line, instruction in _logical_instructions()
        if instruction.upper().startswith("COPY ")
        for source in _copy_sources(instruction)
    }
    assert "." not in copy_sources
    assert "./" not in copy_sources
    assert MODEL_SUPPORT_COPY_ADDITIONS <= copy_sources
    assert X402_ORIGIN_COPY_ADDITIONS <= copy_sources
    assert GDW_ACQUISITION_COPY_ADDITIONS <= copy_sources
    assert GDW_ORPHAN_REPAIR_COPY_ADDITIONS <= copy_sources
    assert METER_ACCESS_COPY_ADDITIONS <= copy_sources
    assert MODEL_ACCESS_COPY_ADDITIONS <= copy_sources
    assert RUNLOOP_JOURNEY_COPY_ADDITIONS <= copy_sources
    assert ACTION_IDENTITY_COPY_ADDITIONS <= copy_sources
    assert WAKE_ROUTE_COPY_ADDITIONS <= copy_sources
    assert RAG_REFERENCE_AUTH_COPY_ADDITIONS <= copy_sources
    assert STATE_STORE_COPY_ADDITIONS <= copy_sources
    assert PUBLIC_ESTATE_COPY_ADDITIONS <= copy_sources
    assert READINESS_READER_COPY_ADDITIONS <= copy_sources
    assert EXECUTION_OBSERVER_COPY_ADDITIONS <= copy_sources
    assert RUNTIME_IDENTITY_COPY_ADDITIONS <= copy_sources
    assert REPLICATION_COPY_ADDITIONS <= copy_sources
    assert SIGNING_STATE_COPY_ADDITIONS <= copy_sources
    assert MASTER_WORKCELL_COPY_ADDITIONS <= copy_sources
    assert RAG_SYNTHESIS_CONTROLLER_COPY_ADDITIONS <= copy_sources
    assert X402_MANIFEST_COPY_ADDITIONS <= copy_sources
    assert BUILD_ENV_FANOUT_COPY_ADDITIONS <= copy_sources
    assert EVIDENCE_GRAPH_COPY_ADDITIONS <= copy_sources
    assert TRACE_OBSERVATION_COPY_ADDITIONS <= copy_sources
    assert ORO_EVIDENCE_COPY_ADDITIONS <= copy_sources
    assert CPU_LAB_CONTRACT_COPY_ADDITIONS <= copy_sources
    assert FLAVIN_SPIN_COPY_ADDITIONS <= copy_sources
    assert POOL_RECEIPT_INGEST_COPY_ADDITIONS <= copy_sources
    copy_sources -= (
        MODEL_SUPPORT_COPY_ADDITIONS
        | X402_ORIGIN_COPY_ADDITIONS
        | GDW_ACQUISITION_COPY_ADDITIONS
        | GDW_ORPHAN_REPAIR_COPY_ADDITIONS
        | METER_ACCESS_COPY_ADDITIONS
        | MODEL_ACCESS_COPY_ADDITIONS
        | RUNLOOP_JOURNEY_COPY_ADDITIONS
        | ACTION_IDENTITY_COPY_ADDITIONS
        | WAKE_ROUTE_COPY_ADDITIONS
        | RAG_REFERENCE_AUTH_COPY_ADDITIONS
        | STATE_STORE_COPY_ADDITIONS
        | PUBLIC_ESTATE_COPY_ADDITIONS
        | READINESS_READER_COPY_ADDITIONS
        | EXECUTION_OBSERVER_COPY_ADDITIONS
        | RUNTIME_IDENTITY_COPY_ADDITIONS
        | REPLICATION_COPY_ADDITIONS
        | SIGNING_STATE_COPY_ADDITIONS
        | MASTER_WORKCELL_COPY_ADDITIONS
        | RAG_SYNTHESIS_CONTROLLER_COPY_ADDITIONS
        | PUBLIC_ESTATE_COPY_ADDITIONS
        | X402_MANIFEST_COPY_ADDITIONS
        | BUILD_ENV_FANOUT_COPY_ADDITIONS
        | EVIDENCE_GRAPH_COPY_ADDITIONS
        | TRACE_OBSERVATION_COPY_ADDITIONS
        | ORO_EVIDENCE_COPY_ADDITIONS
        | CPU_LAB_CONTRACT_COPY_ADDITIONS
        | FLAVIN_SPIN_COPY_ADDITIONS
        | POOL_RECEIPT_INGEST_COPY_ADDITIONS
    )
    encoded_allowlist = ("\n".join(sorted(copy_sources)) + "\n").encode("utf-8")
    assert len(copy_sources) == COPY_SOURCE_ALLOWLIST_COUNT
    assert hashlib.sha256(encoded_allowlist).hexdigest() == COPY_SOURCE_ALLOWLIST_SHA256
    assert "load: ${{ github.event_name == 'pull_request' }}" in workflow
    assert "Smoke test image (PR builds — loaded into local daemon)" in workflow


def test_civilian_packaging_preserves_every_previous_source() -> None:
    sources = {
        source
        for _line, instruction in _logical_instructions()
        if instruction.upper().startswith("COPY ")
        for source in _copy_sources(instruction)
    }
    assert CIVILIAN_COPY_ADDITIONS <= sources
    assert MODEL_SUPPORT_COPY_ADDITIONS <= sources
    assert X402_ORIGIN_COPY_ADDITIONS <= sources
    assert GDW_ACQUISITION_COPY_ADDITIONS <= sources
    assert GDW_ORPHAN_REPAIR_COPY_ADDITIONS <= sources
    assert METER_ACCESS_COPY_ADDITIONS <= sources
    assert MODEL_ACCESS_COPY_ADDITIONS <= sources
    assert RUNLOOP_JOURNEY_COPY_ADDITIONS <= sources
    assert ACTION_IDENTITY_COPY_ADDITIONS <= sources
    assert WAKE_ROUTE_COPY_ADDITIONS <= sources
    assert RAG_REFERENCE_AUTH_COPY_ADDITIONS <= sources
    assert STATE_STORE_COPY_ADDITIONS <= sources
    assert PUBLIC_ESTATE_COPY_ADDITIONS <= sources
    assert READINESS_READER_COPY_ADDITIONS <= sources
    assert EXECUTION_OBSERVER_COPY_ADDITIONS <= sources
    assert RUNTIME_IDENTITY_COPY_ADDITIONS <= sources
    assert REPLICATION_COPY_ADDITIONS <= sources
    assert SIGNING_STATE_COPY_ADDITIONS <= sources
    assert MASTER_WORKCELL_COPY_ADDITIONS <= sources
    assert RAG_SYNTHESIS_CONTROLLER_COPY_ADDITIONS <= sources
    assert X402_MANIFEST_COPY_ADDITIONS <= sources
    assert BUILD_ENV_FANOUT_COPY_ADDITIONS <= sources
    assert EVIDENCE_GRAPH_COPY_ADDITIONS <= sources
    assert TRACE_OBSERVATION_COPY_ADDITIONS <= sources
    assert ORO_EVIDENCE_COPY_ADDITIONS <= sources
    assert CPU_LAB_CONTRACT_COPY_ADDITIONS <= sources
    assert FLAVIN_SPIN_COPY_ADDITIONS <= sources
    assert POOL_RECEIPT_INGEST_COPY_ADDITIONS <= sources
    previous = (
        sources - CIVILIAN_COPY_ADDITIONS - MODEL_SUPPORT_COPY_ADDITIONS
        - X402_ORIGIN_COPY_ADDITIONS
        - GDW_ACQUISITION_COPY_ADDITIONS - GDW_ORPHAN_REPAIR_COPY_ADDITIONS
        - METER_ACCESS_COPY_ADDITIONS - RUNLOOP_JOURNEY_COPY_ADDITIONS
        - MODEL_ACCESS_COPY_ADDITIONS
        - ACTION_IDENTITY_COPY_ADDITIONS - RAG_REFERENCE_AUTH_COPY_ADDITIONS
        - WAKE_ROUTE_COPY_ADDITIONS
        - STATE_STORE_COPY_ADDITIONS
        - PUBLIC_ESTATE_COPY_ADDITIONS
        - READINESS_READER_COPY_ADDITIONS
        - EXECUTION_OBSERVER_COPY_ADDITIONS
        - RUNTIME_IDENTITY_COPY_ADDITIONS
        - REPLICATION_COPY_ADDITIONS
        - SIGNING_STATE_COPY_ADDITIONS
        - MASTER_WORKCELL_COPY_ADDITIONS
        - RAG_SYNTHESIS_CONTROLLER_COPY_ADDITIONS
        - PUBLIC_ESTATE_COPY_ADDITIONS
        - X402_MANIFEST_COPY_ADDITIONS
        - BUILD_ENV_FANOUT_COPY_ADDITIONS
        - EVIDENCE_GRAPH_COPY_ADDITIONS
        - TRACE_OBSERVATION_COPY_ADDITIONS
        - ORO_EVIDENCE_COPY_ADDITIONS
        - CPU_LAB_CONTRACT_COPY_ADDITIONS
        - FLAVIN_SPIN_COPY_ADDITIONS
        - POOL_RECEIPT_INGEST_COPY_ADDITIONS
    )
    encoded = ("\n".join(sorted(previous)) + "\n").encode("utf-8")
    assert len(previous) == PRE_CIVILIAN_ALLOWLIST_COUNT
    assert hashlib.sha256(encoded).hexdigest() == PRE_CIVILIAN_ALLOWLIST_SHA256


def test_public_hf_docs_preserve_the_previous_copy_allowlist() -> None:
    sources = {
        source
        for _line, instruction in _logical_instructions()
        if instruction.upper().startswith("COPY ")
        for source in _copy_sources(instruction)
    }
    assert HF_DOCS_COPY_ADDITIONS <= sources
    assert MODEL_SUPPORT_COPY_ADDITIONS <= sources
    assert X402_ORIGIN_COPY_ADDITIONS <= sources
    assert GDW_ACQUISITION_COPY_ADDITIONS <= sources
    assert GDW_ORPHAN_REPAIR_COPY_ADDITIONS <= sources
    assert METER_ACCESS_COPY_ADDITIONS <= sources
    assert MODEL_ACCESS_COPY_ADDITIONS <= sources
    assert RUNLOOP_JOURNEY_COPY_ADDITIONS <= sources
    assert ACTION_IDENTITY_COPY_ADDITIONS <= sources
    assert WAKE_ROUTE_COPY_ADDITIONS <= sources
    assert RAG_REFERENCE_AUTH_COPY_ADDITIONS <= sources
    assert STATE_STORE_COPY_ADDITIONS <= sources
    assert PUBLIC_ESTATE_COPY_ADDITIONS <= sources
    assert READINESS_READER_COPY_ADDITIONS <= sources
    assert EXECUTION_OBSERVER_COPY_ADDITIONS <= sources
    assert RUNTIME_IDENTITY_COPY_ADDITIONS <= sources
    assert REPLICATION_COPY_ADDITIONS <= sources
    assert SIGNING_STATE_COPY_ADDITIONS <= sources
    assert MASTER_WORKCELL_COPY_ADDITIONS <= sources
    assert RAG_SYNTHESIS_CONTROLLER_COPY_ADDITIONS <= sources
    assert X402_MANIFEST_COPY_ADDITIONS <= sources
    assert BUILD_ENV_FANOUT_COPY_ADDITIONS <= sources
    assert EVIDENCE_GRAPH_COPY_ADDITIONS <= sources
    assert TRACE_OBSERVATION_COPY_ADDITIONS <= sources
    assert ORO_EVIDENCE_COPY_ADDITIONS <= sources
    assert CPU_LAB_CONTRACT_COPY_ADDITIONS <= sources
    assert FLAVIN_SPIN_COPY_ADDITIONS <= sources
    assert POOL_RECEIPT_INGEST_COPY_ADDITIONS <= sources
    previous = (
        sources - HF_DOCS_COPY_ADDITIONS - MODEL_SUPPORT_COPY_ADDITIONS
        - X402_ORIGIN_COPY_ADDITIONS
        - GDW_ACQUISITION_COPY_ADDITIONS - GDW_ORPHAN_REPAIR_COPY_ADDITIONS
        - METER_ACCESS_COPY_ADDITIONS - RUNLOOP_JOURNEY_COPY_ADDITIONS
        - MODEL_ACCESS_COPY_ADDITIONS
        - ACTION_IDENTITY_COPY_ADDITIONS - RAG_REFERENCE_AUTH_COPY_ADDITIONS
        - WAKE_ROUTE_COPY_ADDITIONS
        - STATE_STORE_COPY_ADDITIONS
        - PUBLIC_ESTATE_COPY_ADDITIONS
        - READINESS_READER_COPY_ADDITIONS
        - EXECUTION_OBSERVER_COPY_ADDITIONS
        - RUNTIME_IDENTITY_COPY_ADDITIONS
        - REPLICATION_COPY_ADDITIONS
        - SIGNING_STATE_COPY_ADDITIONS
        - MASTER_WORKCELL_COPY_ADDITIONS
        - RAG_SYNTHESIS_CONTROLLER_COPY_ADDITIONS
        - PUBLIC_ESTATE_COPY_ADDITIONS
        - X402_MANIFEST_COPY_ADDITIONS
        - BUILD_ENV_FANOUT_COPY_ADDITIONS
        - EVIDENCE_GRAPH_COPY_ADDITIONS
        - TRACE_OBSERVATION_COPY_ADDITIONS
        - ORO_EVIDENCE_COPY_ADDITIONS
        - CPU_LAB_CONTRACT_COPY_ADDITIONS
        - FLAVIN_SPIN_COPY_ADDITIONS
        - POOL_RECEIPT_INGEST_COPY_ADDITIONS
    )
    encoded = ("\n".join(sorted(previous)) + "\n").encode("utf-8")
    assert len(previous) == PRE_HF_DOCS_ALLOWLIST_COUNT
    assert hashlib.sha256(encoded).hexdigest() == PRE_HF_DOCS_ALLOWLIST_SHA256


def test_public_estate_binding_ships_at_the_runtime_reader_path() -> None:
    """Local renderer tests cannot establish that the binding ships in the image."""
    source = "static/shared/public-estate-contract.v1.json"
    destinations = []
    in_runtime = False
    for _line, instruction in _logical_instructions():
        if instruction.upper().startswith("FROM "):
            in_runtime = instruction.upper().endswith(" AS RUNTIME")
        if not in_runtime or not instruction.upper().startswith("COPY "):
            continue
        if source in _copy_sources(instruction):
            payload = instruction.split(maxsplit=1)[1].strip()
            destination = (json.loads(payload)[-1] if payload.startswith("[")
                           else shlex.split(payload)[-1])
            target = Path(destination)
            if destination.endswith("/"):
                target /= Path(source).name
            destinations.append(target.as_posix())
    assert destinations == [source]


def test_signing_state_is_batched_once_with_runtime_identity() -> None:
    rows = [instruction for _line, instruction in _logical_instructions()
            if instruction.upper().startswith("COPY ")
            and "szl_signing_state.py" in _copy_sources(instruction)]
    assert len(rows) == 1
    assert "szl_runtime_identity.py" in _copy_sources(rows[0])
    assert shlex.split(rows[0])[-1] == "./"


def test_master_workcell_is_batched_into_existing_layers() -> None:
    rows = [instruction for _line, instruction in _logical_instructions()
            if instruction.upper().startswith("COPY ")
            and MASTER_WORKCELL_COPY_ADDITIONS & set(_copy_sources(instruction))]
    assert len(rows) == 2
    module_row = next(row for row in rows if "szl_master_workcell.py" in _copy_sources(row))
    assert "szl_runtime_identity.py" in _copy_sources(module_row)
    assert shlex.split(module_row)[-1] == "./"
    data_row = next(row for row in rows
                    if "data/master_workcell_dag_20261027.json" in _copy_sources(row))
    assert "data/genome.json" in _copy_sources(data_row)
    assert shlex.split(data_row)[-1] == "./data/"


def test_build_env_fanout_is_batched_once_with_the_existing_origin_module() -> None:
    rows = [instruction for _line, instruction in _logical_instructions()
            if instruction.upper().startswith("COPY ")
            and "a11oy_build_env_fanout.py" in _copy_sources(instruction)]
    assert len(rows) == 1
    assert "a11oy_x402_admission.py" in _copy_sources(rows[0])
    assert shlex.split(rows[0])[-1] == "./"


def test_flavin_spin_research_is_batched_once_without_new_runtime_layer() -> None:
    rows = [instruction for _line, instruction in _logical_instructions()
            if instruction.upper().startswith("COPY ")
            and FLAVIN_SPIN_COPY_ADDITIONS & set(_copy_sources(instruction))]
    assert len(rows) == 1
    assert "szl_quantum_bio.py" in _copy_sources(rows[0])
    assert shlex.split(rows[0])[-1] == "./"
