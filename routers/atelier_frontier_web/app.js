(() => {
  "use strict";

  const REGISTRY = "/api/a11oy/v1/atelier/frontier/registry";
  const EVALUATE = "/api/a11oy/v1/atelier/frontier/evaluate";
  const $ = (id) => document.getElementById(id);
  const state = { registry: null };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function link(href, text, className) {
    const node = element("a", className, text);
    node.href = href;
    if (href.startsWith("http")) {
      node.target = "_blank";
      node.rel = "noopener noreferrer";
    }
    return node;
  }

  function setText(id, value) {
    const node = $(id);
    if (node) node.textContent = value == null ? "—" : String(value);
  }

  function renderMetrics(registry) {
    const inventory = registry.source_inventory || {};
    const policies = inventory.reuse_policy_counts || {};
    setText("repoCount", inventory.observed_public_repository_count);
    setText("cleanCount", policies.CLEAN_ROOM_ONLY || 0);
    setText("licensedCount", policies.ADAPT_WITH_NOTICE || 0);
    setText("snapshotState", registry.evidence_class || "UNAVAILABLE");
  }

  function renderLanes(registry) {
    const grid = $("laneGrid");
    grid.textContent = "";
    for (const lane of registry.capability_lanes || []) {
      const card = element("article", "lane");
      const top = element("div", "lane-top");
      top.append(element("h3", "", lane.label), element("span", "state", lane.state));
      card.append(top, element("p", "", lane.improvement));

      const bindings = element("div", "bindings");
      for (const binding of lane.bindings || []) bindings.append(link(binding, binding));
      if (!bindings.childElementCount) bindings.append(element("span", "state", "NO LIVE BINDING"));
      card.append(bindings);

      const refs = element("div", "refs");
      refs.append(element("b", "", `${lane.reference_count || 0} reference repositories`));
      refs.append(document.createElement("br"));
      refs.append(document.createTextNode((lane.references || []).join(" · ") || "UNAVAILABLE"));
      card.append(refs);
      grid.append(card);
    }
  }

  function populateFilters(registry) {
    const policy = $("policy");
    const lane = $("lane");
    const policies = Object.keys(registry.source_inventory?.reuse_policy_counts || {}).sort();
    for (const value of policies) {
      const option = element("option", "", value);
      option.value = value;
      policy.append(option);
    }
    for (const item of registry.capability_lanes || []) {
      const option = element("option", "", item.label);
      option.value = item.id;
      lane.append(option);
    }
  }

  function renderRepositories() {
    const registry = state.registry;
    if (!registry) return;
    const query = $("search").value.trim().toLowerCase();
    const policy = $("policy").value;
    const lane = $("lane").value;
    const rows = $("repoRows");
    rows.textContent = "";

    const repositories = (registry.source_inventory?.repositories || []).filter((item) => {
      const haystack = [item.name, item.license_state, item.reuse_policy, item.note, ...(item.lanes || [])].join(" ").toLowerCase();
      return (!query || haystack.includes(query)) &&
        (policy === "all" || item.reuse_policy === policy) &&
        (lane === "all" || (item.lanes || []).includes(lane));
    });

    for (const item of repositories) {
      const tr = document.createElement("tr");
      const name = document.createElement("td");
      name.append(link(item.source, item.name));
      const license = element("td", "", item.license_state);
      const reuse = document.createElement("td");
      reuse.append(element("span", "policy", item.reuse_policy));
      const lanes = element("td", "lane-list", (item.lanes || []).join(" · "));
      const note = element("td", "", item.note);
      tr.append(name, license, reuse, lanes, note);
      rows.append(tr);
    }
    setText("repoResultCount", `${repositories.length} of ${registry.source_inventory?.observed_public_repository_count || 0} repositories shown`);
  }

  function buildSliders() {
    const labels = [
      ["evidence", "Evidence quality", 72],
      ["repeatability", "Repeatability", 68],
      ["coverage", "Capability coverage", 70],
      ["governance", "Governance maturity", 84],
      ["energy", "Energy efficiency input", 50],
    ];
    const host = $("sliders");
    for (const [name, labelText, value] of labels) {
      const row = element("div", "slider");
      const label = element("label", "", labelText);
      label.htmlFor = name;
      const input = document.createElement("input");
      input.id = name;
      input.name = name;
      input.type = "range";
      input.min = "0";
      input.max = "100";
      input.value = String(value);
      const output = element("output", "", value);
      output.htmlFor = name;
      input.addEventListener("input", () => { output.value = input.value; output.textContent = input.value; });
      row.append(label, input, output);
      host.append(row);
    }
  }

  async function evaluate(event) {
    if (event) event.preventDefault();
    const params = new URLSearchParams();
    for (const name of ["evidence", "repeatability", "coverage", "governance", "energy"]) params.set(name, $(name).value);
    params.set("safety", $("safety").checked ? "1" : "0");
    params.set("energy_state", $("energyState").value);

    try {
      const response = await fetch(`${EVALUATE}?${params.toString()}`, { cache: "no-store", headers: { accept: "application/json" } });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
      const decision = body.decision?.state || "UNAVAILABLE";
      const result = document.querySelector(".result");
      result.dataset.decision = decision;
      setText("decisionLabel", decision);
      setText("scoreValue", Number(body.formula?.score || 0).toFixed(3));
      setText("reason", body.decision?.reason);
      setText("quality", Number(body.formula?.quality || 0).toFixed(4));
      setText("energyFactor", Number(body.formula?.energy_factor || 0).toFixed(4));
      setText("fingerprint", body.derivation_fingerprint?.sha256);
    } catch (error) {
      setText("decisionLabel", "UNAVAILABLE");
      setText("reason", error instanceof Error ? error.message : "evaluation failed");
    }
  }

  async function boot() {
    buildSliders();
    $("scoreForm").addEventListener("submit", evaluate);
    $("energyState").addEventListener("change", () => {
      const unavailable = $("energyState").value === "UNAVAILABLE";
      $("energy").disabled = unavailable;
    });
    $("energy").disabled = true;

    try {
      const response = await fetch(REGISTRY, { cache: "no-store", headers: { accept: "application/json" } });
      if (!response.ok) throw new Error(`registry HTTP ${response.status}`);
      state.registry = await response.json();
      renderMetrics(state.registry);
      renderLanes(state.registry);
      populateFilters(state.registry);
      renderRepositories();
      for (const id of ["search", "policy", "lane"]) $(id).addEventListener(id === "search" ? "input" : "change", renderRepositories);
    } catch (error) {
      const grid = $("laneGrid");
      grid.textContent = "";
      grid.append(element("p", "error", error instanceof Error ? error.message : "registry unavailable"));
      setText("snapshotState", "UNAVAILABLE");
    }
    await evaluate();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
