# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
# Authored by the NEMOTRON SIGNED-TRAJECTORY build team. Co-Authored-By: Perplexity Computer Agent.
"""
szl_nemotron_ingest — map nvidia/Nemotron-Agentic-v1 into the SZL trajectory schema.

WHAT THIS IS (honest framing):
    A pure-CPU mapper that takes rows from NVIDIA's open agentic dataset
    (nvidia/Nemotron-Agentic-v1, 335,122 samples, CC BY 4.0) and re-expresses
    each multi-turn conversation as an SZL trajectory: one signed-step receipt
    per agent/tool turn (see szl_trajectory_sign). The output is QLoRA-ready and
    every step is independently signature-verifiable.

ATTRIBUTION (CC BY 4.0 — REQUIRED, never strip):
    Source dataset : nvidia/Nemotron-Agentic-v1
    Owner          : NVIDIA Corporation
    License         : Creative Commons Attribution 4.0 International (CC BY 4.0)
    Subsets         : interactive_agent (19,028) + tool_calling (316,094) = 335,122
    URL             : https://huggingface.co/datasets/nvidia/Nemotron-Agentic-v1
    Each emitted trajectory carries source="nvidia", verified=False, signed-status
    per the signer, label="SAMPLE", and the full attribution block above. We do NOT
    redistribute NVIDIA's raw rows here; we ship a representative SAMPLE mapping and
    the mapper so the full 335k can be re-derived locally from the open source.

WHAT THIS IS *NOT*:
    - Not a model. Not a training run. Not an Ultra reproduction. The signed corpus
      is a DATASET property. Actual QLoRA/GRPO training = ROADMAP (FORGE order,
      needs >=2x80GB GPU).
    - We do not claim NVIDIA endorses SZL. CC BY 4.0 attribution != endorsement.

SOURCE ROW SCHEMA (from the HF dataset card / preview):
    {
      "uuid": str,
      "messages": [ {role, content, [tool_calls], [tool_call_id], ...}, ... ],
      "license": "cc-by-4.0",
      "used_in": ["nano_v3", ...],
      "tools":  [ {"type":"function","function":{name,description,parameters}}, ... ],
      "reasoning": "on" | "off"
    }

MAPPING (Nemotron message -> SZL trajectory step):
    role "assistant" with tool_calls -> step {role:assistant, pattern:ReAct,
        action: the tool_call(s), restraint_verdict via _verdict_for()}
    role "tool"                      -> step {role:tool, observation: content}
    role "assistant" plain text      -> step {role:assistant, action: text,
        pattern: Reflexion if it looks like a self-correction else AutoReview}
    role "system"/"user"             -> recorded as trajectory context (not a
        signed agent action), surfaced in provenance.

ADDITIVE · stdlib + szl_trajectory_sign only · CPU-only · no network required.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, Optional

import szl_trajectory_sign as sts

SOURCE_DATASET = "nvidia/Nemotron-Agentic-v1"
SOURCE_OWNER = "NVIDIA Corporation"
SOURCE_LICENSE = "CC BY 4.0"
SOURCE_LICENSE_FULL = "Creative Commons Attribution 4.0 International (CC BY 4.0)"
SOURCE_URL = "https://huggingface.co/datasets/nvidia/Nemotron-Agentic-v1"
SOURCE_SUBSETS = {"interactive_agent": 19028, "tool_calling": 316094}
SOURCE_TOTAL = 335122

ATTRIBUTION = {
    "source_dataset": SOURCE_DATASET,
    "source_owner": SOURCE_OWNER,
    "license": SOURCE_LICENSE,
    "license_full": SOURCE_LICENSE_FULL,
    "url": SOURCE_URL,
    "subsets": SOURCE_SUBSETS,
    "total_source_samples": SOURCE_TOTAL,
    "note": (
        "Re-expressed into the SZL trajectory schema under CC BY 4.0. Attribution to "
        "NVIDIA is required and does not imply endorsement. Raw NVIDIA rows are not "
        "redistributed here; this is a representative SAMPLE mapping plus the mapper."
    ),
}

# Reflexion cue words: an assistant turn that reads like a self-correction.
_REFLEXION_CUES = (
    "let me reconsider", "i was wrong", "correction", "actually,", "on second thought",
    "let me retry", "that was incorrect", "i made an error", "let me fix",
)


def _verdict_for(msg: Dict[str, Any], tools_present: bool) -> str:
    """Conservative Restraint verdict for a mapped Nemotron turn.

    Honest defaults ("never engage on doubt"): a tool call with arguments is
    ALLOW; an assistant turn that declines/escalates -> HOLD/DECLINE; ambiguous
    tool environments -> MONITOR.
    """
    content = (msg.get("content") or "")
    low = content.lower() if isinstance(content, str) else ""
    if any(w in low for w in ("cannot", "i'm sorry, but", "not able to", "decline",
                              "against policy", "i can't")):
        return "DECLINE"
    if any(w in low for w in ("need to verify", "please confirm", "let me check",
                              "i need more information", "could you clarify")):
        return "HOLD"
    if msg.get("tool_calls"):
        return "ALLOW"
    if tools_present and msg.get("role") == "assistant" and not low.strip():
        return "MONITOR"
    return "ALLOW"


def _pattern_for(msg: Dict[str, Any], prev_assistant_text: str) -> str:
    role = msg.get("role")
    content = msg.get("content") or ""
    low = content.lower() if isinstance(content, str) else ""
    # A self-correcting turn is Reflexion even if it also calls a tool (the
    # backtrack is the salient property for the trajectory corpus).
    if role == "assistant" and any(c in low for c in _REFLEXION_CUES):
        return "Reflexion"
    if msg.get("tool_calls"):
        return "ReAct"
    if role == "assistant":
        return "AutoReview"
    return "ReAct"


def _action_of(msg: Dict[str, Any]) -> Any:
    """Extract the agent action: tool_calls if present, else the text content."""
    tcs = msg.get("tool_calls")
    if tcs:
        # Normalise to {name, arguments} pairs (OpenAI-style function tool_calls).
        out = []
        for tc in tcs:
            fn = (tc or {}).get("function", {}) if isinstance(tc, dict) else {}
            out.append({"name": fn.get("name"), "arguments": fn.get("arguments")})
        return {"tool_calls": out}
    return msg.get("content", "")


def map_row(row: Dict[str, Any], *, label: str = "SAMPLE",
            environment: str = "nemotron-agentic") -> Dict[str, Any]:
    """Map ONE Nemotron-Agentic-v1 row to a sealed, DSSE-signed SZL trajectory.

    Returns the seal() dict: {"provenance", "steps", "jsonl"} with the attribution
    and source UUID embedded in provenance.extra.
    """
    uuid_src = row.get("uuid") or ""
    messages: List[Dict[str, Any]] = row.get("messages") or []
    tools = row.get("tools") or []
    tools_present = bool(tools)
    reasoning = row.get("reasoning", "off")
    used_in = row.get("used_in") or []

    # Reconstruct a short task descriptor from the first user turn.
    task = ""
    for m in messages:
        if m.get("role") == "user":
            c = m.get("content") or ""
            task = (c[:160] + "…") if isinstance(c, str) and len(c) > 160 else c
            break

    t = sts.SignedTrajectory(task=task or f"nemotron:{uuid_src[:8]}",
                             environment=environment, label=label)
    last_assistant_idx: Optional[int] = None
    last_assistant_text = ""
    context_turns: List[Dict[str, Any]] = []

    for m in messages:
        role = m.get("role")
        if role in ("system", "user"):
            # Context, not a signed agent action — preserved in provenance.
            context_turns.append({"role": role,
                                  "content": (m.get("content") or "")[:500]})
            continue
        if role == "tool":
            # Observation turn: attach as a tool observation step.
            t.add(action={"tool_result_for": m.get("tool_call_id")},
                  observation=m.get("content", ""), role="tool",
                  pattern="ReAct", restraint_verdict="MONITOR")
            continue
        if role == "assistant":
            pattern = _pattern_for(m, last_assistant_text)
            verdict = _verdict_for(m, tools_present)
            is_corr = pattern == "Reflexion"
            t.add(action=_action_of(m), observation="", role="assistant",
                  pattern=pattern, restraint_verdict=verdict,
                  is_correction=is_corr,
                  correction_of=last_assistant_idx if is_corr else None,
                  tool_calls=([{"function": (tc or {}).get("function", {})}
                               for tc in (m.get("tool_calls") or [])] or None))
            last_assistant_idx = len(t.steps) - 1
            if isinstance(m.get("content"), str):
                last_assistant_text = m["content"]

    sealed = t.seal(outcome="mapped")
    sealed["provenance"]["source"] = "nvidia"
    sealed["provenance"]["verified"] = False
    sealed["provenance"]["reasoning_mode"] = reasoning
    sealed["provenance"]["used_in"] = used_in
    sealed["provenance"]["source_uuid"] = uuid_src
    sealed["provenance"]["context_turns"] = context_turns
    sealed["provenance"]["tools_count"] = len(tools)
    sealed["provenance"]["attribution"] = ATTRIBUTION
    return sealed


def map_rows(rows: Iterable[Dict[str, Any]], *, label: str = "SAMPLE",
             environment: str = "nemotron-agentic") -> List[Dict[str, Any]]:
    return [map_row(r, label=label, environment=environment) for r in rows]


# --------------------------------------------------------------------------- #
# Representative SAMPLE rows (faithful to the published schema; NOT NVIDIA's
# verbatim rows — see ATTRIBUTION.note). Used to ship a demo corpus CPU-only.
# --------------------------------------------------------------------------- #
def sample_rows() -> List[Dict[str, Any]]:
    """A handful of schema-faithful representative rows (tool_calling +
    interactive_agent flavours), so the served demo has real content offline."""
    return [
        {
            "uuid": "ff6ab2b0-7551-468c-8606-a7c3b0c75b68",
            "license": "cc-by-4.0",
            "used_in": ["nano_v3"],
            "reasoning": "on",
            "tools": [{"type": "function", "function": {
                "name": "place_order",
                "description": "Create a new food delivery order",
                "parameters": {"type": "object", "properties": {
                    "user_id": {"type": "string"},
                    "restaurant_id": {"type": "string"}}}}}],
            "messages": [
                {"role": "system", "content": "You are a customer service agent. "
                 "Follow the <policy>…</policy>. You may message the user or call a tool."},
                {"role": "user", "content": "Order me a large pepperoni pizza from Tony's."},
                {"role": "assistant", "content": "Let me check the menu first.",
                 "tool_calls": [{"type": "function", "function": {
                     "name": "get_menu", "arguments": "{\"restaurant_id\":\"tonys\"}"}}]},
                {"role": "tool", "tool_call_id": "c1",
                 "content": "{\"items\":[{\"id\":\"p_lg\",\"name\":\"Large Pepperoni\"}]}"},
                {"role": "assistant", "content": "I need to verify your delivery address "
                 "before placing the order. Could you confirm it?"},
                {"role": "user", "content": "123 Main St, 10588."},
                {"role": "assistant", "content": "Placing your order now.",
                 "tool_calls": [{"type": "function", "function": {
                     "name": "place_order",
                     "arguments": "{\"user_id\":\"u1\",\"restaurant_id\":\"tonys\"}"}}]},
                {"role": "tool", "tool_call_id": "c2",
                 "content": "{\"order_id\":\"o_99\",\"status\":\"confirmed\"}"},
                {"role": "assistant", "content": "Done — order o_99 is confirmed."},
            ],
        },
        {
            "uuid": "a1c9d2e3-0000-4aaa-bbbb-1234567890ab",
            "license": "cc-by-4.0",
            "used_in": ["super_v3"],
            "reasoning": "on",
            "tools": [{"type": "function", "function": {
                "name": "search_flights",
                "description": "Search available flights",
                "parameters": {"type": "object", "properties": {
                    "origin": {"type": "string"}, "dest": {"type": "string"}}}}}],
            "messages": [
                {"role": "system", "content": "You are a travel agent. Obey policy."},
                {"role": "user", "content": "Find me a flight JFK to LAX tomorrow."},
                {"role": "assistant", "content": "Searching flights.",
                 "tool_calls": [{"type": "function", "function": {
                     "name": "search_flights",
                     "arguments": "{\"origin\":\"JFK\",\"dest\":\"LAZ\"}"}}]},
                {"role": "tool", "tool_call_id": "c1",
                 "content": "{\"error\":\"unknown airport LAZ\"}"},
                {"role": "assistant", "content": "Correction: I mistyped the airport "
                 "code. Let me retry with LAX.",
                 "tool_calls": [{"type": "function", "function": {
                     "name": "search_flights",
                     "arguments": "{\"origin\":\"JFK\",\"dest\":\"LAX\"}"}}]},
                {"role": "tool", "tool_call_id": "c2",
                 "content": "{\"flights\":[{\"id\":\"f1\",\"dep\":\"08:00\"}]}"},
                {"role": "assistant", "content": "Found flight f1 departing 08:00."},
            ],
        },
        {
            "uuid": "b2d0e4f5-1111-4ccc-dddd-0987654321fe",
            "license": "cc-by-4.0",
            "used_in": ["ultra_v3"],
            "reasoning": "off",
            "tools": [{"type": "function", "function": {
                "name": "issue_refund",
                "description": "Issue a refund subject to policy tier",
                "parameters": {"type": "object", "properties": {
                    "order_id": {"type": "string"},
                    "refund_tier": {"type": "string", "enum": ["full", "partial"]}}}}}],
            "messages": [
                {"role": "system", "content": "Refund agent. Enforce refund policy strictly."},
                {"role": "user", "content": "I want a full refund on order o_77, no receipt."},
                {"role": "assistant", "content": "I'm sorry, but I cannot issue a full "
                 "refund without proof of purchase under policy. I can escalate to a "
                 "human reviewer if you'd like."},
            ],
        },
    ]


# --------------------------------------------------------------------------- #
# Optional: load real NVIDIA rows from a local JSONL (if a user has downloaded
# the dataset). Network-free; only reads what's on disk.
# --------------------------------------------------------------------------- #
def load_local_jsonl(path: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if limit is not None and i >= limit:
                break
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    return rows


def build_sample_corpus(label: str = "SAMPLE") -> Dict[str, Any]:
    """Map the representative sample rows; return {trajectories, jsonl, stats}."""
    sealed = map_rows(sample_rows(), label=label)
    all_steps_jsonl: List[str] = []
    for s in sealed:
        if s["jsonl"]:
            all_steps_jsonl.append(s["jsonl"])
    jsonl = "\n".join(all_steps_jsonl)
    total_steps = sum(s["provenance"]["total_steps"] for s in sealed)
    verdict_counts: Dict[str, int] = {}
    pattern_counts: Dict[str, int] = {}
    for s in sealed:
        for st in s["steps"]:
            verdict_counts[st["restraint_verdict"]] = \
                verdict_counts.get(st["restraint_verdict"], 0) + 1
            pattern_counts[st["pattern"]] = pattern_counts.get(st["pattern"], 0) + 1
    return {
        "trajectories": sealed,
        "jsonl": jsonl,
        "stats": {
            "label": label,
            "trajectory_count": len(sealed),
            "total_steps": total_steps,
            "verdict_counts": verdict_counts,
            "pattern_counts": pattern_counts,
            "signing_available": sts.signing_available(),
            "attribution": ATTRIBUTION,
        },
    }


if __name__ == "__main__":
    corpus = build_sample_corpus()
    v = sts.verify_jsonl(corpus["jsonl"])
    print(json.dumps({
        "trajectories": corpus["stats"]["trajectory_count"],
        "total_steps": corpus["stats"]["total_steps"],
        "verdict_counts": corpus["stats"]["verdict_counts"],
        "pattern_counts": corpus["stats"]["pattern_counts"],
        "verify": {k: v[k] for k in ("total_steps", "all_hash_ok", "signed", "sig_ok")},
        "attribution_license": corpus["stats"]["attribution"]["license"],
    }, indent=2))
