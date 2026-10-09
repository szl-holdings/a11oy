#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Policy overlay for the immutable Domain Experience v4 renderer.

The generated renderer stays byte-identical in the adjacent base module. This
module applies the reviewed Sentra receipt-verifier semantics while preserving
Terra forge 0.2.2, the current Lyte source pin, every non-Sentra vertical, and
the canonical single-writer publisher contract.

Importing this module performs no network or provider mutation.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
from types import ModuleType
from typing import Any

BASE_IMPLEMENTATION_PATH = Path(__file__).with_name(
    "_hf_publish_vertical_flagships_v4_impl_base.py"
)
SENTRA_OVERLAY_VERSION = "receipt-verifier/v1"


def _load_base() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "szl_hf_vertical_flagships_v4_base", BASE_IMPLEMENTATION_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load immutable flagship base: {BASE_IMPLEMENTATION_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = _load_base()
if getattr(_BASE, "TERRA_FORGE_MARKER", None) != 'data-szl-vertical-forge="0.2.2"':
    raise RuntimeError("immutable flagship base is not Terra forge 0.2.2")
if getattr(_BASE, "TERRA_FORGE_GENERATOR", None) != "szl-vertical-forge/0.2.2":
    raise RuntimeError("immutable flagship base has an unexpected Terra generator")

_sentra = {
    "slug": "sentra",
    "title": "CHAPAQ",
    "vertical": "ASSURANCE COMMAND",
    "short": "Public receipt verification and assurance evidence",
    "source": (
        "https://github.com/szl-holdings/a11oy/blob/main/"
        "scripts/hf_publish_vertical_flagships_v4_impl.py"
    ),
    "upstream": (
        "https://szlholdings-a11oy.hf.space/api/a11oy/v1/verify/receipt"
    ),
    "workflow": ("RECEIPT", "SIGNATURE", "DIGEST", "CHAIN", "VERDICT"),
    "lens": "receipt",
    "labels": ("Verifier contract", "Integrity checks", "Evidence verdict"),
}

_rows = tuple(getattr(_BASE, "FLAGSHIPS", ()))
if sum(1 for row in _rows if row.get("slug") == "sentra") != 1:
    raise RuntimeError("immutable flagship base must contain exactly one Sentra row")
_BASE.FLAGSHIPS = tuple(
    _sentra if row.get("slug") == "sentra" else row for row in _rows
)

_BASE.DOMAIN_CSS = dict(getattr(_BASE, "DOMAIN_CSS", {}))
_BASE.DOMAIN_CSS["sentra"] = r''':root{--bg:#030506;--panel:rgba(7,12,15,.92);--muted:#8ca1a8;--accent:#54f0d1;--accent2:#ff5d73}.domain{margin-top:48px;display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.8fr);gap:14px}.verification{min-height:410px;position:relative;overflow:hidden;background:radial-gradient(circle at 30% 30%,rgba(84,240,209,.08),transparent 35%),linear-gradient(rgba(84,240,209,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(84,240,209,.045) 1px,transparent 1px);background-size:auto,28px 28px,28px 28px}.node{position:absolute;inline-size:74px;block-size:74px;border:1px solid var(--accent);border-radius:50%;display:grid;place-items:center;background:#061014;font:800 9px ui-monospace,monospace;text-align:center}.n1{left:8%;top:18%}.n2{left:42%;top:10%}.n3{right:8%;top:38%;border-color:var(--accent2)}.n4{left:34%;bottom:9%}.path{position:absolute;block-size:1px;background:linear-gradient(90deg,var(--accent),var(--accent2));transform-origin:left center}.x1{left:16%;top:27%;inline-size:31%;transform:rotate(-8deg)}.x2{left:49%;top:20%;inline-size:37%;transform:rotate(25deg)}.x3{left:42%;top:65%;inline-size:42%;transform:rotate(-22deg)}.iris{position:absolute;inset:22% 28%;display:grid;place-items:center;pointer-events:none}.iris-ring{inline-size:min(52%,240px);aspect-ratio:1;border-radius:50%;border:1px dashed rgba(84,240,209,.38);display:grid;place-items:center;background:repeating-conic-gradient(from 0deg,rgba(84,240,209,.12) 0 8deg,transparent 8deg 16deg)}.iris-aperture{inline-size:22%;aspect-ratio:1;border-radius:50%;background:#030506;border:2px solid var(--accent);transform:scale(.16);box-shadow:inset 0 0 16px rgba(84,240,209,.18)}.queue{display:grid;gap:8px}.incident{padding:12px;border:1px solid var(--line);display:grid;grid-template-columns:64px 1fr;gap:10px}.sev{font:900 10px ui-monospace,monospace;color:var(--accent2)}html[data-iris=gated] .iris-aperture{transform:scale(.42)}html[data-iris=open] .iris-aperture{transform:scale(.42)}@media(max-width:850px){.domain{grid-template-columns:1fr}}'''

_BASE.DOMAIN_HTML = dict(getattr(_BASE, "DOMAIN_HTML", {}))
_BASE.DOMAIN_HTML["sentra"] = '''<div class="domain"><section class="panel verification" aria-label="Illustrative receipt verification graph"><span class="illus">Illustrative — schematic, not live data</span><span class="iris" aria-hidden="true"><span class="iris-ring"><span class="iris-aperture"></span></span></span><span class="path x1"></span><span class="path x2"></span><span class="path x3"></span><div class="node n1">RECEIPT</div><div class="node n2">SIGNATURE</div><div class="node n3">DIGEST</div><div class="node n4">CHAIN</div></section><aside class="panel queue"><span class="illus">Illustrative — schematic, not live data</span><div class="mono">VERIFICATION EVIDENCE QUEUE</div><div class="incident"><span class="sev">CONTRACT</span><span>The live upstream describes the public verifier and its supported checks; it does not claim a receipt verdict.</span></div><div class="incident"><span class="sev">VERDICT</span><span>PASS requires an actual caller-supplied receipt and successful signature, payload-digest, and hash-chain checks.</span></div><div class="incident"><span class="sev">SCOPE</span><span>This read-only surface performs no admission or approval. Immune engine migration remains UNVERIFIED until its contracts and runtime parity are proven.</span></div></aside></div>'''

_BASE.DOMAIN_HTML["sentra"] += '''<section id="sentra-verifier-handoff" class="panel queue" style="margin-top:14px" aria-labelledby="sentra-verifier-title">
<h2 id="sentra-verifier-title">Verify a receipt</h2>
<p>Open the existing verifier to paste a receipt and a public key. Offline checks run in your browser. Online checks require a separate explicit action.</p>
<a id="sentra-open-verifier" href="https://szlholdings-a11oy.hf.space/verify" target="_blank" rel="noopener noreferrer">Open receipt verifier</a>
<p>Trust scope: a supplied public key proves only the check against that key. Runtime keys are REPO_DECLARED until pinned out of band. Independent validation: UNKNOWN. Receipt integrity does not prove output truth, signer authority, authorization, admission, approval, or production readiness.</p>
</section>'''

_PROBE_LIVE = (
    '{"status":"LIVE" if r.is_success else "UNAVAILABLE","http_status":r.status_code,'
    '"latency_ms":round((time.time()-started)*1000,1),"source":CFG["upstream"],"data":body}'
)
_PROBE_REACHABLE = (
    '{"status":"REACHABLE" if r.is_success else "UNAVAILABLE",'
    '"honesty":"HTTP success is reachability, not MEASURED","receipt_verified":False,'
    '"http_status":r.status_code,"latency_ms":round((time.time()-started)*1000,1),'
    '"source":CFG["upstream"],"data":body}'
)
# /healthz stays HTTP 200 for orchestrators and the finance container smoke
# (the a11oy /api/livez convention), but `ok` is no longer a constant: it is the
# shell's own landing/panels integrity. Upstream state stays on /api/live.
_HEALTHZ_CONSTANT = (
    '@app.get("/healthz")\ndef healthz():\n'
    '    return {"ok":True,"product":CFG["title"],"source":CFG["product_source"],'
    '"public_experience":CFG["public_experience"],"domain":CFG["slug"]}\n'
)
_HEALTHZ_PROCESS_SCOPED = (
    '@app.get("/healthz")\ndef healthz():\n'
    '    integrity=local_integrity()\n'
    '    return {"ok":integrity["ready"],"status":"PROCESS_ALIVE",'
    '"scope":"process liveness plus local landing/panels integrity; '
    'not upstream health, not production readiness",'
    '"production_ready":False,'
    '"integrity":{"state":integrity["state"],"checks":integrity["checks"]},'
    '"readiness":"/readyz","upstream":"/api/live",'
    '"product":CFG["title"],"source":CFG["product_source"],'
    '"public_experience":CFG["public_experience"],"domain":CFG["slug"]}\n'
)
_LIVEBAR_OPEN = (
    "s.className='status '+(j.status==='LIVE'?'is-live':'');"
    "s.children[1].textContent=j.status+' / '+(j.latency_ms??'-')+' ms';"
)
_LIVEBAR_CLOSED = (
    "const verified=j.status==='MEASURED'&&j.receipt_verified===true;"
    "const reachable=j.status==='REACHABLE'||j.status==='LIVE';"
    "s.className='status';"
    "s.dataset.reachability=reachable?'REACHABLE':'UNAVAILABLE';"
    "s.children[1].textContent=(verified?'MEASURED':(reachable?'REACHABLE':'UNAVAILABLE'))"
    "+' / '+(j.latency_ms??'-')+' ms';"
    "const root=document.documentElement;"
    "if(root.dataset.domain==='sentra'){root.dataset.iris='closed';}"
)

# Finance is a thin read-only projection of its canonical source-owned API.
# The immutable base renderer remains byte-identical; no second publisher exists.
_finance_spec = importlib.util.spec_from_file_location(
    "szl_finance_read_projection", Path(__file__).with_name("hf_finance_read_proxy.py")
)
if _finance_spec is None or _finance_spec.loader is None:
    raise RuntimeError("finance read projection is unavailable")
_finance_module = importlib.util.module_from_spec(_finance_spec)
_finance_spec.loader.exec_module(_finance_module)
_BASE.APP = _finance_module.augment(_BASE.APP)
_BASE.FLAGSHIPS = tuple(
    {
        **row,
        "source": "https://github.com/szl-holdings/a11oy/tree/main/verticals/puriq-markets",
        "upstream": "https://szlholdings-a11oy.hf.space/api/a11oy/v1/finance/overview",
    } if row.get("slug") == "finance" else row
    for row in _BASE.FLAGSHIPS
)

# Bind the emitted image and dependency lock, not only the CI environment.
_runtime_spec = importlib.util.spec_from_file_location(
    "szl_flagship_runtime_contract", Path(__file__).with_name("hf_flagship_runtime_contract.py")
)
if _runtime_spec is None or _runtime_spec.loader is None:
    raise RuntimeError("flagship runtime contract is unavailable")
_runtime_module = importlib.util.module_from_spec(_runtime_spec)
_runtime_spec.loader.exec_module(_runtime_module)
_runtime_module.apply_runtime_contract(_BASE)

# Finance UI consumes only the validated same-origin read projection.
_workspace_spec = importlib.util.spec_from_file_location(
    "szl_finance_workspace", Path(__file__).with_name("hf_finance_workspace.py")
)
if _workspace_spec is None or _workspace_spec.loader is None:
    raise RuntimeError("finance workspace contract is unavailable")
_workspace_module = importlib.util.module_from_spec(_workspace_spec)
_workspace_spec.loader.exec_module(_workspace_module)
_workspace_module.apply_workspace(_BASE)

# Export the complete base API after applying the overlay. Function objects keep
# the base module globals, which are synchronized again before public calls that
# depend on mutable module contracts.
for _name in dir(_BASE):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_BASE, _name)

