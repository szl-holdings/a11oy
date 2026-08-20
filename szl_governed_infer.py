# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""szl_governed_infer.py — close the BRAIN -> INFERENCE -> RECEIPT -> ENERGY loop.

One governed WRITE turns the harvested estate brain from a queryable index into a
METERED, RECEIPTED inference organ:

  1. GROUND   a query retrieves a REAL Personalized-PageRank grounding subgraph
              from the brain (szl_brain_api.get_index(ns).ask — HippoRAG PPR over
              the honest a11oy_brain_graph). The subgraph is real whether or not a
              model is reachable.
  2. ANSWER   the grounded prompt is sent to the sovereign model at
              SZL_LOCAL_LLM_URL / OLLAMA_URL (model SZL_LOCAL_LLM_MODEL) IF it is
              reachable; the real output-token count (Ollama eval_count) is
              captured. If no model answers -> honest UNAVAILABLE for generated
              text. We NEVER fabricate an answer or a token.
  3. ENERGY   REAL energy is measured as an NVML meter counter-delta bracketing
              the turn (szl_energy_live.meter_snapshot, the #789 exporter path):
              joules = after.total_joules - before.total_joules. Because the meter
              counts the WHOLE GPU and exclusivity is NOT asserted, the honest
              label is MEASURED_SHARED_BOUNDED (an upper bound that may include
              co-tenant energy). No reachable meter / no positive delta ->
              UNAVAILABLE. Joules are NEVER fabricated.
  4. RECEIPT  a DSSE-style SHA-256 hash-chained receipt
              {q, subgraph_ids, answer_digest, model, joules, tokens_per_joule,
               node, ts, prev_hash, receipt_hash} is appended to a restart-durable
              append-only JSONL sidecar (szl-lake / szl-receipt style). When the
              Cosign signing secret is present the receipt is ALSO wrapped in a
              real DSSE envelope (szl_dsse); absent -> honest UNSIGNED marker, no
              fabricated signature. Receipts are emitted ONLY on this WRITE path.

Endpoints (registered BEFORE the SPA catch-all):
  POST /api/<ns>/v1/govern/brain-infer ?q=   run one governed metered turn (WRITE)
  GET  /api/<ns>/v1/govern/receipts     ?limit=  recent receipts + chain verify
  GET  /api/<ns>/v1/govern/verify       ?id=  recompute one receipt's hash -> verdict

NOTE ON THE PATH: the sellable, demo-critical POST /api/<ns>/v1/govern/infer is
already owned by szl_governed_api (Λ-gated governed turn). This module is
ADDITIVE and deliberately mounts the brain-grounded loop at /govern/brain-infer
so it never shadows that surface. /govern/receipts and /govern/verify are new.

DOCTRINE v11 (NON-NEGOTIABLE):
  - honest labels verbatim: MEASURED / MEASURED_SHARED_BOUNDED / MODELED /
    UNAVAILABLE — never upgraded.
  - NEVER fabricate a joule / token / answer / receipt / signature.
  - Λ = Conjecture 1 (advisory); trust <= 0.97; provenance 1.0; locked-8 unchanged.
  - Receipts on WRITES only, NEVER on GETs. Canonical a-11-oy.com.

Additive + import-safe + crash-proof: every external call is guarded; a missing
brain/meter/signing dependency degrades to an honest label, never a raise.
Pure stdlib (json / hashlib / os / socket / threading / datetime) + guarded reuse.
"""

import hashlib
import json
import os
import socket
import threading
import urllib.request
from datetime import datetime, timezone

# Honest label vocabulary (verbatim; never upgraded).
LABEL_MEASURED = "MEASURED"
LABEL_BOUNDED = "MEASURED_SHARED_BOUNDED"
LABEL_MODELED = "MODELED"
LABEL_UNAVAILABLE = "UNAVAILABLE"
RECEIPT_SCHEMA_V1 = "szl.govern.brain-infer/v1"
RECEIPT_SCHEMA_V2 = "szl.govern.inference/v2"

# Grounding subgraph size (k) for the PPR retrieval.
GROUND_K = 12
# Minimum positive counter-delta (joules) to accept as a real measurement; below
# this the meter noise floor dominates and we honestly report UNAVAILABLE.
JOULE_FLOOR = 0.5
# Λ-advisory trust ceiling — a derived confidence is NEVER presented above this.
TRUST_CEILING = 0.97

DOCTRINE = {
    "version": "v11",
    "lambda": "Conjecture 1",
    "locked_count": 8,
    "trust_ceiling": TRUST_CEILING,
    "provenance": 1.0,
    "canonical_domain": "a-11-oy.com",
    "note": ("brain-grounded metered inference; the graph is grounded by real PPR, "
             "energy is a real NVML counter-delta (MEASURED_SHARED_BOUNDED, whole-GPU "
             "upper bound), every write emits a hash-chained + DSSE receipt; "
             "answers/tokens/joules are NEVER fabricated."),
}


# --------------------------------------------------------------------------- #
# Time / hashing helpers.
# --------------------------------------------------------------------------- #
def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


def _node_id():
    """Honest node identity for the receipt (hostname). Never fabricated."""
    try:
        return socket.gethostname() or "unknown-node"
    except Exception:
        return "unknown-node"


# --------------------------------------------------------------------------- #
# Stage 1 — GROUND: real PPR grounding subgraph from the estate brain (guarded).
# --------------------------------------------------------------------------- #
def _ground(query, ns="a11oy", k=GROUND_K):
    """Retrieve the load-bearing grounding subgraph via szl_brain_api PPR.

    Returns {available, subgraph_ids, nodes, seeds, reason}. The subgraph is REAL
    (retrieved from the honest brain graph); a missing brain degrades honestly."""
    try:
        import szl_brain_api as _api  # type: ignore
        idx = _api.get_index(ns)
        res = idx.ask(query, k=k)
        grounding = res.get("grounding_subgraph") or {}
        nodes = grounding.get("nodes") or []
        return {
            "available": True,
            "subgraph_ids": list(res.get("cited_node_ids") or []),
            "nodes": [{"id": n.get("id"), "title": n.get("title"),
                       "kind": n.get("kind"), "ppr": n.get("ppr")}
                      for n in nodes],
            "seeds": [s.get("id") for s in (res.get("seeds") or [])],
            "retrieval": res.get("retrieval"),
        }
    except Exception as exc:  # honest degrade — no fabricated subgraph
        return {"available": False, "subgraph_ids": [], "nodes": [], "seeds": [],
                "reason": f"brain grounding unavailable: {type(exc).__name__}"}


# --------------------------------------------------------------------------- #
# Stage 2 — ANSWER: sovereign model call capturing a REAL token count (guarded).
# --------------------------------------------------------------------------- #
def _local_llm_url():
    return (os.environ.get("SZL_LOCAL_LLM_URL")
            or os.environ.get("OLLAMA_URL")
            or "").rstrip("/")


def _sovereign_gateway():
    return (os.environ.get("A11OY_SOVEREIGN_GATEWAY_URL") or "").rstrip("/")


def _sovereign_answer(query, ground_nodes):
    """Call the sovereign model over the grounding subgraph, IF reachable.

    Prefers an Ollama-compatible /api/generate at SZL_LOCAL_LLM_URL (or the
    A11OY_SOVEREIGN_GATEWAY_URL), so the response's real output-token count
    (eval_count) can be captured for an HONEST tokens_per_joule. No URL/model or
    an unreachable endpoint -> honest UNAVAILABLE (subgraph stays real). NEVER
    fabricates text or a token count."""
    url = _local_llm_url() or _sovereign_gateway()
    model = os.environ.get("SZL_LOCAL_LLM_MODEL", "").strip()
    if not url or not model:
        return {"available": False, "text": None, "tokens": 0, "model": None,
                "label": LABEL_UNAVAILABLE,
                "reason": "no SZL_LOCAL_LLM_URL/A11OY_SOVEREIGN_GATEWAY_URL + "
                          "SZL_LOCAL_LLM_MODEL configured"}
    cited = ", ".join(str(n.get("id")) for n in ground_nodes[:12])
    ctx = "\n".join(f"- {n.get('id')}: {n.get('title')}"
                    for n in ground_nodes[:12])
    prompt = (
        "Answer ONLY from the grounding nodes below. Cite the node ids you use. "
        "If they do not contain the answer, say so plainly.\n\n"
        f"Question: {query}\n\nGrounding nodes:\n{ctx}\n\n"
        f"(available node ids: {cited})")
    try:
        body = json.dumps({"model": model, "prompt": prompt,
                           "stream": False}).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/api/generate", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        text = (payload.get("response") or "").strip()
        if not text:
            return {"available": False, "text": None, "tokens": 0, "model": None,
                    "label": LABEL_UNAVAILABLE,
                    "reason": "sovereign model returned empty response"}
        # eval_count is the REAL number of output tokens generated by Ollama.
        tokens = payload.get("eval_count")
        tokens = int(tokens) if isinstance(tokens, int) else 0
        # Graph-grounded model prose is MODELED (a model's text over a real
        # subgraph), never MEASURED.
        return {"available": True, "text": text, "tokens": tokens,
                "model": f"{url.split('//')[-1]}:{model}", "label": LABEL_MODELED}
    except Exception as exc:
        return {"available": False, "text": None, "tokens": 0, "model": None,
                "label": LABEL_UNAVAILABLE,
                "reason": f"sovereign inference unavailable: {type(exc).__name__}"}


# --------------------------------------------------------------------------- #
# Stage 3 — ENERGY: REAL NVML meter counter-delta bracketing the turn (guarded).
# --------------------------------------------------------------------------- #
def _meter_joules():
    """Return (total_joules_or_None, reachable). Reuses szl_energy_live's #789
    NVML exporter snapshot. NEVER fabricates a reading."""
    try:
        import szl_energy_live as _el  # type: ignore
        snap = _el.meter_snapshot(force=True)
        return snap.get("total_joules"), bool(snap.get("reachable"))
    except Exception:
        return None, False


def _energy_delta(before, after, before_ok, after_ok):
    """Honest counter-delta energy label from two meter snapshots.

    MEASURED_SHARED_BOUNDED when both reads are reachable and the cumulative
    joules delta clears the noise floor (whole-GPU counter — exclusivity NOT
    asserted, so an upper bound). Otherwise UNAVAILABLE. NEVER fabricated."""
    if (before_ok and after_ok and isinstance(before, (int, float))
            and isinstance(after, (int, float))):
        delta = after - before
        if delta >= JOULE_FLOOR:
            return {"joules": round(delta, 6), "label": LABEL_BOUNDED,
                    "before_joules": before, "after_joules": after,
                    "method": "NVML cumulative-counter delta (whole-GPU upper "
                              "bound; exclusivity not asserted)"}
        return {"joules": None, "label": LABEL_UNAVAILABLE,
                "before_joules": before, "after_joules": after,
                "reason": f"counter delta {round(delta, 6)}J below floor "
                          f"{JOULE_FLOOR}J — not a reliable reading"}
    return {"joules": None, "label": LABEL_UNAVAILABLE,
            "reason": "NVML meter not reachable for a before/after counter-delta; "
                      "joules NOT fabricated"}


# --------------------------------------------------------------------------- #
# Stage 4 — RECEIPT: SHA-256 hash-chained, append-only JSONL sidecar (durable).
# --------------------------------------------------------------------------- #
_LOCK = threading.RLock()


def _log_path():
    override = os.environ.get("SZL_GOVERN_INFER_LOG")
    if override:
        return override
    here = os.path.dirname(os.path.abspath(__file__))
    import tempfile
    for cand in (here, tempfile.gettempdir()):
        try:
            os.makedirs(cand, exist_ok=True)
            probe = os.path.join(cand, ".szl_govern_infer.jsonl")
            with open(probe, "a", encoding="utf-8"):
                pass
            return probe
        except Exception:
            continue
    return os.path.join(tempfile.gettempdir(), ".szl_govern_infer.jsonl")


def _read_chain():
    """Replay the append-only log into an ordered receipt list. Deterministic."""
    path = _log_path()
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _prev_hash():
    chain = _read_chain()
    return chain[-1].get("receipt_hash", "") if chain else ""


def _make_receipt(query, subgraph_ids, answer_digest, energy, tokens, model,
                  prev_hash, *, answer_available=False,
                  receipt_source="brain-infer", base_url=""):
    """Build a DSSE-style SHA-256 hash-chained receipt over the governed turn.

    tokens_per_joule is populated ONLY when BOTH a real output-token count and a
    real MEASURED_SHARED_BOUNDED joule delta exist — otherwise it is null with an
    honest UNAVAILABLE label (never fabricated)."""
    joules = energy.get("joules")
    energy_label = energy.get("label", LABEL_UNAVAILABLE)
    tpj = None
    tpj_label = LABEL_UNAVAILABLE
    if (isinstance(joules, (int, float)) and joules > 0 and tokens
            and energy_label in (LABEL_MEASURED, LABEL_BOUNDED)):
        tpj = round(tokens / joules, 6)
        # tokens_per_joule inherits the joule measurement's honest label.
        tpj_label = energy_label
    body = {
        "schema": RECEIPT_SCHEMA_V2,
        "chain_alg": "sha256",
        "receipt_source": str(receipt_source or "unknown"),
        "q": query,
        "query_digest": _sha(query),
        "subgraph_ids": list(subgraph_ids),
        "subgraph_size": len(subgraph_ids),
        "answer_digest": answer_digest,
        "model": model,
        "answer_available": bool(answer_available),
        # A durable receipt is evidence of successful inference only when the
        # provider returned real non-empty text and named the model that ran.
        # Failed attempts still receive an attempt receipt, but never set this.
        "inference_receipted": bool(answer_available and answer_digest
                                      and model),
        "base_url_sha256": _sha(base_url) if base_url else None,
        "joules": joules,
        "energy_label": energy_label,
        "tokens": int(tokens or 0),
        "tokens_per_joule": tpj,
        "tokens_per_joule_label": tpj_label,
        "node": _node_id(),
        "ts": _now_iso(),
        "prev_hash": prev_hash,
    }
    body["receipt_hash"] = _receipt_hash(body)
    return body


def _receipt_hash(body):
    """Canonical SHA-256 over the load-bearing receipt fields (chain link)."""
    parts = [
        body.get("prev_hash", ""),
        body.get("query_digest", ""),
        body.get("answer_digest", ""),
        json.dumps(body.get("subgraph_ids", []), sort_keys=True),
        str(body.get("joules")),
        str(body.get("tokens")),
        str(body.get("model")),
        body.get("node", ""),
        body.get("ts", ""),
    ]
    # Preserve verification of existing v1 receipts while binding every new
    # inference-state field into the v2 hash.
    if body.get("schema") == RECEIPT_SCHEMA_V2:
        parts.extend([
            body.get("receipt_source", ""),
            str(bool(body.get("answer_available"))),
            str(bool(body.get("inference_receipted"))),
            body.get("base_url_sha256") or "",
        ])
    return _sha(*parts)


def record_provider_generation(query, text, model, *, tokens=0, base_url=""):
    """Persist one successful provider generation as a durable v2 receipt.

    This is called only from POST/write paths after a provider returned real,
    non-empty text.  Reachability, configuration, and a routing decision are not
    enough.  The append is fsync'd and immediately replay-verified; failure is
    returned honestly and never upgraded to receipted inference.
    """
    query = (query or "").strip()
    text = (text or "").strip()
    model = (model or "").strip()
    if not query or not text or not model:
        return {"ok": False, "inference_receipted": False,
                "reason": "query, non-empty provider text, and model are required"}
    try:
        token_count = max(0, int(tokens or 0))
    except (TypeError, ValueError):
        token_count = 0
    energy = {"joules": None, "label": LABEL_UNAVAILABLE,
              "reason": "provider-route receipt did not bracket an NVML meter delta"}
    with _LOCK:
        prev = _prev_hash()
        receipt = _make_receipt(
            query, [], _sha(text), energy, token_count, model, prev,
            answer_available=True, receipt_source="llm-route", base_url=base_url)
        _append(receipt)
        chain = _read_chain()
        persisted = bool(chain and chain[-1].get("receipt_hash") == receipt["receipt_hash"])
        verified = persisted and _verify_entry(chain[-1], prev)
    return {
        "ok": bool(verified),
        "inference_receipted": bool(verified),
        "receipt_hash": receipt["receipt_hash"] if verified else None,
        "schema": receipt["schema"],
        "reason": ("durable inference receipt appended and replay-verified"
                   if verified else "receipt append could not be replay-verified"),
    }


def inference_receipt_status(model=""):
    """Read-only successful-inference receipt status; never emits a receipt."""
    wanted = (model or "").strip()
    chain = _read_chain()
    prev = ""
    broken = []
    successful = []
    for idx, entry in enumerate(chain):
        valid = _verify_entry(entry, prev)
        if not valid:
            broken.append(idx)
        prev = entry.get("receipt_hash", prev)
        entry_model = str(entry.get("model") or "")
        model_match = (not wanted or entry_model == wanted
                       or entry_model.endswith(":" + wanted))
        if valid and entry.get("inference_receipted") is True and model_match:
            successful.append(entry)
    latest = successful[-1] if successful else None
    return {
        "inference_receipted": bool(successful and not broken),
        "successful_receipt_count": len(successful),
        "total_receipt_count": len(chain),
        "chain_ok": not broken,
        "latest_receipt_hash": latest.get("receipt_hash") if latest else None,
        "latest_model": latest.get("model") if latest else None,
    }


def _append(receipt):
    path = _log_path()
    with _LOCK:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, sort_keys=True, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())


def _maybe_dsse(receipt):
    """Wrap the receipt in a real DSSE envelope when the Cosign secret is present.

    Honest: absent secret -> UNSIGNED envelope marker (szl_dsse never fabricates a
    signature). A missing szl_dsse module degrades to a plain 'no dsse' note."""
    try:
        import szl_dsse as _dsse  # type: ignore
        env = _dsse.sign_payload(receipt, _dsse.KHIPU_PAYLOAD_TYPE)
        return {"signed": bool(env.get("signed")),
                "honesty": env.get("honesty"),
                "payloadType": env.get("payloadType"),
                "signatures": env.get("signatures", [])}
    except Exception as exc:
        return {"signed": False,
                "honesty": f"DSSE unavailable: {type(exc).__name__}; "
                           "hash-chain receipt still emitted"}


def _verify_entry(entry, prev_hash):
    """A receipt verifies iff its stored prev_hash matches the running chain head
    AND its receipt_hash recomputes exactly. Tamper-evident."""
    if entry.get("prev_hash", "") != prev_hash:
        return False
    return _receipt_hash(entry) == entry.get("receipt_hash")


# --------------------------------------------------------------------------- #
# The governed turn (a WRITE — emits a receipt).
# --------------------------------------------------------------------------- #
def govern_infer(query, ns="a11oy"):
    """Run ONE brain-grounded, metered, receipted inference turn for `query`.

    Returns {answer_label, grounding, receipt, energy, dsse, doctrine}.
    Crash-proof: any fault degrades to an honest response — never raises."""
    query = (query or "").strip()
    try:
        if not query:
            return {"ok": False, "kind": "govern-brain-infer", "ns": ns,
                    "doctrine": DOCTRINE, "error": "empty query (nothing to ground)",
                    "computed_at": _now_iso()}

        # Bracket the ENTIRE governed turn with the NVML counter so the delta
        # captures all GPU work (grounding embed + generation), honestly bounded.
        before_j, before_ok = _meter_joules()

        grounding = _ground(query, ns=ns)
        answer = _sovereign_answer(query, grounding.get("nodes") or [])

        after_j, after_ok = _meter_joules()
        energy = _energy_delta(before_j, after_j, before_ok, after_ok)

        ans_text = answer.get("text")
        answer_digest = _sha(ans_text) if ans_text else _sha("")
        subgraph_ids = grounding.get("subgraph_ids") or []

        with _LOCK:
            prev = _prev_hash()
            receipt = _make_receipt(query, subgraph_ids, answer_digest, energy,
                                    answer.get("tokens", 0), answer.get("model"),
                                    prev,
                                    answer_available=bool(answer.get("available")
                                                          and ans_text),
                                    receipt_source="brain-infer",
                                    base_url=_local_llm_url()
                                             or _sovereign_gateway())
            _append(receipt)
        dsse = _maybe_dsse(receipt)

        return {
            "ok": True, "kind": "govern-brain-infer", "ns": ns,
            "doctrine": DOCTRINE,
            "answer_label": answer.get("label"),
            "answer": {
                "label": answer.get("label"),
                "available": bool(answer.get("available")),
                "text": ans_text,
                "model": answer.get("model"),
                "tokens": answer.get("tokens", 0),
                "note": answer.get("reason", ""),
            },
            "grounding": {
                "available": bool(grounding.get("available")),
                "retrieval": grounding.get("retrieval"),
                "subgraph_ids": subgraph_ids,
                "subgraph_size": len(subgraph_ids),
                "nodes": grounding.get("nodes"),
                "seeds": grounding.get("seeds"),
                "note": grounding.get("reason", "grounding subgraph is REAL "
                        "(PPR over the honest brain graph)"),
            },
            "energy": energy,
            "receipt": receipt,
            "dsse": dsse,
            "honesty": ("grounding subgraph is REAL regardless of model reach; "
                        "generated prose is UNAVAILABLE unless a sovereign model "
                        "answered; joules are a whole-GPU NVML counter-delta "
                        "(MEASURED_SHARED_BOUNDED upper bound) or UNAVAILABLE — "
                        "never fabricated; receipt emitted ONLY on this write."),
            "computed_at": _now_iso(),
        }
    except Exception as exc:  # never raise into the app
        return {"ok": False, "kind": "govern-brain-infer", "ns": ns,
                "doctrine": DOCTRINE,
                "error": f"{type(exc).__name__}: {exc}",
                "computed_at": _now_iso()}


# --------------------------------------------------------------------------- #
# Read views (GETs — NEVER emit a receipt).
# --------------------------------------------------------------------------- #
def list_receipts(limit=50):
    """Recent receipts (newest-first) + an HONEST hash-chain verification.

    Pure read: verifies the chain by replaying prev_hash -> receipt_hash linkage;
    reports chain_ok truthfully and names the first broken link if any."""
    try:
        limit = max(1, min(1000, int(limit)))
    except Exception:
        limit = 50
    chain = _read_chain()
    prev = ""
    broken = []
    for i, entry in enumerate(chain):
        if not _verify_entry(entry, prev):
            broken.append({"index": i,
                           "receipt_hash": entry.get("receipt_hash", "")[:16]})
        prev = entry.get("receipt_hash", prev)
    recent = list(reversed(chain))[:limit]
    view = [{
        "receipt_hash": r.get("receipt_hash"),
        "prev_hash": r.get("prev_hash"),
        "q": r.get("q"),
        "subgraph_size": r.get("subgraph_size"),
        "model": r.get("model"),
        "receipt_source": r.get("receipt_source", "brain-infer"),
        "answer_available": bool(r.get("answer_available")),
        "inference_receipted": bool(r.get("inference_receipted")),
        "joules": r.get("joules"),
        "energy_label": r.get("energy_label"),
        "tokens": r.get("tokens"),
        "tokens_per_joule": r.get("tokens_per_joule"),
        "tokens_per_joule_label": r.get("tokens_per_joule_label"),
        "node": r.get("node"),
        "ts": r.get("ts"),
    } for r in recent]
    return {
        "ok": True, "kind": "govern-brain-infer-receipts",
        "label": LABEL_MEASURED,  # a real replay over the real on-disk chain
        "doctrine": DOCTRINE,
        "count": len(chain),
        "returned": len(view),
        "chain_ok": not broken,
        "broken_links": broken,
        "chain_alg": "sha256",
        "receipts": view,
        "note": ("chain verified by replaying prev_hash -> receipt_hash; "
                 "receipts are emitted ONLY on the /govern/brain-infer write path."),
        "computed_at": _now_iso(),
    }


def verify_receipt(receipt_id):
    """Recompute one receipt's hash and return VERIFIED / FAILED / UNKNOWN.

    VERIFIED: found, prev-link intact, recomputed hash matches.
    FAILED:   found but the chain link or recomputed hash does not match (tamper).
    UNKNOWN:  no receipt with that id (honest — not asserted good or bad)."""
    receipt_id = (receipt_id or "").strip()
    if not receipt_id:
        return {"ok": False, "verdict": "UNKNOWN", "reason": "no id supplied",
                "computed_at": _now_iso()}
    chain = _read_chain()
    prev = ""
    for entry in chain:
        if entry.get("receipt_hash") == receipt_id:
            ok = _verify_entry(entry, prev)
            return {
                "ok": True,
                "verdict": "VERIFIED" if ok else "FAILED",
                "receipt_id": receipt_id,
                "recomputed_hash": _receipt_hash(entry),
                "stored_hash": entry.get("receipt_hash"),
                "prev_hash": entry.get("prev_hash"),
                "chain_prev_expected": prev,
                "label": LABEL_MEASURED,
                "note": ("recomputed SHA-256 over the receipt's own fields + "
                         "prev-link; a mismatch is honestly reported FAILED."),
                "computed_at": _now_iso(),
            }
        prev = entry.get("receipt_hash", prev)
    return {"ok": True, "verdict": "UNKNOWN", "receipt_id": receipt_id,
            "reason": "no receipt with that id on this chain",
            "computed_at": _now_iso()}


# --------------------------------------------------------------------------- #
# Registration — POST /govern/brain-infer (write), GET /govern/{receipts,verify}.
# Raw-Request handlers via app.router.add_route (fallback add_api_route), so they
# resolve BEFORE the SPA catch-all. Does NOT touch the sellable /govern/infer.
# --------------------------------------------------------------------------- #
def register(app, ns="a11oy"):
    import fastapi
    base = f"/api/{ns}/v1/govern"

    async def _infer_handler(request: fastapi.Request):
        from starlette.responses import JSONResponse
        q = ""
        try:
            q = request.query_params.get("q", "") or ""
            if not q:
                raw = await request.body()
                if raw:
                    try:
                        data = json.loads(raw.decode("utf-8"))
                        q = str(data.get("q", "") or data.get("query", ""))
                    except Exception:
                        q = ""
        except Exception:
            q = ""
        return JSONResponse(govern_infer(q, ns=ns))

    async def _receipts_handler(request: fastapi.Request):
        from starlette.responses import JSONResponse
        limit = request.query_params.get("limit", "50")
        return JSONResponse(list_receipts(limit))

    async def _verify_handler(request: fastapi.Request):
        from starlette.responses import JSONResponse
        rid = request.query_params.get("id", "") or ""
        return JSONResponse(verify_receipt(rid))

    routes = [
        (f"{base}/brain-infer", _infer_handler, ["POST"]),
        (f"{base}/receipts", _receipts_handler, ["GET"]),
        (f"{base}/verify", _verify_handler, ["GET"]),
    ]
    router = getattr(app, "router", None)
    add_route = getattr(router, "add_route", None) if router else None
    mounted = []
    for path, fn, methods in routes:
        try:
            if callable(add_route):
                app.router.add_route(path, fn, methods=methods)
            else:
                app.add_api_route(path, fn, methods=methods)
            mounted.append(path)
        except Exception:
            try:
                app.add_api_route(path, fn, methods=methods)
                mounted.append(path)
            except Exception:
                pass
    return mounted


# --------------------------------------------------------------------------- #
# No-server self-test — runs one turn offline and asserts doctrine invariants.
# --------------------------------------------------------------------------- #
def _selftest():
    import tempfile
    # Isolate the chain in a temp log so the self-test never pollutes a real one.
    fd, tmp = tempfile.mkstemp(suffix=".jsonl", prefix="szl_gi_selftest_")
    os.close(fd)
    os.environ["SZL_GOVERN_INFER_LOG"] = tmp
    try:
        out = govern_infer("energy provenance receipt salience brain")
        assert out["kind"] == "govern-brain-infer", out
        rec = out["receipt"]
        assert rec and rec["receipt_hash"], out
        # No model in a bare runtime => honest UNAVAILABLE answer, never fabricated.
        if not out["answer"]["available"]:
            assert out["answer_label"] == LABEL_UNAVAILABLE, out
            assert out["answer"]["text"] is None, out
        # No reachable meter => joules UNAVAILABLE, never fabricated.
        if out["energy"]["label"] == LABEL_UNAVAILABLE:
            assert out["energy"]["joules"] is None, out
        # joules label is only ever an honest member of the vocabulary.
        assert out["energy"]["label"] in (LABEL_BOUNDED, LABEL_MEASURED,
                                          LABEL_UNAVAILABLE), out
        # tokens_per_joule only exists alongside a real joule measurement.
        if rec["tokens_per_joule"] is not None:
            assert rec["energy_label"] in (LABEL_MEASURED, LABEL_BOUNDED), rec
            assert rec["tokens"] > 0, rec

        # A second turn must chain onto the first (prev_hash linkage).
        out2 = govern_infer("second grounded query")
        assert out2["receipt"]["prev_hash"] == rec["receipt_hash"], out2

        # Receipts view verifies the real chain.
        lst = list_receipts(limit=10)
        assert lst["count"] == 2 and lst["chain_ok"] is True, lst

        # Verify verdicts: a real id VERIFIES, a bogus id is honestly UNKNOWN.
        v = verify_receipt(rec["receipt_hash"])
        assert v["verdict"] == "VERIFIED", v
        u = verify_receipt("deadbeef")
        assert u["verdict"] == "UNKNOWN", u

        return {"ok": True, "first_hash": rec["receipt_hash"][:16],
                "second_prev": out2["receipt"]["prev_hash"][:16],
                "chain_ok": lst["chain_ok"], "count": lst["count"],
                "answer_label": out["answer_label"],
                "energy_label": out["energy"]["label"],
                "grounding_available": out["grounding"]["available"]}
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
        os.environ.pop("SZL_GOVERN_INFER_LOG", None)


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
