#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
# Change-class: ADDITIVE - research registry only; no route or UI registration.
"""Primary-source project registry with honest live GitHub metadata.

This module records projects and organizations, not individual people.  The
static registry is deliberately unranked: inclusion means "study this primary
source", not "this is objectively first".  Every adaptation is DECLARED and
attributed ``STUDIED_NOT_COPIED``.

Live stars, detected SPDX license, and the default-branch revision are fetched
from GitHub's API only when explicitly requested.  They are never embedded in
the registry.  A failed or disabled fetch returns null values carrying the
``UNAVAILABLE`` label; it never reuses an expired value as if it were current.

Taxonomy home: research/.  Pure Python standard library; no HTTP framework.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import re
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


REGISTRY_VERSION = "wave-13-primary-projects-v1"
ATTRIBUTION = "STUDIED_NOT_COPIED"
STATIC_LABEL = "DECLARED"
LIVE_LABEL = "MEASURED"
UNAVAILABLE = "UNAVAILABLE"
DEFAULT_TIMEOUT_S = 5.0
DEFAULT_TTL_S = 15 * 60.0
MAX_RESPONSE_BYTES = 2_000_000


_FIELDS: Tuple[Mapping[str, str], ...] = (
    {"id": "reasoning_math", "name": "Reasoning & math"},
    {"id": "quantization_efficient_inference", "name": "Quantization & efficient inference"},
    {"id": "retrieval_memory_long_context", "name": "Retrieval, memory & long context"},
    {"id": "multimodal_vision", "name": "Multimodal & vision"},
    {"id": "biomed_science", "name": "Biomed & science"},
    {"id": "security_red_team", "name": "Security & red-team"},
    {"id": "datasets_curation", "name": "Datasets & curation"},
    {"id": "sovereign_on_metal_serving", "name": "Sovereign / on-metal serving"},
    {
        "id": "verifiable_orchestration_provenance",
        "name": "Verifiable orchestration & provenance",
    },
    {"id": "formal_proof_training", "name": "Formal proof & training"},
)


def _project(
    project_id: str,
    field: str,
    project: str,
    organization: str,
    repo: str,
    license_expected: str,
    primary_paper_docs: Iterable[str],
    adaptation: str,
) -> Mapping[str, Any]:
    return {
        "id": project_id,
        "field": field,
        "project": project,
        "organization": organization,
        "canonical_repo_url": repo,
        "license_expected": license_expected,
        "primary_paper_docs": tuple(primary_paper_docs),
        "szl_adaptation_status": STATIC_LABEL,
        "szl_adaptation": adaptation,
        "attribution": ATTRIBUTION,
    }


# Licenses here are expectations to compare against the live API result, not a
# substitute for inspecting the license at the fetched revision.  UNKNOWN is
# intentional wherever the repository/model license is non-SPDX or uncertain.
_PROJECTS: Tuple[Mapping[str, Any], ...] = (
    # Reasoning & math
    _project("qwen3", "reasoning_math", "Qwen3", "QwenLM", "https://github.com/QwenLM/Qwen3", "Apache-2.0", ("https://arxiv.org/abs/2505.09388",), "Route bounded math prompts through formula-aware evaluation and attach A11oy provenance."),
    _project("deepseek-r1", "reasoning_math", "DeepSeek-R1", "deepseek-ai", "https://github.com/deepseek-ai/DeepSeek-R1", "MIT", ("https://arxiv.org/abs/2501.12948",), "Evaluate explicit reasoning traces against locked-formula and restraint gates before acceptance."),
    _project("kimi-k2-5", "reasoning_math", "Kimi K2.5", "MoonshotAI", "https://github.com/MoonshotAI/Kimi-K2.5", "UNKNOWN", ("https://github.com/MoonshotAI/Kimi-K2.5/blob/main/tech_report.pdf",), "Study long-horizon decomposition while preserving A11oy budgets, receipts, and human override."),
    _project("glm-4-7", "reasoning_math", "GLM-4.7 (GLM-4.5 repository)", "zai-org", "https://github.com/zai-org/GLM-4.5", "MIT", ("https://github.com/zai-org/GLM-4.5",), "Compare tool-using math runs with the same local formula corpus and honesty labels."),
    _project("minimax-m2-5", "reasoning_math", "MiniMax M2.5", "MiniMax-AI", "https://github.com/MiniMax-AI/MiniMax-M2.5", "UNKNOWN", ("https://github.com/MiniMax-AI/MiniMax-M2.5",), "Test agentic reasoning under explicit step, token, thermal, and energy budgets."),

    # Quantization & efficient inference
    _project("llama-cpp-inference", "quantization_efficient_inference", "llama.cpp", "ggml-org", "https://github.com/ggml-org/llama.cpp", "MIT", ("https://github.com/ggml-org/llama.cpp/tree/master/examples/quantize",), "Expose local quantization profiles through a hardware-probed A11oy serving plan."),
    _project("vllm-inference", "quantization_efficient_inference", "vLLM", "vllm-project", "https://github.com/vllm-project/vllm", "Apache-2.0", ("https://github.com/vllm-project/vllm/tree/main/docs",), "Adapt paged serving concepts behind A11oy admission control and measured resource receipts."),
    _project("sglang-inference", "quantization_efficient_inference", "SGLang", "sgl-project", "https://github.com/sgl-project/sglang", "Apache-2.0", ("https://github.com/sgl-project/sglang/tree/main/docs",), "Study structured serving and prefix reuse with tenant isolation and bounded caches."),
    _project("bitnet", "quantization_efficient_inference", "BitNet", "microsoft", "https://github.com/microsoft/BitNet", "MIT", ("https://arxiv.org/abs/2402.17764",), "Benchmark low-bit kernels on the actual laptop before declaring any supported profile."),
    _project("tensorrt-llm", "quantization_efficient_inference", "TensorRT-LLM", "NVIDIA", "https://github.com/NVIDIA/TensorRT-LLM", "Apache-2.0", ("https://github.com/NVIDIA/TensorRT-LLM/tree/main/docs",), "Compare engine plans with reproducible revisions, VRAM evidence, and measured throughput."),

    # Retrieval, memory & long context
    _project("cognee", "retrieval_memory_long_context", "cognee", "topoteretes", "https://github.com/topoteretes/cognee", "Apache-2.0", ("https://github.com/topoteretes/cognee/tree/main/docs",), "Study graph-backed ingestion while retaining A11oy source digests and deletion controls."),
    _project("letta", "retrieval_memory_long_context", "Letta", "letta-ai", "https://github.com/letta-ai/letta", "Apache-2.0", ("https://github.com/letta-ai/letta/tree/main/docs",), "Adapt bounded agent memory with explicit provenance, retention, and operator-visible state."),
    _project("mem0", "retrieval_memory_long_context", "Mem0", "mem0ai", "https://github.com/mem0ai/mem0", "Apache-2.0", ("https://github.com/mem0ai/mem0/tree/main/docs",), "Evaluate memory extraction behind consent, namespace isolation, and auditable forgetting."),
    _project("graphiti", "retrieval_memory_long_context", "Graphiti", "getzep", "https://github.com/getzep/graphiti", "Apache-2.0", ("https://github.com/getzep/graphiti",), "Study temporal knowledge graphs with source-time and ingestion-time retained separately."),
    _project("zep-ce", "retrieval_memory_long_context", "Zep Community Edition", "getzep", "https://github.com/getzep/zep", "Apache-2.0", ("https://github.com/getzep/zep",), "Compare self-hosted memory semantics without claiming parity or importing implementation code."),

    # Multimodal & vision
    _project("qwen3-vl", "multimodal_vision", "Qwen3-VL", "QwenLM", "https://github.com/QwenLM/Qwen3-VL", "Apache-2.0", ("https://github.com/QwenLM/Qwen3-VL",), "Gate image and document observations as cited evidence, never as unqualified ground truth."),
    _project("glm-v", "multimodal_vision", "GLM-V / GLM-4.5V", "zai-org", "https://github.com/zai-org/GLM-V", "MIT", ("https://arxiv.org/abs/2507.01006",), "Study multimodal reasoning with modality-specific confidence and redaction before retention."),
    _project("internvl", "multimodal_vision", "InternVL", "OpenGVLab", "https://github.com/OpenGVLab/InternVL", "MIT", ("https://arxiv.org/abs/2312.14238",), "Evaluate open multimodal checkpoints through a reproducible visual task harness."),
    _project("janus", "multimodal_vision", "Janus", "deepseek-ai", "https://github.com/deepseek-ai/Janus", "MIT", ("https://arxiv.org/abs/2410.13848",), "Separate understanding and generation evidence paths in A11oy receipts."),
    _project("minicpm-o", "multimodal_vision", "MiniCPM-o", "OpenBMB", "https://github.com/OpenBMB/MiniCPM-o", "UNKNOWN", ("https://github.com/OpenBMB/MiniCPM-o",), "Probe laptop-feasible multimodal inference with measured latency and explicit modality limits."),

    # Biomed & science
    _project("gpt-oss", "biomed_science", "gpt-oss", "openai", "https://github.com/openai/gpt-oss", "Apache-2.0", ("https://github.com/openai/gpt-oss",), "Evaluate scientific reasoning only on cited corpora with domain-expert review required."),
    _project("glm-4-5v-science", "biomed_science", "GLM-4.5V", "zai-org", "https://github.com/zai-org/GLM-V", "MIT", ("https://arxiv.org/abs/2507.01006",), "Test chart and document understanding without upgrading it to clinical validity."),
    _project("deepseek-r1-science", "biomed_science", "DeepSeek-R1", "deepseek-ai", "https://github.com/deepseek-ai/DeepSeek-R1", "MIT", ("https://arxiv.org/abs/2501.12948",), "Run scientific derivations through unit, citation, and formal-invariant checks."),
    _project("openmed", "biomed_science", "OpenMed", "maziyarpanahi", "https://github.com/maziyarpanahi/openmed", "Apache-2.0", ("https://arxiv.org/abs/2508.01630",), "Study local clinical NLP with privacy boundaries; outputs remain non-diagnostic and review-gated."),
    _project("physicsnemo", "biomed_science", "PhysicsNeMo", "NVIDIA", "https://github.com/NVIDIA/physicsnemo", "Apache-2.0", ("https://github.com/NVIDIA/physicsnemo/tree/main/docs",), "Map physics residuals into the existing A11oy formula and evidence gates."),

    # Security & red-team
    _project("garak", "security_red_team", "garak", "NVIDIA", "https://github.com/NVIDIA/garak", "Apache-2.0", ("https://github.com/NVIDIA/garak/tree/main/docs",), "Translate probe outcomes into deny-by-default test evidence, not a blanket safety claim."),
    _project("pyrit", "security_red_team", "PyRIT", "Azure", "https://github.com/Azure/PyRIT", "MIT", ("https://github.com/Azure/PyRIT/tree/main/doc",), "Adapt orchestrated red-team cases to governed, rate-limited A11oy evaluation runs."),
    _project("owasp-genai-top10", "security_red_team", "OWASP Top 10 for LLM Applications", "OWASP", "https://github.com/OWASP/www-project-top-10-for-large-language-model-applications", "CC-BY-SA-4.0", ("https://genai.owasp.org/llm-top-10/",), "Crosswalk each risk category to enforceable gates and evidence-bearing tests."),
    _project("promptfoo", "security_red_team", "promptfoo", "promptfoo", "https://github.com/promptfoo/promptfoo", "MIT", ("https://github.com/promptfoo/promptfoo/tree/main/site/docs",), "Study declarative adversarial evaluations while keeping A11oy policy decisions local."),
    _project("llm-guard", "security_red_team", "LLM Guard", "ProtectAI", "https://github.com/protectai/llm-guard", "MIT", ("https://github.com/protectai/llm-guard/tree/main/docs",), "Compare input/output scanners as advisory signals under the constitutional gate."),

    # Datasets & curation
    _project("hf-datasets", "datasets_curation", "Datasets", "huggingface", "https://github.com/huggingface/datasets", "Apache-2.0", ("https://github.com/huggingface/datasets/tree/main/docs",), "Record dataset revisions, configuration, splits, and source licenses in ingestion receipts."),
    _project("kagglehub", "datasets_curation", "KaggleHub", "Kaggle", "https://github.com/Kaggle/kagglehub", "Apache-2.0", ("https://github.com/Kaggle/kagglehub",), "Resolve assets into a quarantined cache with checksums and explicit terms review."),
    _project("openml-python", "datasets_curation", "OpenML Python", "openml", "https://github.com/openml/openml-python", "BSD-3-Clause", ("https://github.com/openml/openml-python/tree/main/doc",), "Preserve task and dataset identifiers so experiments can be replayed exactly."),
    _project("croissant", "datasets_curation", "Croissant", "mlcommons", "https://github.com/mlcommons/croissant", "Apache-2.0", ("https://docs.mlcommons.org/croissant/docs/croissant-spec.html",), "Emit Croissant-compatible metadata alongside A11oy provenance without replacing receipts."),
    _project("datatrove", "datasets_curation", "DataTrove", "huggingface", "https://github.com/huggingface/datatrove", "Apache-2.0", ("https://github.com/huggingface/datatrove/tree/main/docs",), "Study scalable filtering with auditable rejection reasons and reversible curation manifests."),

    # Sovereign / on-metal serving
    _project("vllm-serving", "sovereign_on_metal_serving", "vLLM", "vllm-project", "https://github.com/vllm-project/vllm", "Apache-2.0", ("https://github.com/vllm-project/vllm/tree/main/docs",), "Run only profiles admitted by real VRAM, driver, and model-license probes."),
    _project("ollama", "sovereign_on_metal_serving", "Ollama", "ollama", "https://github.com/ollama/ollama", "MIT", ("https://github.com/ollama/ollama/tree/main/docs",), "Use a loopback-only local backend with explicit model digests and bounded concurrency."),
    _project("llama-cpp-serving", "sovereign_on_metal_serving", "llama.cpp", "ggml-org", "https://github.com/ggml-org/llama.cpp", "MIT", ("https://github.com/ggml-org/llama.cpp/tree/master/examples/server",), "Adapt the local server behind A11oy authentication, quotas, and receipt-on-write rules."),
    _project("sglang-serving", "sovereign_on_metal_serving", "SGLang", "sgl-project", "https://github.com/sgl-project/sglang", "Apache-2.0", ("https://github.com/sgl-project/sglang/tree/main/docs",), "Study high-throughput local serving with isolation and honest capacity reporting."),
    _project("kserve", "sovereign_on_metal_serving", "KServe", "kserve", "https://github.com/kserve/kserve", "Apache-2.0", ("https://github.com/kserve/website/tree/main/docs",), "Map portable serving declarations to signed deployment policy and rollback evidence."),

    # Verifiable orchestration & provenance
    _project("risc0", "verifiable_orchestration_provenance", "RISC Zero zkVM", "risc0", "https://github.com/risc0/risc0", "Apache-2.0 OR MIT", ("https://dev.risczero.com/proof-system-in-detail.pdf",), "Explore bounded proof adapters while labeling unproved A11oy paths as unavailable."),
    _project("rekor", "verifiable_orchestration_provenance", "Rekor", "sigstore", "https://github.com/sigstore/rekor", "Apache-2.0", ("https://github.com/sigstore/rekor/tree/main/docs",), "Anchor selected receipt digests to transparency evidence without signing on reads."),
    _project("in-toto", "verifiable_orchestration_provenance", "in-toto", "in-toto", "https://github.com/in-toto/in-toto", "Apache-2.0", ("https://github.com/in-toto/docs",), "Map A11oy action receipts to supply-chain step attestations with verified identities."),
    _project("slsa", "verifiable_orchestration_provenance", "SLSA", "slsa-framework", "https://github.com/slsa-framework/slsa", "Apache-2.0", ("https://slsa.dev/spec/v1.2/",), "Use SLSA levels as externally defined criteria, never as a self-awarded badge."),
    _project("ezkl", "verifiable_orchestration_provenance", "EZKL", "zkonduit", "https://github.com/zkonduit/ezkl", "MIT", ("https://github.com/zkonduit/ezkl/tree/main/docs",), "Prototype proof-carrying small-model inference and report unsupported operators honestly."),
    _project("opengradient", "verifiable_orchestration_provenance", "OpenGradient SDK", "OpenGradient", "https://github.com/OpenGradient/sdk", "UNKNOWN", ("https://github.com/OpenGradient/sdk/tree/main/docs",), "Study externally verifiable execution receipts without treating third-party claims as local proof."),

    # Formal proof & training
    _project("lean4", "formal_proof_training", "Lean 4", "leanprover", "https://github.com/leanprover/lean4", "Apache-2.0", ("https://github.com/leanprover/lean4/tree/master/doc",), "Keep runtime formula claims linked to checked theorem names and exact proof revisions."),
    _project("mathlib4", "formal_proof_training", "mathlib4", "leanprover-community", "https://github.com/leanprover-community/mathlib4", "Apache-2.0", ("https://github.com/leanprover-community/mathlib4/tree/master/Mathlib",), "Study reusable lemmas while maintaining A11oy theorem ownership and dependency manifests."),
    _project("trl", "formal_proof_training", "TRL", "huggingface", "https://github.com/huggingface/trl", "Apache-2.0", ("https://github.com/huggingface/trl/tree/main/docs",), "Run post-training experiments as versioned recipes with baseline, seed, and evaluation receipts."),
    _project("peft", "formal_proof_training", "PEFT", "huggingface", "https://github.com/huggingface/peft", "Apache-2.0", ("https://github.com/huggingface/peft/tree/main/docs",), "Prefer laptop-feasible adapters and record base-model plus adapter revisions independently."),
    _project("unsloth", "formal_proof_training", "Unsloth", "unslothai", "https://github.com/unslothai/unsloth", "Apache-2.0", ("https://github.com/unslothai/unsloth/tree/main/docs",), "Study memory-efficient fine-tuning only after a hardware probe selects a safe recipe."),
)


_REPO_PATH = re.compile(r"^/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$")
_CACHE: Dict[str, Tuple[float, Mapping[str, Any]]] = {}
_CACHE_LOCK = threading.RLock()


def _repo_slug(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise ValueError("canonical_repo_url must be an https://github.com owner/repo URL")
    if parsed.query or parsed.fragment or not _REPO_PATH.fullmatch(parsed.path):
        raise ValueError("canonical_repo_url must not contain a subpath, query, or fragment")
    owner, repo = parsed.path.strip("/").split("/", 1)
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    return f"{owner}/{repo}"


def _iso_utc(epoch_s: float) -> str:
    return datetime.fromtimestamp(epoch_s, timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_reason(exc: BaseException) -> str:
    text = " ".join(str(exc).split()) or exc.__class__.__name__
    return text[:240]


def _unavailable(repo_url: str, reason: str) -> Dict[str, Any]:
    return {
        "label": UNAVAILABLE,
        "freshness": UNAVAILABLE,
        "source": "GitHub REST API",
        "source_url": f"https://api.github.com/repos/{_repo_slug(repo_url)}",
        "stars": None,
        "stars_label": UNAVAILABLE,
        "license": None,
        "license_label": UNAVAILABLE,
        "revision": None,
        "revision_label": UNAVAILABLE,
        "default_branch": None,
        "fetched_at": None,
        "fetched_at_label": UNAVAILABLE,
        "reason": reason,
    }


def _request_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "a11oy-primary-project-registry/1.0",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _read_json(url: str, timeout_s: float, opener: Callable[..., Any]) -> Mapping[str, Any]:
    request = Request(url, headers=_request_headers(), method="GET")
    response = opener(request, timeout=timeout_s)
    try:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("GitHub response exceeded the bounded response size")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub response was not a JSON object")
    return payload


def clear_cache() -> None:
    """Clear only the in-memory live-metadata cache (primarily for tests)."""
    with _CACHE_LOCK:
        _CACHE.clear()


def fetch_github_metadata(
    repo_url: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    ttl_s: float = DEFAULT_TTL_S,
    opener: Optional[Callable[..., Any]] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Fetch stars, SPDX license, and the default-branch commit revision.

    ``opener`` is injectable for deterministic tests and must follow the small
    ``urllib.request.urlopen(request, timeout=...)`` interface.  A cache entry is
    used only while it is inside ``ttl_s``.  Any fetch/parse/shape failure returns
    an ``UNAVAILABLE`` envelope with null live values.
    """
    slug = _repo_slug(repo_url)
    if not isinstance(timeout_s, (int, float)) or not 0 < float(timeout_s) <= 30.0:
        raise ValueError("timeout_s must be in (0, 30]")
    if not isinstance(ttl_s, (int, float)) or float(ttl_s) < 0:
        raise ValueError("ttl_s must be non-negative")
    current = time.time() if now is None else float(now)

    with _CACHE_LOCK:
        cached = _CACHE.get(slug)
        if cached and current - cached[0] < float(ttl_s):
            result = deepcopy(cached[1])
            result["freshness"] = "CACHE_FRESH"
            result["cache_age_s"] = round(max(0.0, current - cached[0]), 3)
            return result

    open_url = urlopen if opener is None else opener
    repo_api = f"https://api.github.com/repos/{slug}"
    try:
        repo_payload = _read_json(repo_api, float(timeout_s), open_url)
        stars = repo_payload.get("stargazers_count")
        branch = repo_payload.get("default_branch")
        if isinstance(stars, bool) or not isinstance(stars, int) or stars < 0:
            raise ValueError("GitHub stargazers_count was missing or invalid")
        if not isinstance(branch, str) or not branch.strip():
            raise ValueError("GitHub default_branch was missing or invalid")

        commit_api = f"{repo_api}/commits/{quote(branch, safe='')}"
        commit_payload = _read_json(commit_api, float(timeout_s), open_url)
        revision = commit_payload.get("sha")
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
            raise ValueError("GitHub commit sha was missing or invalid")

        license_obj = repo_payload.get("license")
        spdx = license_obj.get("spdx_id") if isinstance(license_obj, dict) else None
        if not isinstance(spdx, str) or not spdx or spdx == "NOASSERTION":
            spdx = None
        result: Dict[str, Any] = {
            "label": LIVE_LABEL,
            "freshness": "LIVE",
            "source": "GitHub REST API",
            "source_url": repo_api,
            "stars": stars,
            "stars_label": LIVE_LABEL,
            "license": spdx,
            "license_label": LIVE_LABEL if spdx else UNAVAILABLE,
            "revision": revision.lower(),
            "revision_label": LIVE_LABEL,
            "default_branch": branch,
            "fetched_at": _iso_utc(current),
            "fetched_at_label": LIVE_LABEL,
            "reason": None,
        }
    except Exception as exc:  # urllib, timeout, decoding, and schema failures
        return _unavailable(repo_url, f"live GitHub metadata unavailable: {_safe_reason(exc)}")

    with _CACHE_LOCK:
        _CACHE[slug] = (current, deepcopy(result))
    return deepcopy(result)