if _PROBE_LIVE not in APP:
    raise RuntimeError("flagship APP probe contract is not the expected LIVE-on-success mapper")
APP = APP.replace(_PROBE_LIVE, _PROBE_REACHABLE, 1)
if APP.count(_HEALTHZ_CONSTANT) != 1:
    raise RuntimeError("flagship APP healthz is not the expected unconditional ok:True handler")
APP = APP.replace(_HEALTHZ_CONSTANT, _HEALTHZ_PROCESS_SCOPED, 1)
_BASE.APP = APP


def _sync_contract() -> None:
    _BASE.FLAGSHIPS = tuple(FLAGSHIPS)
    _BASE.DOMAIN_CSS = dict(DOMAIN_CSS)
    _BASE.DOMAIN_HTML = dict(DOMAIN_HTML)
    _BASE.APP = APP
    _BASE.TERRA_FORGE_BUNDLE = TERRA_FORGE_BUNDLE
    _BASE.TERRA_FORGE_MARKER = TERRA_FORGE_MARKER
    _BASE.TERRA_FORGE_GENERATOR = TERRA_FORGE_GENERATOR
    _BASE.TERRA_FORGE_SOURCE_REPOSITORY = TERRA_FORGE_SOURCE_REPOSITORY


def load_terra_forge_bundle() -> tuple[str, dict[str, Any]]:
    _sync_contract()
    return _BASE.load_terra_forge_bundle()


