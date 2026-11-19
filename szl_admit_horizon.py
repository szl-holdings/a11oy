#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""szl_admit_horizon.py - when, and through which evidence, an admitted claim lapses.

Read-only analysis over the locked admit rule in ``szl_verify_nine``::

    G = exp(sum w_i ln x_i / sum w_i)
    admit <=> G >= tau  and  min(x) > 0

Each claim is the weighted geometric mean of its children (evidence or other
claims). In log space that is a weighted average, so across a DAG every
claim's log-score is linear in the evidence log-scores::

    ln s_n = sum_j A[n, j] ln x_j        A[n, j] = sum over paths of prod(w / W)

which gives exact closed forms for claim n and evidence j:

    margin       m_n  = ln s_n - ln tau_n
    admit floor  x_j* = x_j * exp(-m_n / A[n, j])            all else fixed
    horizon      t_n* = min(m_n / sum_j A[n, j] lambda_j, min_j T_j)
    deficit      -ln s_n = sum_j A[n, j] * (-ln x_j)         exact attribution

lambda_j = ln 2 / half_life_s is a decay rate the evidence itself declares;
T_j = expires_in_s is a declared hard expiry, after which x_j = 0 and
min(x) > 0 fails. Rates are never invented: evidence that declares neither
and is not declared ``static`` makes every horizon depending on it UNKNOWN,
and the declared-only value is reported only as an upper bound.

Claims are gated, deny-by-default: a claim admits only if its own locked rule
holds and every child claim admits (SACM: an undefeated conclusion needs
undefeated premises). Its horizon is the earliest lapse along that chain and
each admit floor is the strictest one along it. Withdrawing evidence means a
veto (score 0), never removal and renormalisation, which could raise G.

Horizons are projections from declared rates and are labelled MODELED. This
module is a read path: it signs nothing and mints no receipt. ADMITTED means
the locked rule holds; it is not P(all claims hold), since G >= prod(x).

