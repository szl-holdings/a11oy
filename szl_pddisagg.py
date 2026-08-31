"""
szl_pddisagg.py — SZL Prefill/Decode Disaggregation Map. An HONEST, MODELED
diagram + latency-model of splitting the PREFILL stage from the DECODE stage across the
a11oy mesh nodes (omen / betterwithage), showing which stage maps to which node.

Frontier context (cited, NEVER claimed as SZL's own): prefill/decode (PD)
disaggregation — running the compute-bound prefill (prompt ingestion, TTFT) on one pool
and the memory-bandwidth-bound decode (token generation, TPOT) on another — is becoming
the standard high-throughput serving architecture (see NVIDIA Dynamo v1.2.0,
github.com/ai-dynamo/dynamo, and the survey arXiv:2603.13358). a11oy does NOT yet
disaggregate: it does not actually route prefill to one node and decode to another. This
surface is a STRUCTURAL-ONLY / ROADMAP map — a deterministic latency MODEL of what the
split WOULD look like across the mesh, with an honest label. If mesh/state shows a node
LIVE it may be referenced, but this GET NEVER fabricates a real disaggregated dispatch.

  GET  /api/<ns>/v1/frontier/pddisagg?prompt_tokens=&gen_tokens=&prefill_node=&decode_node=

Returned JSON (top-level `label`, metrics nested under `payload`)
----------------------------------------------------------------------------
  label                       : "MODELED"
  payload.prompt_tokens       : modeled prompt length (prefill work)
  payload.gen_tokens          : modeled generated length (decode work)
  payload.nodes[]             : {id, stage, role} — mesh node → stage mapping (omen/betterwithage)
  payload.colocated           : {ttft_ms, tpot_ms, total_ms} — single-pool baseline model
  payload.disaggregated       : {ttft_ms, tpot_ms, total_ms, kv_transfer_ms} — split model
  payload.speedup             : modeled total-latency ratio colocated/disaggregated
  payload.stages              : {prefill, decode} descriptors (bound, node, cost model)
  payload.roadmap             : what a11oy would need to actually disaggregate (honest gap)
  payload.parts_labeled       : which parts are STRUCTURAL-ONLY vs ROADMAP
  payload.honest_note         : plain-language honesty disclaimer
  payload.citations           : dict of citable sources (verbatim, never claimed as ours)
  payload.computed_at         : ISO-8601 UTC timestamp

HONEST STATUS
  STRUCTURAL-ONLY / ROADMAP — the node→stage map and the TTFT/TPOT/KV-transfer latency
    figures are a deterministic arithmetic MODEL, genuinely computed from the inputs and
    reported, not fabricated. a11oy does NOT actually disaggregate prefill from decode
    today; the split, the cross-node KV-cache transfer, and the speedup are a ROADMAP
    design, not a MEASURED serving result. No live node reading backs any number here.

DOCTRINE v11
  Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1 (advisory, gray, never
  green). No fabricated dispatch; no MEASURED label without a live reading. Pure stdlib.
  Deterministic. 0 runtime CDN. RECEIPT-ON-WRITE, NOT ON-READ (this GET signs nothing).

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-08):
  NVIDIA Dynamo (disaggregated serving; PD disaggregation), v1.2.0:
    https://github.com/ai-dynamo/dynamo
  Survey / analysis of prefill-decode disaggregation for LLM serving:
    arXiv:2603.13358   https://arxiv.org/abs/2603.13358
  DistServe (disaggregating prefill and decoding — foundational result):
    Zhong et al. 2024, arXiv:2401.09670   https://arxiv.org/abs/2401.09670
  Splitwise (phase splitting for LLM inference):
    Patel et al. 2024, arXiv:2311.18677   https://arxiv.org/abs/2311.18677
"""
import hashlib
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import JSONResponse

CITATIONS = {
    "NVIDIA Dynamo v1.2.0 (disaggregated serving; PD disaggregation)": "https://github.com/ai-dynamo/dynamo",
    "Prefill/Decode disaggregation survey — arXiv:2603.13358": "https://arxiv.org/abs/2603.13358",
    "DistServe — Zhong et al. 2024 arXiv:2401.09670": "https://arxiv.org/abs/2401.09670",
    "Splitwise — Patel et al. 2024 arXiv:2311.18677": "https://arxiv.org/abs/2311.18677",
}