_base_html = _BASE.html


def html(item: dict[str, Any]) -> str:
    _sync_contract()
    page = _base_html(item)
    if _LIVEBAR_OPEN not in page:
        raise RuntimeError("flagship livebar still opens on HTTP LIVE")
    page = page.replace(_LIVEBAR_OPEN, _LIVEBAR_CLOSED, 1)
    if item.get("slug") == "sentra":
        page = page.replace('<html lang="en"', '<html lang="en" data-iris="closed"', 1)
    return page


_BASE.html = html

# Every publication scope qualifies Finance's public forwarding functionality.
# File parity/process liveness alone cannot admit a broken or replaced projection.
_base_observe_flagship = _BASE.observe_flagship
_base_observation_passes = _BASE.observation_passes
_gate_spec = importlib.util.spec_from_file_location(
    "szl_finance_functional_gate", Path(__file__).with_name("hf_finance_functional_gate.py"))
_gate_module = importlib.util.module_from_spec(_gate_spec)
_gate_spec.loader.exec_module(_gate_module)


_projection_spec = importlib.util.spec_from_file_location(
    "szl_finance_projection_manifest", Path(__file__).with_name("hf_finance_projection_manifest.py"))
if _projection_spec is None or _projection_spec.loader is None:
    raise RuntimeError("finance projection manifest contract is unavailable")