Prior art, cited not claimed: the weighted geometric mean of probabilities is
the logarithmic opinion pool (Genest & Zidek 1986, Statistical Science 1(1));
its input sensitivity is that of the weighted product model (Triantaphyllou &
Sanchez 1997, Decision Sciences 28(1)); the lapse time is the series-system
reliability crossing time with rate sum(w_i lambda_i) / W; dependency labels
follow truth maintenance (Doyle 1979; de Kleer 1986); for a model additive in
log space the per-evidence deficit terms are its exact Shapley attribution
(Lundberg & Lee 2017). The SZL part is the binding: lapse forecasts, admit
floors and counterfactual loss of support computed on the locked admit
contract, failing closed when freshness is undeclared.
"""

import hashlib
import json
import math
from typing import Any, Mapping

import szl_verify_nine as nine

SCHEMA = "szl.admit_horizon/v1"
MODELED = "MODELED"
UNKNOWN = "UNKNOWN"
ALREADY_DENIED = "ALREADY_DENIED"
NO_DECLARED_LAPSE = "NO_DECLARED_LAPSE"

_EVIDENCE_FIELDS = {"score", "half_life_s", "expires_in_s", "static"}
_CLAIM_FIELDS = {"children", "tau"}
_LN2 = math.log(2.0)


class HorizonContractError(ValueError):
    """Input that cannot be analysed honestly. Nothing is computed for it."""


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise HorizonContractError(f"{name} must be a finite number")
    return float(value)


def _parse(graph: Any) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if not isinstance(graph, Mapping):
        raise HorizonContractError("graph must be an object")
    if set(graph) - {"evidence", "claims"}:
        raise HorizonContractError(f"unknown graph field(s) {sorted(set(graph) - {'evidence', 'claims'})}")
    evidence, claims = graph.get("evidence"), graph.get("claims")
    if not isinstance(evidence, Mapping) or not evidence:
        raise HorizonContractError("evidence must be a non-empty object")
    if not isinstance(claims, Mapping) or not claims:
        raise HorizonContractError("claims must be a non-empty object")

    ev: dict[str, dict[str, Any]] = {}
    for eid, spec in evidence.items():
        if not isinstance(eid, str) or not eid or not isinstance(spec, Mapping):
            raise HorizonContractError("each evidence entry needs a non-empty id and an object")
        if set(spec) - _EVIDENCE_FIELDS:
            raise HorizonContractError(f"evidence {eid}: unknown field(s) {sorted(set(spec) - _EVIDENCE_FIELDS)}")
        score = _number(spec.get("score"), f"evidence {eid}: score")
        if not 0.0 <= score <= 1.0:
            raise HorizonContractError(f"evidence {eid}: score must be in [0, 1]")
        static = spec.get("static", False)
        if not isinstance(static, bool):
            raise HorizonContractError(f"evidence {eid}: static must be a boolean")
        half, expires = spec.get("half_life_s"), spec.get("expires_in_s")
        if half is not None:
            half = _number(half, f"evidence {eid}: half_life_s")
            if half <= 0:
                raise HorizonContractError(f"evidence {eid}: half_life_s must be > 0")
        if expires is not None:
            expires = _number(expires, f"evidence {eid}: expires_in_s")
            if expires < 0:
                raise HorizonContractError(f"evidence {eid}: expires_in_s must be >= 0")
        if static and (half is not None or expires is not None):
            raise HorizonContractError(f"evidence {eid}: static evidence cannot declare decay or expiry")
        ev[eid] = {
            "score": score,
            "rate": _LN2 / half if half is not None else 0.0,
            "expires": expires,
            "declared": static or half is not None or expires is not None,
        }

    cl: dict[str, dict[str, Any]] = {}
    for cid, spec in claims.items():
        if not isinstance(cid, str) or not cid or not isinstance(spec, Mapping):
            raise HorizonContractError("each claim needs a non-empty id and an object")
        if cid in ev:
            raise HorizonContractError(f"id {cid} is both evidence and a claim")
        if set(spec) - _CLAIM_FIELDS:
            raise HorizonContractError(f"claim {cid}: unknown field(s) {sorted(set(spec) - _CLAIM_FIELDS)}")
        tau = _number(spec.get("tau", nine.POLICY_TAU), f"claim {cid}: tau")
        if not 0.0 < tau <= 1.0:
            raise HorizonContractError(f"claim {cid}: tau must be in (0, 1]")
        children = spec.get("children")
        if not isinstance(children, Mapping) or not children:
            raise HorizonContractError(f"claim {cid}: children must be a non-empty object")
        weights = {}
        for child, weight in children.items():
            weight = _number(weight, f"claim {cid}: weight of {child}")
            if weight <= 0:
                raise HorizonContractError(f"claim {cid}: weight of {child} must be > 0")
            weights[child] = weight
        cl[cid] = {"children": weights, "tau": tau}

    for cid, claim in cl.items():
        for child in claim["children"]:
            if child not in ev and child not in cl:
                raise HorizonContractError(f"claim {cid}: unknown child {child}")
    return ev, cl


def _coefficients(ev: dict[str, Any], cl: dict[str, Any]) -> dict[str, dict[str, float]]:
    coef: dict[str, dict[str, float]] = {}
    active: set[str] = set()

    def visit(node: str) -> dict[str, float]:
        if node in ev:
            return {node: 1.0}
        if node in coef:
            return coef[node]
        if node in active:
            raise HorizonContractError(f"cycle through claim {node}")
        active.add(node)
        children = cl[node]["children"]
        total = sum(children.values())
        out: dict[str, float] = {}
        for child, weight in children.items():
            for leaf, a in visit(child).items():
                out[leaf] = out.get(leaf, 0.0) + (weight / total) * a
        active.discard(node)
        coef[node] = out
        return out

    try:
        for node in cl:
            visit(node)
    except RecursionError:
        raise HorizonContractError("claim graph is too deep to analyse") from None
    return coef


def _scores(ev: dict[str, Any], cl: dict[str, Any]) -> dict[str, float]:
    # Independent of the linear form: the direct recursive locked GM.
    memo = {eid: spec["score"] for eid, spec in ev.items()}

    def score(node: str) -> float:
        if node not in memo:
            children = cl[node]["children"]
            memo[node] = nine.weighted_gm([score(c) for c in children], list(children.values()))
        return memo[node]

    for node in cl:
        score(node)
    return memo


def _horizon(margin: float, deps: dict[str, float], ev: dict[str, Any]) -> dict[str, Any]:
    rate = sum(a * ev[j]["rate"] for j, a in deps.items())
    t_decay = margin / rate if rate > 0 else math.inf
    expiries = sorted((ev[j]["expires"], j) for j in deps if ev[j]["expires"] is not None)
    t_expiry, first_expiry = expiries[0] if expiries else (math.inf, None)
    seconds = min(t_decay, t_expiry)
    undeclared = sorted(j for j in deps if not ev[j]["declared"])

    if math.isinf(seconds):
        cause, drivers = None, []
    elif t_expiry <= t_decay:
        cause, drivers = "expiry", [first_expiry]
    else:
        cause = "decay"
        drivers = sorted((j for j in deps if ev[j]["rate"] > 0), key=lambda j: (-deps[j] * ev[j]["rate"], j))

    out: dict[str, Any] = {"cause": cause, "evidence": drivers}
    if undeclared:
        out.update(state=UNKNOWN, seconds=None, undeclared=undeclared,
                   upper_bound_s=None if math.isinf(seconds) else round(seconds, 3))
    elif math.isinf(seconds):
        out.update(state=NO_DECLARED_LAPSE, seconds=None)
    else:
        out.update(state=MODELED, seconds=round(seconds, 3))
    return out


def _earliest(own: dict[str, Any], reports: dict[str, dict[str, Any]],
              child_claims: list[str]) -> dict[str, Any]:
    # A gated claim lapses when it or any child claim it relies on lapses.
    # Child dependencies are a subset of the parent's, so UNKNOWN propagates.
    def bound(h: dict[str, Any]) -> float:
        value = h["seconds"] if h["state"] == MODELED else h.get("upper_bound_s")
        return math.inf if value is None else value

    best, via = own, None
    for child in child_claims:
        h = reports[child]["horizon"]
        if bound(h) < bound(best):
            best, via = h, child
    if via is None:
        return own
    out = {**own, "cause": f"child_claim:{via}", "evidence": best["evidence"]}
    key = "seconds" if own["state"] == MODELED else "upper_bound_s"
    out[key] = bound(best)
    if own["state"] == NO_DECLARED_LAPSE:  # only reachable if a child is bounded
        out.update(state=MODELED, seconds=bound(best))
    return out


def _claim_report(node: str, ev: dict[str, Any], cl: dict[str, Any],
                  coef: dict[str, dict[str, float]], scores: dict[str, float],
                  reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if node in reports:
        return reports[node]
    claim = cl[node]
    children = claim["children"]
    tau = claim["tau"]
    child_claims = sorted(c for c in children if c in cl)
    for child in child_claims:
        _claim_report(child, ev, cl, coef, scores, reports)
    own = nine.admit([scores[c] for c in children], tau, list(children.values()))
    denied_children = [c for c in child_claims if not reports[c]["admit"]]
    admitted = own["admit"] and not denied_children
    deps = coef[node]
    s = scores[node]
    report: dict[str, Any] = {
        "claim": node, "score": round(s, 6), "tau": tau,
        "status": nine.ADMITTED if admitted else nine.DENY, "admit": admitted, "dang": own["dang"],
        "gate": {"own_rule_admits": own["admit"], "denied_child_claims": denied_children},
        "depends_on": sorted(deps),
    }
    reports[node] = report
    if s == 0.0:
        zero = sorted(j for j in deps if ev[j]["score"] == 0.0)
        report.update(margin=None, deficit=None, floors=[],
                      horizon={"state": ALREADY_DENIED, "seconds": 0.0, "cause": "zero_evidence", "evidence": zero})
        return report

    linear = sum(a * math.log(ev[j]["score"]) for j, a in deps.items())
    if abs(linear - math.log(s)) > 1e-9:
        raise AssertionError(f"claim {node}: linear form disagrees with the direct geometric mean")

    margin = math.log(s) - math.log(tau)
    if own["admit"] and margin < 0:
        margin = 0.0  # boundary rounding: the locked verdict is authoritative
    report["margin"] = round(margin, 6)

    terms = {j: a * -math.log(ev[j]["score"]) for j, a in deps.items()}
    total = sum(terms.values())
    report["deficit"] = {
        "neg_ln_score": round(total, 6),
        "terms": [
            {"evidence": j, "coefficient": round(deps[j], 6), "neg_ln": round(t, 6),
             "share": round(t / total, 6) if total > 0 else 0.0}
            for j, t in sorted(terms.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    }

    floors = []
    for j in sorted(deps, key=lambda j: (-deps[j], j)):
        x = ev[j]["score"]
        log_target = math.log(x) - margin / deps[j]
        if admitted:
            # The strictest floor along the gated chain binds.
            floor, binding = math.exp(log_target), node
            for child in child_claims:
                for row in reports[child]["floors"]:
                    if row["evidence"] == j and row["admit_floor_exact"] > floor:
                        floor, binding = row["admit_floor_exact"], row["binding_claim"]
            floors.append({"evidence": j, "score": x, "admit_floor": round(floor, 6),
                           "admit_floor_exact": floor, "binding_claim": binding,
                           "relative_drop_allowed": round(1.0 - floor / x, 6)})
        else:
            feasible = log_target <= 0.0
            floors.append({"evidence": j, "score": x, "repair_scope": "own_rule_only",
                           "single_input_repair_feasible": feasible,
                           "repair_needs": round(math.exp(log_target), 6) if feasible else None})
    report["floors"] = floors

    if admitted:
        report["horizon"] = _earliest(_horizon(margin, deps, ev), reports, child_claims)
    else:
        cause = "below_tau" if not own["admit"] else "child_claim_denied"
        report["horizon"] = {"state": ALREADY_DENIED, "seconds": 0.0, "cause": cause, "evidence": denied_children}
    return report


def _digest(graph: Mapping[str, Any]) -> str:
    canonical = json.dumps(graph, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def analyze(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Score, floors and lapse horizon for every claim in an evidence DAG."""
    ev, cl = _parse(graph)
    coef = _coefficients(ev, cl)
    scores = _scores(ev, cl)
    reports: dict[str, dict[str, Any]] = {}
    for node in sorted(cl):
        _claim_report(node, ev, cl, coef, scores, reports)
    return {
        "schema": SCHEMA,
        "admit_rule": "weighted_geometric_mean (szl.model_admit_contract/v1), gated on child claims",
        "label": MODELED,
        "receipt_minted": False,
        "input_sha256": _digest(graph),
        "claims": [reports[node] for node in sorted(cl)],
    }


