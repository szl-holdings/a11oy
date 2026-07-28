// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
(() => {
  "use strict";

  const API = "/api/a11oy/v1/gdw";
  const $ = (id) => document.getElementById(id);
  const state = { sessionId: null, latest: null };

  function token(prefix) {
    const random = globalThis.crypto && crypto.randomUUID
      ? crypto.randomUUID().replaceAll("-", "")
      : String(Date.now());
    return `${prefix}-${random.slice(0, 24)}`;
  }

  function setNotice(message, kind = "info") {
    const element = $("notice");
    element.textContent = message;
    element.dataset.kind = kind;
  }

  function show(value) {
    state.latest = value;
    $("output").textContent = JSON.stringify(value, null, 2);
  }

  function short(value, width = 20) {
    if (!value) return "—";
    const text = String(value);
    return text.length > width ? `${text.slice(0, width)}…` : text;
  }

  async function request(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(path, {
        ...options,
        signal: controller.signal,
        headers: {
          accept: "application/json",
          ...(options.body ? { "content-type": "application/json" } : {}),
          ...(options.headers || {}),
        },
      });
      const body = await response.json().catch(() => ({
        error: "INVALID_RESPONSE",
        message: "The endpoint did not return JSON.",
      }));
      if (!response.ok) {
        const error = new Error(body.message || body.reason || `HTTP ${response.status}`);
        error.body = body;
        error.status = response.status;
        throw error;
      }
      return body;
    } finally {
      clearTimeout(timeout);
    }
  }

  function applySession(body) {
    state.sessionId = body.session_id;
    $("session-id").value = body.session_id;
    $("session-step").textContent = String(body.state.step);
    $("session-hash").textContent = short(body.state_hash);
    $("session-hash").title = body.state_hash;
    if (body.receipt) {
      const envelope = body.receipt.dsse || {};
      $("receipt-signing").textContent = envelope.signed ? "SIGNED" : "UNSIGNED";
      $("receipt-id").textContent = short(body.receipt.receipt?.receipt_id);
    }
  }

  async function refreshStatus() {
    const connection = $("connection-state");
    connection.textContent = "checking runtime";
    connection.dataset.state = "pending";
    try {
      const body = await request(`${API}/status`);
      const ready = Boolean(body.runtime_ready);
      $("runtime-ready").textContent = ready ? "READY" : "UNAVAILABLE";
      $("storage-ready").textContent = body.storage_ready ? "ATTACHED" : "UNAVAILABLE";
      $("storage-basis").textContent = body.storage?.persistent_required
        ? `required · ${body.storage.required_mount || "mount"}`
        : "development store";
      connection.textContent = ready ? "runtime ready" : "degraded honestly";
      connection.dataset.state = ready ? "ready" : "unavailable";
      if (!ready) {
        setNotice("The governed API is registered but durable storage is unavailable. State writes fail closed until the required mount is attached.", "error");
      }
      return body;
    } catch (error) {
      connection.textContent = "endpoint unavailable";
      connection.dataset.state = "unavailable";
      setNotice(error.message, "error");
      throw error;
    }
  }

  async function recoverSession() {
    const sessionId = $("session-id").value.trim();
    if (!sessionId) return setNotice("Enter a session ID to recover.", "error");
    try {
      const body = await request(`${API}/sessions/${encodeURIComponent(sessionId)}`);
      applySession(body);
      show(body);
      setNotice(`Recovered ${sessionId} without minting a receipt.`, "success");
    } catch (error) {
      show(error.body || { error: error.message });
      setNotice(error.message, "error");
    }
  }

  $("refresh-status").addEventListener("click", () => refreshStatus().catch(() => {}));
  $("generate-session").addEventListener("click", () => {
    $("session-id").value = token("gdw");
  });
  $("recover-session").addEventListener("click", recoverSession);
  $("session-risk").addEventListener("input", (event) => {
    $("session-risk-value").textContent = Number(event.target.value).toFixed(2);
    $("step-risk").value = event.target.value;
  });
  $("lambda").addEventListener("input", (event) => {
    $("lambda-value").textContent = Number(event.target.value).toFixed(2);
  });

  $("session-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const sessionId = $("session-id").value.trim();
    try {
      const body = await request(`${API}/sessions`, {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          risk_budget: Number($("session-risk").value),
        }),
      });
      applySession(body);
      $("idempotency-key").value = token("step");
      show(body);
      setNotice(`Session ${sessionId} committed with a session.create receipt.`, "success");
    } catch (error) {
      show(error.body || { error: error.message });
      setNotice(error.message, "error");
    }
  });

  $("step-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.sessionId) {
      return setNotice("Create or recover a session before proposing a step.", "error");
    }
    const experts = $("experts").value.split(",")
      .map((value) => value.trim()).filter(Boolean);
    try {
      const evidenceId = $("evidence-id").value.trim();
      const evidence = [];
      if (evidenceId) {
        const uri = $("evidence-uri").value.trim();
        const contentHash = $("evidence-hash").value.trim();
        const observed = $("evidence-observed").value;
        if (!uri || !/^[0-9a-f]{64}$/.test(contentHash) || !observed) {
          throw new Error("Attached evidence requires a URI, lowercase SHA-256, and observed time.");
        }
        evidence.push({
          evidence_id: evidenceId,
          uri,
          content_hash: contentHash,
          trust: Number($("evidence-trust").value),
          observed_at: new Date(observed).toISOString(),
        });
      }
      const body = await request(
        `${API}/sessions/${encodeURIComponent(state.sessionId)}/step`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotency_key: $("idempotency-key").value.trim(),
            request: $("request-text").value,
            evidence,
            allowed_experts: experts,
            risk_budget: Number($("step-risk").value),
          }),
        },
      );
      applySession(body);
      const receipt = body.audit?.receipt || {};
      $("receipt-signing").textContent = body.khipu_receipt?.signed ? "SIGNED" : "UNSIGNED";
      $("receipt-id").textContent = short(body.khipu_receipt?.receipt_id || receipt.receipt_id);
      $("idempotency-key").value = token("step");
      show(body);
      setNotice(
        body.replayed
          ? "Idempotent replay returned the stored result; no second write was minted."
          : `Kernel decision ${body.decision}; the persisted result is receipt-bound.`,
        "success",
      );
    } catch (error) {
      show(error.body || { error: error.message });
      setNotice(error.message, "error");
    }
  });

  $("aggregate-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const sources = JSON.parse($("sources").value);
      const body = await request(`${API}/aggregate`, {
        method: "POST",
        body: JSON.stringify({
          sources,
          lam: Number($("lambda").value),
          egyptian: $("egyptian").checked,
          depth: 4,
        }),
      });
      show(body);
      setNotice("MODELED aggregate computed. This is not training or performance evidence.", "success");
    } catch (error) {
      show(error.body || { error: error.message });
      setNotice(error instanceof SyntaxError ? "Sources must be valid JSON." : error.message, "error");
    }
  });

  $("copy-output").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("output").textContent);
      setNotice("Latest JSON copied.", "success");
    } catch {
      setNotice("Clipboard access is unavailable in this browser context.", "error");
    }
  });

  $("session-id").value = token("gdw");
  $("idempotency-key").value = token("step");
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
  $("evidence-observed").value = now.toISOString().slice(0, 16);
  refreshStatus().catch(() => {});
})();