# MODELED per-stage cost coefficients (STRUCTURAL sketch; NOT measured on any GPU).
# Prefill is compute-bound: cost grows ~linearly with prompt tokens (batched matmuls).
# Decode is memory-bandwidth-bound: per-token cost is roughly constant, paid gen_tokens
# times (autoregressive). KV-cache transfer is the disaggregation tax (prefill node →
# decode node) modeled from the prompt's KV footprint.
_PREFILL_MS_PER_TOK = 0.28      # modeled prefill ms per prompt token (compute-bound)
_DECODE_MS_PER_TOK = 12.0       # modeled decode ms per generated token (bandwidth-bound)
_KV_MS_PER_TOK = 0.06           # modeled cross-node KV-cache transfer ms per prompt token
_COLOCATED_CONTENTION = 1.18    # modeled slowdown when prefill+decode share one pool
_MESH_NODES = ("omen", "betterwithage")


def _read_node_reachability():
    """REAL in-request read: probe the mesh node roster and report per-node reachability.

    The node -> stage mapping below is only meaningful if the nodes it names actually
    exist and can be reached, so we read that from the live orchestrator IN THIS REQUEST
    (szl_mesh_orchestrator.mesh_status(), which sets `reachable` only on a real 2xx).
    An unreachable node is reported as unreachable — a real negative observation, never
    upgraded and never faked. If the orchestrator is unavailable we say so and the map
    degrades honestly instead of implying a fleet that was never checked.
    """
    try:
        import szl_mesh_orchestrator as _mo
        st = _mo.mesh_status()
    except Exception as e:  # noqa: BLE001 — no orchestrator => honest unknown
        return {"read": False,
                "reason": f"mesh orchestrator unavailable: {type(e).__name__}",
                "nodes": {}, "reachable_count": None,
                "source": "szl_mesh_orchestrator.mesh_status (unavailable)"}
    rows = {}
    for n in (st.get("nodes") or []):
        name = str(n.get("name") or "").strip().lower()
        if not name:
            continue
        rows[name] = {"reachable": bool(n.get("reachable")),
                      "state": n.get("state"),
                      "joules_label": n.get("joules_label")}
    return {"read": True,
            "source": "szl_mesh_orchestrator.mesh_status (real probes THIS request)",
            "mesh_state": st.get("mesh_state"),
            "nodes": rows,
            "reachable_count": sum(1 for r in rows.values() if r["reachable"]),
            "note": ("reachability is set only by a real 2xx this request; an unreachable "
                     "node is a real negative observation, never a fabricated positive")}


def _model(prompt_tokens=1024, gen_tokens=256, prefill_node="omen", decode_node="betterwithage"):
    """Deterministic STRUCTURAL latency model of colocated vs disaggregated serving.

    colocated: one pool does prefill THEN decode, paying a modeled contention penalty on
      both phases (the field's known interference between compute-bound prefill and
      bandwidth-bound decode when they share a device).
    disaggregated: prefill on `prefill_node`, decode on `decode_node`, no contention, but
      paying a modeled cross-node KV-cache transfer to hand the prompt state over.
    """
    prompt_tokens = max(1, min(int(prompt_tokens), 1_000_000))
    gen_tokens = max(1, min(int(gen_tokens), 1_000_000))
    pnode = prefill_node if prefill_node in _MESH_NODES else _MESH_NODES[0]
    dnode = decode_node if decode_node in _MESH_NODES else _MESH_NODES[1]

    # base (uncontended) phase costs
    prefill_ms = prompt_tokens * _PREFILL_MS_PER_TOK
    decode_ms = gen_tokens * _DECODE_MS_PER_TOK
    kv_transfer_ms = prompt_tokens * _KV_MS_PER_TOK

    # colocated: contention penalty on both phases, no cross-node transfer.
    co_ttft = round(prefill_ms * _COLOCATED_CONTENTION, 3)
    co_tpot = round(_DECODE_MS_PER_TOK * _COLOCATED_CONTENTION, 3)
    co_total = round((prefill_ms + decode_ms) * _COLOCATED_CONTENTION, 3)

    # disaggregated: uncontended phases + KV handoff before decode starts.
    di_ttft = round(prefill_ms + kv_transfer_ms, 3)
    di_tpot = round(_DECODE_MS_PER_TOK, 3)
    di_total = round(prefill_ms + kv_transfer_ms + decode_ms, 3)

    speedup = round(co_total / di_total, 4) if di_total else 0.0

    reach = _read_node_reachability()

    def _live(nid):
        row = (reach.get("nodes") or {}).get(nid)
        if row is None:
            return {"reachable": None, "state": "UNKNOWN (not read this request)"}
        return {"reachable": row["reachable"], "state": row["state"]}

    nodes = [
        {"id": pnode, "stage": "prefill", "role": "compute-bound (prompt ingestion, TTFT)",
         "live": _live(pnode)},
        {"id": dnode, "stage": "decode", "role": "memory-bandwidth-bound (token generation, TPOT)",
         "live": _live(dnode)},
    ]

    return {
        "prompt_tokens": prompt_tokens,
        "gen_tokens": gen_tokens,
        "nodes": nodes,
        "node_reachability": reach,
        "mesh_nodes": list(_MESH_NODES),
        "colocated": {"ttft_ms": co_ttft, "tpot_ms": co_tpot, "total_ms": co_total,
                      "contention_factor": _COLOCATED_CONTENTION},
        "disaggregated": {"ttft_ms": di_ttft, "tpot_ms": di_tpot, "total_ms": di_total,
                          "kv_transfer_ms": round(kv_transfer_ms, 3)},
        "speedup": speedup,
        "stages": {
            "prefill": {"bound": "compute", "node": pnode,
                        "cost_model": f"{_PREFILL_MS_PER_TOK} ms/prompt-token"},
            "decode": {"bound": "memory-bandwidth", "node": dnode,
                       "cost_model": f"{_DECODE_MS_PER_TOK} ms/gen-token"},
        },
    }


