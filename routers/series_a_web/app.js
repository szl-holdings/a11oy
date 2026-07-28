(() => {
  "use strict";
  const API = "/api/a11oy/v1/series-a";
  const terminal = (value) => value == null ? "UNKNOWN" : String(value);
  const set = (key, value) => {
    const node = document.querySelector(`[data-key="${key}"]`);
    if (node) node.textContent = terminal(value);
  };
  const sha256 = async (text) => {
    const bytes = new TextEncoder().encode(text);
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, "0")).join("");
  };
  const request = async (path, options = {}) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(API + path, {cache: "no-store", ...options, signal: controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } finally { clearTimeout(timer); }
  };
  const load = async () => {
    try {
      const [status, trust, receipts] = await Promise.all([
        request("/status"), request("/trust"), request("/receipts")
      ]);
      set("estate", status.state);
      set("repos", status.counts?.github_repositories);
      set("prs", status.counts?.github_open_pull_requests);
      set("spaces", status.counts?.spaces);
      set("models", status.counts?.models);
      set("datasets", status.counts?.datasets);
      set("trust", trust.score_0_to_100);
      set("signer", status.signature_status || status.signing_key_source);
      document.getElementById("updated").textContent = status.observed_at ? `Observed ${status.observed_at}` : status.detail || "Terminal state reached";
      const list = document.getElementById("receipts");
      list.replaceChildren(...(receipts.items || []).slice(0, 8).map(item => {
        const li = document.createElement("li");
        li.textContent = `${item.kind} · ${item.receipt_hash.slice(0, 14)}… · ${item.envelope.signature_status}`;
        return li;
      }));
      if (!list.children.length) list.innerHTML = "<li>OBSERVED · no receipts yet</li>";
    } catch (error) {
      ["estate", "trust", "signer"].forEach(key => set(key, error.name === "AbortError" ? "TIMED_OUT" : "UNAVAILABLE"));
      document.getElementById("updated").textContent = error.name === "AbortError" ? "Timed out after 8 seconds" : String(error.message || error);
    }
  };
  document.getElementById("refresh").addEventListener("click", async () => {
    const button = document.getElementById("refresh");
    button.disabled = true;
    try {
      await request("/refresh", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify({actor: "series-a-ui"})});
    } catch (error) {
      document.getElementById("updated").textContent = String(error.message || error);
    } finally { button.disabled = false; await load(); }
  });
  document.getElementById("passport").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const evidenceStatement = JSON.stringify({
      source: "series-a-ui",
      target: form.get("target"),
      label: form.get("label"),
      observed_at: new Date().toISOString()
    });
    const body = {
      principal_id: "series-a-ui",
      action: {type: form.get("type"), target: form.get("target"), impact: "MODERATE", irreversible: false},
      evidence: [{evidence_id: "ui-observation", label: form.get("label"), content_digest: await sha256(evidenceStatement)}],
      expected_if_withheld: "Current state persists",
      expected_if_acted: "Bounded action completes or fails closed"
    };
    const output = document.getElementById("passport-result");
    output.textContent = "EVALUATING";
    try {
      const value = await request("/passports/evaluate", {method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(body)});
      output.textContent = JSON.stringify({decision: value.passport.decision, reason_codes: value.passport.reason_codes, passport_digest: value.passport_digest, signature_status: value.decision_receipt.envelope.signature_status}, null, 2);
    } catch (error) { output.textContent = `UNAVAILABLE: ${error.message || error}`; }
    await load();
  });
  load();
  window.setInterval(load, 60000);
})();
