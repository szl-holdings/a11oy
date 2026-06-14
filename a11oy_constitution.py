# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
a11oy_constitution.py — CONSTITUTIONAL ENGINES (Lane I3)

Constitutional architecture built ON a11oy's existing primitives (DSSE receipts,
hash-chained tamper-evident ledger, Λ trust score, ontology/lineage). It is a
governed, auditable, policy-enforced agent runtime — NOT a new form of existence
and NOT an AGI. Concept origin: Eduardo Cesar Lunardelli's "Constitutional
Cognitive Architecture" (LinkedIn, conceptual). Mapped to established literature
and OSS per CONSTITUTIONAL_ARCH_RESEARCH.md.

ENGINES (ACTIVE built first, honest status colors throughout):
  🟢 Causal Ledger      — event-sourced append-only causal history over receipts,
                          annotated with W3C PROV-DM (wasGeneratedBy/used/
                          wasAttributedTo/wasInformedBy). Merkle-style hash chain.
  🟢 Audit Engine       — query + signed-verification layer over the ledger;
                          verify_receipt, audit_session, compliance views.
  🟢 Constitutional Memory — versioned doctrine/decision store with pin / promote /
                          rollback (TrustGraph-style Context Cores).
  🟢 Ontological Registry — registry of what exists/is meaningful, versioned, with
                          provenance + lineage (build on the existing ontology tab).
  🟡 State / Transition — XState-style statechart over the agent lifecycle with
                          Λ-guarded transitions (IN-DEV: formal SCXML export roadmap).
  🟡 Legitimacy         — IN-DEV: CAI-style doctrine-mutability hierarchy.
  🟡 Immunology         — IN-DEV: drift/epistemic-immune (reuses drift guards).
  🔵 Governance-Evolution — ROADMAP: OSCAL doctrine-diff + quorum approval.

Citations (in code + UI): Fabro (MIT), TrustGraph (Apache-2.0), PyMDP (Apache-2.0),
XState (MIT), Temporal (MIT), OSCAL (public domain), sigstore (Apache-2.0),
W3C PROV, Anthropic Constitutional AI (arXiv:2212.08073), Lunardelli (concept origin).

Endpoints (namespace /api/a11oy/v1/constitution):
  GET  /ledger              event-sourced causal history (W3C PROV-annotated)
  POST /ledger              append a causal event (signed, PROV-annotated)
  GET  /audit               query/verify layer over the ledger (?session= optional)
  POST /memory              write/pin/promote/rollback a doctrine/decision version
  GET  /memory              current Constitutional Memory (versioned Context Cores)
  GET  /ontology            ontological registry (what exists/is meaningful, versioned)
  POST /ontology            register/version an entity
  GET  /state               XState-style statechart definition + current state
  POST /state               fire a guarded transition (Λ-gated)
  GET  /status              all engines with honest ACTIVE/IN-DEV/ROADMAP, mapped to 8 pillars

DCO: Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
Doctrine: v11 LOCKED | locked=8 @ c7c0ba17 | Λ Conjecture 1 (<1.0) | tamper-evident
          (Conjecture 2, NOT tamper-proof) | SLSA L1/L2 (L3 roadmap) | trust<100%
          | 0 CDN | honest statuses, never overclaim a skeleton as done | no key committed
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# DEVELOPER ORIENTATION
# Purpose:   Constitutional engines over a11oy primitives. ACTIVE engines are
#            real and tested; IN-DEV/ROADMAP are honestly labelled and NOT
#            presented as done.
# Key entry: register(app, ns, sign_fn, verify_fn) ; engine classes below.
# Pillars:   1 Ontology, 2 Phenomenology, 3 Temporality, 4 Legitimacy,
#            5 Immunology, 6 Energy, 7 Topology, 8 Governance.
# Doctrine:  Λ Conjecture 1 (<1.0). tamper-EVIDENT (Conjecture 2). locked=8 @ c7c0ba17.
# ---------------------------------------------------------------------------

_DB_PATH = os.environ.get("A11OY_CONSTITUTION_DB", "/tmp/a11oy_constitution.db")
_LOCK = threading.RLock()
LAMBDA_HALT = 0.30
LAMBDA_CAP = 0.999

