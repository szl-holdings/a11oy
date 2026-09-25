# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Fail-closed paint: HTTP 200 is REACHABLE, not MEASURED/ALLOW/UP.

Command Center governed acts need a cycle receipt. Catch/missing JSON is
UNAVAILABLE. Read-only inspect/estate may stay ALLOW because they cannot
execute a write.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CYCLE_SCHEMA = "szl.frontier.ouroboros-cycle.v1"
CYCLE_URL = "https://szlholdings-szl-frontier.hf.space/frontier/ouroboros-cycle.v1.json"
COMMAND = ROOT / "pages" / "command-center.html"
OPERATOR = ROOT / "pages" / "operator-pane.html"
COMMAND_V2 = ROOT / "pages" / "command-v2.html"
CONSTELLATION = ROOT / "pages" / "constellation.html"
SECOND_BRAIN = ROOT / "pages" / "second-brain.html"
HOLO = ROOT / "static" / "3d" / "holographic.html"
LANDING = ROOT / "a11oy_landing.html"
CONSOLES = (
    ROOT / "console" / "index.html",
    ROOT / "pages" / "console.html",
    ROOT / "pages_console.html",
)


def paint_from_cycle(cycle: dict | None) -> str:
    if not cycle:
        return "UNAVAILABLE"
    if cycle.get("schema") != CYCLE_SCHEMA:
        return "UNAVAILABLE"
    if cycle.get("productionPromotion") is True:
        return "DENY"
    if cycle.get("lambda") != "CONJECTURE_1" or cycle.get("lambdaNeverATheorem") is not True:
        return "DENY"  # Lambda is Conjecture 1, never a theorem.
    if cycle.get("authority") != "PROPOSAL_ONLY":
        return "DENY"
    if cycle.get("invariantsOk") is not True:
        return "DENY"
    shadow = cycle.get("shadow") or {}
    if isinstance(shadow, dict) and shadow.get("executable") is True:
        return "DENY"
    if cycle.get("verdict") == "ALLOW":
        return "ALLOW"
    if cycle.get("verdict") in {
        "HARD_DENY",
        "LAMBDA_VETO",
        "DENY_DEFAULT",
        "ESCALATE",
    }:
        return "DENY"
    return "UNAVAILABLE"


def _allow_cycle(**overrides: object) -> dict:
    body = {
        "schema": CYCLE_SCHEMA,
        "verdict": "ALLOW",
        "invariantsOk": True,
        "productionPromotion": False,
        "authority": "PROPOSAL_ONLY",
        "lambda": "CONJECTURE_1",
        "lambdaNeverATheorem": True,
    }
    body.update(overrides)
    return body


def test_null_and_missing_json_cannot_paint_allow() -> None:
    assert paint_from_cycle(None) == "UNAVAILABLE"
    assert paint_from_cycle({}) == "UNAVAILABLE"
    assert paint_from_cycle({"schema": "other", "verdict": "ALLOW"}) == "UNAVAILABLE"


def test_deny_verdicts_and_promotion_cannot_paint_allow() -> None:
    for verdict in ("HARD_DENY", "LAMBDA_VETO", "DENY_DEFAULT", "ESCALATE"):
        assert paint_from_cycle(_allow_cycle(verdict=verdict)) == "DENY"
    assert paint_from_cycle(_allow_cycle(productionPromotion=True)) == "DENY"
    # Inv2 window: Lambda is Conjecture 1, never a theorem.
    theorem_claim = _allow_cycle()
    theorem_claim["lambda"] = "THEOREM"
    theorem_claim["lambdaNeverATheorem"] = False  # never a theorem
    assert paint_from_cycle(theorem_claim) == "DENY"
    assert paint_from_cycle(_allow_cycle(shadow={"executable": True})) == "DENY"


def test_bound_allow_cycle_paints_allow() -> None:
    assert paint_from_cycle(_allow_cycle()) == "ALLOW"