_projection_module = importlib.util.module_from_spec(_projection_spec)
_projection_spec.loader.exec_module(_projection_module)
FINANCE_PROJECTION_MANIFEST_PATH = _projection_module.MANIFEST_PATH
_finance_upload_active = False
_finance_payloads: dict[str, bytes] = {}
_finance_expected_payloads: dict[str, bytes] = {}
_finance_source_identity: tuple[str, int] | None = None
_finance_witnesses: dict[str, dict[str, Any]] = {}
_finance_terminal_witness: dict[str, Any] | None = None


def finance_projection_manifest_bytes(files: dict[str, bytes], revision: str, run_id: int) -> bytes:
    return _projection_module.manifest_bytes(files, revision, run_id)


def _observe_finance_projection(row: dict[str, Any]) -> dict[str, Any]:
    global _finance_terminal_witness
    if _finance_terminal_witness is not None:
        # A denied public read is terminal for this invocation, even if the
        # runtime later reports another Hub head. Do not change endpoints.
        return _finance_terminal_witness
    revision = row.get("build_info", {}).get("hf_revision")
    if not isinstance(revision, str):
        return {"complete": False, "evidence_class": "UNAVAILABLE", "failure_code": "INVALID_HUB_REVISION"}
    if revision in _finance_witnesses:
        cached = _finance_witnesses[revision]
        if _projection_module.witness_matches(cached, dict(_finance_payloads),
                row["source_revision"], row["workflow_run_id"], revision):
            return cached
    witness = _projection_module.observe_projection(
        dict(_finance_payloads), row["source_revision"], row["workflow_run_id"], revision)
    if witness.get("complete") is True:
        _finance_witnesses[revision] = witness
    elif witness.get("terminal_authority_failure") is True:
        _finance_terminal_witness = witness
    # Ordinary transient failures stay negative but may recover in the existing
    # publisher observation loop. A denial never retries or changes endpoints.
    return witness