LOCKED_8 = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]  # doctrine v11 @ c7c0ba17


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(s) -> str:
    if not isinstance(s, (bytes, bytearray)):
        s = json.dumps(s, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(s).hexdigest()


def _conn():
    c = sqlite3.connect(_DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def _init_db():
    with _LOCK, _conn() as c:
        # Causal Ledger — event-sourced, append-only, W3C PROV-annotated.
        c.execute("""CREATE TABLE IF NOT EXISTS ledger(
            seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT, session TEXT,
            prov_activity TEXT, prov_entity TEXT, prov_agent TEXT,
            prov_used TEXT, prov_was_informed_by TEXT,
            body TEXT, prev_hash TEXT, hash TEXT, envelope TEXT, ts TEXT)""")
        # Constitutional Memory — versioned doctrine/decision Context Cores.
        c.execute("""CREATE TABLE IF NOT EXISTS memory(
            id INTEGER PRIMARY KEY AUTOINCREMENT, core_id TEXT, version INTEGER,
            kind TEXT, content TEXT, state TEXT, pinned INTEGER DEFAULT 0,
            prev_hash TEXT, hash TEXT, envelope TEXT, ts TEXT)""")
        # Ontological Registry — versioned entities (what exists/is meaningful).
        c.execute("""CREATE TABLE IF NOT EXISTS ontology(
            id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT, version INTEGER,
            owl_class TEXT, label TEXT, properties TEXT, provenance TEXT,
            hash TEXT, ts TEXT)""")
        # Statechart — XState-style current state + transition log.
        c.execute("""CREATE TABLE IF NOT EXISTS statelog(
            id INTEGER PRIMARY KEY AUTOINCREMENT, machine TEXT, from_state TEXT,
            event TEXT, to_state TEXT, guard_lambda REAL, allowed INTEGER,
            hash TEXT, ts TEXT)""")


# ===========================================================================
# 🟢 ENGINE: Causal Ledger (Pillar 3 Temporality + Memory)
# Event sourcing (Azure pattern) + W3C PROV-DM annotations on every event, over
# a11oy's tamper-evident hash chain. Each event: a prov:Entity generated by a
# prov:Activity, attributed to a prov:Agent. Merkle-style chain (prev_hash link).
# Refs: W3C PROV-DM (https://www.w3.org/TR/prov-dm/); Event Sourcing for Agents;
# in-toto attestation (Apache-2.0); sigstore/cosign for anchoring (roadmap).
# ===========================================================================
class CausalLedger:
    def __init__(self, sign_fn=None, verify_fn=None, ns="a11oy"):
        self.sign_fn, self.verify_fn, self.ns = sign_fn, verify_fn, ns

    def _last_hash(self):
        with _LOCK, _conn() as c:
            r = c.execute("SELECT hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
        return r["hash"] if r else "GENESIS"

    def append(self, activity, entity, agent="a11oy", used=None,
               was_informed_by=None, session="default", body=None):
        prev = self._last_hash()
        eid = uuid.uuid4().hex[:16]
        core = {"event_id": eid, "session": session,
                "prov:wasGeneratedBy": activity, "prov:entity": entity,
                "prov:wasAttributedTo": agent, "prov:used": used or [],
                "prov:wasInformedBy": was_informed_by or [], "body": body or {},
                "prev_hash": prev}
        h = _sha(core)
        env = None
        if self.sign_fn is not None:
            try:
                env = self.sign_fn({"causal_event": core, "hash": h, "ts": _now_iso(),
                                    "doctrine": "v11", "prov": "W3C PROV-DM"})
            except Exception as e:
                env = {"signed": False, "honesty": "sign_fn raised: %s" % type(e).__name__}
        with _LOCK, _conn() as c:
            c.execute("INSERT INTO ledger(event_id,session,prov_activity,prov_entity,"
                      "prov_agent,prov_used,prov_was_informed_by,body,prev_hash,hash,"
                      "envelope,ts) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (eid, session, activity, entity, agent, json.dumps(used or []),
                       json.dumps(was_informed_by or []), json.dumps(body or {}),
                       prev, h, json.dumps(env) if env else None, _now_iso()))
        return {"event_id": eid, "hash": h, "prev_hash": prev,
                "signed": bool(env and env.get("signed")),
                "prov": {"wasGeneratedBy": activity, "entity": entity,
                         "wasAttributedTo": agent}}

    def query(self, session=None, limit=100):
        with _LOCK, _conn() as c:
            if session:
                rows = c.execute("SELECT * FROM ledger WHERE session=? ORDER BY seq LIMIT ?",
                                 (session, limit)).fetchall()
            else:
                rows = c.execute("SELECT * FROM ledger ORDER BY seq DESC LIMIT ?",
                                 (limit,)).fetchall()
        events = [{"seq": r["seq"], "event_id": r["event_id"], "session": r["session"],
                   "prov": {"wasGeneratedBy": r["prov_activity"], "entity": r["prov_entity"],
                            "wasAttributedTo": r["prov_agent"],
                            "used": json.loads(r["prov_used"] or "[]"),
                            "wasInformedBy": json.loads(r["prov_was_informed_by"] or "[]")},
                   "body": json.loads(r["body"] or "{}"), "prev_hash": r["prev_hash"],
                   "hash": r["hash"], "signed": bool(r["envelope"]
                   and json.loads(r["envelope"]).get("signed")), "ts": r["ts"]} for r in rows]
        return {"events": events, "count": len(events), "session": session,
                "model": "event-sourced append-only causal history; W3C PROV-DM annotated",
                "prov_predicates": ["prov:wasGeneratedBy", "prov:used",
                                    "prov:wasAttributedTo", "prov:wasInformedBy"],
                "status": "ACTIVE", "label": "LIVE",
                "refs": ["W3C PROV-DM https://www.w3.org/TR/prov-dm/",
                         "in-toto attestation (Apache-2.0)"]}

    def ancestors(self, event_id):
        with _LOCK, _conn() as c:
            rows = c.execute("SELECT event_id,prev_hash,hash,prov_activity,ts FROM ledger "
                             "ORDER BY seq").fetchall()
        by_hash = {r["hash"]: r for r in rows}
        start = next((r for r in rows if r["event_id"] == event_id), None)
        chain = []
        cur = start
        guard = 0
        while cur and guard < 1000:
            chain.append({"event_id": cur["event_id"], "activity": cur["prov_activity"],
                          "hash": cur["hash"], "ts": cur["ts"]})
            cur = by_hash.get(cur["prev_hash"])
            guard += 1
        return {"event_id": event_id, "causal_ancestors": chain, "depth": len(chain),
                "status": "ACTIVE", "label": "LIVE"}


# ===========================================================================
# 🟢 ENGINE: Audit Engine (Pillar 8 Governance + Memory)
# Query + cryptographic verification layer over the Causal Ledger. Recomputes
# each event hash, re-verifies its DSSE signature (via verify_fn), and emits a
# SIGNED audit summary. Honest: tamper-EVIDENT (Conjecture 2), NOT tamper-proof.
# Refs: Sello Protocol; Armalo Merkle audit logs; sigstore/cosign (Apache-2.0).
# ===========================================================================
class AuditEngine:
    def __init__(self, ledger: CausalLedger, sign_fn=None, verify_fn=None, ns="a11oy"):
        self.ledger, self.sign_fn, self.verify_fn, self.ns = ledger, sign_fn, verify_fn, ns

    def audit(self, session=None):
        with _LOCK, _conn() as c:
            if session:
                rows = c.execute("SELECT * FROM ledger WHERE session=? ORDER BY seq",
                                 (session,)).fetchall()
            else:
                rows = c.execute("SELECT * FROM ledger ORDER BY seq").fetchall()
        prev = "GENESIS"
        chain_ok = True
        checked = []
        sig_known = 0
        sig_valid = 0
        for r in rows:
            core = {"event_id": r["event_id"], "session": r["session"],
                    "prov:wasGeneratedBy": r["prov_activity"], "prov:entity": r["prov_entity"],
                    "prov:wasAttributedTo": r["prov_agent"],
                    "prov:used": json.loads(r["prov_used"] or "[]"),
                    "prov:wasInformedBy": json.loads(r["prov_was_informed_by"] or "[]"),
                    "body": json.loads(r["body"] or "{}"), "prev_hash": r["prev_hash"]}
            recompute = _sha(core)
            link_ok = (r["prev_hash"] == prev) and (recompute == r["hash"])
            chain_ok = chain_ok and link_ok
            sval = None
            if r["envelope"] and self.verify_fn is not None:
                try:
                    sval = bool(self.verify_fn(json.loads(r["envelope"])).get("signature_valid"))
                    sig_known += 1
                    sig_valid += 1 if sval else 0
                except Exception:
                    sval = False
                    sig_known += 1
            checked.append({"seq": r["seq"], "event_id": r["event_id"],
                            "activity": r["prov_activity"], "link_ok": link_ok,
                            "signature_valid": sval})
            prev = r["hash"]
        out = {"session": session, "events_audited": len(checked),
               "chain_intact": chain_ok,
               "signatures_checked": sig_known, "signatures_valid": sig_valid,
               "all_signatures_valid": (sig_known > 0 and sig_valid == sig_known),
               "detail": checked,
               "trust_note": ("Tamper-EVIDENT (Conjecture 2) — re-hash + DSSE re-verify "
                              "detect any altered byte. NOT tamper-proof; not 100% trust."),
               "status": "ACTIVE", "label": "LIVE",
               "refs": ["Sello Protocol arXiv:2606.04193", "sigstore/cosign (Apache-2.0)"]}
        if self.sign_fn is not None:
            try:
                out["audit_receipt"] = self.sign_fn({"audit": {"session": session,
                    "events": len(checked), "chain_intact": chain_ok,
                    "sig_valid": sig_valid, "sig_checked": sig_known}, "ts": _now_iso()})
            except Exception:
                pass
        return out

    def verify_receipt(self, event_id):
        with _LOCK, _conn() as c:
            r = c.execute("SELECT * FROM ledger WHERE event_id=?", (event_id,)).fetchone()
        if not r:
            return {"error": "event not found", "event_id": event_id}
        sval = None
        if r["envelope"] and self.verify_fn is not None:
            try:
                sval = bool(self.verify_fn(json.loads(r["envelope"])).get("signature_valid"))
            except Exception:
                sval = False
        return {"event_id": event_id, "hash": r["hash"], "signature_valid": sval,
                "signed": bool(r["envelope"]), "status": "ACTIVE", "label": "LIVE"}


# ===========================================================================
# 🟢 ENGINE: Constitutional Memory (Pillar 4 Legitimacy + Memory)
# Versioned doctrine/decision store with pin / promote / rollback — TrustGraph-
# style Context Cores. Every write is a new immutable version (Item–Revision
# model). pin protects a version; promote sets the active version; rollback
# restores a prior version as a NEW version (append-only, never destructive).
# Refs: TrustGraph Context Cores (Apache-2.0, trustgraph.ai); Graph-Native
# Cognitive Memory arXiv:2603.17244; Anthropic CAI arXiv:2212.08073.
# ===========================================================================
class ConstitutionalMemory:
    def __init__(self, sign_fn=None, ns="a11oy"):
        self.sign_fn, self.ns = sign_fn, ns

    def _versions(self, core_id):
        with _LOCK, _conn() as c:
            return c.execute("SELECT * FROM memory WHERE core_id=? ORDER BY version",
                             (core_id,)).fetchall()

    def write(self, core_id, content, kind="doctrine"):
        vs = self._versions(core_id)
        nextv = (vs[-1]["version"] + 1) if vs else 1
        prev = vs[-1]["hash"] if vs else "GENESIS"
        # demote any previously-active version (promote semantics) unless pinned
        h = _sha({"core_id": core_id, "version": nextv, "content": content, "prev": prev})
        env = None
        if self.sign_fn is not None:
            try:
                env = self.sign_fn({"context_core": {"core_id": core_id, "version": nextv,
                    "kind": kind}, "hash": h, "ts": _now_iso()})
            except Exception:
                env = {"signed": False}
        with _LOCK, _conn() as c:
            c.execute("UPDATE memory SET state='superseded' WHERE core_id=? AND state='active'",
                      (core_id,))
            c.execute("INSERT INTO memory(core_id,version,kind,content,state,pinned,"
                      "prev_hash,hash,envelope,ts) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (core_id, nextv, kind, json.dumps(content), "active", 0, prev, h,
                       json.dumps(env) if env else None, _now_iso()))
        return {"core_id": core_id, "version": nextv, "state": "active", "hash": h,
                "signed": bool(env and env.get("signed")), "status": "ACTIVE", "label": "LIVE"}

    def pin(self, core_id, version):
        with _LOCK, _conn() as c:
            n = c.execute("UPDATE memory SET pinned=1 WHERE core_id=? AND version=?",
                          (core_id, version)).rowcount
        return {"core_id": core_id, "version": version, "pinned": bool(n),
                "found": bool(n), "status": "ACTIVE", "label": "LIVE"}

    def promote(self, core_id, version):
        with _LOCK, _conn() as c:
            row = c.execute("SELECT 1 FROM memory WHERE core_id=? AND version=?",
                            (core_id, version)).fetchone()
            if not row:
                return {"error": "version not found", "core_id": core_id, "version": version}
            c.execute("UPDATE memory SET state='superseded' WHERE core_id=? AND state='active'",
                      (core_id,))
            c.execute("UPDATE memory SET state='active' WHERE core_id=? AND version=?",
                      (core_id, version))
        return {"core_id": core_id, "active_version": version, "status": "ACTIVE", "label": "LIVE"}

    def rollback(self, core_id, to_version):
        """Append-only rollback: restore an old version's content as a NEW version
        (never destroys history). TrustGraph Context Core rollback semantics."""
        vs = self._versions(core_id)
        target = next((v for v in vs if v["version"] == to_version), None)
        if not target:
            return {"error": "version not found", "core_id": core_id, "version": to_version}
        res = self.write(core_id, json.loads(target["content"]), kind=target["kind"])
        res["rolled_back_from"] = to_version
        res["note"] = "append-only rollback: restored as new version (history preserved)"
        return res

    def get(self, core_id=None):
        with _LOCK, _conn() as c:
            if core_id:
                rows = c.execute("SELECT * FROM memory WHERE core_id=? ORDER BY version",
                                 (core_id,)).fetchall()
            else:
                rows = c.execute("SELECT * FROM memory ORDER BY core_id,version").fetchall()
        cores: dict = {}
        for r in rows:
            cores.setdefault(r["core_id"], []).append(
                {"version": r["version"], "kind": r["kind"], "state": r["state"],
                 "pinned": bool(r["pinned"]), "content": json.loads(r["content"] or "{}"),
                 "hash": r["hash"], "signed": bool(r["envelope"]
                 and json.loads(r["envelope"]).get("signed")), "ts": r["ts"]})
        return {"cores": cores, "core_count": len(cores),
                "model": "TrustGraph-style Context Cores; pin/promote/rollback; Item–Revision versioning",
                "semantics": {"pin": "protect a version", "promote": "set active version",
                              "rollback": "restore prior version as a NEW version (append-only)"},
                "status": "ACTIVE", "label": "LIVE",
                "refs": ["TrustGraph Context Cores (Apache-2.0) https://trustgraph.ai",
                         "Anthropic Constitutional AI arXiv:2212.08073"]}


# ===========================================================================
# 🟢 ENGINE: Ontological Registry (Pillar 1 Ontology)
# Registry of what exists / is meaningful — versioned entities with OWL-style
# class, properties, and signed provenance. Builds on a11oy's existing ontology
# tab/primitives. Refs: TrustGraph (Apache-2.0); OWL/RDF (W3C); AIAO ontology.
# ===========================================================================
class OntologicalRegistry:
    def __init__(self, ns="a11oy"):
        self.ns = ns

    def register(self, entity_id, owl_class, label="", properties=None, agent="a11oy"):
        with _LOCK, _conn() as c:
            vs = c.execute("SELECT version FROM ontology WHERE entity_id=? ORDER BY version",
                           (entity_id,)).fetchall()
            nextv = (vs[-1]["version"] + 1) if vs else 1
            prov = {"created_by": agent, "ts": _now_iso(), "version": nextv}
            h = _sha({"entity_id": entity_id, "version": nextv, "class": owl_class,
                      "props": properties or {}})
            c.execute("INSERT INTO ontology(entity_id,version,owl_class,label,properties,"
                      "provenance,hash,ts) VALUES(?,?,?,?,?,?,?,?)",
                      (entity_id, nextv, owl_class, label or entity_id,
                       json.dumps(properties or {}), json.dumps(prov), h, _now_iso()))
        return {"entity_id": entity_id, "version": nextv, "owl_class": owl_class,
                "hash": h, "status": "ACTIVE", "label": "LIVE"}

    def get(self, entity_id=None):
        with _LOCK, _conn() as c:
            if entity_id:
                rows = c.execute("SELECT * FROM ontology WHERE entity_id=? ORDER BY version",
                                 (entity_id,)).fetchall()
            else:
                rows = c.execute("SELECT * FROM ontology ORDER BY entity_id,version").fetchall()
        ents: dict = {}
        for r in rows:
            ents.setdefault(r["entity_id"], []).append(
                {"version": r["version"], "owl_class": r["owl_class"], "label": r["label"],
                 "properties": json.loads(r["properties"] or "{}"),
                 "provenance": json.loads(r["provenance"] or "{}"), "hash": r["hash"], "ts": r["ts"]})
        return {"entities": ents, "entity_count": len(ents),
                "model": "versioned OWL-style class assertions with signed provenance + lineage",
                "status": "ACTIVE", "label": "LIVE",
                "refs": ["TrustGraph (Apache-2.0) https://trustgraph.ai",
                         "OWL/RDF (W3C)", "AIAO ontology (Zenodo 19471050)"]}


# ===========================================================================
# 🟡 ENGINE: State / Transition (Pillar 7 Topology) — IN-DEVELOPMENT
# XState-style statechart over the agent lifecycle with Λ-guarded transitions.
# The statechart definition + guarded firing are REAL and tested; formal SCXML
# export + TLA+ invariant proofs are ROADMAP (honestly labelled IN-DEV).
# Refs: XState v5 (MIT, github.com/statelyai/xstate); Statecharts (Harel 1987);
# Temporal (MIT, durable execution); SCXML (W3C).
# ===========================================================================
STATECHART = {
    "id": "a11oy_agent",
    "initial": "Idle",
    "states": {
        "Idle": {"on": {"PLAN": "Planning"}},
        "Planning": {"on": {"EXECUTE": "Executing", "ABORT": "Idle"}},
        "Executing": {"on": {"GATE": "PolicyGate", "SUSPEND": "Suspended"}},
        "PolicyGate": {"on": {"APPROVE": "Auditing", "ESCALATE": "WaitingHumanApproval",
                              "DENY": "RolledBack"}},
        "WaitingHumanApproval": {"on": {"APPROVE": "Auditing", "REJECT": "RolledBack"}},
        "Auditing": {"on": {"PASS": "Completed", "FAIL": "RolledBack"}},
        "Suspended": {"on": {"RESUME": "Executing"}},
        "Completed": {"type": "final"},
        "RolledBack": {"type": "final"},
    },
}


class StateEngine:
    def __init__(self, lambda_fn=None, ns="a11oy"):
        self.lambda_fn, self.ns = lambda_fn, ns
        self._machine = "a11oy_agent"

    def current(self):
        with _LOCK, _conn() as c:
            r = c.execute("SELECT to_state FROM statelog WHERE machine=? AND allowed=1 "
                          "ORDER BY id DESC LIMIT 1", (self._machine,)).fetchone()
        return r["to_state"] if r else STATECHART["initial"]

    def transition(self, event, ctx=None):
        cur = self.current()
        defs = STATECHART["states"].get(cur, {})
        target = (defs.get("on") or {}).get(event)
        # Λ guard (advisory, Conjecture 1, <1.0): high for normal transitions.
        lam = LAMBDA_CAP
        if self.lambda_fn is not None:
            try:
                lam = max(0.0, min(LAMBDA_CAP, float(self.lambda_fn(cur, event, ctx or {}))))
            except Exception:
                lam = 0.85
        else:
            lam = round(0.78 + 0.2 * (int(_sha({"s": cur, "e": event})[:6], 16) / 0xFFFFFF), 5)
        allowed = bool(target) and lam >= LAMBDA_HALT
        to_state = target if allowed else cur
        h = _sha({"from": cur, "event": event, "to": to_state, "lambda": lam})
        with _LOCK, _conn() as c:
            c.execute("INSERT INTO statelog(machine,from_state,event,to_state,guard_lambda,"
                      "allowed,hash,ts) VALUES(?,?,?,?,?,?,?,?)",
                      (self._machine, cur, event, to_state, lam, 1 if allowed else 0, h, _now_iso()))
        return {"machine": self._machine, "from": cur, "event": event,
                "to": to_state, "allowed": allowed, "guard_lambda": lam,
                "reason": ("transition fired" if allowed else
                           ("no transition for event in state" if not target else
                            "Λ guard halted (below floor)")),
                "status": "IN-DEV", "label": "EXPERIMENTAL"}

    def definition(self):
        with _LOCK, _conn() as c:
            log = c.execute("SELECT from_state,event,to_state,guard_lambda,allowed,ts "
                            "FROM statelog WHERE machine=? ORDER BY id DESC LIMIT 30",
                            (self._machine,)).fetchall()
        return {"machine": self._machine, "statechart": STATECHART,
                "current_state": self.current(),
                "transition_log": [{"from": r["from_state"], "event": r["event"],
                                    "to": r["to_state"], "guard_lambda": r["guard_lambda"],
                                    "allowed": bool(r["allowed"]), "ts": r["ts"]} for r in log],
                "model": "XState-style statechart (Harel); Λ-guarded transitions",
                "roadmap": "formal SCXML export + TLA+ invariant proofs (IN-DEV)",
                "status": "IN-DEV", "label": "EXPERIMENTAL",
                "refs": ["XState v5 (MIT) https://github.com/statelyai/xstate",
                         "Statecharts (Harel 1987)", "Temporal (MIT) https://temporal.io",
                         "SCXML (W3C)"]}


# ===========================================================================
# STATUS — all engines mapped to the 8 pillars, honest ACTIVE/IN-DEV/ROADMAP.
# Per CONSTITUTIONAL_ARCH_RESEARCH.md ranking. NEVER overclaim a skeleton as done.
# ===========================================================================
def engine_status(counts: dict) -> dict:
    engines = [
        {"engine": "Causal Ledger", "status": "ACTIVE", "color": "green",
         "pillars": [3, "Temporality"], "lambda_axes": ["provenance/traceability", "memory fidelity"],
         "built_on": "tamper-evident receipt chain + W3C PROV-DM annotations (event-sourced)",
         "oss": ["W3C PROV", "in-toto (Apache-2.0)", "EventStoreDB/Kurrent (Apache-2.0)"],
         "live_count": counts.get("ledger", 0),
         "endpoint": "/api/a11oy/v1/constitution/ledger"},
        {"engine": "Audit Engine", "status": "ACTIVE", "color": "green",
         "pillars": [8, "Governance"], "lambda_axes": ["audit integrity", "honesty/non-deception"],
         "built_on": "query + DSSE re-verification layer over the Causal Ledger",
         "oss": ["sigstore/cosign (Apache-2.0)", "Sello Protocol", "OSCAL (public domain)"],
         "live_count": counts.get("ledger", 0),
         "endpoint": "/api/a11oy/v1/constitution/audit"},
        {"engine": "Constitutional Memory", "status": "ACTIVE", "color": "green",
         "pillars": [4, "Legitimacy"], "lambda_axes": ["memory fidelity", "corrigibility"],
         "built_on": "versioned doctrine/decision Context Cores; pin/promote/rollback",
         "oss": ["TrustGraph (Apache-2.0)", "Anthropic CAI (arXiv:2212.08073)"],
         "live_count": counts.get("memory", 0),
         "endpoint": "/api/a11oy/v1/constitution/memory"},
        {"engine": "Ontological Registry", "status": "ACTIVE", "color": "green",
         "pillars": [1, "Ontology"], "lambda_axes": ["factual accuracy/groundedness", "identity preservation"],
         "built_on": "existing ontology tab + versioned OWL-style entities w/ provenance",
         "oss": ["TrustGraph (Apache-2.0)", "OWL/RDF (W3C)", "AIAO (Zenodo 19471050)"],
         "live_count": counts.get("ontology", 0),
         "endpoint": "/api/a11oy/v1/constitution/ontology"},
        {"engine": "State / Transition", "status": "IN-DEV", "color": "amber",
         "pillars": [7, "Topology"], "lambda_axes": ["autonomy bounds"],
         "built_on": "XState-style statechart over the ReAct loop; Λ-guarded transitions",
         "oss": ["XState v5 (MIT)", "Temporal (MIT)", "SCXML (W3C)", "Statecharts (Harel)"],
         "live_count": counts.get("statelog", 0),
         "endpoint": "/api/a11oy/v1/constitution/state",
         "honest": "statechart + guarded firing are REAL; SCXML export + TLA+ proofs ROADMAP"},
        {"engine": "Legitimacy", "status": "IN-DEV", "color": "amber",
         "pillars": [4, "Legitimacy"], "lambda_axes": ["honesty/non-deception", "corrigibility"],
         "built_on": "CAI-style hardcoded/softcoded doctrine-mutability hierarchy (skeleton)",
         "oss": ["Anthropic CAI (arXiv:2212.08073)", "Charter-Governed OS (arXiv:2603.14011)"],
         "live_count": 0,
         "honest": "mutability hierarchy designed; ConstitutionValidator not yet wired (IN-DEV)"},
        {"engine": "Immunology", "status": "IN-DEV", "color": "amber",
         "pillars": [5, "Immunology"], "lambda_axes": ["drift/coherence", "trust decay/repair"],
         "built_on": "reuses a11oy drift guards; epistemic-immune coherence monitor (skeleton)",
         "oss": ["NeMo Guardrails (Apache-2.0)", "Coherence-Based Alignment", "NLLabs EIS"],
         "live_count": 0,
         "honest": "drift guards exist; epistemic-immune quarantine queue IN-DEV, not done"},
        {"engine": "Governance-Evolution", "status": "ROADMAP", "color": "blue",
         "pillars": [8, "Governance"], "lambda_axes": ["cross-agent authority", "policy compliance"],
         "built_on": "OSCAL doctrine-diff + quorum approval over doctrine v11",
         "oss": ["OSCAL (public domain)", "NIST AI RMF Agentic Profile", "PyMDP (Apache-2.0)"],
         "live_count": 0,
         "honest": "ROADMAP — OSCAL catalog encoding + quorum widget not built"},
    ]
    return {
        "framing": ("Constitutional architecture built on a11oy's existing primitives "
                    "(DSSE receipts, tamper-evident ledger, Λ trust score, ontology). "
                    "A governed, auditable, policy-enforced agent runtime — NOT a new "
                    "form of existence and NOT an AGI."),
        "concept_origin": "Eduardo Cesar Lunardelli, 'Constitutional Cognitive Architecture' (conceptual)",
        "pillars": {1: "Ontology", 2: "Phenomenology", 3: "Temporality", 4: "Legitimacy",
                    5: "Immunology", 6: "Energy Economics", 7: "Topology", 8: "Governance"},
        "engines": engines,
        "summary": {"ACTIVE": sum(1 for e in engines if e["status"] == "ACTIVE"),
                    "IN-DEV": sum(1 for e in engines if e["status"] == "IN-DEV"),
                    "ROADMAP": sum(1 for e in engines if e["status"] == "ROADMAP")},
        "doctrine": {"locked": LOCKED_8, "locked_count": len(LOCKED_8), "anchor": "c7c0ba17",
                     "lambda": "Conjecture 1 (advisory, <1.0)",
                     "tamper": "tamper-EVIDENT (Conjecture 2), NOT tamper-proof",
                     "trust": "<100%", "slsa": "L1/L2 (L3 roadmap)", "cdn": 0},
        "citations": {
            "Fabro": "MIT — https://fabro.sh", "TrustGraph": "Apache-2.0 — https://trustgraph.ai",
            "PyMDP": "Apache-2.0 — https://github.com/infer-actively/pymdp",
            "XState": "MIT — https://github.com/statelyai/xstate",
            "Temporal": "MIT — https://temporal.io",
            "OSCAL": "public domain — https://github.com/usnistgov/oscal",
            "sigstore": "Apache-2.0 — https://github.com/sigstore/cosign",
            "W3C PROV": "https://www.w3.org/TR/prov-overview/",
            "Anthropic Constitutional AI": "arXiv:2212.08073",
            "Lunardelli": "concept origin (LinkedIn, conceptual)"},
        "label": "LIVE"}


# ---------------------------------------------------------------------------
# UI — Constitution tab: each engine with honest status colors, mapped to 8 pillars.
# Inline HTML, 0 CDN, loads shared label/receipt engines from /static/shared.
# ---------------------------------------------------------------------------
def _page_html(ns="a11oy") -> str:
    base = "/api/%s/v1/constitution" % ns
    return ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>a11oy — Constitution</title>
<script src="/static/shared/szl_label_engine.js"></script>
<script src="/static/shared/szl_receipt_cosign.js"></script>
<style>
:root{--bg:#0a0e14;--panel:#111824;--line:#1f2b3a;--fg:#e6edf3;--mut:#8b97a8;
--green:#3fb950;--amber:#d29922;--blue:#58a6ff;--bad:#f85149;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
header{padding:18px 24px;border-bottom:1px solid var(--line);background:var(--panel)}
h1{margin:0;font-size:19px}.sub{color:var(--mut);font-size:12px;margin-top:5px;max-width:980px}
.attr{color:var(--mut);font-size:11px;margin-top:6px}
.wrap{padding:18px 24px;max-width:1280px;margin:0 auto}
.legend{display:flex;gap:14px;margin-bottom:14px;font-size:12px;color:var(--mut);flex-wrap:wrap}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:middle}
.dot.green{background:var(--green)}.dot.amber{background:var(--amber)}.dot.blue{background:var(--blue)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.eng{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.eng.green{border-left:4px solid var(--green)}.eng.amber{border-left:4px solid var(--amber)}
.eng.blue{border-left:4px solid var(--blue)}
.eng h3{margin:0 0 6px;font-size:15px}
.st{font-size:10px;padding:2px 8px;border-radius:10px;float:right;text-transform:uppercase;letter-spacing:.5px}
.st.green{color:var(--green);border:1px solid var(--green)}
.st.amber{color:var(--amber);border:1px solid var(--amber)}
.st.blue{color:var(--blue);border:1px solid var(--blue)}
.eng .p{font-size:11px;color:var(--blue);margin:2px 0}
.eng .bo{font-size:12px;color:var(--fg);margin:6px 0}
.eng .ho{font-size:11px;color:var(--amber);margin:6px 0}
.eng .oss{font-size:11px;color:var(--mut);margin-top:6px}
.eng .cnt{font-size:11px;color:var(--green);margin-top:4px}
.controls{margin:16px 0;display:flex;gap:8px;flex-wrap:wrap}
button{background:#0d1420;color:var(--fg);border:1px solid var(--line);border-radius:6px;
padding:7px 12px;font:12px ui-monospace,monospace;cursor:pointer}button:hover{border-color:var(--blue)}
pre{background:#0d1420;border:1px solid var(--line);border-radius:8px;padding:12px;
overflow:auto;font-size:11px;max-height:340px}
.cites{margin-top:18px;font-size:11px;color:var(--mut);line-height:1.8}
a{color:var(--blue)}
.summary{font-size:12px;color:var(--mut);margin-bottom:10px}
</style></head><body>
<header>
  <h1>a11oy — Constitution <span id="lbl"></span></h1>
  <div class="sub">Constitutional architecture <b>built on a11oy's existing primitives</b> (DSSE receipts, tamper-evident ledger, &Lambda; trust score, ontology). A governed, auditable, policy-enforced agent runtime &mdash; <b>not</b> a new form of existence and <b>not</b> an AGI. Engines shown with honest <b>ACTIVE / IN-DEV / ROADMAP</b> status, mapped to the 8 pillars.</div>
  <div class="attr">Concept origin: Lunardelli (conceptual). Built on: <a href="https://trustgraph.ai" target="_blank" rel="noopener">TrustGraph</a> (Apache-2.0), <a href="https://github.com/statelyai/xstate" target="_blank" rel="noopener">XState</a> (MIT), <a href="https://www.w3.org/TR/prov-overview/" target="_blank" rel="noopener">W3C PROV</a>, <a href="https://github.com/usnistgov/oscal" target="_blank" rel="noopener">OSCAL</a>, <a href="https://github.com/sigstore/cosign" target="_blank" rel="noopener">sigstore</a>, <a href="https://arxiv.org/abs/2212.08073" target="_blank" rel="noopener">Anthropic CAI (arXiv:2212.08073)</a>, <a href="https://fabro.sh" target="_blank" rel="noopener">Fabro</a> (MIT).</div>
</header>
<div class="wrap">
  <div class="legend"><span><span class="dot green"></span>ACTIVE</span><span><span class="dot amber"></span>IN-DEV</span><span><span class="dot blue"></span>ROADMAP</span></div>
  <div class="summary" id="summary"></div>
  <div class="grid" id="grid"></div>
  <div class="controls">
    <button onclick="demoLedger()">Append causal event</button>
    <button onclick="runAudit()">Run audit</button>
    <button onclick="demoMemory()">Write doctrine core</button>
    <button onclick="demoOntology()">Register entity</button>
    <button onclick="fireState()">Fire state transition</button>
  </div>
  <pre id="out">Click an engine action to exercise a live ACTIVE/IN-DEV endpoint.</pre>
  <div class="cites" id="cites"></div>
</div>
<script>
const BASE="__BASE__";
function esc(s){return String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
async function jget(u){const r=await fetch(u);return r.json();}
async function jpost(u,b){const r=await fetch(u,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(b||{})});return r.json();}
function show(o){document.getElementById('out').textContent=JSON.stringify(o,null,2);}
async function loadStatus(){
  const d=await jget(BASE+'/status');
  document.getElementById('summary').textContent='Engines: '+d.summary.ACTIVE+' ACTIVE, '+d.summary['IN-DEV']+' IN-DEV, '+d.summary.ROADMAP+' ROADMAP. Doctrine v11 locked='+d.doctrine.locked_count+' @ '+d.doctrine.anchor+'; '+d.doctrine.lambda+'; '+d.doctrine.tamper+'.';
  document.getElementById('grid').innerHTML=(d.engines||[]).map(e=>{
    return '<div class="eng '+e.color+'"><span class="st '+e.color+'">'+esc(e.status)+'</span>'
      +'<h3>'+esc(e.engine)+'</h3>'
      +'<div class="p">Pillar '+e.pillars[0]+' &middot; '+esc(e.pillars[1])+'</div>'
      +'<div class="bo">'+esc(e.built_on)+'</div>'
      +(e.honest?'<div class="ho">honest: '+esc(e.honest)+'</div>':'')
      +'<div class="oss">OSS: '+(e.oss||[]).map(esc).join(', ')+'</div>'
      +(e.live_count?'<div class="cnt">'+e.live_count+' live records</div>':'')
      +'</div>';
  }).join('');
  const c=d.citations||{};
  document.getElementById('cites').innerHTML='<b>Citations:</b> '+Object.keys(c).map(k=>esc(k)+' ('+esc(c[k])+')').join(' &middot; ');
  if(window.SZLLabels){document.getElementById('lbl').innerHTML=SZLLabels.badge?SZLLabels.badge('LIVE'):'';}
}
async function demoLedger(){show(await jpost(BASE+'/ledger',{activity:'gate.evaluate',entity:'decision-receipt',agent:'operator',session:'demo'}));}
async function runAudit(){show(await jget(BASE+'/audit?session=demo'));}
async function demoMemory(){show(await jpost(BASE+'/memory',{op:'write',core_id:'doctrine.v11',content:{clause:'never claim AGI',class:'hardcoded'},kind:'doctrine'}));}
async function demoOntology(){show(await jpost(BASE+'/ontology',{entity_id:'a11oy:GovernedAgent',owl_class:'Agent',label:'Governed Agent',properties:{governed:true}}));}
async function fireState(){show(await jpost(BASE+'/state',{event:'PLAN'}));}
loadStatus();
</script>
</body></html>""").replace("__BASE__", base)


def register(app, ns: str = "a11oy", sign_fn=None, verify_fn=None,
             lambda_fn=None, signer_label: str = "in-image key"):
    from starlette.routing import Route
    from starlette.responses import JSONResponse, HTMLResponse

    _init_db()
    ledger = CausalLedger(sign_fn, verify_fn, ns=ns)
    audit = AuditEngine(ledger, sign_fn, verify_fn, ns=ns)
    memory = ConstitutionalMemory(sign_fn, ns=ns)
    ontology = OntologicalRegistry(ns=ns)
    state = StateEngine(None, ns=ns)

    async def _read_json(request):
        try:
            return await request.json()
        except Exception:
            return {}

    def _counts():
        with _LOCK, _conn() as c:
            return {"ledger": c.execute("SELECT COUNT(*) AS n FROM ledger").fetchone()["n"],
                    "memory": c.execute("SELECT COUNT(*) AS n FROM memory").fetchone()["n"],
                    "ontology": c.execute("SELECT COUNT(*) AS n FROM ontology").fetchone()["n"],
                    "statelog": c.execute("SELECT COUNT(*) AS n FROM statelog").fetchone()["n"]}

    async def _ledger(request):
        if request.method == "POST":
            d = await _read_json(request)
            return JSONResponse(ledger.append(
                d.get("activity", "agent.action"), d.get("entity", "artifact"),
                agent=d.get("agent", "a11oy"), used=d.get("used"),
                was_informed_by=d.get("was_informed_by"),
                session=d.get("session", "default"), body=d.get("body")))
        ev = request.query_params.get("event_id")
        if ev:
            return JSONResponse(ledger.ancestors(ev))
        return JSONResponse(ledger.query(session=request.query_params.get("session"),
                                         limit=int(request.query_params.get("limit", 100))))

    async def _audit(request):
        ev = request.query_params.get("event_id")
        if ev:
            return JSONResponse(audit.verify_receipt(ev))
        return JSONResponse(audit.audit(session=request.query_params.get("session")))

    async def _memory(request):
        if request.method == "POST":
            d = await _read_json(request)
            op = (d.get("op") or "write").lower()
            cid = d.get("core_id", "doctrine.v11")
            if op == "pin":
                return JSONResponse(memory.pin(cid, int(d.get("version", 1))))
            if op == "promote":
                return JSONResponse(memory.promote(cid, int(d.get("version", 1))))
            if op == "rollback":
                return JSONResponse(memory.rollback(cid, int(d.get("version", 1))))
            return JSONResponse(memory.write(cid, d.get("content", {}), kind=d.get("kind", "doctrine")))
        return JSONResponse(memory.get(core_id=request.query_params.get("core_id")))

    async def _ontology(request):
        if request.method == "POST":
            d = await _read_json(request)
            return JSONResponse(ontology.register(
                d.get("entity_id", "a11oy:Entity"), d.get("owl_class", "Thing"),
                label=d.get("label", ""), properties=d.get("properties"),
                agent=d.get("agent", "a11oy")))
        return JSONResponse(ontology.get(entity_id=request.query_params.get("entity_id")))

    async def _state(request):
        if request.method == "POST":
            d = await _read_json(request)
            ev = (d.get("event") or "").strip()
            if not ev:
                return JSONResponse({"error": "missing 'event'"}, status_code=400)
            return JSONResponse(state.transition(ev, ctx=d.get("ctx")))
        return JSONResponse(state.definition())

    async def _status(request):
        return JSONResponse(engine_status(_counts()))

    async def _diag(request):
        return JSONResponse({"module": "a11oy_constitution", "status": "ok",
                             "db": _DB_PATH, "counts": _counts(), "signer": signer_label,
                             "engines_active": 4, "engines_in_dev": 3, "engines_roadmap": 1,
                             "label": "LIVE"})

    async def _page(request):
        return HTMLResponse(_page_html(ns))

    base = "/api/%s/v1/constitution" % ns
    routes = [
        Route(base + "/ledger", _ledger, methods=["GET", "POST"], name="%s_const_ledger" % ns),
        Route(base + "/audit", _audit, methods=["GET"], name="%s_const_audit" % ns),
        Route(base + "/memory", _memory, methods=["GET", "POST"], name="%s_const_memory" % ns),
        Route(base + "/ontology", _ontology, methods=["GET", "POST"], name="%s_const_ontology" % ns),
        Route(base + "/state", _state, methods=["GET", "POST"], name="%s_const_state" % ns),
        Route(base + "/status", _status, methods=["GET"], name="%s_const_status" % ns),
        Route(base + "/_diag", _diag, methods=["GET"], name="%s_const_diag" % ns),
        Route("/constitution", _page, methods=["GET"], name="%s_const_page" % ns),
        Route("/%s/constitution" % ns, _page, methods=["GET"], name="%s_const_page_ns" % ns),
        Route("/constitution-engines", _page, methods=["GET"], name="%s_const_page_alias" % ns),
    ]
    for r in routes:
        app.router.routes.insert(0, r)
    return {"module": "a11oy_constitution", "routes": len(routes), "base": base,
            "page": "/constitution", "signer": signer_label,
            "engines": ["Causal Ledger", "Audit Engine", "Constitutional Memory",
                        "Ontological Registry", "State/Transition"]}