def projects() -> List[Dict[str, Any]]:
    """Return a caller-owned copy of the unranked static registry."""
    return deepcopy(list(_PROJECTS))


def info() -> Dict[str, Any]:
    """Return a deterministic, JSON-ready description of this registry."""
    counts = {field["id"]: 0 for field in _FIELDS}
    for item in _PROJECTS:
        counts[item["field"]] += 1
    fields = [
        {"id": field["id"], "name": field["name"], "project_count": counts[field["id"]]}
        for field in _FIELDS
    ]
    return {
        "ok": True,
        "service": "a11oy.primary_project_registry",
        "version": REGISTRY_VERSION,
        "label": STATIC_LABEL,
        "attribution": ATTRIBUTION,
        "ranking": "NONE",
        "scope": "projects_and_organizations_only",
        "source_policy": "primary official GitHub, standards, and paper URLs only",
        "license_policy": "license_expected is static guidance; live license is reported beside a fetched revision",
        "live_metadata_policy": "never hand-typed; explicit fetch, bounded timeout, TTL cache, UNAVAILABLE on failure",
        "field_count": len(_FIELDS),
        "project_count": len(_PROJECTS),
        "fields": fields,
    }


def _field_selection(fields: Optional[Iterable[str]]) -> Tuple[str, ...]:
    allowed = tuple(field["id"] for field in _FIELDS)
    if fields is None:
        return allowed
    requested = tuple(dict.fromkeys(fields))
    unknown = sorted(set(requested) - set(allowed))
    if unknown:
        raise ValueError(f"unknown field id(s): {', '.join(unknown)}")
    return requested


