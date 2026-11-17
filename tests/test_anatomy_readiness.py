#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Synthetic endpoint fixtures test Anatomy honesty, not deployed readiness."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BODY = ROOT / "console" / "anatomy-map" / "live-body.js"
PAGE = BODY.with_suffix(".html")

DRIVER = r"""
import { readFileSync } from "node:fs";
import vm from "node:vm";
const input = JSON.parse(readFileSync(0, "utf8"));
const body = (await import("data:text/javascript;base64," +
  Buffer.from(readFileSync(process.argv[1], "utf8")).toString("base64"))).default;
const payload = input.payload;
if (input.nonFinite) {
  payload[input.nonFinite.field] =
    input.nonFinite.value === "NaN" ? NaN : Infinity;
}
const requests = [];
globalThis.fetch = async (url, options) => {
  requests.push({url, method: options.method, credentials: options.credentials});
  if (input.fetchError) throw new Error("fixture transport failure");
  return {
    ok: (input.httpStatus ?? 200) < 400,
    status: input.httpStatus ?? 200,
    headers: {get: () => input.contentType ?? "application/json"},
    json: async () => {
      if (input.parseError) throw new Error("fixture invalid JSON");
      return payload;
    },
  };
};
const organ = body.ORGANS.find(o => o.id === (input.organ ?? "operator"));
let result = input.action === "immune"
  ? await body.fetchImmune()
  : await body.probeOrgan(organ);
if (input.consumer) {
  const html = readFileSync(process.argv[2], "utf8");
  const name = input.action === "immune" ? "refreshImmune" : "refreshOrgans";
  const source = html.match(new RegExp("async function " + name +
    "\\(\\) \\{[\\s\\S]*?\\n\\}"))[0];
  const row = {dataset: {}, detail: {textContent: ""}};
  row.querySelector = () => row.detail;
  const logs = [];
  const context = {
    LiveBody: {...body, ORGANS: [organ], probeOrgan: async () => result,
      fetchImmune: async () => result},
    STATE: vm.runInNewContext("(" + html.match(/const STATE = (\{[^\n]+\});/)[1] + ")"),
    organRows: new Map([[organ.id, row]]),
    organMeshes: new Map([[organ.id, {mat: {emissiveIntensity: 0}}]]),
    setOrganDot: () => {}, swarm: {count: 0}, SWARM_MAX: 100,
    logLine: value => logs.push(value),
  };
  await vm.runInNewContext(source + "; " + name + "()", context);
  result = {probe: result, detail: row.detail.textContent,
    immune: context.STATE.immune, particles: context.swarm.count, logs};
}
console.log(JSON.stringify({result, requests}));
"""


