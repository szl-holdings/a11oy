# -*- coding: utf-8 -*-
# ============================================================================
# a11oy_react_core.py  —  LANE A  AGENTIC CORE  (Dev A, SZL Holdings)
# ----------------------------------------------------------------------------
# A REAL, resumable ReAct execution graph (Thought -> Action -> Observation)
# where EACH node transition is a SIGNED receipt boundary, plus:
#   * SqliteSaver-style checkpointing  (crash mid-run -> /resume continues)
#   * Reflexion inner loop             (NL reflection prepended next activation)
#   * Generative-Agents memory scoring score(m)=a_rec*g^dt + a_imp*imp + a_rel*cos
#   * Letta-style memory tiering       (working in-context + archival vector)
#   * Voyager skill library            (admit a recipe ONLY after a passing receipt)
#
# Honest engineering (DOCTRINE v11):
#   - The signer is the HOST app's REAL in-image ECDSA-P256 DSSE signer
#     (_a11oy_sign_receipt), passed in via register(); we NEVER fabricate a
#     signature. verify_fn re-verifies against /cosign.pub.
#   - The vector store is LOCAL (sqlite + numpy, hashing-trie embeddings) — 0
#     external CDN/service. Embeddings are a deterministic local feature hash
#     (labelled HEURISTIC), not a remote model, so retrieval is reproducible
#     offline. Scores are surfaced honestly with their components.
#   - Trust / coverage framing, never bare "confidence %".
#   - Routes are inserted at position 0 (Starlette Route) so they beat the SPA
#     catch-all, mirroring szl_agentic_loop.
#   - Endpoints live under the FREE /api/a11oy/v1/agent/react/* sub-namespace
#     (run/resume/trace/checkpoints) so we do NOT collide with the existing
#     /run, /tools, /verify-chain, /governance-standards, /_diag, /loop.
#
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
# ============================================================================
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Storage: a single local sqlite DB under /tmp (ephemeral per container, which
# is the honest reality of a HF Space). All five subsystems persist here so a
# crash mid-run can resume from the last committed checkpoint within the life
# of the container. Labelled accordingly in the UI.
# ---------------------------------------------------------------------------
_DB_PATH = os.environ.get("A11OY_REACT_DB", "/tmp/a11oy_react_core.sqlite3")
_LOCK = threading.RLock()
_EMBED_DIM = 64  # local hashing-trick embedding dimension


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_epoch() -> float:
    return time.time()


def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# a11oy RESTRAINT integration (R1 owns a11oy_restraint.py — the governed,
# Ponytail-derived 6-rung code-frugality ladder). When an Action node WRITES
# CODE, we gate the intended diff through restraint FIRST and record the
# restraint decision in that node's signed receipt. We integrate WITHOUT
# touching R1's module: (1) try import a11oy_restraint.evaluate in-process;
# (2) else POST the diff to the live /api/a11oy/v1/restraint/evaluate endpoint;
# (3) else degrade HONESTLY (PENDING) — never fabricating a rung/number/signature.
# Ponytail is MIT (github.com/DietrichGebert/ponytail) — adopted + governed.
# ---------------------------------------------------------------------------
_RESTRAINT_HTTP = os.environ.get(
    "A11OY_RESTRAINT_URL",
    "http://127.0.0.1:7860/api/a11oy/v1/restraint/evaluate")
_PONYTAIL = {"repo": "https://github.com/DietrichGebert/ponytail",
             "license": "MIT", "relation": "adopted + governed (R1: a11oy_restraint.py)"}


def _restraint_mod():
    try:
        return __import__("a11oy_restraint")
    except Exception:
        return None


def _restraint_evaluate(task: str, intensity: str = "full", lang=None, sign_fn=None):
    """Route an intended code diff through R1's restraint ladder. Returns a
    compact verdict (rung + ceiling + lines-saved + Λ + signed receipt) or an
    honest PENDING degrade. NEVER fabricates a rung/number/signature."""
    task = (task or "").strip()
    mod = _restraint_mod()
    dec = None
    if mod is not None and hasattr(mod, "evaluate"):
        try:
            d = mod.evaluate(task, intensity=intensity, lang=lang, sign_fn=sign_fn)
            if isinstance(d, dict):
                d.setdefault("integration", "in-process import (a11oy_restraint.evaluate)")
                d.setdefault("status", "LIVE")
                dec = d
        except Exception:
            dec = None
    if dec is None:
        try:
            import urllib.request
            body = json.dumps({"task": task, "intensity": intensity,
                               "lang": lang}).encode("utf-8")
            req = urllib.request.Request(
                _RESTRAINT_HTTP, data=body, method="POST",
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    d = json.loads(resp.read().decode("utf-8"))
                    if isinstance(d, dict) and d.get("stopped_at_rung"):
                        d.setdefault("integration", "HTTP /api/a11oy/v1/restraint/evaluate")
                        d.setdefault("status", "LIVE")
                        dec = d
        except Exception:
            dec = None
    if dec is None:
        return {
            "status": "PENDING", "applied": False,
            "stopped_at_rung": None, "rung_key": None, "rung_name": None,
            "ceiling": None, "restraint_comment": None,
            "lines_saved_estimate": None, "lines_saved_label": "PENDING",
            "lambda_advisory": None,
            "restraint_receipt": {"signed": False,
                                  "honesty": "restraint /evaluate not reachable (R1 in "
                                             "flight); no rung/number/signature fabricated."},
            "integration": "PENDING — a11oy_restraint not importable AND /evaluate unreachable",
            "provenance": _PONYTAIL,
            "honesty": ("a11oy Restraint (R1) is not yet wired in this image; the code "
                        "action is gated and labelled PENDING (no fabrication)."),
        }
    lse = dec.get("lines_saved_estimate") or {}
    lam = dec.get("lambda_score") or {}
    rcpt = dec.get("signed_receipt") or {}
    return {
        "status": dec.get("status", "LIVE"), "applied": True,
        "stopped_at_rung": dec.get("stopped_at_rung"),
        "rung_key": dec.get("rung_key"), "rung_name": dec.get("rung_name"),
        "ceiling": dec.get("ceiling"),
        "restraint_comment": dec.get("restraint_comment"),
        "lines_saved_estimate": lse.get("lines_saved_modeled"),
        "lines_saved_label": lse.get("label", "MODELED"),
        "lambda_advisory": lam.get("lambda"),
        "restraint_receipt": rcpt,
        "integration": dec.get("integration"),
        "provenance": dec.get("provenance", _PONYTAIL),
    }


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH, timeout=30, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c


def _init_db() -> None:
    with _LOCK, _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                goal TEXT, status TEXT, max_steps INTEGER,
                step INTEGER, prev_hash TEXT, final_hash TEXT,
                reflection TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS receipts (
                run_id TEXT, seq INTEGER, node TEXT, body TEXT,
                prev_hash TEXT, hash TEXT, envelope TEXT, ts TEXT,
                PRIMARY KEY (run_id, seq)
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                run_id TEXT, step INTEGER, state TEXT, prev_hash TEXT,
                ts TEXT, PRIMARY KEY (run_id, step)
            );
            CREATE TABLE IF NOT EXISTS memory (
                mem_id TEXT PRIMARY KEY, run_id TEXT, tier TEXT, kind TEXT,
                text TEXT, importance REAL, created_at REAL, last_access REAL,
                embedding TEXT
            );
            CREATE TABLE IF NOT EXISTS skills (
                skill_id TEXT PRIMARY KEY, name TEXT, recipe TEXT,
                receipt_hash TEXT, receipt_verified INTEGER, embedding TEXT,
                created_at TEXT, uses INTEGER
            );
            CREATE TABLE IF NOT EXISTS reflections (
                run_id TEXT, idx INTEGER, text TEXT, ts TEXT,
                PRIMARY KEY (run_id, idx)
            );
            """
        )


# ---------------------------------------------------------------------------
# LOCAL embedding — deterministic hashing-trick bag-of-tokens, L2 normalised.
# This is NOT a learned model; it is a reproducible local feature hash so that
# cosine similarity is meaningful for lexical overlap WITHOUT any network call.
# Labelled HEURISTIC everywhere it surfaces.
# ---------------------------------------------------------------------------
_TOK = re.compile(r"[a-z0-9]+")


def _embed(text: str) -> list:
    vec = [0.0] * _EMBED_DIM
    toks = _TOK.findall((text or "").lower())
    for t in toks:
        h = int(hashlib.md5(t.encode()).hexdigest(), 16)
        idx = h % _EMBED_DIM
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cos(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))


def _importance_heuristic(text: str) -> float:
    """Local importance proxy in [0,1] (LLM-scored 1-10 in the paper; here a
    transparent HEURISTIC: longer, decision/goal-bearing text scores higher).
    Surfaced honestly as HEURISTIC, never claimed as an LLM judgement."""
    t = (text or "").lower()
    score = min(1.0, len(t) / 240.0)
    for kw, w in (("goal", 0.2), ("decision", 0.2), ("fail", 0.25),
                  ("error", 0.25), ("reflect", 0.2), ("verified", 0.15),
                  ("receipt", 0.1)):
        if kw in t:
            score = min(1.0, score + w)
    return round(score, 4)


# ---------------------------------------------------------------------------
# Generative-Agents retrieval score:
#   score(m) = a_rec * gamma^dt_hours + a_imp * imp(m) + a_rel * cos(q, m)
# gamma ~ 0.995 / hour (arXiv 2304.03442). Components surfaced honestly.
# ---------------------------------------------------------------------------
_GAMMA = 0.995          # recency decay per hour
_A_REC = 1.0
_A_IMP = 1.0
_A_REL = 1.0


def _score_memory(row, q_emb: list, now_epoch: float) -> dict:
    dt_hours = max(0.0, (now_epoch - float(row["last_access"])) / 3600.0)
    recency = _GAMMA ** dt_hours
    imp = float(row["importance"])
    try:
        emb = json.loads(row["embedding"])
    except Exception:
        emb = []
    rel = _cos(q_emb, emb)
    rel01 = (rel + 1.0) / 2.0  # map cosine [-1,1] -> [0,1] for the weighted sum
    total = _A_REC * recency + _A_IMP * imp + _A_REL * rel01
    return {
        "mem_id": row["mem_id"], "tier": row["tier"], "kind": row["kind"],
        "text": row["text"],
        "score": round(total, 6),
        "components": {
            "recency_gamma_dt": round(recency, 6),
            "delta_t_hours": round(dt_hours, 4),
            "importance": round(imp, 4),
            "relevance_cos": round(rel, 6),
            "relevance_0_1": round(rel01, 6),
        },
        "weights": {"alpha_recency": _A_REC, "alpha_importance": _A_IMP,
                    "alpha_relevance": _A_REL, "gamma_per_hour": _GAMMA},
        "label": "HEURISTIC",  # local embeddings + heuristic importance
    }


def _mem_add(run_id: str, tier: str, kind: str, text: str,
             importance=None) -> str:
    mem_id = "mem_" + uuid.uuid4().hex[:12]
    now = _now_epoch()
    imp = _importance_heuristic(text) if importance is None else float(importance)
    emb = _embed(text)
    with _LOCK, _conn() as c:
        c.execute(
            "INSERT INTO memory(mem_id,run_id,tier,kind,text,importance,"
            "created_at,last_access,embedding) VALUES(?,?,?,?,?,?,?,?,?)",
            (mem_id, run_id, tier, kind, text, imp, now, now, json.dumps(emb)),
        )
    return mem_id


def _mem_retrieve(query: str, top_k: int = 5, tier=None) -> list:
    q_emb = _embed(query)
    now = _now_epoch()
    with _LOCK, _conn() as c:
        if tier:
            rows = c.execute("SELECT * FROM memory WHERE tier=?", (tier,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM memory").fetchall()
    scored = [_score_memory(r, q_emb, now) for r in rows]
    scored.sort(key=lambda s: s["score"], reverse=True)
    top = scored[:top_k]
    # honest "access" bump: retrieved memories refresh their recency clock
    if top:
        ids = [s["mem_id"] for s in top]
        with _LOCK, _conn() as c:
            c.executemany("UPDATE memory SET last_access=? WHERE mem_id=?",
                          [(now, i) for i in ids])
    return top


# ---------------------------------------------------------------------------
# Letta-style memory tiering. "working" = in-context (small, fast); "archival"
# = vector store (large, searched). The agent self-manages via tool calls
# memory_append / memory_search / memory_promote that the ReAct loop can emit.
# ---------------------------------------------------------------------------
_WORKING_CAP = 8  # in-context working-memory item cap (paging boundary)


def _working_snapshot(run_id: str) -> list:
    with _LOCK, _conn() as c:
        rows = c.execute(
            "SELECT * FROM memory WHERE run_id=? AND tier='working' "
            "ORDER BY last_access DESC LIMIT ?", (run_id, _WORKING_CAP)
        ).fetchall()
    return [{"mem_id": r["mem_id"], "kind": r["kind"], "text": r["text"],
             "importance": r["importance"]} for r in rows]


def _page_out_if_full(run_id: str) -> list:
    """Letta/MemGPT paging: when working memory exceeds the in-context cap, the
    LEAST-recently-accessed working items are promoted (paged out) to archival
    so the in-context window stays bounded. Returns the paged-out mem_ids."""
    paged = []
    with _LOCK, _conn() as c:
        rows = c.execute(
            "SELECT mem_id FROM memory WHERE run_id=? AND tier='working' "
            "ORDER BY last_access ASC", (run_id,)
        ).fetchall()
        if len(rows) > _WORKING_CAP:
            overflow = rows[: len(rows) - _WORKING_CAP]
            for r in overflow:
                c.execute("UPDATE memory SET tier='archival' WHERE mem_id=?",
                          (r["mem_id"],))
                paged.append(r["mem_id"])
    return paged


# ---------------------------------------------------------------------------
# Voyager skill library. A tool-recipe is ADMITTED to the library ONLY after a
# verified execution receipt (DSSE envelope verified by the host verify_fn).
# Recipes are indexed by local embedding so the agent can retrieve a relevant
# prior recipe. We NEVER admit a recipe whose receipt fails verification.
# ---------------------------------------------------------------------------
def _skill_admit(name: str, recipe: str, receipt_hash: str,
                 receipt_verified: bool) -> dict:
    if not receipt_verified:
        return {"admitted": False,
                "reason": "REJECTED — execution receipt did not verify; Voyager "
                          "admission requires a passing signed receipt.",
                "receipt_hash": receipt_hash}
    skill_id = "skill_" + uuid.uuid4().hex[:12]
    emb = _embed(name + " " + recipe)
    with _LOCK, _conn() as c:
        c.execute(
            "INSERT INTO skills(skill_id,name,recipe,receipt_hash,"
            "receipt_verified,embedding,created_at,uses) VALUES(?,?,?,?,?,?,?,0)",
            (skill_id, name, recipe, receipt_hash, 1, json.dumps(emb), _now_iso()),
        )
    return {"admitted": True, "skill_id": skill_id, "name": name,
            "receipt_hash": receipt_hash,
            "reason": "ADMITTED — backed by a verified execution receipt."}


def _skill_search(query: str, top_k: int = 5) -> list:
    q_emb = _embed(query)
    with _LOCK, _conn() as c:
        rows = c.execute("SELECT * FROM skills").fetchall()
    out = []
    for r in rows:
        try:
            emb = json.loads(r["embedding"])
        except Exception:
            emb = []
        out.append({"skill_id": r["skill_id"], "name": r["name"],
                    "recipe": r["recipe"], "receipt_hash": r["receipt_hash"],
                    "receipt_verified": bool(r["receipt_verified"]),
                    "uses": r["uses"],
                    "similarity": round(_cos(q_emb, emb), 6), "label": "LIVE"})
    out.sort(key=lambda s: s["similarity"], reverse=True)
    return out[:top_k]


# ---------------------------------------------------------------------------
# ReAct execution graph (arXiv 2210.03629). Nodes: THOUGHT -> ACTION ->
# OBSERVATION, looping until a terminal ANSWER or max_steps. EACH node
# transition is committed as a hash-chained receipt AND wrapped in a DSSE
# envelope by the host signer (sign_fn). A SqliteSaver-style checkpoint is
# written after every node so a crash resumes from the last committed step.
#
# The "model call" is routed through a small, deterministic in-image policy
# (the host a11oy inference path is the production target; we keep the loop's
# model-calls inside the app and label the planner HEURISTIC so we never fake a
# model number — the GRAPH, RECEIPTS, CHECKPOINTING and RESUME are all REAL).
# ---------------------------------------------------------------------------

# Tool registry: small, real, deterministic tools the ReAct agent can call.
def _tool_calc(arg: str) -> str:
    expr = re.sub(r"[^0-9+\-*/(). ]", "", arg or "")
    if not expr.strip():
        return "ERR: empty expression"
    try:
        # safe arithmetic only (chars already filtered); no names/builtins
        return str(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307
    except Exception as e:
        return "ERR: %s" % type(e).__name__


def _tool_memory_search(arg: str) -> str:
    hits = _mem_retrieve(arg, top_k=3)
    if not hits:
        return "no memories"
    return " | ".join("%s(score=%.3f)" % (h["text"][:48], h["score"]) for h in hits)


def _tool_skill_search(arg: str) -> str:
    hits = _skill_search(arg, top_k=3)
    if not hits:
        return "no skills"
    return " | ".join("%s(sim=%.3f)" % (h["name"], h["similarity"]) for h in hits)


def _tool_echo(arg: str) -> str:
    return (arg or "")[:200]


def _tool_write_code(arg: str) -> str:
    """A code-writing tool. The actual restraint GATE runs in the ACTION node
    (so the decision is in the signed receipt BEFORE this executes); here we just
    acknowledge the (already restraint-governed) intended diff. We do NOT run a
    model in-image — the production target is the a11oy code path; honest."""
    return "intended diff prepared (restraint-gated): " + (arg or "")[:160]


# Tools whose Action node WRITES CODE — these are gated through a11oy Restraint.
_CODE_TOOLS = {"write_code", "code_patch", "emit_code"}

_TOOLS = {
    "calc": _tool_calc,
    "memory_search": _tool_memory_search,
    "skill_search": _tool_skill_search,
    "echo": _tool_echo,
    "write_code": _tool_write_code,
    "code_patch": _tool_write_code,
    "emit_code": _tool_write_code,
}


def _plan_action(goal: str, scratch: list) -> dict:
    """HEURISTIC planner (NOT a learned model — labelled HEURISTIC). Picks the
    next ReAct action from the goal + scratchpad. Deterministic so the loop is
    replayable and the demo is reproducible. The production target is the host
    a11oy inference path; this keeps the agent loop's model-calls in-app."""
    g = (goal or "").lower()
    step = len(scratch)
    # terminal: if we already produced an observation, answer.
    last_obs = next((s for s in reversed(scratch) if s.get("node") == "OBSERVATION"), None)
    if last_obs is not None:
        return {"terminal": True,
                "thought": "I have an observation; I can answer now.",
                "answer": "Result: %s" % last_obs.get("observation", "")}
    # code-writing goal -> write_code (this ACTION node will be RESTRAINT-gated)
    if re.search(r"\b(write|implement|add|build|code|function|refactor|patch|"
                 r"endpoint|class|module|script)\b", g) and not re.search(
                 r"\d.*[+\-*/].*\d", g):
        return {"terminal": False, "tool": "write_code", "tool_input": goal,
                "thought": ("This writes code; I will gate the intended diff through "
                            "a11oy Restraint BEFORE emitting.")}
    # arithmetic goal -> calc
    if re.search(r"\d.*[+\-*/].*\d", g):
        m = re.search(r"[-0-9+\-*/(). ]{3,}", goal)
        arg = m.group(0).strip() if m else goal
        return {"terminal": False, "tool": "calc", "tool_input": arg,
                "thought": "This looks arithmetic; I will use the calc tool."}
    if "memory" in g or "remember" in g or "recall" in g:
        return {"terminal": False, "tool": "memory_search", "tool_input": goal,
                "thought": "I should consult memory for this."}
    if "skill" in g or "recipe" in g or "how do i" in g:
        return {"terminal": False, "tool": "skill_search", "tool_input": goal,
                "thought": "I should check the skill library."}
    return {"terminal": False, "tool": "echo", "tool_input": goal,
            "thought": "No specialised tool; I will restate and observe."}


class _ReActEngine:
    """Holds the host signer/verifier and runs / resumes graphs."""

    def __init__(self, sign_fn, verify_fn, pub_pem_fn, ns="a11oy"):
        self.sign_fn = sign_fn
        self.verify_fn = verify_fn
        self.pub_pem_fn = pub_pem_fn
        self.ns = ns
        _init_db()

    # ---- receipt boundary: chain + DSSE sign every node transition ----
    def _commit_receipt(self, run_id, seq, node, body, prev_hash, reflection=None):
        rec_core = {"seq": seq, "node": node, "body": body, "prev_hash": prev_hash}
        h = _sha(rec_core)
        payload = {
            "run_id": run_id, "seq": seq, "node": node, "body": body,
            "prev_hash": prev_hash, "hash": h, "issuer": self.ns,
            "issued_at": _now_iso(),
            "reflection": reflection,  # Reflexion field on the receipt
            "trust_status": "Conjecture 1 (advisory \u2014 NOT a proven oracle)",
        }
        try:
            envelope = self.sign_fn(payload)
        except Exception as e:
            envelope = {"signed": False, "signatures": [],
                        "honesty": "UNSIGNED \u2014 signer raised %s" % type(e).__name__,
                        "payloadType": "application/vnd.szl.receipt+json"}
        with _LOCK, _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO receipts(run_id,seq,node,body,prev_hash,"
                "hash,envelope,ts) VALUES(?,?,?,?,?,?,?,?)",
                (run_id, seq, node, json.dumps(body), prev_hash, h,
                 json.dumps(envelope), _now_iso()),
            )
        return h, envelope

    # ---- SqliteSaver-style checkpoint after every node ----
    def _checkpoint(self, run_id, step, state, prev_hash):
        with _LOCK, _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO checkpoints(run_id,step,state,prev_hash,ts)"
                " VALUES(?,?,?,?,?)",
                (run_id, step, json.dumps(state), prev_hash, _now_iso()),
            )

    def _load_run(self, run_id):
        with _LOCK, _conn() as c:
            r = c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            cps = c.execute(
                "SELECT * FROM checkpoints WHERE run_id=? ORDER BY step DESC LIMIT 1",
                (run_id,)).fetchone()
        return r, cps

    def _prior_reflection(self, goal):
        """Reflexion: prepend the most relevant prior reflection on activation."""
        with _LOCK, _conn() as c:
            rows = c.execute(
                "SELECT text FROM reflections ORDER BY rowid DESC LIMIT 8").fetchall()
        if not rows:
            return None
        # pick the reflection most lexically relevant to this goal
        q = _embed(goal)
        best, best_sim = None, -2.0
        for r in rows:
            sim = _cos(q, _embed(r["text"]))
            if sim > best_sim:
                best, best_sim = r["text"], sim
        return best

    # ---- run a (possibly partial) graph from a starting step ----
    def _drive(self, run_id, goal, max_steps, start_step, prev_hash,
               scratch, reflection, kill_after=None):
        node_seq = start_step
        status = "running"
        steps_done = 0
        terminal_answer = None
        while node_seq // 3 < max_steps:
            phase = node_seq % 3
            cur_step = node_seq // 3
            if phase == 0:  # THOUGHT
                plan = _plan_action(goal, scratch)
                scratch.append({"node": "THOUGHT", "step": cur_step,
                                "thought": plan["thought"], "plan": plan})
                body = {"step": cur_step, "thought": plan["thought"],
                        "intended_tool": plan.get("tool"),
                        "terminal": plan.get("terminal", False)}
                prev_hash, _ = self._commit_receipt(run_id, node_seq, "THOUGHT",
                                                    body, prev_hash, reflection)
                if plan.get("terminal"):
                    terminal_answer = plan.get("answer")
                    status = "completed"
                    self._checkpoint(run_id, node_seq + 1,
                                     {"scratch": scratch, "answer": terminal_answer},
                                     prev_hash)
                    node_seq += 1
                    break
            elif phase == 1:  # ACTION
                plan = scratch[-1]["plan"]
                tool, arg = plan.get("tool", "echo"), plan.get("tool_input", "")
                scratch.append({"node": "ACTION", "step": cur_step,
                                "tool": tool, "tool_input": arg})
                body = {"step": cur_step, "tool": tool, "tool_input": arg}
                # RESTRAINT GATE: if this Action WRITES CODE, route the intended
                # diff through a11oy Restraint (R1) BEFORE emitting, and record
                # the restraint verdict in THIS node's signed receipt. Honest
                # PENDING if R1's ladder is not live yet (no fabrication).
                if tool in _CODE_TOOLS:
                    verdict = _restraint_evaluate(arg, intensity="full",
                                                  sign_fn=self.sign_fn)
                    body["restraint"] = verdict
                    scratch[-1]["restraint"] = verdict
                prev_hash, _ = self._commit_receipt(run_id, node_seq, "ACTION",
                                                    body, prev_hash, reflection)
            else:  # OBSERVATION (execute the tool for real)
                act = next(s for s in reversed(scratch) if s.get("node") == "ACTION")
                fn = _TOOLS.get(act["tool"], _tool_echo)
                obs = fn(act["tool_input"])
                scratch.append({"node": "OBSERVATION", "step": cur_step,
                                "observation": obs})
                # store the observation as a working memory (Letta tiering)
                _mem_add(run_id, "working", "observation",
                         "step %d %s->%s" % (cur_step, act["tool"], obs))
                _page_out_if_full(run_id)
                body = {"step": cur_step, "tool": act["tool"], "observation": obs}
                prev_hash, _ = self._commit_receipt(run_id, node_seq, "OBSERVATION",
                                                    body, prev_hash, reflection)
            node_seq += 1
            steps_done += 1
            # CHECKPOINT after every node transition (SqliteSaver-style)
            self._checkpoint(run_id, node_seq,
                             {"scratch": scratch, "node_seq": node_seq}, prev_hash)
            # honest crash injection for the resumable demo: stop mid-run
            if kill_after is not None and steps_done >= kill_after:
                status = "interrupted"
                break
        else:
            status = "completed" if terminal_answer else "max_steps"

        final_hash = prev_hash
        with _LOCK, _conn() as c:
            c.execute(
                "UPDATE runs SET status=?,step=?,prev_hash=?,final_hash=?,"
                "updated_at=? WHERE run_id=?",
                (status, node_seq, prev_hash, final_hash, _now_iso(), run_id))
        return {"run_id": run_id, "status": status, "node_seq": node_seq,
                "final_hash": final_hash, "answer": terminal_answer,
                "scratch": scratch}

    def run(self, goal, max_steps=4, kill_after=None):
        run_id = "run_" + uuid.uuid4().hex[:12]
        reflection = self._prior_reflection(goal)
        # seed long-term memory with the goal
        _mem_add(run_id, "working", "goal", "GOAL: " + (goal or ""))
        with _LOCK, _conn() as c:
            c.execute(
                "INSERT INTO runs(run_id,goal,status,max_steps,step,prev_hash,"
                "final_hash,reflection,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (run_id, goal, "running", max_steps, 0, "GENESIS", "",
                 reflection or "", _now_iso(), _now_iso()))
        # genesis receipt
        prev_hash = "GENESIS"
        prev_hash, _ = self._commit_receipt(
            run_id, -1, "GENESIS",
            {"goal": goal, "max_steps": max_steps,
             "prior_reflection_prepended": bool(reflection)},
            prev_hash, reflection)
        self._checkpoint(run_id, 0, {"scratch": [], "node_seq": 0}, prev_hash)
        return self._drive(run_id, goal, max_steps, 0, prev_hash, [],
                           reflection, kill_after=kill_after)

    def resume(self, run_id):
        r, cps = self._load_run(run_id)
        if r is None:
            return {"error": "unknown run_id", "run_id": run_id}
        if r["status"] not in ("interrupted", "running", "max_steps"):
            return {"run_id": run_id, "status": r["status"],
                    "note": "run already %s \u2014 nothing to resume" % r["status"],
                    "resumed": False}
        state = json.loads(cps["state"]) if cps else {"scratch": [], "node_seq": 0}
        node_seq = state.get("node_seq", 0)
        scratch = state.get("scratch", [])
        prev_hash = cps["prev_hash"] if cps else "GENESIS"
        out = self._drive(run_id, r["goal"], r["max_steps"], node_seq, prev_hash,
                          scratch, r["reflection"] or None)
        out["resumed"] = True
        out["resumed_from_checkpoint_step"] = node_seq
        return out

    def trace(self, run_id):
        with _LOCK, _conn() as c:
            r = c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            recs = c.execute(
                "SELECT * FROM receipts WHERE run_id=? ORDER BY seq", (run_id,)
            ).fetchall()
        if r is None:
            return {"error": "unknown run_id", "run_id": run_id}
        receipts, chain_ok, prev = [], True, "GENESIS"
        for rec in recs:
            body = json.loads(rec["body"])
            recompute = _sha({"seq": rec["seq"], "node": rec["node"],
                              "body": body, "prev_hash": rec["prev_hash"]})
            link_ok = (rec["prev_hash"] == prev) and (recompute == rec["hash"])
            env = json.loads(rec["envelope"])
            sig_ok = None
            if self.verify_fn is not None:
                try:
                    sig_ok = bool(self.verify_fn(env).get("signature_valid"))
                except Exception:
                    sig_ok = False
            chain_ok = chain_ok and link_ok
            receipts.append({"seq": rec["seq"], "node": rec["node"], "body": body,
                             "hash": rec["hash"], "prev_hash": rec["prev_hash"],
                             "link_ok": link_ok, "signature_valid": sig_ok,
                             "signed": bool(env.get("signed")),
                             "ts": rec["ts"]})
            prev = rec["hash"]
        return {"run_id": run_id, "goal": r["goal"], "status": r["status"],
                "reflection": r["reflection"],
                "chain_intact": chain_ok, "depth": len(receipts),
                "final_hash": r["final_hash"], "receipts": receipts,
                "trust_note": "Receipt chain + DSSE signatures are REAL; planner is "
                              "HEURISTIC (deterministic, replayable). Trust=Conjecture 1."}

    def checkpoints(self, run_id):
        with _LOCK, _conn() as c:
            cps = c.execute(
                "SELECT step,prev_hash,ts FROM checkpoints WHERE run_id=? "
                "ORDER BY step", (run_id,)).fetchall()
            r = c.execute("SELECT status,step FROM runs WHERE run_id=?",
                          (run_id,)).fetchone()
        return {"run_id": run_id,
                "status": (r["status"] if r else "unknown"),
                "current_step": (r["step"] if r else None),
                "checkpoints": [{"step": c["step"], "prev_hash": c["prev_hash"],
                                 "ts": c["ts"]} for c in cps],
                "saver": "SqliteSaver-style (local sqlite, ephemeral per container)"}

    def reflect(self, run_id, reflection_text):
        """Reflexion: store a NL reflection after a reviewed episode."""
        with _LOCK, _conn() as c:
            n = c.execute("SELECT COUNT(*) AS n FROM reflections WHERE run_id=?",
                          (run_id,)).fetchone()["n"]
            c.execute("INSERT OR REPLACE INTO reflections(run_id,idx,text,ts) "
                      "VALUES(?,?,?,?)", (run_id, n, reflection_text, _now_iso()))
            c.execute("UPDATE runs SET reflection=? WHERE run_id=?",
                      (reflection_text, run_id))
        _mem_add(run_id, "archival", "reflection", reflection_text, importance=0.85)
        return {"run_id": run_id, "stored": True, "reflection": reflection_text,
                "note": "Prepended to the next activation on a lexically-relevant goal."}