def observe_flagship(row: dict[str, Any]) -> None:
    _base_observe_flagship(row)
    if row.get("slug") == "finance" and _base_observation_passes(
            row, source_revision=row["source_revision"], workflow_run_id=str(row["workflow_run_id"])):
        row["finance_functional"] = _gate_module.observe_finance(row["source_revision"])
        row["finance_projection"] = _observe_finance_projection(row)
    elif row.get("slug") == "finance":
        row["finance_functional"] = {"complete": False, "state": "WAITING_FOR_EXACT_RUNTIME"}
        row["finance_projection"] = {"complete": False, "evidence_class": "UNAVAILABLE",
                                     "failure_code": "WAITING_FOR_EXACT_RUNTIME"}


def observation_passes(row: dict[str, Any], *, source_revision: str, workflow_run_id: str) -> bool:
    shell_passes = _base_observation_passes(row, source_revision=source_revision, workflow_run_id=workflow_run_id)
    if not shell_passes or row.get("slug") != "finance":
        return shell_passes
    if (not isinstance(workflow_run_id, str) or not workflow_run_id.isascii()
            or not workflow_run_id.isdigit() or int(workflow_run_id) <= 0):
        return False
    return bool(row.get("finance_functional", {}).get("complete") is True
        and _projection_module.witness_matches(row.get("finance_projection"), dict(_finance_payloads),
            source_revision, int(workflow_run_id), row.get("build_info", {}).get("hf_revision")))


_BASE.observe_flagship = observe_flagship
_BASE.observation_passes = observation_passes


def upload_text(api: Any, repo_id: str, path: str, content: str) -> Any:
    """Bind every generated Hub commit title to the tested GitHub source."""
    source_revision = os.getenv("GITHUB_SHA", "").strip().lower()
    if not _projection_module._revision(source_revision):
        raise RuntimeError("flagship upload requires an exact 40-hex GITHUB_SHA")
    finance = repo_id == _projection_module.REPOSITORY
    if finance and path not in _projection_module.OWNED_PATHS:
        raise RuntimeError("finance upload path is outside the owned projection")
    if finance and _finance_upload_active and path in _finance_payloads:
        raise RuntimeError("finance projection contains a duplicate upload path")
    raw = content.encode("utf-8")
    if finance:
        identity = _finance_identity()
        expected = _finance_expected_payloads if _finance_upload_active else render_finance_payloads(*identity)
        if (_finance_upload_active and identity != _finance_source_identity) or raw != expected[path]:
            raise RuntimeError("finance upload differs from the preflight projection")
    result = api.upload_file(
        path_or_fileobj=raw,
        path_in_repo=path,
        repo_id=repo_id,
        repo_type="space",
        commit_message=f"feat(domain-v4): publish {path} from szl-holdings/a11oy@{source_revision}",
    )
    if finance and _finance_upload_active:
        _finance_payloads[path] = raw
        if set(_finance_payloads) == set(_projection_module.OWNED_PATHS):
            manifest = finance_projection_manifest_bytes(dict(_finance_payloads), *identity)
            api.upload_file(path_or_fileobj=manifest, path_in_repo=FINANCE_PROJECTION_MANIFEST_PATH,
                repo_id=repo_id, repo_type="space",
                commit_message=f"feat(domain-v4): publish {FINANCE_PROJECTION_MANIFEST_PATH} from szl-holdings/a11oy@{source_revision}")
    return result


_BASE.upload_text = upload_text


_base_readme = _BASE.readme