def snapshot(
    *,
    fetch_live: bool = False,
    fields: Optional[Iterable[str]] = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    ttl_s: float = DEFAULT_TTL_S,
    max_workers: int = 5,
    opener: Optional[Callable[..., Any]] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Return a JSON-ready registry snapshot; performs no network I/O by default.

    With ``fetch_live=True``, unique repositories are fetched concurrently and
    results are mapped back to every field entry.  Duplicate cross-field projects
    therefore share one revision-bound observation.  This function registers no
    HTTP route; a caller may expose the returned payload separately.
    """
    selected = set(_field_selection(fields))
    items = [deepcopy(dict(item)) for item in _PROJECTS if item["field"] in selected]

    if not fetch_live:
        for item in items:
            item["live_metadata"] = _unavailable(
                item["canonical_repo_url"],
                "live fetch disabled; static registry only",
            )
        payload = info()
        payload.update({
            "live_metadata_requested": False,
            "live_metadata_summary": {LIVE_LABEL: 0, UNAVAILABLE: len(items)},
            "selected_fields": [field["id"] for field in _FIELDS if field["id"] in selected],
            "snapshot_project_count": len(items),
            "unique_repository_count": len({item["canonical_repo_url"] for item in items}),
            "projects": items,
        })
        return payload

    if not isinstance(max_workers, int) or not 1 <= max_workers <= 16:
        raise ValueError("max_workers must be in [1, 16]")
    unique_repos = tuple(dict.fromkeys(item["canonical_repo_url"] for item in items))
    metadata: Dict[str, Mapping[str, Any]] = {}

    def fetch(repo_url: str) -> Mapping[str, Any]:
        return fetch_github_metadata(
            repo_url,
            timeout_s=timeout_s,
            ttl_s=ttl_s,
            opener=opener,
            now=now,
        )

    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(unique_repos)))) as pool:
        futures = {pool.submit(fetch, repo): repo for repo in unique_repos}
        for future in as_completed(futures):
            repo = futures[future]
            try:
                metadata[repo] = future.result()
            except Exception as exc:  # defensive: one project must not abort the snapshot
                metadata[repo] = _unavailable(repo, f"live metadata worker unavailable: {_safe_reason(exc)}")

    counts = {LIVE_LABEL: 0, UNAVAILABLE: 0}
    for item in items:
        observed = deepcopy(metadata[item["canonical_repo_url"]])
        item["live_metadata"] = observed
        counts[observed["label"] if observed["label"] == LIVE_LABEL else UNAVAILABLE] += 1
    payload = info()
    payload.update({
        "live_metadata_requested": True,
        "live_metadata_summary": counts,
        "selected_fields": [field["id"] for field in _FIELDS if field["id"] in selected],
        "snapshot_project_count": len(items),
        "unique_repository_count": len(unique_repos),
        "projects": items,
    })
    return payload


__all__ = [
    "ATTRIBUTION",
    "DEFAULT_TIMEOUT_S",
    "DEFAULT_TTL_S",
    "LIVE_LABEL",
    "REGISTRY_VERSION",
    "STATIC_LABEL",
    "UNAVAILABLE",
    "clear_cache",
    "fetch_github_metadata",
    "info",
    "projects",
    "snapshot",
]
