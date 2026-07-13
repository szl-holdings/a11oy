"""a11oy_ayllu.py — register the ayllu (ingested-and-reborn tribe) on the a11oy app.

Follows a11oy's module convention: expose `register(app, ns="a11oy") -> str`, mounted
by serve.py inside a try/except guard so a11oy boots unaffected if anything here fails.

The model backend is a11oy's OWN orchestrator (see ayllu/backend.py): ask/council now
produce REAL answers when a reachable local endpoint or credentialed remote provider
is available, and an honest, clearly-labeled stub otherwise — never a fabricated answer. Cost is bounded:
prompt length is capped, council fan-out is capped, and ask/council carry a process-
wide rate limit (429 + Retry-After).

Receipts use `szl_dsse` when present, else an honest UNSIGNED DSSE envelope (never a
fabricated signature). The DSSE payload chains the backend model + energy-receipt hash.

Routes:
  GET  /api/{ns}/v1/ayllu/roster   — roster + honest live/stub backend status
  POST /api/{ns}/v1/ayllu/ask      — one persona, bounded + honest + receipted
  POST /api/{ns}/v1/ayllu/council  — bounded multi-persona deliberation (capped fan-out)
  GET  /api/{ns}/v1/ayllu/lounge   — recent collaboration feed
  GET  /ayllu                      — honest human-readable chat + council page
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

# FastAPI resolves endpoint annotations with get_type_hints against THIS module's
# globals. The handlers in register() annotate `request: "Request"` — a string
# forward-ref, because of `from __future__ import annotations` above — so `Request`
# (and the response classes) MUST be importable at MODULE level, or FastAPI cannot
# recognize the special Request parameter and mis-treats it as a REQUIRED query
# param (every GET route then 422s with loc=["query","request"]). They are also
# imported locally inside register() for the call sites; this module-level (guarded)
# import is solely what makes the string annotations resolvable at route-build time.
try:
    from fastapi import Request  # noqa: F401
    from fastapi.responses import HTMLResponse, JSONResponse  # noqa: F401
except Exception:  # pragma: no cover - fastapi absent only where register() is never called
    Request = HTMLResponse = JSONResponse = None  # type: ignore

# POC (szl-substrate extraction): prefer the shared package as the single source
# of truth; fall back to the local vendored copy so nothing breaks if the package
# is not installed in this runtime. See szl-holdings/szl-substrate MIGRATION.md.
try:
    from szl_substrate import szl_dsse as _dsse  # type: ignore  # single source of truth
    _dsse_source = "szl-substrate"
except Exception:  # pragma: no cover
    try:
        import szl_dsse as _dsse  # type: ignore  # fall back to local vendored copy
        _dsse_source = "local-vendored"
    except Exception:
        _dsse = None  # honest UNSIGNED fallback
        _dsse_source = "unavailable"

from ayllu import __version__ as _AYLLU_VERSION
from ayllu import backend as _backend
from ayllu.lounge import Lounge
from ayllu.loop import run_turn
from ayllu.model_binding import family_binding, persona_binding
from ayllu.personas import ROSTER, get_persona

__version__ = _AYLLU_VERSION

# ---- cost + abuse bounds (public Space; real token cost once live) -----------
MAX_PROMPT_CHARS = 6000
MAX_BODY_BYTES = 24 * 1024
COUNCIL_MAX = 5                                     # hard cap on participants / call
COUNCIL_DEBATE_MAX = 3  # debate doubles model calls; tighter cap bounds cost
ASK_MAX_TOKENS = 384
ASK_TURN_TIMEOUT_S = 45.0
COUNCIL_MAX_TOKENS = 192
COUNCIL_TURN_TIMEOUT_S = 45.0
COUNCIL_DEFAULT = ["Amaru", "Kamachiq", "Qhatuq"]  # architect · orchestrator · markets

COUNCIL_CONTRACT_VERSION = "2.0"
COUNCIL_SCHEMA = "szl.ayllu.evidence-bound-council/v2"
NEMO_ARTIFACT = "https://huggingface.co/SZLHOLDINGS/szl-nemo"

# One process-wide opt-in lounge (in-memory, honest source labels). Public ask and
# council handlers do not automatically publish caller output into it.
_LOUNGE = Lounge()


class _BodyTooLarge(ValueError):
    pass


async def _bounded_json_body(request: "Request") -> Dict[str, Any]:
    """Read one bounded JSON object before any paid inference is attempted."""
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            size = int(declared)
        except ValueError as exc:
            raise ValueError("invalid content-length") from exc
        if size < 0:
            raise ValueError("invalid content-length")
        if size > MAX_BODY_BYTES:
            raise _BodyTooLarge(f"request body exceeds {MAX_BODY_BYTES} bytes")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BODY_BYTES:
            raise _BodyTooLarge(f"request body exceeds {MAX_BODY_BYTES} bytes")
        data.extend(chunk)
    try:
        value = json.loads(bytes(data).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON body") from exc
    if not isinstance(value, dict):
        raise ValueError("request body must be a JSON object")
    return value


class _RateBucket:
    """Tiny process-wide sliding-window limiter. Honest: bounds THIS process only."""

    def __init__(self, limit: int, window_s: float) -> None:
        self.limit = int(limit)
        self.window = float(window_s)
        self._hits: list[float] = []
        self._lock = threading.Lock()

    def check(self) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            self._hits = [t for t in self._hits if now - t < self.window]
            if len(self._hits) >= self.limit:
                retry = self.window - (now - self._hits[0])
                return False, max(1, int(retry) + 1)
            self._hits.append(now)
            return True, 0


_ASK_BUCKET = _RateBucket(30, 60.0)      # 30 asks / minute (process-wide)
_COUNCIL_BUCKET = _RateBucket(8, 60.0)   # 8 councils / minute (process-wide)


def _receipt_sha(receipt: Optional[dict]) -> Optional[str]:
    if not receipt:
        return None
    try:
        body = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(body).hexdigest()
    except Exception:
        return None


def _make_receipt(payload: Dict[str, Any], sign_fn=None) -> Dict[str, Any]:
    """Wrap payload in DSSE without overstating the signer's identity.

    ``szl_dsse`` is the organization-key path: it signs only when an operator
    injects the established Cosign private-key runtime secret. ``sign_fn`` is
    the host's explicitly boot-ephemeral development signer. Prefer the former
    only when its key is genuinely loadable, then fall back to the development
    signer. With neither path available, emit an honest unsigned envelope.
    """
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    honesty = "UNSIGNED — szl_dsse not present; no signature fabricated."
    if _dsse is not None:
        try:
            signing_available = getattr(_dsse, "signing_available", None)
            if (callable(signing_available) and signing_available()
                    and hasattr(_dsse, "sign_payload")):
                return _dsse.sign_payload(
                    payload, "application/vnd.szl.receipt+json")
        except Exception as exc:
            honesty = (f"UNSIGNED — organization-key signer unavailable "
                       f"({str(exc)[:80]}); no signature fabricated.")
    if callable(sign_fn):
        try:
            env = sign_fn(payload)
            if isinstance(env, dict):
                return env
            honesty = "UNSIGNED - runtime signer returned a non-object; no signature fabricated."
        except Exception as exc:
            honesty = (f"UNSIGNED - runtime signer raised ({str(exc)[:80]}); "
                       "no signature fabricated.")
    if _dsse is not None:
        try:
            # No organization key and no host development signer: use the
            # canonical implementation only to construct its explicit UNSIGNED
            # envelope (it never fabricates signature bytes).
            if hasattr(_dsse, "sign_payload"):
                return _dsse.sign_payload(
                    payload, "application/vnd.szl.receipt+json")
        except Exception as exc:
            honesty = (f"UNSIGNED — szl_dsse.sign raised ({str(exc)[:80]}); "
                       "no signature fabricated.")
    return {
        "payloadType": "application/vnd.szl.receipt+json",
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [],
        "signed": False,
        "honesty": honesty,
    }


def _sha256_json(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _council_store_path(ns: str) -> tuple[str, str]:
    """Resolve Council state without claiming an unverified durable mount.

    Operators can name an exact path or an established data directory.  Local
    development defaults to a gitignored directory beside this module, which
    survives process restarts but is *not* claimed to survive a container or
    Space rebuild.
    """
    exact = os.environ.get("A11OY_AYLLU_KHIPU_PATH")
    if exact:
        return exact, "A11OY_AYLLU_KHIPU_PATH"
    data_dir = os.environ.get("A11OY_DATA_DIR")
    if data_dir:
        return os.path.join(data_dir, "ayllu", f"khipu_{ns}_council.sqlite3"), "A11OY_DATA_DIR"
    khipu_dir = os.environ.get("SZL_KHIPU_DIR")
    if khipu_dir:
        return os.path.join(khipu_dir, f"khipu_{ns}_council.sqlite3"), "SZL_KHIPU_DIR"
    return str(Path(__file__).resolve().parent / ".a11oy-state"
               / f"khipu_{ns}_council.sqlite3"), "REPOSITORY_LOCAL_DEVELOPMENT_STATE"


def _open_council_store(ns: str):
    """Open the repository's tested durable Khipu implementation.

    Returns ``(store, metadata)``.  Failure is explicit; the caller may still
    use the legacy in-memory DAG but must report that downgrade.
    """
    path, configured_by = _council_store_path(ns)
    try:
        from szl_be_hardening import DurableKhipu
        store = DurableKhipu("ayllu_council", ns=ns, path=path)
        durable = store.backend in ("sqlite", "json")
        meta = {
            "backend": store.backend,
            "durable": durable,
            "configured_by": configured_by,
            "survives_process_restart": durable,
            "survives_redeploy": "NOT_VERIFIED",
            "redeploy_requirement": (
                "Mount the configured path on persistent storage; a writable "
                "local/container filesystem alone does not prove redeploy persistence."
            ),
        }
        return store, meta
    except Exception as exc:
        return None, {
            "backend": "memory",
            "durable": False,
            "configured_by": configured_by,
            "survives_process_restart": False,
            "survives_redeploy": "NOT_VERIFIED",
            "error": type(exc).__name__,
            "honesty": "Durable Khipu unavailable; Council will use the in-process DAG.",
        }


def _council_store_metadata(store, fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if store is None:
        return dict(fallback or {
            "backend": "memory", "durable": False,
            "survives_process_restart": False,
            "survives_redeploy": "NOT_VERIFIED",
        })
    backend = getattr(store, "backend", "memory")
    base = dict(fallback or {})
    base.update({
        "backend": backend,
        "durable": backend in ("sqlite", "json"),
        "survives_process_restart": backend in ("sqlite", "json"),
        "survives_redeploy": "NOT_VERIFIED",
    })
    return base


def council_manifest(ns: str = "a11oy",
                     chain_storage: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Side-effect-free, investor-readable contract for the bounded council."""
    base = f"/api/{ns}/v1/ayllu"
    return {
        "schema": "szl.ayllu.council-manifest/v1",
        "contract_schema": COUNCIL_SCHEMA,
        "contract_version": COUNCIL_CONTRACT_VERSION,
        "purpose": (
            "Produce a bounded, evidence-bearing advisory record from multiple "
            "personas. The Council proposes; it never executes an external action."
        ),
        "try": {
            "method": "POST",
            "endpoint": base + "/council",
            "body": {"prompt": "Review this proposed agent action",
                     "personas": ["Amaru", "Yupaq", "Kamachiq"],
                     "debate": True},
        },
        "evidence": [
            "prompt SHA-256",
            "persona/model/round/output digest per turn",
            "Nemo governed-route decision and DSSE receipt",
            "deterministic replay key over participants, mode, and output digests",
            "Khipu chain receipt with runtime-reported storage backend and durability",
            "outer Council DSSE receipt",
        ],
        "limits": {
            "request_body_bytes": MAX_BODY_BYTES,
            "prompt_chars": MAX_PROMPT_CHARS,
            "participants": COUNCIL_MAX,
            "debate_participants": COUNCIL_DEBATE_MAX,
            "debate_rounds": 2,
            "ask_tokens_per_turn": ASK_MAX_TOKENS,
            "ask_timeout_s": ASK_TURN_TIMEOUT_S,
            "council_tokens_per_turn": COUNCIL_MAX_TOKENS,
            "council_timeout_s": COUNCIL_TURN_TIMEOUT_S,
            "round_fanout": "CONCURRENT_BOUNDED",
            "effectors": "none",
            "decision_state": "PROPOSAL_ONLY",
            "semantic_consensus": "NOT_MEASURED",
            "chain_storage": chain_storage or {
                "backend": "NOT_INSPECTED",
                "durable": "NOT_INSPECTED",
                "survives_process_restart": "NOT_INSPECTED",
                "survives_redeploy": "NOT_VERIFIED",
            },
        },
        "reproduce": {
            "manifest": base + "/council/manifest",
            "verifier": f"/api/{ns}/v1/verify/receipt",
            "public_key": "/cosign.pub",
        },
        "nemo": {
            "artifact": NEMO_ARTIFACT,
            "artifact_kind": "configuration-recipe",
            "weights_present": False,
            "training_state": "NOT_PERFORMED",
            "honesty": (
                "The current SZL-Nemo Hub artifact is a card and Modelfile recipe, "
                "not SZL-trained weights. Council answers use the live A11OY router."
            ),
        },
        "model_family": family_binding(
            namespace=ns, backend_status=_backend.backend_status()),
        "evaluation": {
            "council_effectiveness": "NOT_MEASURED",
            "required_next": (
                "golden cases with decision-quality, calibration, dissent-recall, "
                "cost, latency, and human-overturn outcomes"
            ),
        },
    }