def readme(item: dict[str, Any]) -> str:
    """Present the four generated cards without changing their original evidence."""
    _sync_contract()
    original = _base_readme(item)
    if item["slug"] not in ("terra", "sentra", "counsel", "finance"):
        return original
    boundary = original.index("\n---\n", 4) + len("\n---\n")
    front_matter, body = original[:boundary], original[boundary:]
    descriptions = {
        "terra": "Inspect property evidence, ownership context and underwriting assumptions in a governed decision workspace.",
        "sentra": "Inspect receipt-verification contracts and hand an explicit receipt to the existing verifier.",
        "counsel": "Organize matter research, drafting and cited evidence in a workspace with explicit verification boundaries.",
        "finance": "Inspect financial observations, modeled scenarios and decision evidence with their provenance and limits.",
    }
    lead = f'''\n<!-- szl:card-presentation:v1 -->
<p><a href="https://huggingface.co/spaces/SZLHOLDINGS/szl-command-lab"><img src="https://raw.githubusercontent.com/szl-holdings/.github/main/profile/assets/szl/logos/szl_mark_holographic.svg" alt="SZL Holdings" width="112" /></a></p>

# {item['title']}

{descriptions[item['slug']]}

**Artifact:** Domain application over the shared vertical runtime

**Stage:** Capability-specific evidence required

[**Explore Command Lab →**](https://huggingface.co/spaces/SZLHOLDINGS/szl-command-lab) · [**Build with the source →**](https://github.com/szl-holdings/a11oy) · [**Open this workspace →**](https://huggingface.co/spaces/SZLHOLDINGS/{item['slug']})

## Use limits

- An HTTP success establishes reachability only. Inspect the returned evidence state before relying on a result.
- Observed evidence, modeled analysis and human approval remain separate. This card grants no action authority.
- A receipt-integrity check does not establish output accuracy, signer authority or operational readiness.

<details>
<summary>Technical documentation and original publication evidence</summary>

<!-- szl:preserved-source-body:start -->
'''
    card = (front_matter + lead + body
            + "\n<!-- szl:preserved-source-body:end -->\n\n</details>\n")
    if item.get("slug") == "finance":
        card += ("\n## Current projection evidence\n\n"
            "[finance-projection-manifest.json](finance-projection-manifest.json) is a DECLARED "
            "file table for the seven current A11oy-owned upload payloads, including config.json. "
            "The publisher's separate immutable-revision byte witness must pass together with the existing "
            "Finance functionality checks. This is source-projection coverage, not a signature, runtime-image "
            "inclusion proof, model qualification, authorization, or release approval.\n\n"
            "The retained szl-artifact-manifest.json is a legacy Hub-only record; its qualification is UNKNOWN "
            "and it is not the current A11oy projection's attestation. It and unrelated Hub-only files are "
            "not written or deleted by this publisher. Their retained bytes are not verified by "
            "this witness and are outside this projection's evidence scope.\n")
    return card


# The existing base publisher calls its own module globals. Bind the reviewed
# presentation there too, so every generated card follows the same source path.
_BASE.readme = readme


def _finance_identity() -> tuple[str, int]:
    revision = os.getenv("GITHUB_SHA", "").strip().lower()
    run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    if (not _projection_module._revision(revision) or not run_id.isascii()
            or not run_id.isdigit() or int(run_id) <= 0):
        raise RuntimeError("finance projection requires exact source and positive workflow identity")
    return revision, int(run_id)