def counterfactual(graph: Mapping[str, Any], changes: Mapping[str, Any]) -> dict[str, Any]:
    """Which claims lose (or regain) support if evidence scores change; 0.0 withdraws."""
    ev, _ = _parse(graph)
    if not isinstance(changes, Mapping) or not changes:
        raise HorizonContractError("changes must be a non-empty object")
    for eid, score in changes.items():
        if eid not in ev:
            raise HorizonContractError(f"change targets unknown evidence {eid}")
        if not 0.0 <= _number(score, f"change {eid}") <= 1.0:
            raise HorizonContractError(f"change {eid}: score must be in [0, 1]")
    changed = {
        "evidence": {eid: {**spec, **({"score": changes[eid]} if eid in changes else {})}
                     for eid, spec in graph["evidence"].items()},
        "claims": graph["claims"],
    }
    before = {c["claim"]: c["status"] for c in analyze(graph)["claims"]}
    after = {c["claim"]: c["status"] for c in analyze(changed)["claims"]}
    return {
        "schema": SCHEMA + "#counterfactual",
        "label": MODELED,
        "receipt_minted": False,
        "input_sha256": _digest(graph),
        "changes": dict(sorted(changes.items())),
        "lost_support": sorted(c for c in before if before[c] == nine.ADMITTED and after[c] != nine.ADMITTED),
        "regained_support": sorted(c for c in before if before[c] != nine.ADMITTED and after[c] == nine.ADMITTED),
        "before": before,
        "after": after,
    }