def _nemo_council_route(prompt: str, sign_fn=None) -> Dict[str, Any]:
    """Run the existing Nemo router and expose the evidence Council needs."""
    try:
        import a11oy_nemo_core as nemo
        routed = nemo.govern_route(prompt, top_k=3, sign_fn=sign_fn)
        experts = routed.get("experts") or []
        return {
            "state": routed.get("routing_evidence_state", "HEURISTIC"),
            "source": "a11oy_nemo_core.govern_route",
            "model": routed.get("model"),
            "model_version": routed.get("model_version"),
            "experts_selected": routed.get("experts_selected") or [],
            "selection_basis": [e.get("selection_basis") for e in experts],
            "overall_lambda_advisory": routed.get("overall_lambda_advisory"),
            "below_advisory_floor": any(bool(e.get("below_advisory_floor"))
                                        for e in experts),
            "limits": routed.get("routing_limits"),
            "receipt": routed.get("receipt"),
        }
    except Exception as exc:
        return {
            "state": "UNAVAILABLE",
            "source": "a11oy_nemo_core.govern_route",
            "error": type(exc).__name__,
            "honesty": "Nemo routing unavailable; no route or score fabricated.",
        }


def _build_council_contract(prompt: str, result: Dict[str, Any],
                            nemo_route: Dict[str, Any],
                            ns: str = "a11oy") -> Dict[str, Any]:
    family = family_binding(namespace=ns, backend_status=_backend.backend_status())
    rounds = result.get("rounds") or []
    turn_evidence = []
    for turn in rounds:
        answer = turn.get("answer")
        turn_evidence.append({
            "persona": turn.get("persona"),
            "round": turn.get("round"),
            "model": turn.get("model"),
            "stub": bool(turn.get("stub")),
            "timeout": bool(turn.get("timeout", False)),
            "token_budget": turn.get("token_budget"),
            "timeout_s": turn.get("timeout_s"),
            "correctness_state": ("NOT_APPLICABLE_STUB" if bool(turn.get("stub"))
                                  else "UNVERIFIED_MODEL_OUTPUT"),
            "output_sha256": (hashlib.sha256(str(answer).encode("utf-8")).hexdigest()
                              if answer is not None else None),
            "energy_receipt_sha256": _receipt_sha(turn.get("energy_receipt")),
            "model_binding": turn.get("model_binding"),
            "model_binding_sha256": (
                _sha256_json(turn["model_binding"])
                if isinstance(turn.get("model_binding"), dict) else None
            ),
        })
    replay_material = {
        "contract_version": COUNCIL_CONTRACT_VERSION,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "participants": result.get("participants") or [],
        "mode": result.get("mode"),
        "turns": turn_evidence,
    }
    live_turns = sum(1 for t in turn_evidence if not t["stub"])
    timeout_turns = sum(1 for t in turn_evidence if t["timeout"])
    if not turn_evidence:
        evidence_state = "UNAVAILABLE"
    elif timeout_turns and not live_turns:
        evidence_state = "UNAVAILABLE"
    elif live_turns == len(turn_evidence):
        evidence_state = "LIVE"
    elif live_turns:
        evidence_state = "MIXED"
    else:
        evidence_state = "STUB"
    return {
        "schema": COUNCIL_SCHEMA,
        "contract_version": COUNCIL_CONTRACT_VERSION,
        "purpose": "bounded multi-persona advisory deliberation",
        "decision_state": "PROPOSAL_ONLY",
        "approval_state": "HUMAN_REVIEW_REQUIRED",
        "evidence_state": evidence_state,
        "correctness_state": "NOT_VERIFIED",
        "prompt_sha256": replay_material["prompt_sha256"],
        "turn_evidence": turn_evidence,
        "model_family": family,
        "model_family_binding_sha256": _sha256_json(family),
        "routing": nemo_route,
        "formula_path": [
            {"id": "lambda-aggregate", "state": "CONJECTURE_1_ADVISORY"},
            {"id": "active-flux-crossover", "state": "MODELED"},
            {"id": "dsse-pae", "state": "IMPLEMENTED"},
        ],
        "semantic_consensus": {
            "state": "NOT_MEASURED",
            "honesty": (
                "Multiple answers do not prove consensus or correctness. Semantic "
                "agreement, dissent recall, and decision quality require labeled evals."
            ),
        },
        "limits": {
            "participants_max": COUNCIL_MAX,
            "debate_participants_max": COUNCIL_DEBATE_MAX,
            "rounds_max": 2,
            "tokens_per_turn_max": COUNCIL_MAX_TOKENS,
            "turn_timeout_s": COUNCIL_TURN_TIMEOUT_S,
            "round_fanout": "CONCURRENT_BOUNDED",
            "timeout_turns": timeout_turns,
            "model_calls_observed": len(turn_evidence),
            "external_effectors": 0,
            "automatic_commit": False,
        },
        "human_checkpoint": {
            "required": True,
            "satisfied": False,
            "next_action": "Review evidence and explicitly approve, revise, or reject.",
        },
        "replay": {
            "key": "sha256:" + _sha256_json(replay_material),
            "material": replay_material,
            "verifier": "/api/a11oy/v1/verify/receipt",
            "public_key": "/cosign.pub",
        },
        "training": {
            "artifact": NEMO_ARTIFACT,
            "weights_present": False,
            "state": "NOT_PERFORMED",
        },
    }