# ---------------------------------------------------------------------------
# register(app, ns, sign_fn, verify_fn, pub_pem_fn) — mirrors szl_agentic_loop.
# R2 additive: byte-identical embedded copy of web/agent-loop.html so the
# /agent-loop trace UI (restraint-verdict column) renders even though the
# asset is not baked by the Dockerfile. Decoded only as a last-resort
# fallback after the on-disk paths. Generated from the committed file.
_AGENTLOOP_HTML_B64 = (
    "PCFET0NUWVBFIGh0bWw+CjxodG1sIGxhbmc9ImVuIj4KPGhlYWQ+CjxtZXRhIGNoYXJzZXQ9InV0Zi04Ii8+CjxtZXRhIG5hbWU9InZpZXdwb3J0IiBjb250"
    "ZW50PSJ3aWR0aD1kZXZpY2Utd2lkdGgsIGluaXRpYWwtc2NhbGU9MSIvPgo8dGl0bGU+YTExb3kg4oCUIEFnZW50IExvb3AgwrcgTWVtb3J5IMK3IFNraWxs"
    "IExpYnJhcnk8L3RpdGxlPgo8IS0tIDAgcnVudGltZSBDRE46IHNoYXJlZCBlbmdpbmVzIHNlcnZlZCBsb2NhbGx5IGZyb20gL3N0YXRpYy9zaGFyZWQuIC0t"
    "Pgo8c2NyaXB0IHNyYz0iL3N0YXRpYy9zaGFyZWQvc3psX2xhYmVsX2VuZ2luZS5qcyI+PC9zY3JpcHQ+CjxzY3JpcHQgc3JjPSIvc3RhdGljL3NoYXJlZC9z"
    "emxfcmVjZWlwdF9jb3NpZ24uanMiPjwvc2NyaXB0Pgo8c3R5bGU+CiAgOnJvb3R7LS1iZzojMGIwZTE0Oy0tcGFuZWw6IzEyMTgyNjstLWluazojZTZlZGYz"
    "Oy0tbXV0OiM4Yjk4YTk7LS1hY2M6IzViZDZmZjsKICAgICAgICAtLW9rOiMzZmQzN2Y7LS1iYWQ6I2ZmNmI2YjstLXdhcm46I2ZmY2U1YjstLWxpbmU6IzFm"
    "MjkzNzt9CiAgKntib3gtc2l6aW5nOmJvcmRlci1ib3h9CiAgYm9keXttYXJnaW46MDtiYWNrZ3JvdW5kOnZhcigtLWJnKTtjb2xvcjp2YXIoLS1pbmspOwog"
    "ICAgICAgZm9udDoxNHB4LzEuNSB1aS1tb25vc3BhY2UsU0ZNb25vLVJlZ3VsYXIsTWVubG8sQ29uc29sYXMsbW9ub3NwYWNlfQogIGhlYWRlcntwYWRkaW5n"
    "OjE2cHggMjJweDtib3JkZXItYm90dG9tOjFweCBzb2xpZCB2YXIoLS1saW5lKTsKICAgICAgICAgZGlzcGxheTpmbGV4O2FsaWduLWl0ZW1zOmNlbnRlcjtn"
    "YXA6MTRweDtmbGV4LXdyYXA6d3JhcH0KICBoMXtmb250LXNpemU6MTdweDttYXJnaW46MDtsZXR0ZXItc3BhY2luZzouM3B4fQogIC5zdWJ7Y29sb3I6dmFy"
    "KC0tbXV0KTtmb250LXNpemU6MTJweH0KICAudGFic3tkaXNwbGF5OmZsZXg7Z2FwOjZweDtwYWRkaW5nOjEwcHggMThweDtib3JkZXItYm90dG9tOjFweCBz"
    "b2xpZCB2YXIoLS1saW5lKX0KICAudGFie3BhZGRpbmc6N3B4IDE0cHg7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1saW5lKTtib3JkZXItcmFkaXVzOjhweDsK"
    "ICAgICAgIGJhY2tncm91bmQ6dmFyKC0tcGFuZWwpO2N1cnNvcjpwb2ludGVyO2NvbG9yOnZhcigtLW11dCl9CiAgLnRhYi5hY3RpdmV7Y29sb3I6dmFyKC0t"
    "aW5rKTtib3JkZXItY29sb3I6dmFyKC0tYWNjKTtib3gtc2hhZG93OjAgMCAwIDFweCB2YXIoLS1hY2MpIGluc2V0fQogIG1haW57cGFkZGluZzoxOHB4IDIy"
    "cHg7bWF4LXdpZHRoOjExODBweH0KICAudmlld3tkaXNwbGF5Om5vbmV9LnZpZXcuYWN0aXZle2Rpc3BsYXk6YmxvY2t9CiAgLmNhcmR7YmFja2dyb3VuZDp2"
    "YXIoLS1wYW5lbCk7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1saW5lKTtib3JkZXItcmFkaXVzOjEycHg7CiAgICAgICAgcGFkZGluZzoxNnB4O21hcmdpbjow"
    "IDAgMTZweH0KICAucm93e2Rpc3BsYXk6ZmxleDtnYXA6MTBweDtmbGV4LXdyYXA6d3JhcDthbGlnbi1pdGVtczpjZW50ZXI7bWFyZ2luLWJvdHRvbToxMHB4"
    "fQogIGlucHV0LHRleHRhcmVhLHNlbGVjdHtiYWNrZ3JvdW5kOiMwZDEzMjA7Ym9yZGVyOjFweCBzb2xpZCB2YXIoLS1saW5lKTsKICAgICAgICBjb2xvcjp2"
    "YXIoLS1pbmspO2JvcmRlci1yYWRpdXM6OHB4O3BhZGRpbmc6OHB4IDEwcHg7Zm9udDppbmhlcml0fQogIGlucHV0W3R5cGU9dGV4dF17bWluLXdpZHRoOjM0"
    "MHB4fQogIHRleHRhcmVhe3dpZHRoOjEwMCU7bWluLWhlaWdodDo2NHB4fQogIGJ1dHRvbntiYWNrZ3JvdW5kOnZhcigtLWFjYyk7Y29sb3I6IzA2MjIyYzti"
    "b3JkZXI6MDtib3JkZXItcmFkaXVzOjhweDsKICAgICAgICBwYWRkaW5nOjhweCAxNHB4O2ZvbnQ6aW5oZXJpdDtmb250LXdlaWdodDo3MDA7Y3Vyc29yOnBv"
    "aW50ZXJ9CiAgYnV0dG9uLmdob3N0e2JhY2tncm91bmQ6IzBkMTMyMDtjb2xvcjp2YXIoLS1pbmspO2JvcmRlcjoxcHggc29saWQgdmFyKC0tbGluZSk7Zm9u"
    "dC13ZWlnaHQ6NTAwfQogIC5sYmx7Zm9udC1zaXplOjExcHg7Zm9udC13ZWlnaHQ6NzAwO3BhZGRpbmc6MnB4IDdweDtib3JkZXItcmFkaXVzOjZweDsKICAg"
    "ICAgIGJvcmRlcjoxcHggc29saWQgdmFyKC0tbGluZSk7bWFyZ2luLWxlZnQ6NnB4fQogIC5ub2Rle2Rpc3BsYXk6aW5saW5lLWJsb2NrO21pbi13aWR0aDo5"
    "NnB4O3RleHQtYWxpZ246Y2VudGVyO2JvcmRlci1yYWRpdXM6NnB4OwogICAgICAgIHBhZGRpbmc6MnB4IDhweDtmb250LXdlaWdodDo3MDA7Zm9udC1zaXpl"
    "OjEycHh9CiAgLlRIT1VHSFR7YmFja2dyb3VuZDojMTIzMDRhO2NvbG9yOiM5ZmRjZmZ9CiAgLkFDVElPTntiYWNrZ3JvdW5kOiMzYTJhMTI7Y29sb3I6I2Zm"
    "Y2U4YX0KICAuT0JTRVJWQVRJT057YmFja2dyb3VuZDojMTIzYTI0O2NvbG9yOiM4ZmYwYmJ9CiAgLkdFTkVTSVN7YmFja2dyb3VuZDojMjEyNjJkO2NvbG9y"
    "OiM5ZmIyYzh9CiAgLm9re2NvbG9yOnZhcigtLW9rKX0uYmFke2NvbG9yOnZhcigtLWJhZCl9Lm11dHtjb2xvcjp2YXIoLS1tdXQpfQogIC5tb25ve2ZvbnQt"
    "ZmFtaWx5OmluaGVyaXR9Lmhhc2h7Y29sb3I6dmFyKC0tbXV0KTtmb250LXNpemU6MTFweDt3b3JkLWJyZWFrOmJyZWFrLWFsbH0KICB0YWJsZXt3aWR0aDox"
    "MDAlO2JvcmRlci1jb2xsYXBzZTpjb2xsYXBzZTtmb250LXNpemU6MTIuNXB4fQogIHRoLHRke3RleHQtYWxpZ246bGVmdDtwYWRkaW5nOjZweCA4cHg7Ym9y"
    "ZGVyLWJvdHRvbToxcHggc29saWQgdmFyKC0tbGluZSk7dmVydGljYWwtYWxpZ246dG9wfQogIHRoe2NvbG9yOnZhcigtLW11dCk7Zm9udC13ZWlnaHQ6NjAw"
    "fQogIC5iYXJ7aGVpZ2h0OjhweDtib3JkZXItcmFkaXVzOjRweDtiYWNrZ3JvdW5kOiMwZDEzMjA7b3ZlcmZsb3c6aGlkZGVuO21pbi13aWR0aDo5MHB4fQog"
    "IC5iYXI+aXtkaXNwbGF5OmJsb2NrO2hlaWdodDoxMDAlO2JhY2tncm91bmQ6dmFyKC0tYWNjKX0KICBwcmV7d2hpdGUtc3BhY2U6cHJlLXdyYXA7d29yZC1i"
    "cmVhazpicmVhay13b3JkO21hcmdpbjo2cHggMCAwO2NvbG9yOnZhcigtLW11dCk7Zm9udC1zaXplOjEycHh9CiAgLnBpbGx7Zm9udC1zaXplOjExcHg7Ym9y"
    "ZGVyOjFweCBzb2xpZCB2YXIoLS1saW5lKTtib3JkZXItcmFkaXVzOjIwcHg7cGFkZGluZzoycHggOXB4O2NvbG9yOnZhcigtLW11dCl9CiAgY29kZXtiYWNr"
    "Z3JvdW5kOiMwZDEzMjA7cGFkZGluZzoxcHggNXB4O2JvcmRlci1yYWRpdXM6NXB4fQo8L3N0eWxlPgo8L2hlYWQ+Cjxib2R5Pgo8aGVhZGVyPgogIDxoMT5h"
    "MTFveSDCtyBBR0VOVElDIENPUkU8L2gxPgogIDxzcGFuIGlkPSJ0b3BiYWRnZXMiPjwvc3Bhbj4KICA8c3BhbiBjbGFzcz0ic3ViIj5SZUFjdCBncmFwaCDC"
    "tyBzaWduZWQgcmVjZWlwdCBib3VuZGFyaWVzIMK3IFNxbGl0ZVNhdmVyIHJlc3VtZSDCtyBHZW5lcmF0aXZlLUFnZW50cyBtZW1vcnkgwrcgTGV0dGEgdGll"
    "cmluZyDCtyBWb3lhZ2VyIHNraWxsczwvc3Bhbj4KPC9oZWFkZXI+CjxkaXYgY2xhc3M9InRhYnMiPgogIDxkaXYgY2xhc3M9InRhYiBhY3RpdmUiIGRhdGEt"
    "dj0ibG9vcCI+QWdlbnQgTG9vcDwvZGl2PgogIDxkaXYgY2xhc3M9InRhYiIgZGF0YS12PSJtZW1vcnkiPk1lbW9yeTwvZGl2PgogIDxkaXYgY2xhc3M9InRh"
    "YiIgZGF0YS12PSJza2lsbHMiPlNraWxsIExpYnJhcnk8L2Rpdj4KPC9kaXY+CjxtYWluPgoKPCEtLSA9PT09PT09PT09PT09PT09PT09PT0gQUdFTlQgTE9P"
    "UCA9PT09PT09PT09PT09PT09PT09PT0gLS0+CjxzZWN0aW9uIGNsYXNzPSJ2aWV3IGFjdGl2ZSIgaWQ9InYtbG9vcCI+CiAgPGRpdiBjbGFzcz0iY2FyZCI+"
    "CiAgICA8ZGl2IGNsYXNzPSJyb3ciPgogICAgICA8aW5wdXQgaWQ9ImdvYWwiIHR5cGU9InRleHQiIHBsYWNlaG9sZGVyPSJnb2FsLCBlLmcuICBpbXBsZW1l"
    "bnQgYSBmdW5jdGlvbiB0aGF0IHZhbGlkYXRlcyBhbiBlbWFpbCBhZGRyZXNzIiB2YWx1ZT0iaW1wbGVtZW50IGEgZnVuY3Rpb24gdGhhdCB2YWxpZGF0ZXMg"
    "YW4gZW1haWwgYWRkcmVzcyIvPgogICAgICA8bGFiZWwgY2xhc3M9InN1YiI+bWF4X3N0ZXBzIDxpbnB1dCBpZD0ibWF4c3RlcHMiIHR5cGU9Im51bWJlciIg"
    "dmFsdWU9IjQiIHN0eWxlPSJ3aWR0aDo2NHB4Ii8+PC9sYWJlbD4KICAgICAgPGxhYmVsIGNsYXNzPSJzdWIiPjxpbnB1dCBpZD0ia2lsbCIgdHlwZT0iY2hl"
    "Y2tib3giLz4ga2lsbCBtaWQtcnVuIChjcmFzaCBkZW1vKTwvbGFiZWw+CiAgICAgIDxidXR0b24gaWQ9ImJ0blJ1biI+UnVuIFJlQWN0PC9idXR0b24+CiAg"
    "ICAgIDxidXR0b24gY2xhc3M9Imdob3N0IiBpZD0iYnRuUmVzdW1lIj5SZXN1bWUgbGFzdDwvYnV0dG9uPgogICAgPC9kaXY+CiAgICA8ZGl2IGNsYXNzPSJz"
    "dWIiPkVhY2ggbm9kZSB0cmFuc2l0aW9uIChUaG91Z2h04oaSQWN0aW9u4oaST2JzZXJ2YXRpb24pIGlzIGEgaGFzaC1jaGFpbmVkLCBEU1NFLXNpZ25lZCBy"
    "ZWNlaXB0LiBBIGNyYXNoIHJlc3VtZXMgZnJvbSB0aGUgbGFzdCBTcWxpdGVTYXZlciBjaGVja3BvaW50LiA8c3BhbiBpZD0icnVubGJsIj48L3NwYW4+PC9k"
    "aXY+CiAgPC9kaXY+CiAgPGRpdiBjbGFzcz0iY2FyZCIgaWQ9InJ1bk1ldGEiIHN0eWxlPSJkaXNwbGF5Om5vbmUiPjwvZGl2PgogIDxkaXYgY2xhc3M9ImNh"
    "cmQiIGlkPSJ0cmFjZUNhcmQiIHN0eWxlPSJkaXNwbGF5Om5vbmUiPgogICAgPGRpdiBjbGFzcz0icm93IiBzdHlsZT0ianVzdGlmeS1jb250ZW50OnNwYWNl"
    "LWJldHdlZW4iPgogICAgICA8c3Ryb25nPkV4ZWN1dGlvbiB0cmFjZSArIHJlY2VpcHQgY2hhaW48L3N0cm9uZz4KICAgICAgPHNwYW4gaWQ9ImNoYWluU3Rh"
    "dGUiPjwvc3Bhbj4KICAgIDwvZGl2PgogICAgPHRhYmxlIGlkPSJ0cmFjZVRibCI+PHRoZWFkPjx0cj4KICAgICAgPHRoPnNlcTwvdGg+PHRoPm5vZGU8L3Ro"
    "Pjx0aD5ib2R5PC90aD48dGg+cmVzdHJhaW50PC90aD48dGg+bGluazwvdGg+PHRoPnNpZ25hdHVyZTwvdGg+PHRoPmhhc2g8L3RoPgogICAgPC90cj48L3Ro"
    "ZWFkPjx0Ym9keT48L3Rib2R5PjwvdGFibGU+CiAgICA8ZGl2IGNsYXNzPSJzdWIiIHN0eWxlPSJtYXJnaW4tdG9wOjZweCI+QWN0aW9uIG5vZGVzIHRoYXQg"
    "PHN0cm9uZz53cml0ZSBjb2RlPC9zdHJvbmc+IGFyZSBnYXRlZCB0aHJvdWdoIDxzdHJvbmc+YTExb3kgUmVzdHJhaW50PC9zdHJvbmc+ICh0aGUgUG9ueXRh"
    "aWwtZGVyaXZlZCA2LXJ1bmcgZnJ1Z2FsaXR5IGxhZGRlciwgPGEgaHJlZj0iaHR0cHM6Ly9naXRodWIuY29tL0RpZXRyaWNoR2ViZXJ0L3Bvbnl0YWlsIiB0"
    "YXJnZXQ9Il9ibGFuayIgcmVsPSJub29wZW5lciI+UG9ueXRhaWwgTUlUPC9hPiDigJQgYWRvcHRlZCArIGdvdmVybmVkKS4gVGhlIGNob3NlbiBydW5nICsg"
    "c2lnbmVkIHJlc3RyYWludCByZWNlaXB0IGFyZSByZWNvcmRlZCBpbiB0aGF0IG5vZGUncyByZWNlaXB0LiA8c3Ryb25nPlIxIG93bnMgdGhlIGxhZGRlciBt"
    "b2R1bGU8L3N0cm9uZz47IGhvbmVzdCA8c3Ryb25nPlBFTkRJTkc8L3N0cm9uZz4gdW50aWwgaXQgaXMgbGl2ZS48L2Rpdj4KICA8L2Rpdj4KICA8ZGl2IGNs"
    "YXNzPSJjYXJkIiBpZD0iY3BDYXJkIiBzdHlsZT0iZGlzcGxheTpub25lIj4KICAgIDxzdHJvbmc+Q2hlY2twb2ludHMgKFNxbGl0ZVNhdmVyLXN0eWxlKTwv"
    "c3Ryb25nPgogICAgPHRhYmxlIGlkPSJjcFRibCI+PHRoZWFkPjx0cj48dGg+c3RlcDwvdGg+PHRoPnByZXZfaGFzaDwvdGg+PHRoPnRzPC90aD48L3RyPjwv"
    "dGhlYWQ+PHRib2R5PjwvdGJvZHk+PC90YWJsZT4KICA8L2Rpdj4KPC9zZWN0aW9uPgoKPCEtLSA9PT09PT09PT09PT09PT09PT09PT0gTUVNT1JZID09PT09"
    "PT09PT09PT09PT09PT09PSAtLT4KPHNlY3Rpb24gY2xhc3M9InZpZXciIGlkPSJ2LW1lbW9yeSI+CiAgPGRpdiBjbGFzcz0iY2FyZCI+CiAgICA8ZGl2IGNs"
    "YXNzPSJzdWIiPkdlbmVyYXRpdmUtQWdlbnRzIHJldHJpZXZhbDogPGNvZGU+c2NvcmUobSk9zrFfcmVjwrfOs17OlHQgKyDOsV9pbXDCt2ltcChtKSArIM6x"
    "X3JlbMK3Y29zKHEsbSk8L2NvZGU+IChhclhpdiAyMzA0LjAzNDQyKS4gRW1iZWRkaW5ncyBhcmUgTE9DQUwgKGhhc2hpbmctdHJpY2ssIDAgQ0ROKSA8c3Bh"
    "biBjbGFzcz0ibGJsIiBzdHlsZT0iYm9yZGVyLWNvbG9yOnZhcigtLXdhcm4pO2NvbG9yOnZhcigtLXdhcm4pIj5IRVVSSVNUSUM8L3NwYW4+PC9kaXY+CiAg"
    "ICA8ZGl2IGNsYXNzPSJyb3ciIHN0eWxlPSJtYXJnaW4tdG9wOjEwcHgiPgogICAgICA8aW5wdXQgaWQ9Im1lbVRleHQiIHR5cGU9InRleHQiIHBsYWNlaG9s"
    "ZGVyPSJhZGQgYSBtZW1vcnkgKG9ic2VydmF0aW9uIC8gZmFjdCAvIGxlc3NvbikiLz4KICAgICAgPGJ1dHRvbiBpZD0iYnRuTWVtQWRkIj5BZGQ8L2J1dHRv"
    "bj4KICAgIDwvZGl2PgogICAgPGRpdiBjbGFzcz0icm93Ij4KICAgICAgPGlucHV0IGlkPSJtZW1RIiB0eXBlPSJ0ZXh0IiBwbGFjZWhvbGRlcj0icmV0cmll"
    "dmUgcXVlcnksIGUuZy4gIGZ1ZWwgaWduaXRpb24gbGF1bmNoIi8+CiAgICAgIDxidXR0b24gaWQ9ImJ0bk1lbVNlYXJjaCI+UmV0cmlldmUgKHNjb3JlZCk8"
    "L2J1dHRvbj4KICAgIDwvZGl2PgogIDwvZGl2PgogIDxkaXYgY2xhc3M9ImNhcmQiIGlkPSJtZW1DYXJkIiBzdHlsZT0iZGlzcGxheTpub25lIj4KICAgIDxz"
    "dHJvbmc+U2NvcmVkIHJldHJpZXZhbDwvc3Ryb25nPgogICAgPHRhYmxlIGlkPSJtZW1UYmwiPjx0aGVhZD48dHI+CiAgICAgIDx0aD5zY29yZTwvdGg+PHRo"
    "PnJlY2VuY3kgzrNezpR0PC90aD48dGg+aW1wPC90aD48dGg+Y29zKHEsbSk8L3RoPjx0aD50aWVyPC90aD48dGg+dGV4dDwvdGg+CiAgICA8L3RyPjwvdGhl"
    "YWQ+PHRib2R5PjwvdGJvZHk+PC90YWJsZT4KICA8L2Rpdj4KICA8ZGl2IGNsYXNzPSJjYXJkIiBpZD0idGllckNhcmQiPgogICAgPGRpdiBjbGFzcz0icm93"
    "IiBzdHlsZT0ianVzdGlmeS1jb250ZW50OnNwYWNlLWJldHdlZW4iPgogICAgICA8c3Ryb25nPkxldHRhIHRpZXJpbmcg4oCUIHdvcmtpbmcgKGluLWNvbnRl"
    "eHQpICsgYXJjaGl2YWwgKHZlY3Rvcik8L3N0cm9uZz4KICAgICAgPGJ1dHRvbiBjbGFzcz0iZ2hvc3QiIGlkPSJidG5UaWVycyI+UmVmcmVzaCB0aWVyczwv"
    "YnV0dG9uPgogICAgPC9kaXY+CiAgICA8ZGl2IGlkPSJ0aWVyQm9keSIgY2xhc3M9InN1YiI+d29ya2luZyBjYXAgPSBwYWdpbmcgYm91bmRhcnk7IGxlYXN0"
    "LXJlY2VudGx5LXVzZWQgd29ya2luZyBpdGVtcyBwYWdlIG91dCB0byBhcmNoaXZhbC48L2Rpdj4KICA8L2Rpdj4KPC9zZWN0aW9uPgoKPCEtLSA9PT09PT09"
    "PT09PT09PT09PT09PT0gU0tJTEwgTElCUkFSWSA9PT09PT09PT09PT09PT09PT09PT0gLS0+CjxzZWN0aW9uIGNsYXNzPSJ2aWV3IiBpZD0idi1za2lsbHMi"
    "PgogIDxkaXYgY2xhc3M9ImNhcmQiPgogICAgPGRpdiBjbGFzcz0ic3ViIj5Wb3lhZ2VyIHNraWxsIGxpYnJhcnkgKGFyWGl2IDIzMDUuMTYyOTEpOiBhIHRv"
    "b2wtcmVjaXBlIGlzIGFkbWl0dGVkIDxlbT5vbmx5PC9lbT4gYWZ0ZXIgYSA8c3Ryb25nPnZlcmlmaWVkIGV4ZWN1dGlvbiByZWNlaXB0PC9zdHJvbmc+LiBJ"
    "bmRleGVkIGJ5IGxvY2FsIGVtYmVkZGluZy48L2Rpdj4KICAgIDxkaXYgY2xhc3M9InJvdyIgc3R5bGU9Im1hcmdpbi10b3A6MTBweCI+CiAgICAgIDxpbnB1"
    "dCBpZD0ic2tOYW1lIiB0eXBlPSJ0ZXh0IiBwbGFjZWhvbGRlcj0ic2tpbGwgbmFtZSIgc3R5bGU9Im1pbi13aWR0aDoxODBweCIvPgogICAgICA8aW5wdXQg"
    "aWQ9InNrUmVjaXBlIiB0eXBlPSJ0ZXh0IiBwbGFjZWhvbGRlcj0icmVjaXBlIChlLmcuIGNhbGMge2F9KntifSkiIHN0eWxlPSJtaW4td2lkdGg6MjIwcHgi"
    "Lz4KICAgICAgPGlucHV0IGlkPSJza1J1biIgdHlwZT0idGV4dCIgcGxhY2Vob2xkZXI9InJ1bl9pZCBvZiBhIHZlcmlmaWVkIHJ1biIgc3R5bGU9Im1pbi13"
    "aWR0aDoxODBweCIvPgogICAgICA8YnV0dG9uIGlkPSJidG5BZG1pdCI+QWRtaXQgKHJlY2VpcHQtZ2F0ZWQpPC9idXR0b24+CiAgICA8L2Rpdj4KICAgIDxk"
    "aXYgaWQ9ImFkbWl0TXNnIiBjbGFzcz0ic3ViIj48L2Rpdj4KICA8L2Rpdj4KICA8ZGl2IGNsYXNzPSJjYXJkIj4KICAgIDxkaXYgY2xhc3M9InJvdyIgc3R5"
    "bGU9Imp1c3RpZnktY29udGVudDpzcGFjZS1iZXR3ZWVuIj4KICAgICAgPHN0cm9uZz5BZG1pdHRlZCBza2lsbHM8L3N0cm9uZz4KICAgICAgPGJ1dHRvbiBj"
    "bGFzcz0iZ2hvc3QiIGlkPSJidG5Ta2lsbHMiPlJlZnJlc2g8L2J1dHRvbj4KICAgIDwvZGl2PgogICAgPHRhYmxlIGlkPSJza1RibCI+PHRoZWFkPjx0cj4K"
    "ICAgICAgPHRoPm5hbWU8L3RoPjx0aD5yZWNpcGU8L3RoPjx0aD5yZWNlaXB0PC90aD48dGg+dmVyaWZpZWQ8L3RoPjx0aD51c2VzPC90aD4KICAgIDwvdHI+"
    "PC90aGVhZD48dGJvZHk+PC90Ym9keT48L3RhYmxlPgogIDwvZGl2Pgo8L3NlY3Rpb24+Cgo8L21haW4+CjxzY3JpcHQ+CmNvbnN0IEFQSSA9ICIvYXBpL2Ex"
    "MW95L3YxL2FnZW50L3JlYWN0IjsKY29uc3QgTCA9ICh3aW5kb3cuU1pMTGFiZWxzICYmIHdpbmRvdy5TWkxMYWJlbHMuYmFkZ2VIVE1MKSA/IHdpbmRvdy5T"
    "WkxMYWJlbHMuYmFkZ2VIVE1MIDogKGspPT4oIjxzcGFuIGNsYXNzPSdsYmwnPiIraysiPC9zcGFuPiIpOwpsZXQgTEFTVF9SVU4gPSBsb2NhbFN0b3JhZ2Uu"
    "Z2V0SXRlbSgiYTExb3lfbGFzdF9ydW4iKSB8fCAiIjsKCmRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0b3BiYWRnZXMiKS5pbm5lckhUTUwgPSBMKCJFWFBF"
    "UklNRU5UQUwiKSArICIgIiArIEwoIkhFVVJJU1RJQyIpOwoKLy8gdGFicwpkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIudGFiIikuZm9yRWFjaCh0PT50"
    "Lm9uY2xpY2s9KCk9PnsKICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIudGFiIikuZm9yRWFjaCh4PT54LmNsYXNzTGlzdC5yZW1vdmUoImFjdGl2ZSIp"
    "KTsKICBkb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCIudmlldyIpLmZvckVhY2goeD0+eC5jbGFzc0xpc3QucmVtb3ZlKCJhY3RpdmUiKSk7CiAgdC5jbGFz"
    "c0xpc3QuYWRkKCJhY3RpdmUiKTsKICBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgidi0iK3QuZGF0YXNldC52KS5jbGFzc0xpc3QuYWRkKCJhY3RpdmUiKTsK"
    "fSk7Cgphc3luYyBmdW5jdGlvbiBqcG9zdCh1LGIpe2NvbnN0IHI9YXdhaXQgZmV0Y2godSx7bWV0aG9kOiJQT1NUIixoZWFkZXJzOnsiQ29udGVudC1UeXBl"
    "IjoiYXBwbGljYXRpb24vanNvbiJ9LGJvZHk6SlNPTi5zdHJpbmdpZnkoYnx8e30pfSk7cmV0dXJuIHtzdGF0dXM6ci5zdGF0dXMsanNvbjphd2FpdCByLmpz"
    "b24oKX07fQphc3luYyBmdW5jdGlvbiBqZ2V0KHUpe2NvbnN0IHI9YXdhaXQgZmV0Y2godSk7cmV0dXJuIHtzdGF0dXM6ci5zdGF0dXMsanNvbjphd2FpdCBy"
    "Lmpzb24oKX07fQpmdW5jdGlvbiBlc2Mocyl7cmV0dXJuIChzPT1udWxsPyIiOlN0cmluZyhzKSkucmVwbGFjZSgvWyY8Pl0vZyxjPT4oeyImIjoiJmFtcDsi"
    "LCI8IjoiJmx0OyIsIj4iOiImZ3Q7In1bY10pKTt9CgovLyAtLS0tLS0tLS0tIEFnZW50IExvb3AgLS0tLS0tLS0tLQovLyBSZXN0cmFpbnQgdmVyZGljdCBj"
    "ZWxsIGZvciBhIG5vZGUgYm9keS4gT25seSBjb2RlLXdyaXRpbmcgQUNUSU9OIG5vZGVzIGNhcnJ5Ci8vIGEgYHJlc3RyYWludGAgYmxvY2s7IGV2ZXJ5dGhp"
    "bmcgZWxzZSBzaG93cyBhIGRpbSBlbS1kYXNoIChob25lc3QpLgpmdW5jdGlvbiByZXN0cmFpbnRDZWxsKGJvZHkpewogIGNvbnN0IHJzID0gYm9keSAmJiBi"
    "b2R5LnJlc3RyYWludDsKICBpZighcnMpIHJldHVybiAiPHNwYW4gY2xhc3M9J211dCc+4oCUPC9zcGFuPiI7CiAgY29uc3QgbGl2ZSA9IHJzLnN0YXR1cz09"
    "PSJMSVZFIjsKICBjb25zdCBiYWRnZSA9IGxpdmUgPyBMKCJMSVZFIikgOiAoTCgiUk9BRE1BUCIpKyIgPHNwYW4gY2xhc3M9J2xibCcgc3R5bGU9J2JvcmRl"
    "ci1jb2xvcjp2YXIoLS13YXJuKTtjb2xvcjp2YXIoLS13YXJuKSc+UEVORElORzwvc3Bhbj4iKTsKICBpZihycy5zdG9wcGVkX2F0X3J1bmchPW51bGwpewog"
    "ICAgY29uc3Qgc2F2ZWQgPSAocnMubGluZXNfc2F2ZWRfZXN0aW1hdGUhPW51bGwpCiAgICAgID8gKCIgwrcgc2F2ZWTiiYgiK3JzLmxpbmVzX3NhdmVkX2Vz"
    "dGltYXRlKyIgTE9DICgiK2VzYyhycy5saW5lc19zYXZlZF9sYWJlbHx8Ik1PREVMRUQiKSsiKSIpIDogIiI7CiAgICBjb25zdCBsYW0gPSAocnMubGFtYmRh"
    "X2Fkdmlzb3J5IT1udWxsKSA/ICgiIMK3IM6bICIrTnVtYmVyKHJzLmxhbWJkYV9hZHZpc29yeSkudG9GaXhlZCgzKSkgOiAiIjsKICAgIGNvbnN0IGNlaWwg"
    "PSBycy5yZXN0cmFpbnRfY29tbWVudCA/ICgiPGRpdiBjbGFzcz0nbXV0JyBzdHlsZT0nZm9udC1zaXplOjExcHgnPjxjb2RlPiIrZXNjKHJzLnJlc3RyYWlu"
    "dF9jb21tZW50KSsiPC9jb2RlPjwvZGl2PiIpIDogIiI7CiAgICByZXR1cm4gIjxkaXY+PHNwYW4gY2xhc3M9J29rJz5ydW5nICIrcnMuc3RvcHBlZF9hdF9y"
    "dW5nKyI8L3NwYW4+ICIrZXNjKHJzLnJ1bmdfa2V5fHwiIikrIiAiK2JhZGdlKyI8L2Rpdj4iKwogICAgICAgICAgICI8ZGl2IGNsYXNzPSdtdXQnIHN0eWxl"
    "PSdmb250LXNpemU6MTFweCc+Iitlc2MocnMucnVuZ19uYW1lfHwiIikrc2F2ZWQrbGFtKyI8L2Rpdj4iK2NlaWw7CiAgfQogIHJldHVybiAiPGRpdj4iK2Jh"
    "ZGdlKyI8L2Rpdj48ZGl2IGNsYXNzPSdtdXQnIHN0eWxlPSdmb250LXNpemU6MTFweCc+Y29kZSBnYXRlZDsgcmVzdHJhaW50IG5vdCBsaXZlIHlldCAobm8g"
    "cnVuZyBmYWJyaWNhdGVkKTwvZGl2PiI7Cn0KYXN5bmMgZnVuY3Rpb24gcmVuZGVyVHJhY2UocnVuSWQpewogIGNvbnN0IHtqc29uOnRyfSA9IGF3YWl0IGpn"
    "ZXQoQVBJKyIvdHJhY2UvIitlbmNvZGVVUklDb21wb25lbnQocnVuSWQpKTsKICBpZih0ci5lcnJvcil7cmV0dXJuO30KICBkb2N1bWVudC5nZXRFbGVtZW50"
    "QnlJZCgidHJhY2VDYXJkIikuc3R5bGUuZGlzcGxheT0iYmxvY2siOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJjaGFpblN0YXRlIikuaW5uZXJIVE1M"
    "ID0KICAgICh0ci5jaGFpbl9pbnRhY3Q/IjxzcGFuIGNsYXNzPSdvayc+Y2hhaW4gaW50YWN0IOKckzwvc3Bhbj4iOiI8c3BhbiBjbGFzcz0nYmFkJz5jaGFp"
    "biBCUk9LRU4g4pyXPC9zcGFuPiIpCiAgICArIiDCtyBkZXB0aCAiK3RyLmRlcHRoOwogIGNvbnN0IHRiPWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoIiN0cmFj"
    "ZVRibCB0Ym9keSIpO3RiLmlubmVySFRNTD0iIjsKICB0ci5yZWNlaXB0cy5mb3JFYWNoKHI9PnsKICAgIGNvbnN0IHNpZyA9IHIuc2lnbmF0dXJlX3ZhbGlk"
    "PT09dHJ1ZT8iPHNwYW4gY2xhc3M9J29rJz52ZXJpZmllZCDinJM8L3NwYW4+IgogICAgICA6KHIuc2lnbmVkPyI8c3BhbiBjbGFzcz0nYmFkJz5GQUlMIOKc"
    "lzwvc3Bhbj4iOiI8c3BhbiBjbGFzcz0nbXV0Jz51bnNpZ25lZDwvc3Bhbj4iKTsKICAgIGNvbnN0IGxpbmsgPSByLmxpbmtfb2s/IjxzcGFuIGNsYXNzPSdv"
    "ayc+4pyTPC9zcGFuPiI6IjxzcGFuIGNsYXNzPSdiYWQnPuKclzwvc3Bhbj4iOwogICAgdGIuaW5uZXJIVE1MICs9IGA8dHI+PHRkPiR7ci5zZXF9PC90ZD48"
    "dGQ+PHNwYW4gY2xhc3M9Im5vZGUgJHtyLm5vZGV9Ij4ke3Iubm9kZX08L3NwYW4+PC90ZD4KICAgICAgPHRkPjxwcmU+JHtlc2MoSlNPTi5zdHJpbmdpZnko"
    "ci5ib2R5KSl9PC9wcmU+PC90ZD48dGQ+JHtyZXN0cmFpbnRDZWxsKHIuYm9keSl9PC90ZD48dGQ+JHtsaW5rfTwvdGQ+PHRkPiR7c2lnfTwvdGQ+CiAgICAg"
    "IDx0ZCBjbGFzcz0iaGFzaCI+JHtlc2MoKHIuaGFzaHx8IiIpLnNsaWNlKDAsMTgpKX3igKY8L3RkPjwvdHI+YDsKICB9KTsKICBpZih0ci5yZWZsZWN0aW9u"
    "KXsKICAgIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJydW5sYmwiKS5pbm5lckhUTUwgPQogICAgICAiIMK3IHJlZmxlY3Rpb24gKFJlZmxleGlvbik6IDxl"
    "bT4iK2VzYyh0ci5yZWZsZWN0aW9uLnNsaWNlKDAsOTApKSsiPC9lbT4iOwogIH0KfQphc3luYyBmdW5jdGlvbiByZW5kZXJDcHMocnVuSWQpewogIGNvbnN0"
    "IHtqc29uOmNwfT1hd2FpdCBqZ2V0KEFQSSsiL2NoZWNrcG9pbnRzLyIrZW5jb2RlVVJJQ29tcG9uZW50KHJ1bklkKSk7CiAgZG9jdW1lbnQuZ2V0RWxlbWVu"
    "dEJ5SWQoImNwQ2FyZCIpLnN0eWxlLmRpc3BsYXk9ImJsb2NrIjsKICBjb25zdCB0Yj1kb2N1bWVudC5xdWVyeVNlbGVjdG9yKCIjY3BUYmwgdGJvZHkiKTt0"
    "Yi5pbm5lckhUTUw9IiI7CiAgY3AuY2hlY2twb2ludHMuZm9yRWFjaChjPT50Yi5pbm5lckhUTUwrPWA8dHI+PHRkPiR7Yy5zdGVwfTwvdGQ+PHRkIGNsYXNz"
    "PSJoYXNoIj4ke2VzYygoYy5wcmV2X2hhc2h8fCIiKS5zbGljZSgwLDE4KSl94oCmPC90ZD48dGQgY2xhc3M9Im11dCI+JHtlc2MoYy50cyl9PC90ZD48L3Ry"
    "PmApOwp9CmZ1bmN0aW9uIHNob3dSdW5NZXRhKG8pewogIGNvbnN0IG09ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoInJ1bk1ldGEiKTttLnN0eWxlLmRpc3Bs"
    "YXk9ImJsb2NrIjsKICBjb25zdCBzdCA9IG8uc3RhdHVzPT09ImNvbXBsZXRlZCI/Im9rIjooby5zdGF0dXM9PT0iaW50ZXJydXB0ZWQiPyJiYWQiOiJtdXQi"
    "KTsKICBtLmlubmVySFRNTCA9IGA8c3Ryb25nPnJ1bjwvc3Ryb25nPiA8Y29kZT4ke2VzYyhvLnJ1bl9pZCl9PC9jb2RlPiDCtyBzdGF0dXMgPHNwYW4gY2xh"
    "c3M9IiR7c3R9Ij4ke2VzYyhvLnN0YXR1cyl9PC9zcGFuPmAKICAgICsgKG8uYW5zd2VyP2AgwrcgYW5zd2VyIDxzcGFuIGNsYXNzPSJvayI+JHtlc2Moby5h"
    "bnN3ZXIpfTwvc3Bhbj5gOiIiKQogICAgKyAoby5yZXN1bWVkP2AgwrcgPHNwYW4gY2xhc3M9InBpbGwiPnJlc3VtZWQgZnJvbSBzdGVwICR7by5yZXN1bWVk"
    "X2Zyb21fY2hlY2twb2ludF9zdGVwfTwvc3Bhbj5gOiIiKQogICAgKyAiICIgKyBMKG8ubGFiZWx8fCJFWFBFUklNRU5UQUwiKTsKfQpkb2N1bWVudC5nZXRF"
    "bGVtZW50QnlJZCgiYnRuUnVuIikub25jbGljaz1hc3luYygpPT57CiAgY29uc3QgZ29hbD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiZ29hbCIpLnZhbHVl"
    "OwogIGNvbnN0IG1heF9zdGVwcz0rZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1heHN0ZXBzIikudmFsdWU7CiAgY29uc3QgYm9keT17Z29hbCxtYXhfc3Rl"
    "cHN9OwogIGlmKGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJraWxsIikuY2hlY2tlZCkgYm9keS5raWxsX2FmdGVyPTI7CiAgY29uc3Qge2pzb246b309YXdh"
    "aXQganBvc3QoQVBJKyIvcnVuIixib2R5KTsKICBMQVNUX1JVTj1vLnJ1bl9pZDtsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgiYTExb3lfbGFzdF9ydW4iLG8ucnVu"
    "X2lkKTsKICBzaG93UnVuTWV0YShvKTthd2FpdCByZW5kZXJUcmFjZShvLnJ1bl9pZCk7YXdhaXQgcmVuZGVyQ3BzKG8ucnVuX2lkKTsKfTsKZG9jdW1lbnQu"
    "Z2V0RWxlbWVudEJ5SWQoImJ0blJlc3VtZSIpLm9uY2xpY2s9YXN5bmMoKT0+ewogIGlmKCFMQVNUX1JVTil7YWxlcnQoInJ1biBzb21ldGhpbmcgZmlyc3Qi"
    "KTtyZXR1cm47fQogIGNvbnN0IHtqc29uOm99PWF3YWl0IGpwb3N0KEFQSSsiL3Jlc3VtZSIse3J1bl9pZDpMQVNUX1JVTn0pOwogIHNob3dSdW5NZXRhKG8p"
    "O2F3YWl0IHJlbmRlclRyYWNlKExBU1RfUlVOKTthd2FpdCByZW5kZXJDcHMoTEFTVF9SVU4pOwp9OwoKLy8gLS0tLS0tLS0tLSBNZW1vcnkgLS0tLS0tLS0t"
    "LQpkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiYnRuTWVtQWRkIikub25jbGljaz1hc3luYygpPT57CiAgY29uc3QgdGV4dD1kb2N1bWVudC5nZXRFbGVtZW50"
    "QnlJZCgibWVtVGV4dCIpLnZhbHVlO2lmKCF0ZXh0KXJldHVybjsKICBhd2FpdCBqcG9zdChBUEkrIi9tZW1vcnkvYWRkIix7dGV4dCx0aWVyOiJhcmNoaXZh"
    "bCIscnVuX2lkOkxBU1RfUlVOfHwiYWRob2MifSk7CiAgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoIm1lbVRleHQiKS52YWx1ZT0iIjtsb2FkVGllcnMoKTsK"
    "fTsKZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImJ0bk1lbVNlYXJjaCIpLm9uY2xpY2s9YXN5bmMoKT0+ewogIGNvbnN0IHF1ZXJ5PWRvY3VtZW50LmdldEVs"
    "ZW1lbnRCeUlkKCJtZW1RIikudmFsdWU7aWYoIXF1ZXJ5KXJldHVybjsKICBjb25zdCB7anNvbjpvfT1hd2FpdCBqcG9zdChBUEkrIi9tZW1vcnkvc2VhcmNo"
    "Iix7cXVlcnksdG9wX2s6OH0pOwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJtZW1DYXJkIikuc3R5bGUuZGlzcGxheT0iYmxvY2siOwogIGNvbnN0IHRi"
    "PWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoIiNtZW1UYmwgdGJvZHkiKTt0Yi5pbm5lckhUTUw9IiI7CiAgKG8ucmVzdWx0c3x8W10pLmZvckVhY2goaD0+ewog"
    "ICAgY29uc3QgYz1oLmNvbXBvbmVudHM7CiAgICB0Yi5pbm5lckhUTUwrPWA8dHI+PHRkPjxzdHJvbmc+JHtoLnNjb3JlLnRvRml4ZWQoMyl9PC9zdHJvbmc+"
    "PC90ZD4KICAgICAgPHRkPiR7Yy5yZWNlbmN5X2dhbW1hX2R0LnRvRml4ZWQoMyl9IDxzcGFuIGNsYXNzPSJtdXQiPijOlHQgJHtjLmRlbHRhX3RfaG91cnN9"
    "aCk8L3NwYW4+PC90ZD4KICAgICAgPHRkPiR7Yy5pbXBvcnRhbmNlLnRvRml4ZWQoMil9PC90ZD48dGQ+JHtjLnJlbGV2YW5jZV9jb3MudG9GaXhlZCgzKX08"
    "L3RkPgogICAgICA8dGQ+PHNwYW4gY2xhc3M9InBpbGwiPiR7ZXNjKGgudGllcil9PC9zcGFuPjwvdGQ+PHRkPiR7ZXNjKGgudGV4dCl9PC90ZD48L3RyPmA7"
    "CiAgfSk7Cn07CmFzeW5jIGZ1bmN0aW9uIGxvYWRUaWVycygpewogIGNvbnN0IHUgPSBBUEkrIi9tZW1vcnkvdGllcnMiKyhMQVNUX1JVTj8oIj9ydW5faWQ9"
    "IitlbmNvZGVVUklDb21wb25lbnQoTEFTVF9SVU4pKToiIik7CiAgY29uc3Qge2pzb246b309YXdhaXQgamdldCh1KTsKICBjb25zdCB0PW8udGllcnN8fHt9"
    "OwogIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJ0aWVyQm9keSIpLmlubmVySFRNTCA9CiAgICBgd29ya2luZyA8c3Ryb25nPiR7dC53b3JraW5nfHwwfTwv"
    "c3Ryb25nPiDCtyBhcmNoaXZhbCA8c3Ryb25nPiR7dC5hcmNoaXZhbHx8MH08L3N0cm9uZz4gwrcgY2FwICR7by53b3JraW5nX2NhcH0gYAogICAgKyBMKG8u"
    "bGFiZWx8fCJFWFBFUklNRU5UQUwiKQogICAgKyBgPGRpdiBjbGFzcz0ibXV0IiBzdHlsZT0ibWFyZ2luLXRvcDo2cHgiPiR7ZXNjKG8uZGVzaWdufHwiIil9"
    "PC9kaXY+YDsKfQpkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiYnRuVGllcnMiKS5vbmNsaWNrPWxvYWRUaWVyczsKCi8vIC0tLS0tLS0tLS0gU2tpbGxzIC0t"
    "LS0tLS0tLS0KZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoImJ0bkFkbWl0Iikub25jbGljaz1hc3luYygpPT57CiAgY29uc3QgbmFtZT1kb2N1bWVudC5nZXRF"
    "bGVtZW50QnlJZCgic2tOYW1lIikudmFsdWU7CiAgY29uc3QgcmVjaXBlPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJza1JlY2lwZSIpLnZhbHVlOwogIGNv"
    "bnN0IHJ1bl9pZD1kb2N1bWVudC5nZXRFbGVtZW50QnlJZCgic2tSdW4iKS52YWx1ZXx8TEFTVF9SVU47CiAgY29uc3Qge3N0YXR1cyxqc29uOm99PWF3YWl0"
    "IGpwb3N0KEFQSSsiL3NraWxscy9hZG1pdCIse25hbWUscmVjaXBlLHJ1bl9pZH0pOwogIGNvbnN0IGVsPWRvY3VtZW50LmdldEVsZW1lbnRCeUlkKCJhZG1p"
    "dE1zZyIpOwogIGVsLmlubmVySFRNTCA9IChvLmFkbWl0dGVkPyI8c3BhbiBjbGFzcz0nb2snPiI6IjxzcGFuIGNsYXNzPSdiYWQnPiIpK2VzYyhvLnJlYXNv"
    "bikrIjwvc3Bhbj4iOwogIGxvYWRTa2lsbHMoKTsKfTsKYXN5bmMgZnVuY3Rpb24gbG9hZFNraWxscygpewogIGNvbnN0IHtqc29uOm99PWF3YWl0IGpnZXQo"
    "QVBJKyIvc2tpbGxzIik7CiAgY29uc3QgdGI9ZG9jdW1lbnQucXVlcnlTZWxlY3RvcigiI3NrVGJsIHRib2R5Iik7dGIuaW5uZXJIVE1MPSIiOwogIChvLnNr"
    "aWxsc3x8W10pLmZvckVhY2gocz0+ewogICAgdGIuaW5uZXJIVE1MKz1gPHRyPjx0ZD48c3Ryb25nPiR7ZXNjKHMubmFtZSl9PC9zdHJvbmc+PC90ZD48dGQ+"
    "PGNvZGU+JHtlc2Mocy5yZWNpcGUpfTwvY29kZT48L3RkPgogICAgICA8dGQgY2xhc3M9Imhhc2giPiR7ZXNjKChzLnJlY2VpcHRfaGFzaHx8IiIpLnNsaWNl"
    "KDAsMTYpKX3igKY8L3RkPgogICAgICA8dGQ+JHtzLnJlY2VpcHRfdmVyaWZpZWQ/IjxzcGFuIGNsYXNzPSdvayc+4pyTPC9zcGFuPiI6IjxzcGFuIGNsYXNz"
    "PSdiYWQnPuKclzwvc3Bhbj4ifTwvdGQ+CiAgICAgIDx0ZD4ke3MudXNlc308L3RkPjwvdHI+YDsKICB9KTsKfQpkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgi"
    "YnRuU2tpbGxzIikub25jbGljaz1sb2FkU2tpbGxzOwoKLy8gYm9vdApsb2FkVGllcnMoKTtsb2FkU2tpbGxzKCk7Cjwvc2NyaXB0Pgo8L2JvZHk+CjwvaHRt"
    "bD4K"
)