def _receipt_design(payload):
    """UNSIGNED content-hash preview (design-only). RECEIPT-ON-WRITE, NOT ON-READ."""
    canonical = "|".join([
        f"prompt={payload['prompt_tokens']}",
        f"gen={payload['gen_tokens']}",
        f"prefill_node={payload['stages']['prefill']['node']}",
        f"decode_node={payload['stages']['decode']['node']}",
        f"co_total={payload['colocated']['total_ms']}",
        f"di_total={payload['disaggregated']['total_ms']}",
        f"speedup={payload['speedup']}",
    ])
    return {
        "kind": "pd-disaggregation-map-receipt (STRUCTURAL-ONLY design — no real dispatch)",
        "binds": [
            "prompt/gen token counts",
            "node → stage mapping (omen/betterwithage)",
            "modeled colocated vs disaggregated latency + speedup",
        ],
        "signature": "DSSE_PLACEHOLDER (cosign founder-gated) — NOT applied here",
        "signed": False,
        "minted_on_this_get": False,
        "receipt_preview_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "preview_digest_alg": "SHA-256 over a canonical map summary (UNSIGNED preview only)",
        "doctrine": "RECEIPT-ON-WRITE, NOT ON-READ — a GET signs nothing and grows no chain.",
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _h_pddisagg(req: Request):
    prompt_tokens = _ii(req, "prompt_tokens", 1024)
    gen_tokens = _ii(req, "gen_tokens", 256)
    prefill_node = req.query_params.get("prefill_node", "omen")
    decode_node = req.query_params.get("decode_node", "betterwithage")

    p = _model(prompt_tokens=prompt_tokens, gen_tokens=gen_tokens,
               prefill_node=prefill_node, decode_node=decode_node)
    p["receipt_design"] = _receipt_design(p)
    p.update({
        # MODELED (Wave 32): the latency arithmetic is EVALUATED IN THIS REQUEST from the
        # supplied token counts, and the node -> stage map is now bound to a REAL
        # in-request probe of the mesh roster (per-node reachability read from the live
        # orchestrator). A real computation over real reads is MODELED. The disaggregated
        # DISPATCH remains ROADMAP: a11oy does not split prefill from decode today, so no
        # latency figure here is MEASURED and none ever will be until a timed split runs.
        "label": "MODELED",
        "model": ("prefill/decode disaggregation latency map across the a11oy mesh "
                  "(omen/betterwithage), evaluated in-request against a real node-"
                  "reachability read. a11oy does NOT yet disaggregate — the SPLIT is "
                  "ROADMAP; the latency figures are MODELED, never MEASURED."),
        "provenance": {
            "computed_in_request": True,
            "inputs": {"prompt_tokens": p["prompt_tokens"], "gen_tokens": p["gen_tokens"],
                       "source": "request query parameters"},
            "node_reachability": p.get("node_reachability"),
            "cost_coefficients": {
                "prefill_ms_per_token": _PREFILL_MS_PER_TOK,
                "decode_ms_per_token": _DECODE_MS_PER_TOK,
                "kv_transfer_ms_per_token": _KV_MS_PER_TOK,
                "colocated_contention_factor": _COLOCATED_CONTENTION,
                "basis": "MODELED design coefficients — NOT measured on any GPU",
            },
            "citations": CITATIONS,
            "coverage": 1.0,
        },
        "measured_gap": ("MEASURED would require an actual disaggregated dispatch: prefill "
                         "on one node, a real cross-node KV-cache handoff, decode on the "
                         "other, and a timed end-to-end result. None of that runs today."),
        "roadmap": [
            "a KV-cache transfer path between mesh nodes (prefill node → decode node)",
            "a disaggregation-aware router that dispatches prefill and decode separately",
            "a live node reading to promote any latency figure from MODELED to MEASURED",
        ],
        "parts_labeled": {
            "MODELED": [
                "node → stage mapping (which node runs prefill vs decode)",
                "colocated vs disaggregated TTFT / TPOT / total latency model",
                "modeled KV-cache cross-node transfer cost",
                "modeled speedup ratio",
            ],
            "ROADMAP": [
                "actually disaggregating prefill from decode on the mesh (not done today)",
                "real cross-node KV transfer + disaggregation-aware dispatch",
            ],
            "CITED (not ours)": [
                "NVIDIA Dynamo v1.2.0 (github.com/ai-dynamo/dynamo)",
                "PD-disaggregation survey arXiv:2603.13358",
                "DistServe arXiv:2401.09670, Splitwise arXiv:2311.18677",
            ],
        },
        "honest_note": (
            "MODELED (latency arithmetic + real node-reachability read) / ROADMAP (the "
            "split itself). The node→stage map and every latency figure "
            "(TTFT, TPOT, KV-transfer, total, speedup) are a deterministic arithmetic "
            "MODEL, genuinely computed from the inputs and reported — not fabricated — but "
            "a11oy does NOT actually disaggregate prefill from decode today. There is no "
            "real cross-node KV-cache handoff and no live node reading behind any number, "
            "so nothing here is MEASURED and no disaggregated dispatch is claimed. The "
            "architecture is cited to NVIDIA Dynamo v1.2.0 (github.com/ai-dynamo/dynamo), "
            "the PD-disaggregation survey (arXiv:2603.13358), DistServe (arXiv:2401.09670) "
            "and Splitwise (arXiv:2311.18677) — a11oy claims NONE of these systems as its "
            "own. Λ stays Conjecture 1. Nothing here is in the locked-8."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    return JSONResponse({"label": "MODELED", "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/frontier/pddisagg onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/frontier"
    handlers = [(f"{base}/pddisagg", _h_pddisagg)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    p = _model(prompt_tokens=1024, gen_tokens=256)
    p["receipt_design"] = _receipt_design(p)
    assert p["nodes"][0]["stage"] == "prefill" and p["nodes"][1]["stage"] == "decode"
    assert p["stages"]["prefill"]["node"] == "omen"
    assert p["stages"]["decode"]["node"] == "betterwithage"
    assert p["disaggregated"]["total_ms"] < p["colocated"]["total_ms"], "disagg must model a win"
    assert p["speedup"] > 1.0, "modeled speedup must exceed 1.0"
    assert p["receipt_design"]["signed"] is False and p["receipt_design"]["minted_on_this_get"] is False
    print("nodes:", [(n["id"], n["stage"]) for n in p["nodes"]])
    print("colocated total_ms:", p["colocated"]["total_ms"], "disaggregated total_ms:", p["disaggregated"]["total_ms"])
    print("kv_transfer_ms:", p["disaggregated"]["kv_transfer_ms"], "speedup:", p["speedup"])
    print("receipt preview:", p["receipt_design"]["receipt_preview_digest"][:16], "... signed:", p["receipt_design"]["signed"])
    print("label: MODELED (latency model + real node read; split is ROADMAP)")