def test_command_center_binds_cycle_and_refuses_static_governed_allow() -> None:
    text = COMMAND.read_text(encoding="utf-8")
    assert CYCLE_SCHEMA in text
    assert CYCLE_URL in text
    assert "function paintFromCycle" in text
    assert "function loadPublishedCycle" in text
    assert 'cycle.productionPromotion === true' in text
    assert 'cycle.lambda !== "CONJECTURE_1"' in text
    assert "HARD_DENY" in text and "LAMBDA_VETO" in text and "DENY_DEFAULT" in text
    assert "catch(_err){ return null; }" in text
    assert '{id:"inspect"' in text and 'd:"ALLOW"' in text
    assert '{id:"estate"' in text and "Cannot execute a write." in text
    assert '{id:"score"' in text and 'd:"UNAVAILABLE"' in text and 'gate:"cycle"' in text
    assert '{id:"infer"' in text and 'd:"BLOCKED"' in text
    assert '{id:"zk_prove"' in text and 'd:"UNAVAILABLE"' in text
    assert '{id:"infer", title:"Governed inference", needs:true, d:"ALLOW"' not in text
    assert '{id:"score", title:"Score Lambda advisory", needs:false, d:"ALLOW"' not in text
    assert '{id:"zk_prove", title:"Seal modeled ZK transcript", needs:true, d:"ALLOW"' not in text
    assert "applyCyclePaint(paintFromCycle(cycle))" in text


def test_operator_pane_does_not_paint_measured_on_http_200() -> None:
    text = OPERATOR.read_text(encoding="utf-8")
    assert "<title>a11oy operator pane</title>" in text
    assert "operator pane · MEASURED" not in text
    assert 'honesty: r.ok ? "MEASURED"' not in text
    assert 'honesty: "REACHABLE"' in text
    assert 'honesty: "UNAVAILABLE"' in text
    assert "typeof json !== \"object\"" in text
    assert "catch (err)" in text
    assert 'bag.healthz.honesty === "MEASURED"' not in text
    assert "HTTP 200 is REACHABLE, not MEASURED" in text


def test_command_v2_health_is_reachable_not_measured() -> None:
    text = COMMAND_V2.read_text(encoding="utf-8")
    assert 'health.ok?"MEASURED"' not in text
    assert 'health.ok&&health.json?"REACHABLE"' in text
    assert 'dataset.state=ok?"reachable"' in text
    assert 'dataset.state=ok?"measured"' not in text


def test_constellation_and_second_brain_do_not_upgrade_reachability() -> None:
    constellation = CONSTELLATION.read_text(encoding="utf-8")
    second = SECOND_BRAIN.read_text(encoding="utf-8")
    assert 'p.ok?"MEASURED"' not in constellation
    assert 'p.ok?"REACHABLE"' in constellation
    assert "body=await r.json().catch" in constellation
    assert 'honest.ok?"MEASURED"' not in second
    assert 'honest.ok?"REACHABLE"' in second
    assert "typeof json!==\"object\"" in second
    assert "catch(e){return {ok:false,status:0,json:null};}" in second


def test_holographic_and_landing_catch_cannot_paint_live_or_measured() -> None:
    holo = HOLO.read_text(encoding="utf-8")
    landing = LANDING.read_text(encoding="utf-8")
    assert 'setLabel("brain-lbl", "live", "LIVE")' not in holo
    assert 'setLabel("estate-lbl", "live", "LIVE")' not in holo
    assert 'setLabel("brain-lbl", "reachable", "REACHABLE")' in holo
    assert 'setLabel("estate-lbl", "reachable", "REACHABLE")' in holo
    catch_brain = holo.split("async function loadBrain()", 1)[1].split("async function loadEstate()", 1)[0]
    catch_estate = holo.split("async function loadEstate()", 1)[1].split("let introReturnFocus", 1)[0]
    assert 'setLabel("brain-lbl", "degraded", "NO-LIVE-DATA")' in catch_brain
    assert 'setLabel("brain-lbl", "live", "LIVE")' not in catch_brain
    assert "MEASURED" not in catch_brain
    assert 'setLabel("estate-lbl", "degraded", "MANIFEST")' in catch_estate
    assert 'setLabel("estate-lbl", "live", "LIVE")' not in catch_estate
    assert 'pulseState("health", "REACHABLE"' in landing
    assert 'pulseState("health", "UNAVAILABLE"' in landing
    assert 'pulseState("health", "MEASURED"' not in landing
    assert 'pulseState("health", "LIVE"' not in landing
    assert '.catch(() => pulseState("health", "UNAVAILABLE"' in landing


def test_console_probe_catch_still_unavailable() -> None:
    for path in CONSOLES:
        text = path.read_text(encoding="utf-8")
        assert 'badge b-live">UP' not in text, path
        assert 'b-err">UNAVAILABLE' in text, path