def vector_horizon(scores: list[float], weights: list[float] | None = None,
                   decay: list[Mapping[str, Any]] | None = None, tau: float = nine.POLICY_TAU) -> dict[str, Any]:
    """Single-decision form for a flat /verify-style score vector."""
    if not isinstance(scores, (list, tuple)) or not scores:
        raise HorizonContractError("scores must be a non-empty list")
    weights = list(weights) if weights is not None else [1.0] * len(scores)
    decay = list(decay) if decay is not None else [{} for _ in scores]
    if len(weights) != len(scores) or len(decay) != len(scores):
        raise HorizonContractError("scores, weights and decay must have equal length")
    ids = [f"x{i + 1}" for i in range(len(scores))]
    graph = {
        "evidence": {i: {"score": s, **dict(d)} for i, s, d in zip(ids, scores, decay)},
        "claims": {"decision": {"children": dict(zip(ids, weights)), "tau": tau}},
    }
    return analyze(graph)


def evidence_from_storage_status(status: Mapping[str, Any]) -> dict[str, Any]:
    """Map a ``szl.a11oy-storage-status/v2`` payload to a declared evidence graph.

    a11oy_state_store raises ``alert`` once the oldest unsnapshotted change,
    or (while writable) the oldest snapshot, exceeds ``alert_after_s``. Each
    store therefore expires at ``alert_after_s - worst_age``. A store whose
    health is OK scores 1.0 (binary presence, not a graded confidence); any
    other health scores 0.0. The payload publishes no lease staleness bound,
    so the lease heartbeat stays undeclared and the horizon is UNKNOWN.
    """
    if not isinstance(status, Mapping) or status.get("schema") != "szl.a11oy-storage-status/v2":
        raise HorizonContractError("expected a szl.a11oy-storage-status/v2 payload")
    alert_after = _number(status.get("alert_after_s"), "alert_after_s")
    stores = status.get("stores")
    if not isinstance(stores, Mapping) or not stores:
        raise HorizonContractError("storage status lists no stores")
    writable = status.get("writable") is True
    evidence: dict[str, Any] = {}
    for name, store in sorted(stores.items()):
        if not isinstance(store, Mapping):
            raise HorizonContractError(f"store {name} is not an object")
        ages = [store.get("unsnapshotted_change_age_s")]
        if writable:
            ages.append(store.get("last_snapshot_age_s"))
        worst = max((_number(a, f"store {name} age") for a in ages if a is not None), default=0.0)
        evidence[f"store:{name}"] = {
            "score": 1.0 if store.get("health") == "OK" else 0.0,
            "expires_in_s": max(0.0, alert_after - worst),
        }
    lease = status.get("lease") if isinstance(status.get("lease"), Mapping) else {}
    evidence["lease:heartbeat"] = {"score": 1.0 if lease.get("state") == "ACTIVE" else 0.0}
    return {
        "evidence": evidence,
        "claims": {"storage:durable": {"children": {eid: 1.0 for eid in evidence}}},
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: szl_admit_horizon.py GRAPH.json | --storage-status STATUS.json", file=sys.stderr)
        raise SystemExit(2)
    with open(sys.argv[1], encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, Mapping) and payload.get("schema") == "szl.a11oy-storage-status/v2":
        payload = evidence_from_storage_status(payload)
    print(json.dumps(analyze(payload), indent=2, sort_keys=True))