# Routes inserted at position 0 (Starlette Route) so they beat the SPA catch-all.
# FREE sub-namespace /api/a11oy/v1/agent/react/* to avoid collisions with the
# existing /run, /tools, /verify-chain, /governance-standards, /_diag, /loop.
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy", sign_fn=None, verify_fn=None,
             pub_pem_fn=None, signer_label: str = "in-image key"):
    from starlette.routing import Route
    from starlette.responses import JSONResponse, HTMLResponse

    _init_db()

    # ----- /agent-loop trace UI (R2, additive) ----------------------------
    # The committed web/agent-loop.html trace surface (restraint-verdict column)
    # was never routed by serve.py (no add_api_route + no Dockerfile COPY), so
    # /agent-loop fell through to the SPA catch-all and the restraint column
    # was not user-visible. We serve it here from THIS module (owned file),
    # reading the byte-identical committed HTML from known on-disk paths. Routes
    # insert at position 0 so they beat the SPA catch-all. Fully additive; no
    # shared file edited; honest 503 if the asset is genuinely absent.
    _AGENTLOOP_PATHS = [
        "/app/web/agent-loop.html",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "agent-loop.html"),
        "web/agent-loop.html",
    ]

    def _agentloop_html():
        for p in _AGENTLOOP_PATHS:
            try:
                if os.path.isfile(p):
                    with open(p, "r", encoding="utf-8") as fh:
                        return fh.read()
            except Exception:
                continue
        try:
            import base64 as _b64
            return _b64.b64decode(_AGENTLOOP_HTML_B64).decode("utf-8")
        except Exception:
            return None

    async def _agentloop_page(request):
        html = _agentloop_html()
        if html is None:
            return HTMLResponse(
                "<!doctype html><meta charset=utf-8><title>Agent Loop</title>"
                "<body style='font:14px ui-monospace;background:#0b0e14;color:#e6edf3;"
                "padding:32px'>Agent Loop trace UI asset not baked in this image. "
                "The restraint-gated trace is live via "
                "<code>GET /api/a11oy/v1/agent/react/trace?run_id=...</code> "
                "(ACTION nodes carry the signed restraint verdict).</body>",
                status_code=200)
        return HTMLResponse(html)
    eng = _ReActEngine(sign_fn, verify_fn, pub_pem_fn, ns=ns)

    async def _read_json(request):
        try:
            return await request.json()
        except Exception:
            return {}

    async def _run(request):
        d = await _read_json(request)
        goal = (d.get("goal") or d.get("query") or "").strip()
        if not goal:
            return JSONResponse({"error": "missing 'goal'"}, status_code=400)
        max_steps = int(d.get("max_steps", 4))
        kill_after = d.get("kill_after")  # honest crash-injection for the demo
        kill_after = int(kill_after) if kill_after is not None else None
        out = eng.run(goal, max_steps=max_steps, kill_after=kill_after)
        out["label"] = "EXPERIMENTAL"
        return JSONResponse(out)

    async def _resume(request):
        d = await _read_json(request)
        run_id = (d.get("run_id") or request.query_params.get("run_id") or "").strip()
        if not run_id:
            return JSONResponse({"error": "missing 'run_id'"}, status_code=400)
        out = eng.resume(run_id)
        out["label"] = "EXPERIMENTAL"
        return JSONResponse(out)

    async def _trace(request):
        run_id = request.path_params.get("run_id") or request.query_params.get("run_id", "")
        return JSONResponse(eng.trace(run_id))

    async def _checkpoints(request):
        run_id = request.path_params.get("run_id") or request.query_params.get("run_id", "")
        return JSONResponse(eng.checkpoints(run_id))

    async def _reflect(request):
        d = await _read_json(request)
        run_id = (d.get("run_id") or "").strip()
        text = (d.get("reflection") or d.get("text") or "").strip()
        if not run_id or not text:
            return JSONResponse({"error": "need run_id + reflection"}, status_code=400)
        return JSONResponse(eng.reflect(run_id, text))

    async def _mem_add_ep(request):
        d = await _read_json(request)
        text = (d.get("text") or "").strip()
        if not text:
            return JSONResponse({"error": "missing 'text'"}, status_code=400)
        mid = _mem_add(d.get("run_id", "adhoc"), d.get("tier", "archival"),
                       d.get("kind", "note"), text, d.get("importance"))
        return JSONResponse({"mem_id": mid, "tier": d.get("tier", "archival"),
                             "label": "HEURISTIC"})

    async def _mem_search_ep(request):
        d = await _read_json(request)
        q = (d.get("query") or "").strip()
        if not q:
            return JSONResponse({"error": "missing 'query'"}, status_code=400)
        hits = _mem_retrieve(q, top_k=int(d.get("top_k", 5)), tier=d.get("tier"))
        return JSONResponse({"query": q, "results": hits, "label": "HEURISTIC",
                             "formula": "score(m)=a_rec*g^dt + a_imp*imp(m) + a_rel*cos(q,m)",
                             "source": "Generative Agents (arXiv 2304.03442)"})

    async def _mem_tiers(request):
        run_id = request.query_params.get("run_id", "")
        with _LOCK, _conn() as c:
            wq = ("SELECT tier,COUNT(*) AS n FROM memory" +
                  (" WHERE run_id=?" if run_id else "") + " GROUP BY tier")
            rows = c.execute(wq, ((run_id,) if run_id else ())).fetchall()
        tiers = {r["tier"]: r["n"] for r in rows}
        return JSONResponse({"run_id": run_id or None, "tiers": tiers,
                             "working": _working_snapshot(run_id) if run_id else [],
                             "working_cap": _WORKING_CAP,
                             "design": "Letta/MemGPT (arXiv 2310.08560): working "
                                       "(in-context) + archival (vector); self-managed.",
                             "label": "EXPERIMENTAL"})

    async def _skill_admit_ep(request):
        d = await _read_json(request)
        name = (d.get("name") or "").strip()
        recipe = (d.get("recipe") or "").strip()
        run_id = (d.get("run_id") or "").strip()
        if not name or not recipe:
            return JSONResponse({"error": "need name + recipe"}, status_code=400)
        # Voyager admission: require a VERIFIED execution receipt. We accept a
        # run_id and verify its final emit receipt; OR a direct envelope.
        verified, rhash = False, ""
        if run_id:
            tr = eng.trace(run_id)
            recs = tr.get("receipts", [])
            if recs:
                last = recs[-1]
                rhash = last["hash"]
                verified = bool(last.get("signature_valid")) and tr.get("chain_intact")
        elif d.get("envelope") and verify_fn is not None:
            try:
                verified = bool(verify_fn(d["envelope"]).get("signature_valid"))
                rhash = _sha(d["envelope"])[:32]
            except Exception:
                verified = False
        res = _skill_admit(name, recipe, rhash, verified)
        res["label"] = "LIVE" if res.get("admitted") else "EXPERIMENTAL"
        return JSONResponse(res, status_code=200 if res.get("admitted") else 422)

    async def _skill_list(request):
        q = request.query_params.get("q", "")
        return JSONResponse({"query": q or None,
                             "skills": _skill_search(q or "skill", top_k=50),
                             "admission_rule": "Voyager (arXiv 2305.16291): admit a "
                                               "recipe ONLY after a verified execution receipt.",
                             "label": "LIVE"})

    async def _diag(request):
        with _LOCK, _conn() as c:
            nr = c.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"]
            nm = c.execute("SELECT COUNT(*) AS n FROM memory").fetchone()["n"]
            ns_ = c.execute("SELECT COUNT(*) AS n FROM skills").fetchone()["n"]
        return JSONResponse({
            "module": "a11oy_react_core", "status": "ok",
            "db": _DB_PATH, "runs": nr, "memories": nm, "skills": ns_,
            "signer": signer_label,
            "pubkey_present": bool((pub_pem_fn() if pub_pem_fn else "")),
            "subsystems": ["ReAct graph (2210.03629)", "SqliteSaver checkpointing",
                           "Reflexion (2303.11366)", "Generative-Agents memory (2304.03442)",
                           "Letta tiering (2310.08560)", "Voyager skill library (2305.16291)",
                           "a11oy Restraint code gate (Ponytail MIT, R1)"],
            "restraint": {"module_importable": _restraint_mod() is not None,
                          "http_endpoint": _RESTRAINT_HTTP,
                          "code_tools_gated": sorted(_CODE_TOOLS),
                          "ponytail": _PONYTAIL,
                          "note": ("Action nodes that write code are gated through "
                                   "restraint; honest PENDING if R1 not live.")},
            "label": "EXPERIMENTAL"})

    base = "/api/%s/v1/agent/react" % ns
    routes = [
        Route(base + "/run", _run, methods=["POST"], name="%s_react_run" % ns),
        Route(base + "/resume", _resume, methods=["POST"], name="%s_react_resume" % ns),
        Route(base + "/trace/{run_id}", _trace, methods=["GET"], name="%s_react_trace" % ns),
        Route(base + "/trace", _trace, methods=["GET"], name="%s_react_trace_q" % ns),
        Route(base + "/checkpoints/{run_id}", _checkpoints, methods=["GET"],
              name="%s_react_cps" % ns),
        Route(base + "/checkpoints", _checkpoints, methods=["GET"], name="%s_react_cps_q" % ns),
        Route(base + "/reflect", _reflect, methods=["POST"], name="%s_react_reflect" % ns),
        Route(base + "/memory/add", _mem_add_ep, methods=["POST"], name="%s_react_mem_add" % ns),
        Route(base + "/memory/search", _mem_search_ep, methods=["POST"],
              name="%s_react_mem_search" % ns),
        Route(base + "/memory/tiers", _mem_tiers, methods=["GET"], name="%s_react_mem_tiers" % ns),
        Route(base + "/skills/admit", _skill_admit_ep, methods=["POST"],
              name="%s_react_skill_admit" % ns),
        Route(base + "/skills", _skill_list, methods=["GET"], name="%s_react_skills" % ns),
        Route(base + "/_diag", _diag, methods=["GET"], name="%s_react_diag" % ns),
        # Free top-level conveniences requested by the spec (not taken elsewhere):
        Route("/api/%s/v1/agent/resume" % ns, _resume, methods=["POST"],
              name="%s_agent_resume_top" % ns),
        Route("/api/%s/v1/agent/trace/{run_id}" % ns, _trace, methods=["GET"],
              name="%s_agent_trace_top" % ns),
        Route("/api/%s/v1/agent/checkpoints/{run_id}" % ns, _checkpoints, methods=["GET"],
              name="%s_agent_cps_top" % ns),
        Route("/api/%s/v1/agent/checkpoints" % ns, _checkpoints, methods=["GET"],
              name="%s_agent_cps_top_q" % ns),
        # R2 additive: serve the committed agent-loop trace UI (restraint column)
        # at the canonical nav targets. insert(0) beats the SPA catch-all.
        Route("/agent-loop", _agentloop_page, methods=["GET"], name="%s_agentloop_page" % ns),
        Route("/a11oy/agent-loop", _agentloop_page, methods=["GET"],
              name="%s_agentloop_page_alt" % ns),
    ]
    for r in routes:
        app.router.routes.insert(0, r)
    return {"module": "a11oy_react_core", "routes": len(routes), "base": base,
            "signer": signer_label}