def render_finance_payloads(source_revision: str, workflow_run_id: int) -> dict[str, bytes]:
    """Pure Finance preflight; the recording test binds it to all existing uploads."""
    _sync_contract()
    if (not _projection_module._revision(source_revision)
            or type(workflow_run_id) is not int or workflow_run_id <= 0):
        raise ValueError("exact nonzero source revision and positive run identity required")
    rows = [row for row in FLAGSHIPS if row.get("slug") == "finance"]
    if len(rows) != 1:
        raise ValueError("canonical finance entry must be unique")
    item = rows[0]
    page = html(item)
    card = readme(item)
    page_sha = hashlib.sha256(page.encode("utf-8")).hexdigest()
    config = {
        "slug": "finance", "title": item["title"], "vertical": item["vertical"],
        "product_source": item["source"], "source_repository": DEPLOYMENT_SOURCE_REPOSITORY,
        "source_revision": source_revision, "workflow_run_id": workflow_run_id,
        "hf_repository": ORG + "/finance",
        "artifact_set_sha256": artifact_digest(APP, DOCKER, REQ, page, page, card, "null"),
        "landing_sha256": page_sha, "panels_sha256": page_sha, "forge": None,
        "upstream": item["upstream"], "public_experience": PUBLIC_EXPERIENCE_VERSION,
    }
    files = {path: content.encode("utf-8") for path, content in (
        ("app.py", APP), ("Dockerfile", DOCKER), ("requirements.txt", REQ),
        ("config.json", json.dumps(config, indent=2, sort_keys=True) + "\n"),
        ("index.html", page), ("panels.html", page), ("README.md", card),
    )}
    finance_projection_manifest_bytes(files, source_revision, workflow_run_id)
    return files


def render_sentra_payload(
    source_revision: str, workflow_run_id: int
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Render the existing seven-file contract without entering its writer."""
    if (len(source_revision) != 40
            or any(ch not in "0123456789abcdef" for ch in source_revision)
            or source_revision == "0" * 40):
        raise ValueError("Sentra requires an exact source revision")
    if type(workflow_run_id) is not int or workflow_run_id <= 0:
        raise ValueError("Sentra requires a positive workflow run id")
    matches = [item for item in FLAGSHIPS if item["slug"] == "sentra"]
    if len(matches) != 1:
        raise ValueError("Sentra renderer inventory is ambiguous")
    item = matches[0]
    page = html(item)
    card = readme(item)
    page_sha = hashlib.sha256(page.encode("utf-8")).hexdigest()
    artifacts = artifact_digest(APP, DOCKER, REQ, page, page, card, "null")
    config = json.dumps({
        "slug": "sentra", "title": item["title"], "vertical": item["vertical"],
        "product_source": item["source"], "source_repository": DEPLOYMENT_SOURCE_REPOSITORY,
        "source_revision": source_revision, "workflow_run_id": workflow_run_id,
        "hf_repository": "SZLHOLDINGS/sentra", "artifact_set_sha256": artifacts,
        "landing_sha256": page_sha, "panels_sha256": page_sha, "forge": None,
        "upstream": item["upstream"], "public_experience": PUBLIC_EXPERIENCE_VERSION,
    }, indent=2, sort_keys=True) + "\n"
    files = {path: content.encode("utf-8") for path, content in (
        ("app.py", APP), ("Dockerfile", DOCKER), ("requirements.txt", REQ),
        ("config.json", config), ("index.html", page), ("panels.html", page), ("README.md", card),
    )}
    row = {"id": "SZLHOLDINGS/sentra", "slug": "sentra", "source": item["source"],
           "source_revision": source_revision, "workflow_run_id": workflow_run_id,
           "artifact_set_sha256": artifacts, "landing_sha256": page_sha,
           "panels_sha256": page_sha, "forge": None,
           "root_marker": PUBLIC_EXPERIENCE_MARKER, "actions": []}
    return files, row


def main() -> int:
    global _finance_upload_active, _finance_terminal_witness, _finance_source_identity
    _sync_contract()
    _finance_payloads.clear()
    _finance_expected_payloads.clear()
    _finance_witnesses.clear()
    _finance_terminal_witness = None
    _finance_source_identity = None
    if any(row.get("slug") == "finance" for row in FLAGSHIPS):
        _finance_source_identity = _finance_identity()
        _finance_expected_payloads.update(render_finance_payloads(*_finance_source_identity))
    _finance_upload_active = True
    try:
        return int(_BASE.main())
    finally:
        _finance_upload_active = False


__all__ = tuple(
    sorted(
        name
        for name in globals()
        if not name.startswith("_")
        and name not in {"Any", "ModuleType", "Path", "importlib"}
    )
)


if __name__ == "__main__":
    raise SystemExit(main())