def probe(payload, *, action="immune", **options):
    node = shutil.which("node")
    assert node, "Node is required to execute the shipped Anatomy module"
    run = subprocess.run(
        [node, "--input-type=module", "--eval", DRIVER, str(BODY), str(PAGE)],
        input=json.dumps({"payload": payload, "action": action, **options}),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    output = json.loads(run.stdout)
    assert output["requests"]
    assert all(r["method"] == "GET" and r["credentials"] == "omit"
               for r in output["requests"])
    return output["result"]


@pytest.mark.parametrize("payload", [None, [], "ready", 42, True, {}])
def test_missing_mesh_shape_is_reachable_but_unavailable(payload):
    out = probe(payload)
    assert out["reachable"] is True and out["transport"] == "reachable"
    assert out["countersAvailable"] is False
    assert all(out[key] is None for key in ("intensity", "down", "live", "total"))
    assert "mesh health unavailable" in out["detail"]
    assert "healthy" not in out["detail"]


@pytest.mark.parametrize(
    "payload,live,total",
    [({"engines_total": 3}, None, 3), ({"engines_live": 0}, 0, None)],
)
def test_partial_mesh_counters_preserve_only_observed_values(payload, live, total):
    out = probe(payload)
    assert (out["live"], out["total"]) == (live, total)
    assert out["countersAvailable"] is False
    assert out["intensity"] is None and out["down"] is None
    assert "unavailable" in out["detail"]


@pytest.mark.parametrize("field", ["engines_total", "engines_live"])
@pytest.mark.parametrize("invalid", [None, True, False, "2", -1, 0.5, 2**53])
def test_invalid_mesh_counter_is_not_coerced_to_zero_or_live(field, invalid):
    payload = {"engines_total": 4, "engines_live": 2, field: invalid}
    out = probe(payload)
    assert out["total" if field == "engines_total" else "live"] is None
    assert out["countersAvailable"] is False
    assert out["intensity"] is None and out["down"] is None
    assert "unavailable" in out["detail"]


@pytest.mark.parametrize("field", ["engines_total", "engines_live"])
@pytest.mark.parametrize("value", ["NaN", "Infinity"])
def test_nonfinite_mesh_counter_is_unavailable(field, value):
    out = probe({"engines_total": 4, "engines_live": 2},
                nonFinite={"field": field, "value": value})
    assert out["total" if field == "engines_total" else "live"] is None
    assert out["countersAvailable"] is False
    assert out["intensity"] is None and out["down"] is None


def test_inconsistent_mesh_counter_pair_is_not_clamped_to_healthy():
    out = probe({"engines_total": 2, "engines_live": 3})
    assert (out["total"], out["live"]) == (2, 3)
    assert out["countersAvailable"] is False
    assert out["intensity"] is None and out["down"] is None
    assert "unavailable" in out["detail"]


def test_empty_observed_mesh_has_no_health_fraction():
    out = probe({"engines_total": 0, "engines_live": 0})
    assert out["countersAvailable"] is True
    assert (out["total"], out["live"], out["down"]) == (0, 0, 0)
    assert out["intensity"] is None
    assert "no engines reported; 0/0" in out["detail"]
    assert "health unavailable" in out["detail"] and "healthy" not in out["detail"]


@pytest.mark.parametrize("live,down,intensity", [(4, 0, 0), (3, 1, 0.25), (0, 4, 1)])
def test_valid_mesh_counts_describe_only_source_observations(live, down, intensity):
    out = probe({"engines_total": 4, "engines_live": live})
    assert out["countersAvailable"] is True
    assert (out["live"], out["total"], out["down"]) == (live, 4, down)
    assert out["intensity"] == intensity
    assert "engines reported live" in out["detail"]
    assert "healthy" not in out["detail"] and "operational" not in out["detail"]


@pytest.mark.parametrize(
    "options",
    [{"httpStatus": 503}, {"contentType": "text/html"},
     {"fetchError": True}, {"parseError": True}],
)
def test_failed_mesh_probe_preserves_unknown_counters(options):
    out = probe({"engines_total": 4, "engines_live": 4}, **options)
    assert out["reachable"] is False
    assert out["transport"] == "unreachable" and out["countersAvailable"] is False
    assert all(out[key] is None for key in ("intensity", "down", "live", "total"))
    assert "unavailable" in out["detail"]


@pytest.mark.parametrize("state", ["ready", "degraded", "BLOCKED"])
def test_reachable_organ_preserves_source_state_without_asserting_readiness(state):
    out = probe({"status": state, "operator": {"operator_running": False}},
                action="organ")
    assert out["transport"] == "reachable"
    assert out["readiness"] is None and out["sourceState"] == state
    assert "transport reachable" in out["detail"]
    assert f"source status: {state} (declared)" in out["detail"]


@pytest.mark.parametrize("state", [None, True, 1, {}, ["ready"], "<b>ready</b>"])
def test_invalid_source_state_does_not_become_readiness(state):
    out = probe({"status": state}, action="organ")
    assert out["sourceState"] is None and out["readiness"] is None
    assert "readiness unavailable" in out["detail"]


def test_running_operator_without_status_does_not_invent_ready():
    out = probe({"operator": {"operator_running": True}}, action="organ")
    assert out["sourceState"] is None and out["readiness"] is None
    assert "status unavailable" in out["detail"]
    assert "· ready" not in out["detail"]


def test_real_organ_consumer_displays_reachable_and_blocked_separately():
    out = probe({"status": "BLOCKED"}, action="organ", consumer=True)
    assert "transport reachable" in out["detail"]
    assert "source status: BLOCKED (declared)" in out["detail"]
    assert out["probe"]["readiness"] is None


@pytest.mark.parametrize("options", [{}, {"httpStatus": 503}, {"fetchError": True}])
def test_real_mesh_consumer_displays_unknown_without_fabricated_particles(options):
    out = probe({}, consumer=True, **options)
    assert out["immune"] is None and out["particles"] == 0
    assert any("mesh health unavailable" in line for line in out["logs"])
    assert not any("healthy" in line for line in out["logs"])


def test_real_mesh_consumer_renders_valid_fraction():
    out = probe({"engines_total": 4, "engines_live": 3}, consumer=True)
    assert out["immune"] == 0.25 and out["particles"] == 25
    assert any("3/4 engines reported live" in line for line in out["logs"])


def test_page_labels_and_accessibility_explain_transport_scope():
    html = PAGE.read_text(encoding="utf-8")
    assert "organs · transport probes" in html
    assert "transport reachable; system readiness not assessed." in html
    assert 'aria-label="3D organism: organ glow shows endpoint transport reachability, not operational readiness"' in html
    assert "Source status is declared, not independently verified." in html
    assert "transport unavailable / roadmap" in html
    assert "glow LIVE" not in html and "healthy glow" not in html