def _mint_council_chain(contract: Dict[str, Any], ns: str = "a11oy",
                        store=None,
                        storage_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Append the proposal receipt to durable Khipu, with honest fallback."""
    payload = {
        "contract_version": contract.get("contract_version"),
        "decision_state": contract.get("decision_state"),
        "evidence_state": contract.get("evidence_state"),
        "prompt_sha256": contract.get("prompt_sha256"),
        "replay_key": (contract.get("replay") or {}).get("key"),
    }
    if store is not None:
        try:
            receipt = store.emit("ayllu.council.proposal", payload)
            ok, depth, first_break = store.verify()
            meta = _council_store_metadata(store, storage_meta)
            return {
                "state": "LIVE",
                "organ": "ayllu_council",
                "receipt_id": receipt.get("digest"),
                "seq": receipt.get("seq"),
                "chain_verified": bool(ok),
                "first_break_seq": first_break,
                "depth": depth,
                "persistence": ("PROCESS_RESTART_DURABLE_LOCAL_DISK"
                                if meta["durable"] else
                                "IN_MEMORY_RESETS_ON_RESTART"),
                "storage": meta,
            }
        except Exception as exc:
            # Do not lose the advisory response merely because durable storage
            # failed. Fall through to the legacy in-process chain and report the
            # exact downgrade in the returned evidence.
            storage_meta = {
                **(storage_meta or {}),
                "backend": "memory",
                "durable": False,
                "survives_process_restart": False,
                "survives_redeploy": "NOT_VERIFIED",
                "durable_append_error": type(exc).__name__,
            }
    try:
        import szl_khipu
        dag = szl_khipu.get_dag("ayllu_council", ns=ns)
        receipt = dag.emit("ayllu.council.proposal", payload)
        chain = dag.verify_chain()
        return {
            "state": "LIVE",
            "organ": "ayllu_council",
            "receipt_id": receipt.get("digest"),
            "seq": receipt.get("seq"),
            "chain_verified": bool(chain.get("ok")),
            "depth": dag.depth(),
            "persistence": "IN_MEMORY_RESETS_ON_RESTART",
            "storage": _council_store_metadata(None, storage_meta),
        }
    except Exception as exc:
        return {
            "state": "UNAVAILABLE",
            "organ": "ayllu_council",
            "receipt_id": None,
            "error": type(exc).__name__,
            "honesty": "Khipu append unavailable; no chain receipt fabricated.",
            "storage": _council_store_metadata(None, storage_meta),
        }


# --- The /ayllu page: a working chat + council UI. 0-CDN (pure inline markup, no
#     external assets). `__NS__`/`__VERSION__` are substituted at render time so the
#     JS+CSS braces stay literal (no f-string brace-doubling). --------------------
_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ayllu — a11oy agent council</title>
<style>
:root{--void:#080c14;--panel:#0d1520;--line:#16202c;--teal:#3af4c8;--fg:#dfe7ee;--dim:#7f93a6;--gold:#d4a444}
*{box-sizing:border-box}
body{margin:0;background:var(--void);color:var(--fg);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
background:radial-gradient(60% 40% at 70% -10%,rgba(58,244,200,.07),transparent 60%),
radial-gradient(50% 35% at 10% 110%,rgba(212,164,68,.05),transparent 60%)}
main{max-width:980px;margin:0 auto;padding:36px 22px;position:relative;z-index:1}
h1{color:var(--teal);margin:0 0 4px;font-size:26px;display:flex;align-items:center;gap:10px}
h2{font-size:16px;margin:0 0 10px;color:var(--fg)}
.sub{color:var(--dim);margin:0 0 22px}
.badge{font-size:11px;font-weight:700;letter-spacing:.04em;padding:3px 8px;border-radius:20px;
border:1px solid var(--line);color:var(--dim)}
.badge.live{color:#0a1;background:#0a2a17;border-color:#1c5}
.badge.stub{color:#da3;background:#2a2109;border-color:#a83}
.badge.warn{color:#e66;background:#2a1010;border-color:#a44}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 16px;margin:0 0 16px}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px}
select,textarea,input{width:100%;background:#0a121c;color:var(--fg);border:1px solid var(--line);
border-radius:7px;padding:8px 10px;font:inherit}
.row select{flex:2}.row input{flex:1}
select[multiple]{height:auto}
textarea{resize:vertical;margin-bottom:8px}
button{background:var(--teal);color:#04140f;border:0;border-radius:7px;padding:8px 16px;
font-weight:700;cursor:pointer}
button:disabled{cursor:wait;opacity:.55}
button.mini{background:transparent;color:var(--teal);border:1px solid var(--line);padding:3px 9px;
font-weight:600;font-size:12px}
.hint{color:var(--dim);font-size:12px;margin:0 0 8px}
.out{margin-top:10px}
.turn{border:1px solid var(--line);border-radius:9px;padding:10px 12px;margin-top:8px;background:#0a121c}
.turnh{display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.chip{width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;
font-size:11px;font-weight:800;color:var(--fg);border:1px solid var(--line);flex:none}
.meta{color:var(--dim);font-size:12px;margin-left:auto}
.arch{color:var(--dim);font-size:12px}
.ans{margin-top:7px;white-space:pre-wrap}
.rcpt{color:var(--dim);font-size:12px;margin-top:8px}
.contract{border-left:3px solid var(--teal);padding:9px 11px;margin:10px 0;
background:#071711;color:var(--dim);font-size:12px;line-height:1.6}
.contract b{color:var(--fg)}
.note{color:#da3;font-size:12px;margin-bottom:8px}
.err{color:#e66}
.stub{color:#da3;font-weight:700;font-size:11px}
.roundhdr{margin:14px 0 2px;color:var(--gold);font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.loopchip{font-size:10px;border:1px solid var(--line);border-radius:12px;padding:1px 7px;color:var(--dim)}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);font-size:14px}
th{color:var(--teal);font-weight:600}
.lg{border-top:1px solid var(--line);padding:7px 0}
.src{color:var(--dim);font-size:11px}
.law{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--teal);
padding:12px 14px;border-radius:6px;color:var(--dim);margin-top:6px;font-size:13px}
code{color:var(--teal)}
html{scroll-behavior:smooth}
.topbar{position:sticky;top:0;z-index:20;background:rgba(8,12,20,.92);backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
.tb-wrap{max-width:980px;margin:0 auto;padding:10px 22px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.tb-brand{color:var(--teal);font-weight:800;text-decoration:none;font-size:18px;display:flex;align-items:center;gap:8px}
.tb-nav{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.tb-nav a{color:var(--dim);text-decoration:none;font-size:13px}
.tb-nav a:hover{color:var(--fg)}
.tb-nav a.tb-home{color:var(--gold);font-weight:600}
section[id]{scroll-margin-top:72px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}
.panel{background:#0a121c;border:1px solid var(--line);border-radius:8px;padding:10px 12px;min-width:0}
.panel h3{margin:0 0 6px;font-size:13px;color:var(--teal);display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.kpi{font-size:19px;font-weight:800;color:var(--fg)}
.small{font-size:12px;color:var(--dim)}
.links{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.links a{color:var(--teal);text-decoration:none;font-size:12px;border:1px solid var(--line);border-radius:16px;padding:4px 11px}
.links a:hover{border-color:var(--teal)}
.tgl{display:flex;gap:7px;align-items:center;color:var(--dim);font-size:13px;margin:0 0 8px}
.tgl input{width:auto}
.prov{color:var(--dim);font-size:11px;margin-top:14px;line-height:1.6}
@media (max-width:720px){
 main{padding:24px 14px}
 .tb-wrap{padding:9px 14px;flex-wrap:nowrap}
 .tb-brand{flex:0 0 auto}
 .tb-nav{flex:1 1 auto;min-width:0;flex-wrap:nowrap;overflow-x:auto;
  -webkit-overflow-scrolling:touch;scrollbar-width:none}
 .tb-nav::-webkit-scrollbar{display:none}
 .tb-nav a{flex:0 0 auto}
 .card{padding:14px}
 .row{display:grid;grid-template-columns:minmax(0,1fr)}
 .row select,.row input{width:100%;min-width:0}
 table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;white-space:nowrap}
 .meta{margin-left:0;width:100%}
 section[id]{scroll-margin-top:58px}
}
</style></head><body>
<header class="topbar"><div class="tb-wrap">
<a class="tb-brand" href="/ayllu">Ayllu <span id="badge" class="badge">…</span></a>
<nav class="tb-nav"><a href="#sec-ask">Ask</a><a href="#sec-council">Council</a><a href="#sec-roster">Roster</a><a href="#sec-lounge">Lounge</a><a href="#sec-organism">Organism</a><a href="#sec-mesh">Mesh</a><a class="tb-home" href="/console" title="Back to the a11oy command centre">&#8592; a11oy command centre</a></nav>
</div></header>
<main>
<h1>Ayllu</h1>
<p class="sub">The AlloyScape tribe, ingested and reborn as a11oy's own agent community —
<span id="count">?</span> personas, one guarded loop. v__VERSION__ ·
<span title="Curated, cited text appended to every persona's system prompt — no weights changed anywhere.">knowledge instilled, never "trained"</span> ·
<span id="family">model binding loading</span></p>

<section class="card" id="sec-ask">
  <h2>Ask a persona</h2>
  <div class="row">
    <select id="persona" aria-label="Persona"></select>
    <input id="difficulty" type="number" min="0" max="1" step="0.1"
           placeholder="difficulty 0–1 (optional)" aria-label="Difficulty from zero to one">
  </div>
  <textarea id="askprompt" rows="3" placeholder="Ask a persona…" aria-label="Prompt for the selected persona"></textarea>
  <button id="askbtn">Ask</button>
  <div id="askout" class="out" aria-live="polite"></div>
</section>

<section class="card" id="sec-council">
  <h2>Convene a council</h2>
  <div class="contract"><b>Evidence-bound Council v2.</b> Every run carries a
  Nemo route receipt, per-turn output digests, a replay key, explicit limits, and a
  human checkpoint. State is always <code>PROPOSAL_ONLY</code>; semantic consensus and
  Council effectiveness remain <code>NOT_MEASURED</code> until labeled evaluation exists.
  <a href="/api/__NS__/v1/ayllu/council/manifest">machine-readable contract</a></div>
  <p class="hint">Defaults to 3 core personas; select up to 5 (⌘/Ctrl-click). Fan-out is
  capped to protect cost. Debate mode runs exactly two bounded rounds
  (after arXiv:2305.14325) and is capped to 3 personas.</p>
  <select id="councilsel" multiple size="6" aria-label="Council personas"></select>
  <label class="tgl"><input type="checkbox" id="debate">
  Debate mode — positions, then explicit dissent &amp; converge (2× cost)</label>
  <textarea id="councilprompt" rows="3" placeholder="A question for the council…" aria-label="Question for the council"></textarea>
  <button id="councilbtn">Convene</button>
  <div id="councilout" class="out" aria-live="polite"></div>
</section>

<section class="card" id="sec-roster">
  <h2>Roster</h2>
  <table id="roster"><thead><tr><th>Persona</th><th>Quechua</th><th>Archetype</th>
  <th>a11oy domain</th><th>Forge intent</th><th>Autonomy</th><th>Knowledge</th></tr></thead><tbody></tbody></table>
  <div class="src" style="margin-top:6px">"Instilled ✓" = the shared, cited Wave-13 leaders
  corpus is appended to that persona's system prompt at runtime. No model weights are
  changed anywhere — this is knowledge instillation, not training.</div>
</section>

<section class="card" id="sec-lounge">
  <h2>Opt-in lounge <button id="refreshlounge" class="mini">refresh</button></h2>
  <div id="lounge" class="out"></div>
</section>

<section class="card" id="sec-organism">
  <h2>The organism — anatomy · brain · formulas</h2>
  <div class="src" style="margin:.2rem 0 .6rem">The council is one organ of one governed
  organism. These panels read the same governed endpoints as the command centre — an
  unavailable endpoint says so rather than faking a value.</div>
  <div class="grid">
    <div class="panel"><h3>Formulas <span class="small" id="f-badge">…</span></h3><div id="f-out" class="small">loading…</div></div>
    <div class="panel"><h3>Doctrine lock <span class="small" id="d-badge">…</span></h3><div id="d-out" class="small">loading…</div></div>
    <div class="panel"><h3>Sovereign energy <span class="small" id="e-badge">…</span></h3><div id="e-out" class="small">loading…</div></div>
  </div>
  <div class="links">
    <a href="/living-anatomy">Living anatomy</a>
    <a href="/formulas">PURIQ formulas</a>
    <a href="/wires">The constitution</a>
    <a href="/api/__NS__/v1/brain/graph" title="Full brain graph JSON (~4 MB)">Brain graph (raw JSON)</a>
    <a href="/console">Command centre</a>
  </div>
</section>

<section class="card" id="sec-mesh">
  <h2>Mesh &amp; observability <span class="stub" id="mesh-badge">&#8230;</span></h2>
  <div class="src" style="margin:.2rem 0 .6rem">Live platform context the council runs
  inside, read from the same governed endpoints the command centre uses. Shown honestly:
  an unavailable endpoint says so rather than faking a value.</div>
  <div id="mesh-out" class="out"></div>
  <div id="obs-out" class="out" style="margin-top:.5rem"></div>
</section>

<div class="law"><b>Bounded-autonomy law.</b> Every persona runs under a11oy's
fail-closed Λ-gate; state-changing actions require two-person attestation. The tribe's
"always execute" mandate is deliberately <b>not</b> adopted. Answers come from a11oy's
own model backend + router; when neither a reachable local backend nor a remote
inference credential is available,
<code>ask</code>/<code>council</code> return a clearly-labeled stub — never a fabricated
answer. Debate mode is bounded to exactly two rounds. These turns do direct completion
only (no tool dispatch yet).</div>

<p class="prov"><b>Provenance.</b> Council patterns studied from the field's leaders and
rebuilt in a11oy's own idiom — MetaGPT (SOP role handoffs), CrewAI (role/goal remits),
LangGraph (bounded graph loops), CAMEL (agent societies), OpenAI Agents SDK / Google ADK
(visible handoffs &amp; guardrails) — all permissive-licensed; debate-then-converge after
arXiv:2305.14325. No code was copied from pattern-only sources. Personas carry this as
instilled knowledge (cited text in the system prompt); nothing here was "trained".</p>
</main>
<script>
const NS="__NS__";
const api = p => `/api/${NS}/v1/ayllu/`+p;
const gapi = p => `/api/${NS}/v1/`+p;
async function j(url,opts){
  try{const r=await fetch(url,opts);let d={};
    try{d=await r.json();}catch(e){}
    return {ok:r.ok,status:r.status,data:d};
  }catch(e){return {ok:false,status:'network',data:{error:'request unavailable'}};}
}
function esc(s){return (s==null?'':String(s)).replace(/[&<>]/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function hue(n){let h=0;for(const c of String(n))h=(h*31+c.charCodeAt(0))%360;return h;}
function chip(n){const h=hue(n);
  return `<span class="chip" style="background:hsl(${h} 55% 20%);border-color:hsl(${h} 55% 38%)">`
       + esc(String(n).slice(0,2).toUpperCase())+`</span>`;}
function renderTurn(t){
  const ans = t.answer!=null ? esc(t.answer) : '<i>'+esc(t.honesty)+'</i>';
  const model = t.model?('model: '+esc(t.model)):'no model';
  const tier = (t.tier&&t.tier.route)?(' · tier(advisory): '+esc(t.tier.route)):'';
  const stub = t.stub?' · <span class="stub">STUB</span>':'';
  const loop = (t.loop&&t.loop.mode)?`<span class="loopchip" title="${esc(t.loop.note||'')}">loop: ${esc(t.loop.mode)}</span>`:'';
  return `<div class="turn"><div class="turnh">${chip(t.persona)}<b>${esc(t.persona)}</b>`
       + `<span class="arch">${esc(t.archetype||'')}</span>${loop}`
       + `<span class="meta">${model}${tier}${stub}</span></div>`
       + `<div class="ans">${ans}</div></div>`;
}
async function loadRoster(){
  const {ok,status,data}=await j(api('roster'));
  if(!ok){
    document.getElementById('count').textContent='—';
    const badge=document.getElementById('badge');
    badge.textContent='UNAVAILABLE';badge.className='badge warn';
    badge.title='roster endpoint unavailable ('+String(status)+') — no live state fabricated';
    return;
  }
  document.getElementById('count').textContent=data.count;
  const b=data.backend||{}, badge=document.getElementById('badge'), mode=b.mode||'?';
  badge.textContent=mode.toUpperCase();
  badge.className='badge '+(mode==='live'?'live':mode==='stub'?'stub':'warn');
  badge.title=b.note||'';
  const mf=data.model_family||{}, family=document.getElementById('family');
  family.textContent=(mf.family_id||'model family unknown')+' · '+(mf.binding_state||'UNAVAILABLE');
  family.title='Profile intent only. The actual model is named by each turn receipt.';
  const sel=document.getElementById('persona'), csel=document.getElementById('councilsel');
  const rows=[];
  (data.personas||[]).forEach(p=>{
    const o=document.createElement('option');o.value=p.name;
    o.textContent=p.name+' — '+p.domain;sel.appendChild(o);
    csel.appendChild(o.cloneNode(true));
    const kn=p.knowledge_instilled?'instilled ✓':'—';
    const mb=p.model_binding||{};
    rows.push(`<tr><td>${chip(p.name)} <b>${esc(p.name)}</b></td><td>${esc(p.quechua)}</td>`
      +`<td>${esc(p.archetype)}</td><td>${esc(p.domain)}</td>`
      +`<td>${esc(mb.primary_profile||'UNBOUND')}</td>`
      +`<td>${esc(p.autonomy_level)}</td><td class="src">${kn}</td></tr>`);
  });
  document.querySelector('#roster tbody').innerHTML=rows.join('');
}
document.getElementById('askbtn').onclick=async()=>{
  const btn=document.getElementById('askbtn');
  const persona=document.getElementById('persona').value;
  const prompt=document.getElementById('askprompt').value.trim();
  const d=document.getElementById('difficulty').value;
  const out=document.getElementById('askout');
  if(!prompt){out.innerHTML='<span class="err">enter a prompt</span>';return;}
  out.textContent='…thinking';btn.disabled=true;out.setAttribute('aria-busy','true');
  const body={persona,prompt}; if(d!=='')body.difficulty=parseFloat(d);
  const {ok,status,data}=await j(api('ask'),{method:'POST',
    headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  btn.disabled=false;out.removeAttribute('aria-busy');
  if(!ok){out.innerHTML='<span class="err">'+esc(data.error||('HTTP '+status))+'</span>'
    +(data.retry_after_s?(' (retry in '+data.retry_after_s+'s)'):'');return;}
  const r=data.receipt||{}, sig=r.signed?'signed':'UNSIGNED';
  out.innerHTML=renderTurn(data.turn)
    +`<div class="rcpt">receipt: ${sig} · ask ${esc(String(data.ask_id)).slice(0,8)}</div>`;
};
document.getElementById('councilbtn').onclick=async()=>{
  const btn=document.getElementById('councilbtn');
  const prompt=document.getElementById('councilprompt').value.trim();
  const out=document.getElementById('councilout');
  if(!prompt){out.innerHTML='<span class="err">enter a prompt</span>';return;}
  const picks=[...document.getElementById('councilsel').selectedOptions].map(o=>o.value);
  const debate=document.getElementById('debate').checked;
  out.textContent=debate?'…convening (debate: 2 bounded rounds)':'…convening';
  btn.disabled=true;out.setAttribute('aria-busy','true');
  const body={prompt}; if(picks.length)body.personas=picks; if(debate)body.debate=true;
  const {ok,status,data}=await j(api('council'),{method:'POST',
    headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  btn.disabled=false;out.removeAttribute('aria-busy');
  if(!ok){out.innerHTML='<span class="err">'+esc(data.error||('HTTP '+status))+'</span>'
    +(data.retry_after_s?(' (retry in '+data.retry_after_s+'s)'):'');return;}
  const res=data.result||{}, rounds=res.rounds||[], c=data.contract||{};
  const cap=res.cap_note?('<div class="note">'+esc(res.cap_note)+'</div>'):'';
  const r1=rounds.filter(t=>(t.round||1)===1), r2=rounds.filter(t=>t.round===2);
  const route=c.routing||{}, outer=data.receipt||{};
  const contract=`<div class="contract"><b>${esc(c.decision_state||'PROPOSAL_ONLY')}</b>`
    +` · evidence ${esc(c.evidence_state||'UNKNOWN')}`
    +` · human review ${c.human_checkpoint&&c.human_checkpoint.required?'REQUIRED':'UNKNOWN'}`
    +`<br>Nemo: ${esc((route.experts_selected||[]).join(' + ')||route.state||'unavailable')}`
    +` · route ${esc(route.state||'UNKNOWN')} · outer receipt ${outer.signed?'SIGNED':'UNSIGNED'}`
    +`<br>replay ${esc((c.replay&&c.replay.key)||'unavailable')}`
    +`<br>semantic consensus: ${esc((c.semantic_consensus&&c.semantic_consensus.state)||'NOT_MEASURED')}`
    +`</div>`;
  let html=cap+contract;
  if(r2.length){
    html+='<div class="roundhdr">Round 1 — opening positions</div>'+r1.map(renderTurn).join('');
    html+='<div class="roundhdr">Round 2 — debate &amp; converge (final)</div>'+r2.map(renderTurn).join('');
  }else{
    html+=r1.map(renderTurn).join('');
    if(res.mode==='single-round'&&document.getElementById('debate').checked){
      html+='<div class="src">debate skipped honestly: fewer than two personas produced answers.</div>';
    }
  }
  out.innerHTML=html;
};
async function loadLounge(){
  const {ok,data}=await j(api('lounge')), out=document.getElementById('lounge');
  if(!ok){out.textContent='—';return;}
  const items=(data.recent||[]).slice().reverse();
  out.innerHTML=items.length? items.map(m=>`<div class="lg"><b>${esc(m.persona)}</b> `
    +`<span class="src">${esc(m.source)}</span><div>${esc(m.text)}</div></div>`).join('')
    :'<i>empty</i>';
}
document.getElementById('refreshlounge').onclick=loadLounge;
function unavailable(el,status){el.innerHTML='<span class="src">endpoint unavailable ('
  +esc(String(status))+') — shown honestly, not faked.</span>';}
async function loadFormulas(){
  const b=document.getElementById('f-badge'), out=document.getElementById('f-out');
  const {ok,status,data}=await j(gapi('formulas'));
  if(!ok){b.textContent='offline';unavailable(out,status);return;}
  b.textContent='live';
  const fs=(data.formulas||[]).slice(0,4);
  out.innerHTML='<div class="kpi">'+esc(String(data.count??'—'))+'</div>'
    +'<div class="small">registered formulas</div>'
    +fs.map(f=>`<div class="lg"><code>${esc(f.name)}</code><br><span class="src">${esc(f.proof_status||'')}</span></div>`).join('')
    +'<div class="src" style="margin-top:6px">Λ-aggregator uniqueness remains Conjecture 1 — never claimed proven.</div>';
}
async function loadDoctrine(){
  const b=document.getElementById('d-badge'), out=document.getElementById('d-out');
  const {ok,status,data}=await j(gapi('honest'));
  if(!ok){b.textContent='offline';unavailable(out,status);return;}
  const d=data.doctrine_lock||{};
  b.textContent=esc(d.state||'?');
  out.innerHTML='<div class="kpi">'+esc(String(d.declarations??'—'))+'</div>'
    +'<div class="small">Lean declarations · '+esc(String(d.axioms??'—'))+' axioms · '
    +esc(String(d.sorries??'—'))+' sorries (honest count)</div>'
    +'<div class="lg small">'+esc(d.lambda_note||'')+'</div>';
}
async function loadEnergy(){
  const b=document.getElementById('e-badge'), out=document.getElementById('e-out');
  const {ok,status,data}=await j(gapi('energy/live'));
  if(!ok){b.textContent='offline';unavailable(out,status);return;}
  b.textContent=esc(data.label||'?');
  const nodes=data.nodes||[];
  const live=nodes.filter(n=>n.live).length;
  out.innerHTML='<div class="kpi">'+(data.total_watts!=null?esc(String(data.total_watts))+' W':'—')+'</div>'
    +'<div class="small">'+live+'/'+nodes.length+' sovereign nodes live'
    +(data.total_watts==null?' — no wattage fabricated':'')+'</div>'
    +nodes.slice(0,3).map(n=>`<div class="lg small">${n.live?'●':'○'} ${esc(n.name)}</div>`).join('');
}
async function loadMesh(){
  const badge=document.getElementById('mesh-badge'), out=document.getElementById('mesh-out');
  const {ok,status,data}=await j(gapi('mesh/state'));
  if(!ok){badge.textContent='offline';unavailable(out,status);return;}
  badge.textContent='live';
  const wires=data.wires||{};
  const rows=Object.entries(wires).map(([k,w])=>
    `<tr><td><b>${esc(k)}</b></td><td>${esc(w.edge||'')}</td><td class="src">${esc(w.status||'')}</td></tr>`);
  out.innerHTML=rows.length?('<table><thead><tr><th>Wire</th><th>Edge</th><th>Status</th></tr></thead><tbody>'
    +rows.join('')+'</tbody></table>'
    +'<div class="src" style="margin-top:5px">doctrine '+esc(data.doctrine||'?')
    +' · khipu nodes: '+esc(String(data.khipu_nodes??'—'))+'</div>')
    :'<div class="lg"><b>mesh</b> <span class="src">no wires reported</span></div>';
}
async function loadObs(){
  const out=document.getElementById('obs-out');
  const {ok,status,data}=await j(gapi('observability/summary'));
  if(!ok){unavailable(out,status);return;}
  out.innerHTML='<div class="lg"><b>observability</b><pre class="src" style="white-space:pre-wrap;margin:.3rem 0 0">'
    +esc(JSON.stringify(data.melt||data,null,2).slice(0,600))+'</pre></div>';
}
loadRoster();loadLounge();loadMesh();loadObs();loadFormulas();loadDoctrine();loadEnergy();
</script>
</body></html>"""


def _page_html(ns: str) -> str:
    return _PAGE.replace("__NS__", ns).replace("__VERSION__", str(__version__))


def register(app, ns: str = "a11oy") -> str:
    """Mount the ayllu routes on `app`. Returns a status string."""
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse

    council_store, council_storage = _open_council_store(ns)
    try:
        app.state.ayllu_council_khipu = council_store
        app.state.ayllu_council_khipu_storage = council_storage
    except Exception:
        pass

    def _runtime_signer(request: "Request"):
        """Resolve the host signer lazily: Ayllu registers before serve.py creates it."""
        try:
            signer = getattr(request.app.state, "szl_sign_receipt", None)
            return signer if callable(signer) else None
        except Exception:
            return None

    async def _roster(request: "Request") -> "JSONResponse":
        backend = _backend.backend_status()
        return JSONResponse({
            "count": len(ROSTER),
            "namespace": ns,
            "personas": [
                {**p.metadata(), "model_binding": persona_binding(p.name)}
                for p in ROSTER
            ],
            "backend": backend,
            "model_family": family_binding(namespace=ns, backend_status=backend),
            "law": "a11oy bounded-autonomy (fail-closed Λ-gate); the tribe's unbounded "
                   "'always execute' mandate is NOT adopted",
            "provenance": "ingested from the AlloyScape tribe design; see ayllu/INGEST.md",
            "version": __version__,
        })

    async def _model_binding(request: "Request") -> "JSONResponse":
        return JSONResponse(family_binding(
            namespace=ns, backend_status=_backend.backend_status()))

    async def _council_manifest(request: "Request") -> "JSONResponse":
        storage = getattr(request.app.state, "ayllu_council_khipu_storage",
                          council_storage)
        return JSONResponse(council_manifest(ns, storage))

    async def _ask(request: "Request") -> "JSONResponse":
        ok, retry = _ASK_BUCKET.check()
        if not ok:
            return JSONResponse(
                {"error": "rate limited (process-wide ask budget)", "retry_after_s": retry},
                status_code=429, headers={"Retry-After": str(retry)})
        try:
            body = await _bounded_json_body(request)
        except _BodyTooLarge as exc:
            return JSONResponse({"error": str(exc), "max_bytes": MAX_BODY_BYTES},
                                status_code=413)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        name = body.get("persona")
        prompt = body.get("prompt")
        if not name or not prompt:
            return JSONResponse({"error": "'persona' and 'prompt' are required"},
                                status_code=422)
        if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT_CHARS:
            return JSONResponse(
                {"error": f"'prompt' must be a string ≤ {MAX_PROMPT_CHARS} chars",
                 "max_chars": MAX_PROMPT_CHARS}, status_code=422)
        p = get_persona(name)
        if p is None:
            return JSONResponse(
                {"error": f"unknown persona '{name}'",
                 "known": [x.name for x in ROSTER]}, status_code=404)
        raw_diff = body.get("difficulty")
        try:
            difficulty = None if raw_diff is None else float(raw_diff)
        except (TypeError, ValueError):
            return JSONResponse(
                {"error": "'difficulty' must be a number between 0 and 1"},
                status_code=422)
        async def _ask_complete(**kwargs):
            return await _backend.model_complete(
                **kwargs, max_tokens=ASK_MAX_TOKENS,
                timeout_s=ASK_TURN_TIMEOUT_S)

        turn = await run_turn(p, prompt, model_complete=_ask_complete,
                              difficulty=difficulty)
        binding = turn["model_binding"]
        ask_id = str(uuid.uuid4())
        # Bind the exact answer value returned to the caller.  An empty string is
        # a valid (if unhelpful) model output and must not silently fall through
        # to the honesty explanation in the signed receipt.
        answer = turn.get("answer")
        output_text = answer if answer is not None else (turn.get("honesty") or "")
        receipt = _make_receipt({
            "ask_id": ask_id,
            "persona": p.name,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "output_sha256": hashlib.sha256(output_text.encode()).hexdigest(),
            "tier_advisory": turn.get("tier", {}).get("route"),
            "model": turn.get("model"),
            "stub": turn.get("stub"),
            "energy_receipt_sha256": _receipt_sha(turn.get("energy_receipt")),
            "family_id": binding["family_id"],
            "profile_intent": binding["primary_profile"],
            "binding_state": binding["binding_state"],
            "model_binding_sha256": _sha256_json(binding),
            "honesty": turn.get("honesty"),
        }, sign_fn=_runtime_signer(request))
        return JSONResponse({"ask_id": ask_id, "turn": turn, "receipt": receipt})

    async def _council(request: "Request") -> "JSONResponse":
        ok, retry = _COUNCIL_BUCKET.check()
        if not ok:
            return JSONResponse(
                {"error": "rate limited (process-wide council budget)",
                 "retry_after_s": retry},
                status_code=429, headers={"Retry-After": str(retry)})
        try:
            body = await _bounded_json_body(request)
        except _BodyTooLarge as exc:
            return JSONResponse({"error": str(exc), "max_bytes": MAX_BODY_BYTES},
                                status_code=413)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        prompt = body.get("prompt")
        if not prompt:
            return JSONResponse({"error": "'prompt' is required"}, status_code=422)
        if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT_CHARS:
            return JSONResponse(
                {"error": f"'prompt' must be a string ≤ {MAX_PROMPT_CHARS} chars",
                 "max_chars": MAX_PROMPT_CHARS}, status_code=422)
        debate = bool(body.get("debate", False))
        max_n = COUNCIL_DEBATE_MAX if debate else COUNCIL_MAX
        requested = body.get("personas")
        cap_note = None
        if requested:
            if not isinstance(requested, list):
                return JSONResponse({"error": "'personas' must be a list"},
                                    status_code=422)
            names = [str(n) for n in requested][:max_n]
            if len(requested) > max_n:
                cap_note = (f"requested {len(requested)} personas; capped to "
                            f"{max_n} to bound cost"
                            + (" (debate mode runs two rounds)" if debate else ""))
        else:
            names = list(COUNCIL_DEFAULT)[:max_n]
            cap_note = (f"no personas specified; convened the {len(names)} core "
                        "personas (Amaru, Kamachiq, Qhatuq)")
        personas = [get_persona(n) for n in names]
        personas = [p for p in personas if p is not None]
        if not personas:
            return JSONResponse(
                {"error": "no known personas in request",
                 "known": [x.name for x in ROSTER]}, status_code=422)
        async def _council_complete(**kwargs):
            return await _backend.model_complete(
                **kwargs, max_tokens=COUNCIL_MAX_TOKENS,
                timeout_s=COUNCIL_TURN_TIMEOUT_S)

        result = await _LOUNGE.deliberate(
            prompt, personas, model_complete=_council_complete, debate=debate,
            publish_to_lounge=False)
        if cap_note:
            result["cap_note"] = cap_note
        council_id = str(uuid.uuid4())
        signer = _runtime_signer(request)
        nemo_route = _nemo_council_route(prompt, sign_fn=signer)
        contract = _build_council_contract(prompt, result, nemo_route, ns=ns)
        store = getattr(request.app.state, "ayllu_council_khipu", council_store)
        storage = getattr(request.app.state, "ayllu_council_khipu_storage",
                          council_storage)
        contract["chain"] = _mint_council_chain(
            contract, ns=ns, store=store, storage_meta=storage)
        receipt_body = {
            "council_id": council_id,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "participants": result["participants"],
            "mode": result.get("mode"),
            "models": [r.get("model") for r in result.get("rounds", [])],
            "decision_state": contract["decision_state"],
            "evidence_state": contract["evidence_state"],
            "replay_key": contract["replay"]["key"],
            "turn_evidence": contract["turn_evidence"],
            "model_family_binding_sha256": contract[
                "model_family_binding_sha256"],
            "nemo_route_receipt_sha256": _receipt_sha(
                (contract.get("routing") or {}).get("receipt")),
            "human_checkpoint": contract["human_checkpoint"],
            "chain": contract["chain"],
        }
        receipt = _make_receipt({
            "schema": "szl.ayllu.council-receipt/v2",
            "body": receipt_body,
            "payload_digest": _sha256_json(receipt_body),
            "receipt_id": contract["chain"].get("receipt_id"),
        }, sign_fn=signer)
        return JSONResponse({"council_id": council_id, "result": result,
                             "contract": contract, "receipt": receipt})

    async def _lounge_feed(request: "Request") -> "JSONResponse":
        return JSONResponse({"count": len(_LOUNGE.feed),
                             "recent": _LOUNGE.recent(50)})

    async def _page(request: "Request") -> "HTMLResponse":
        return HTMLResponse(_page_html(ns))

    app.add_api_route(f"/api/{ns}/v1/ayllu/roster", _roster, methods=["GET"],
                      tags=["ayllu"],
                      summary="a11oy-native agent roster + live/stub backend status")
    app.add_api_route(f"/api/{ns}/v1/ayllu/model-binding", _model_binding,
                      methods=["GET"], tags=["ayllu"],
                      summary="Honest SZL-Forge family and Yupaq proposal binding")
    app.add_api_route(f"/api/{ns}/v1/ayllu/ask", _ask, methods=["POST"],
                      tags=["ayllu"],
                      summary="Ask one persona — bounded, honest, receipted")
    app.add_api_route(f"/api/{ns}/v1/ayllu/council/manifest", _council_manifest,
                      methods=["GET"], tags=["ayllu"],
                      summary="Evidence-bound Council contract, limits, and reproduce path")
    app.add_api_route(f"/api/{ns}/v1/ayllu/council", _council, methods=["POST"],
                      tags=["ayllu"],
                      summary="Bounded multi-persona deliberation (capped fan-out; optional 2-round debate mode after arXiv:2305.14325)")
    app.add_api_route(f"/api/{ns}/v1/ayllu/lounge", _lounge_feed, methods=["GET"],
                      tags=["ayllu"], summary="Opt-in collaboration lounge feed")
    app.add_api_route("/ayllu", _page, methods=["GET"], include_in_schema=False)

    return (
        f"ok — ayllu registered: {len(ROSTER)} personas; live model backend "
        f"({_backend.backend_status().get('mode')}); bounded-autonomy Λ-gate; "
        f"/ayllu + /api/{ns}/v1/ayllu/roster|model-binding|ask|council|lounge; "
        f"debate-mode council; council_khipu={council_storage.get('backend')} "
        f"(process_restart_durable={council_storage.get('durable')}, "
        f"redeploy=NOT_VERIFIED); version={__version__}"
    )
