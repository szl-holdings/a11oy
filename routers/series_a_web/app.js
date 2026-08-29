(() => {
  "use strict";

  const VIEWS = ["command", "estate", "claims", "policy", "twin", "passport", "audit"];
  const KEEP = [
    { id: "SZLHOLDINGS/README", role: "Org card", href: "https://huggingface.co/SZLHOLDINGS" },
    { id: "SZLHOLDINGS/a11oy", role: "Product Command Center", href: "https://a-11-oy.com" },
    { id: "SZLHOLDINGS/killinchu", role: "Defense vertical", href: "https://huggingface.co/spaces/SZLHOLDINGS/killinchu" },
    { id: "SZLHOLDINGS/immune", role: "Safety kernel", href: "https://huggingface.co/spaces/SZLHOLDINGS/immune" },
    { id: "SZLHOLDINGS/szl-khipu", role: "Model demo", href: "https://huggingface.co/spaces/SZLHOLDINGS/szl-khipu" },
    { id: "SZLHOLDINGS/szl-atelier", role: "Artifact walk", href: "https://huggingface.co/spaces/SZLHOLDINGS/szl-atelier" },
    { id: "SZLHOLDINGS/governed-receipt-verifier", role: "Receipt replay", href: "https://a11oy.net" }
  ];
  const CLAIMS = [
    ["CLM-ORG-REPOS", "Public GitHub repositories in org szl-holdings", "98", "LIVE"],
    ["CLM-HF-MODELS", "Hugging Face models under SZLHOLDINGS", "43", "LIVE"],
    ["CLM-HF-SPACES", "Hugging Face Spaces under SZLHOLDINGS", "authenticated 7 including README card · unauth author-list 6 · 45 total", "MEASURED"],
    ["CLM-HF-DATASETS", "Hugging Face datasets under SZLHOLDINGS", "36", "LIVE"],
    ["CLM-KHIPU-DL", "SZL-Khipu-1.5B downloads", "502", "LIVE"],
    ["CLM-KHIPU-GGUF-DL", "SZL-Khipu-1.5B-GGUF downloads", "553", "LIVE"],
    ["CLM-FORGE-DL", "SZL-Forge-1.5B-ReceiptAgent downloads", "493", "LIVE"],
    ["CLM-NORM-DL", "szl-governed-norm downloads", "209", "SNAPSHOT"],
    ["CLM-LAMBDA-DL", "szl-lambda-gate downloads", "100", "SNAPSHOT"],
    ["CLM-TABLES-848", "Database tables (verified 2026-05-12)", "848", "SNAPSHOT"],
    ["CLM-ENDPOINTS-5524", "API endpoint declarations (verified 2026-05-12)", "5,524", "SNAPSHOT"],
    ["CLM-TESTS-1220", "Passing platform tests (verified 2026-05-12)", "1,220", "SNAPSHOT"],
    ["CLM-LAMBDA-MS", "Λ overhead median (verified 2026-05-12)", "≤0.59 ms", "SNAPSHOT"],
    ["CLM-DOCTRINE", "Doctrine lock", "v11 LOCKED", "LIVE"],
    ["CLM-LAMBDA", "Λ uniqueness", "Conjecture 1 — not a closed theorem", "LIVE"],
    ["CLM-LOCKED-8", "Locked-proven formulas", "8 · F1 F4 F7 F11 F12 F18 F19 F22", "LIVE"],
    ["CLM-LEAN-COUNTS", "lutar-lean pin (declarations / axioms / sorries)", "749 / 14 / 163", "LIVE"],
    ["CLM-TRUST-CEILING", "Trust ceiling claimed on README", "omitted from /honest", "SNAPSHOT"],
    ["CLM-SHARE-LINKS", "Four ChatGPT share-link transcripts", "unfetchable", "UNKNOWN"],
    ["CLM-HF-WRITE", "Hugging Face write from this surface", "not claimed here", "UNAVAILABLE"],
    ["CLM-BOSS", "boss.technologies identity", "BLOCKED_IDENTITY", "UNKNOWN"]
  ];
  const CONTRADICTIONS = [
    ["CTR-KHIPU-DL", "BLOCKER", "Khipu download count", "Prior ~2.36k vs live 502. Retire 2.36k."],
    ["CTR-LEXICON", "HIGH", "Naming lexicon drift", "Canonical: a11oy — governed execution fabric. Product a-11-oy.com · proof a11oy.net · never a11oy.com."],
    ["CTR-STALE-METRICS", "HIGH", "May 12 platform metrics", "848 tables / 5,524 endpoints / 1,220 tests / ≤0.59 ms Λ stay SNAPSHOT."],
    ["CTR-SPACES", "MEDIUM", "Keep-set listings disagree", "Unauth author-list is 6. Authenticated recapture includes README card. This page does not rewrite the published atlas."],
    ["CTR-SPRAWL", "MEDIUM", "Repo sprawl vs canonical home", "98 repositories. Bind as packages. Do not mint a new flagship."],
    ["CTR-TRUST-CEILING", "LOW", "Trust ceiling missing from honest API", "Either emit it from /honest or stop putting it on the first fold."]
  ];
  const TOOLS = [
    ["echo.ping", "NONE", "admitted"],
    ["receipt.inspect", "NONE", "admitted"],
    ["policy.propose", "NONE", "operator"],
    ["aql.query", "NONE", "admitted"],
    ["fixture.rollback", "REVERSIBLE", "operator"],
    ["prod.write", "IRREVERSIBLE", "prohibited"],
    ["shell.exec", "IRREVERSIBLE", "prohibited"]
  ];
  const AUDIT = [
    ["B1", "LIVE", "Canonical home is szl-holdings/a11oy — no 20th repo minted this session"],
    ["B2", "LIVE", "Lexicon locked: a11oy — governed execution fabric"],
    ["B3", "LIVE", "Claims ledger exists; May 12 metrics degraded to SNAPSHOT"],
    ["B4", "LIVE", "Contradiction ledger scored separately from claims"],
    ["B5", "LIVE", "Vertical slice uses a fixture tool, never a production connector"],
    ["B6", "LIVE", "Receipts DEMO_SIGNED; DSSE UNAVAILABLE; PENDING_SYNC visible"],
    ["B7", "MEASURED", "This page does not claim a Hub write. Authenticated recapture includes the README card; unauth author-list omits it."],
    ["B8", "UNKNOWN", "ChatGPT share-link transcripts UNKNOWN — not fabricated"],
    ["B9", "MODELED", "Bricklayer IP-risk register populated before policy-enforcement code"],
    ["B10", "LIVE", "Calibration Plane proposal-only, outside TCB"]
  ];

  const badgeClass = (state) => {
    const key = String(state || "").toLowerCase();
    if (key === "live" || key === "admitted" || key === "measured") return "badge live";
    if (key === "snapshot" || key === "modeled") return "badge snapshot";
    if (key === "blocker" || key === "prohibited") return "badge blocker";
    return "badge unknown";
  };

  const showView = () => {
    const raw = (location.hash || "#command").replace(/^#/, "");
    const view = VIEWS.includes(raw) ? raw : "command";
    document.querySelectorAll("[data-view]").forEach((el) => {
      el.hidden = el.getAttribute("data-view") !== view;
    });
    document.querySelectorAll("[data-nav]").forEach((a) => {
      if (a.getAttribute("data-nav") === view) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
  };
  window.addEventListener("hashchange", showView);
  showView();

  const fillList = (id, rows, render) => {
    const node = document.getElementById(id);
    if (!node) return;
    node.replaceChildren(...rows.map(render));
  };
  fillList("keep-list", KEEP, (item) => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.className = "id";
    a.href = item.href;
    a.textContent = item.id;
    if (/^https?:/.test(item.href)) {
      a.target = "_blank";
      a.rel = "noopener";
    }
    const role = document.createElement("span");
    role.className = "badge live";
    role.textContent = item.role;
    li.append(a, role);
    return li;
  });
  const claimsBody = document.getElementById("claims-body");
  if (claimsBody) {
    claimsBody.replaceChildren(...CLAIMS.map(([id, statement, value, state]) => {
      const tr = document.createElement("tr");
      const cells = [id, statement, value, state];
      cells.forEach((text, index) => {
        const td = document.createElement("td");
        if (index === 3) {
          const span = document.createElement("span");
          span.className = badgeClass(state);
          span.textContent = state;
          td.append(span);
        } else {
          td.textContent = text;
        }
        tr.append(td);
      });
      return tr;
    }));
  }
  fillList("ctr-list", CONTRADICTIONS, ([id, sev, title, remedy]) => {
    const li = document.createElement("li");
    const name = document.createElement("span");
    name.className = "id";
    name.textContent = `${id} · ${title}`;
    const note = document.createElement("span");
    note.textContent = remedy;
    note.style.color = "var(--muted)";
    note.style.flex = "1";
    const badge = document.createElement("span");
    badge.className = badgeClass(sev);
    badge.textContent = sev;
    li.append(name, note, badge);
    return li;
  });
  fillList("tools-list", TOOLS, ([name, cls, status]) => {
    const li = document.createElement("li");
    const id = document.createElement("span");
    id.className = "id";
    id.textContent = `${name} · ${cls}`;
    const badge = document.createElement("span");
    badge.className = badgeClass(status);
    badge.textContent = status;
    li.append(id, badge);
    return li;
  });
  fillList("audit-list", AUDIT, ([id, state, item]) => {
    const li = document.createElement("li");
    const idEl = document.createElement("span");
    idEl.className = "id";
    idEl.textContent = `${id} · ${item}`;
    const badge = document.createElement("span");
    badge.className = badgeClass(state);
    badge.textContent = state;
    li.append(idEl, badge);
    return li;
  });

  const encoder = new TextEncoder();
  const sha256 = async (text) => {
    const digest = await crypto.subtle.digest("SHA-256", encoder.encode(text));
    return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
  };
  const hmacHex = async (keyRaw, msg) => {
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(keyRaw),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    const sig = await crypto.subtle.sign("HMAC", key, encoder.encode(msg));
    return [...new Uint8Array(sig)].map((value) => value.toString(16).padStart(2, "0")).join("");
  };
  const getDemoKey = async () => {
    const existing = localStorage.getItem("a11oy.demo-key");
    if (existing) return existing;
    const bytes = crypto.getRandomValues(new Uint8Array(32));
    const key = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
    localStorage.setItem("a11oy.demo-key", key);
    return key;
  };
  const FIXTURE = {
    id: "acc-fixture-v1",
    version: "1.0.0",
    expiresAt: "2026-11-27T16:00:00Z",
    prohibited: ["shell.exec", "prod.write", "unsloth.codex"],
    tools: {
      "echo.ping": { allowed: true, cls: "NONE" },
      "receipt.inspect": { allowed: true, cls: "NONE" },
      "policy.propose": { allowed: true, cls: "NONE" },
      "shell.exec": { allowed: false, cls: "IRREVERSIBLE" },
      "prod.write": { allowed: false, cls: "IRREVERSIBLE" }
    }
  };
  const twinForm = document.getElementById("twin-form");
  if (twinForm) {
    twinForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const tool = document.getElementById("twin-tool").value;
      const arg = document.getElementById("twin-arg").value;
      const spec = FIXTURE.tools[tool];
      const expired = Date.parse(FIXTURE.expiresAt) < Date.now();
      let decision = "ALLOW";
      let reason = "Constitution admits the fixture.";
      if (expired) {
        decision = "DENY";
        reason = "Constitution expired. Authority that cannot go stale cannot be audited.";
      } else if (!spec) {
        decision = "DENY";
        reason = `Unknown tool ${tool}. Deny by default.`;
      } else if (!spec.allowed || FIXTURE.prohibited.includes(tool)) {
        decision = "DENY";
        reason = `${tool} is prohibited. Not in the trusted computing base of this slice.`;
      }
      let payload;
      if (decision === "ALLOW") {
        if (tool === "echo.ping") payload = { pong: arg || "ok", ts: new Date().toISOString() };
        else if (tool === "receipt.inspect") payload = { target: arg, intact: true };
        else payload = { proposal: arg, executed: false, note: "Propose never execute." };
      } else {
        payload = { denied: tool, reason };
      }
      const payloadStr = JSON.stringify(payload);
      const payloadHash = await sha256(payloadStr);
      const body = JSON.stringify({
        tool,
        decision,
        constitutionId: FIXTURE.id,
        constitutionVersion: FIXTURE.version,
        payloadHash
      });
      const receiptHash = await sha256(body);
      const signature = await hmacHex(await getDemoKey(), receiptHash);
      document.getElementById("twin-result").textContent = JSON.stringify({
        tool,
        decision,
        reason,
        payload,
        payloadHash,
        receiptHash,
        signature,
        signatureState: "DEMO_SIGNED",
        dsseEnvelope: "UNAVAILABLE",
        flightStatus: "LOCAL",
        blastRadius: spec && spec.cls === "NONE"
          ? "In-memory fixture only. No network, no disk, no prod."
          : "Would touch production. Refused in this slice."
      }, null, 2);
    });
  }

  const API = "/api/a11oy/v1/series-a";
  const EXECUTION_TIMEOUT_MS = 135000;
  const DEFAULT_TARGETS = {
    "estate.refresh": "szl://estate/current",
    "probe.public_surface": "https://a-11-oy.com/healthz"
  };
  const EVENT_KINDS = [
    "estate.refresh",
    "estate.refresh.failed",
    "estate.refresh.skipped",
    "passport.evaluate",
    "passport.execution-denied",
    "passport.outcome"
  ];
  let executableDigest = null;
  let currentEvidence = null;
  let evaluationRevision = 0;
  const terminal = (value) => value == null ? "UNKNOWN" : String(value);
  const set = (key, value) => {
    const node = document.querySelector(`[data-key="${key}"]`);
    if (node) node.textContent = terminal(value);
  };
  const executeButton = document.getElementById("execute");
  const executionOutput = document.getElementById("execution-result");
  const resetExecution = () => {
    executableDigest = null;
    executeButton.disabled = true;
    executionOutput.textContent = "No authorized execution attempted.";
  };
  const invalidateAuthorization = () => {
    evaluationRevision += 1;
    resetExecution();
  };
  const request = async (path, options = {}, timeoutMs = 8000) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(API + path, { cache: "no-store", ...options, signal: controller.signal });
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
      currentEvidence = (
        status.state === "OBSERVED" &&
        status.signature_status === "SIGNED" &&
        status.manifest_digest &&
        status.observed_at &&
        status.valid_until
      ) ? {
        evidence_id: `estate-${status.manifest_digest.slice(0, 16)}`,
        label: "OBSERVED",
        content_digest: status.manifest_digest,
        observed_at: status.observed_at,
        valid_until: status.valid_until,
        source_revision: status.source_revision,
        signature_status: status.signature_status
      } : null;
      document.getElementById("updated").textContent = status.observed_at ? `Observed ${status.observed_at}` : status.detail || "Terminal state reached";
      const list = document.getElementById("receipts");
      list.replaceChildren(...(receipts.items || []).slice(0, 8).map((item) => {
        const li = document.createElement("li");
        li.textContent = `${item.kind} · ${item.receipt_hash.slice(0, 14)}… · ${item.envelope.signature_status}`;
        return li;
      }));
      if (!list.children.length) list.innerHTML = "<li>OBSERVED · no receipts yet</li>";
    } catch (error) {
      ["estate", "trust", "signer"].forEach((key) => set(key, error.name === "AbortError" ? "TIMED_OUT" : "UNAVAILABLE"));
      document.getElementById("updated").textContent = error.name === "AbortError" ? "Timed out after 8 seconds" : String(error.message || error);
    }
  };
  document.getElementById("refresh").addEventListener("click", async () => {
    const button = document.getElementById("refresh");
    let failure = null;
    button.disabled = true;
    try {
      if (!currentEvidence) {
        throw new Error("OBSERVED signed server evidence is required");
      }
      const evaluated = await request("/passports/evaluate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          principal_id: "series-a-ui",
          action: {
            type: "estate.refresh",
            target: "szl://estate/current",
            impact: "MODERATE",
            irreversible: false
          },
          evidence: [{ ...currentEvidence }],
          expected_if_withheld: "Current estate observation remains unchanged",
          expected_if_acted: "A bounded governed estate refresh completes or fails closed"
        })
      });
      if (evaluated.passport?.decision !== "ALLOW") {
        throw new Error(
          `PASSPORT_${evaluated.passport?.decision || "UNAVAILABLE"}: ${
            (evaluated.passport?.reason_codes || []).join(",")
          }`
        );
      }
      const value = await request("/passports/execute", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ passport_digest: evaluated.passport_digest })
      }, EXECUTION_TIMEOUT_MS);
      if (value.outcome?.status !== "SUCCEEDED") {
        throw new Error(
          `SERIES_A_REFRESH_FAILED: ${value.outcome?.error_class || value.outcome?.status || "UNKNOWN"}`
        );
      }
    } catch (error) {
      failure = String(error.message || error);
    } finally {
      button.disabled = false;
      await load();
      if (failure) document.getElementById("updated").textContent = failure;
    }
  });
  const actionSelect = document.querySelector('select[name="type"]');
  const targetInput = document.querySelector('input[name="target"]');
  const evidenceSelect = document.querySelector('select[name="label"]');
  actionSelect.addEventListener("change", () => {
    targetInput.value = DEFAULT_TARGETS[actionSelect.value] || "";
    invalidateAuthorization();
  });
  targetInput.addEventListener("input", invalidateAuthorization);
  evidenceSelect.addEventListener("change", invalidateAuthorization);
  document.getElementById("passport").addEventListener("submit", async (event) => {
    event.preventDefault();
    const revision = ++evaluationRevision;
    resetExecution();
    const form = new FormData(event.currentTarget);
    const selectedLabel = form.get("label");
    const evidenceStatement = JSON.stringify({
      source: "series-a-ui",
      target: form.get("target"),
      label: selectedLabel,
      observed_at: new Date().toISOString()
    });
    const evidence = (
      selectedLabel === "OBSERVED" && currentEvidence
    ) ? [{ ...currentEvidence }] : [{
      evidence_id: "ui-unverified",
      label: "UNKNOWN",
      content_digest: await sha256(evidenceStatement)
    }];
    const body = {
      principal_id: "series-a-ui",
      action: { type: form.get("type"), target: form.get("target"), impact: "MODERATE", irreversible: false },
      evidence,
      expected_if_withheld: "Current state persists",
      expected_if_acted: "Bounded action completes or fails closed"
    };
    const output = document.getElementById("passport-result");
    output.textContent = "EVALUATING";
    try {
      const value = await request("/passports/evaluate", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      if (revision !== evaluationRevision) {
        output.textContent = "STALE · form changed before evaluation completed";
        return;
      }
      output.textContent = JSON.stringify({ decision: value.passport.decision, reason_codes: value.passport.reason_codes, passport_digest: value.passport_digest, signature_status: value.decision_receipt.envelope.signature_status }, null, 2);
      if (value.passport.decision === "ALLOW") {
        executableDigest = value.passport_digest;
        executeButton.disabled = false;
      }
    } catch (error) {
      if (revision === evaluationRevision) output.textContent = `UNAVAILABLE: ${error.message || error}`;
    }
    if (revision === evaluationRevision) await load();
  });
  const renderOutcome = (outcome, receipt) => {
    executionOutput.textContent = JSON.stringify({
      status: outcome.status,
      target: outcome.target,
      http_status: outcome.http_status,
      latency_ms: outcome.latency_ms,
      attempt: outcome.attempt,
      max_attempts: outcome.max_attempts,
      governance: outcome.governance?.decision,
      receipt_hash: receipt.receipt_hash,
      signature_status: receipt.envelope.signature_status
    }, null, 2);
  };
  const recoverOutcome = async (passportDigest) => {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      try {
        const value = await request(
          `/passports/outcomes/${encodeURIComponent(passportDigest)}`
        );
        return { outcome: value.outcome, receipt: value.outcome_receipt };
      } catch {}
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    return null;
  };
  executeButton.addEventListener("click", async () => {
    if (!executableDigest) return;
    const passportDigest = executableDigest;
    executableDigest = null;
    executeButton.disabled = true;
    executionOutput.textContent = "EXECUTING · attempt 1 of 1";
    try {
      const value = await request("/passports/execute", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ passport_digest: passportDigest })
      }, EXECUTION_TIMEOUT_MS);
      renderOutcome(value.outcome, value.outcome_receipt);
    } catch (error) {
      const recovered = await recoverOutcome(passportDigest);
      if (recovered) renderOutcome(recovered.outcome, recovered.receipt);
      else executionOutput.textContent = `PENDING_RECONCILIATION · execution was not retried: ${error.message || error}`;
    }
    await load();
  });
  const eventRail = document.getElementById("events");
  const seenEvents = new Set();
  const appendEvent = (event) => {
    let value;
    try { value = JSON.parse(event.data); }
    catch { return; }
    if (!value.event_id || seenEvents.has(value.event_id)) return;
    seenEvents.add(value.event_id);
    const item = document.createElement("li");
    item.textContent = `${value.kind} · ${value.created_at} · ${value.event_id.slice(0, 14)}…`;
    if (eventRail.firstElementChild?.textContent === "CONNECTING") eventRail.replaceChildren();
    eventRail.prepend(item);
    while (eventRail.children.length > 8) eventRail.lastElementChild.remove();
  };
  if ("EventSource" in window) {
    const source = new EventSource(API + "/events");
    EVENT_KINDS.forEach((kind) => source.addEventListener(kind, appendEvent));
    source.addEventListener("open", () => {
      if (eventRail.firstElementChild?.textContent === "CONNECTING") {
        eventRail.firstElementChild.textContent = "CONNECTED · waiting for governed events";
      }
    });
    source.addEventListener("error", () => {
      if (!eventRail.children.length) eventRail.innerHTML = "<li>RECONNECTING</li>";
    });
  } else {
    eventRail.innerHTML = "<li>UNAVAILABLE · EventSource is not supported</li>";
  }
  load();
  window.setInterval(load, 60000);
})();
