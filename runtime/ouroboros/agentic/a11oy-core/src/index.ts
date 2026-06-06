// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// a11oy-core — doctrine-bound agent orchestrator.
// Every tool call from Cursor / Claude Code / Replit Agent passes through here.

import {
  lambdaGate, mkAxisScore, REPLAY_ROOT,
  type Axes, type LambdaResult, type ReplaySha,
} from "../../formulas/src/index.js";

// ============================================================
// Doctrine V6 — forbidden patterns, blocked actions
// ============================================================
const FORBIDDEN = [
  /\bJr\./i, /AlloyScape/i, /Glass\s*Wing/i, /Glasswing/i,
  /\bMythos\b/i, /Stephen\s*Paul/i, /Perplexity\s*Computer/i, /\banonymous\b/i,
];
const MYTHOS_EXCEPTION = /Claude\s*Mythos\s*Preview/i;

const BLOCKED_ACTIONS = new Set([
  "branch_protection_edit",
  "zenodo_mint",
  "arxiv_submit",
  "npm_publish",
  "force_push",
  "branch_delete",
  "repo_delete",
  "profile_edit",
  "org_edit",
  "cron_create", "cron_edit", "cron_delete",
  "rename_glasswing", "rename_mythos",
  "spend",
  "credential_write",
]);

export interface DoctrineGateResult {
  allowed: boolean;
  reasons: string[];
  forbiddenHits: string[];
  blockedAction: boolean;
  lambda?: LambdaResult;
}

export function doctrineGate(
  action: string,
  payloadText: string,
  axes?: Axes
): DoctrineGateResult {
  const reasons: string[] = [];
  const forbiddenHits: string[] = [];

  if (BLOCKED_ACTIONS.has(action)) {
    reasons.push(`action '${action}' is in the CTO-blocked set`);
  }

  for (const re of FORBIDDEN) {
    if (re.test(payloadText)) {
      // Mythos exception: only "Claude Mythos Preview"
      if (re.source.includes("Mythos") && MYTHOS_EXCEPTION.test(payloadText)) continue;
      forbiddenHits.push(re.source);
      reasons.push(`forbidden pattern hit: ${re.source}`);
    }
  }

  let lambda: LambdaResult | undefined;
  if (axes) {
    lambda = lambdaGate(axes);
    if (!lambda.pass) {
      reasons.push(`Λ gate failed: ${lambda.failures.map(f => f.axis).join(", ")}`);
    }
  }

  return {
    allowed: reasons.length === 0,
    reasons,
    forbiddenHits,
    blockedAction: BLOCKED_ACTIONS.has(action),
    lambda,
  };
}

// ============================================================
// Provider router — Anthropic + OpenAI with Promise.race failover
// ============================================================
export type Provider = "anthropic" | "openai" | "ollama" | "stub";

export interface RouteResult {
  provider: Provider;
  text: string;
  latencyMs: number;
  replayRoot: ReplaySha;
}

async function callAnthropic(prompt: string, signal?: AbortSignal): Promise<string> {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) throw new Error("no ANTHROPIC_API_KEY");
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 4096,
      messages: [{ role: "user", content: prompt }],
    }),
    signal,
  });
  if (!res.ok) throw new Error(`anthropic ${res.status}`);
  const j: any = await res.json();
  return j.content?.[0]?.text ?? "";
}

async function callOpenAI(prompt: string, signal?: AbortSignal): Promise<string> {
  const key = process.env.OPENAI_API_KEY;
  if (!key) throw new Error("no OPENAI_API_KEY");
  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify({
      model: "gpt-4o",
      messages: [{ role: "user", content: prompt }],
    }),
    signal,
  });
  if (!res.ok) throw new Error(`openai ${res.status}`);
  const j: any = await res.json();
  return j.choices?.[0]?.message?.content ?? "";
}

export async function route(prompt: string, opts: { strategy?: "race" | "anthropic" | "openai" } = {}): Promise<RouteResult> {
  const start = performance.now();
  const strategy = opts.strategy ?? "race";

  if (strategy === "anthropic") {
    const text = await callAnthropic(prompt);
    return { provider: "anthropic", text, latencyMs: performance.now() - start, replayRoot: REPLAY_ROOT };
  }
  if (strategy === "openai") {
    const text = await callOpenAI(prompt);
    return { provider: "openai", text, latencyMs: performance.now() - start, replayRoot: REPLAY_ROOT };
  }

  // race
  const ac = new AbortController();
  const a = callAnthropic(prompt, ac.signal).then(t => ({ p: "anthropic" as Provider, t }));
  const o = callOpenAI(prompt, ac.signal).then(t => ({ p: "openai"   as Provider, t }));
  try {
    const winner = await Promise.any([a, o]);
    ac.abort();
    return { provider: winner.p, text: winner.t, latencyMs: performance.now() - start, replayRoot: REPLAY_ROOT };
  } catch {
    // both failed — stub mode
    return {
      provider: "stub",
      text: `[stub] no provider available. prompt was: ${prompt.slice(0, 200)}`,
      latencyMs: performance.now() - start,
      replayRoot: REPLAY_ROOT,
    };
  }
}

// ============================================================
// CTO acceptance log (JSONL)
// ============================================================
import { appendFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname } from "node:path";

const LOG_PATH = process.env.A11OY_LOG_PATH ?? "/home/user/workspace/cto_acceptance_log.jsonl";

export function logAcceptance(entry: {
  action: string;
  files?: string[];
  doctrine: DoctrineGateResult;
  agent: string;
}): void {
  try {
    if (!existsSync(dirname(LOG_PATH))) mkdirSync(dirname(LOG_PATH), { recursive: true });
    appendFileSync(LOG_PATH, JSON.stringify({ ts: new Date().toISOString(), ...entry }) + "\n");
  } catch (e) {
    // never crash on logging failure
    console.error("a11oy log failed:", e);
  }
}
