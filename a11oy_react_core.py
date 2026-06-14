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


_TOOLS = {
    "calc": _tool_calc,
    "memory_search": _tool_memory_search,
    "skill_search": _tool_skill_search,
    "echo": _tool_echo,
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
# Routes inserted at position 0 (Starlette Route) so they beat the SPA catch-all.
# FREE sub-namespace /api/a11oy/v1/agent/react/* to avoid collisions with the
# existing /run, /tools, /verify-chain, /governance-standards, /_diag, /loop.
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy", sign_fn=None, verify_fn=None,
             pub_pem_fn=None, signer_label: str = "in-image key"):
    from starlette.routing import Route
    from starlette.responses import JSONResponse

    _init_db()
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
                           "Letta tiering (2310.08560)", "Voyager skill library (2305.16291)"],
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
    ]
    for r in routes:
        app.router.routes.insert(0, r)
    return {"module": "a11oy_react_core", "routes": len(routes), "base": base,
            "signer": signer_label}
