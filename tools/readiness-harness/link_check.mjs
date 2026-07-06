#!/usr/bin/env node
// Link / typo checker for the a11oy readiness harness.
//
// Two jobs:
//  1) TYPO GATE (always fails): scan the repo for known-bad org slugs that look
//     right but 404 — notably "szl-holding" (missing trailing 's'; the org is
//     "szl-holdings") and "SZLHOLDING" (HF org is "SZLHOLDINGS"). These are silent
//     dead links the eye skips over.
//  2) REACHABILITY (best-effort): de-dupe external http(s) URLs found in the
//     console + key pages and HEAD/GET them with throttling. 4xx/5xx are reported;
//     timeouts on allow-listed flaky hosts are warnings, not failures.
//
// No external deps — Node >= 18 global fetch.
//   node link_check.mjs [--root <repo>] [--reach] [--soft] [--concurrency 4]

import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, extname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = String(argv("root", join(HERE, "..", "..")));
const REACH = !!argv("reach", false);
const SOFT = !!argv("soft", false);
const CONCURRENCY = parseInt(argv("concurrency", "4"), 10);
const TIMEOUT_MS = 12000;

function argv(name, def) {
  const i = process.argv.indexOf("--" + name);
  if (i === -1) return def;
  const v = process.argv[i + 1];
  return v && !v.startsWith("--") ? v : true;
}

// Known typos: [regex, human message]. Word-boundary guarded so "szl-holdings"
// (correct) never matches the "szl-holding" rule.
const TYPOS = [
  [/szl-holding(?![s\w-])/g, 'GitHub org typo: "szl-holding" should be "szl-holdings"'],
  [/github\.com\/szl-holding(?![s\w-])/gi, 'GitHub URL typo: org is "szl-holdings"'],
  [/\bSZLHOLDING(?![S\w])/g, 'HF org typo: "SZLHOLDING" should be "SZLHOLDINGS"'],
  [/huggingface\.co\/SZLHOLDING(?![S\w])/g, 'HF URL typo: org is "SZLHOLDINGS"'],
  [/a11oy\.ne\b(?!t)/g, 'domain typo: "a11oy.ne" should be "a-11-oy.com"'],
  [/szl-holdings\.githu\b(?!b)/g, 'Pages URL typo: "githu" should be "github"'],
];

const SCAN_EXT = new Set([".html", ".md", ".py", ".mjs", ".js", ".ts", ".json", ".yml", ".yaml", ".cff", ".toml"]);
const SKIP_DIR = new Set([".git", "node_modules", ".venv", "dist", "build", "__pycache__", ".uds-build-tmp"]);

function walk(dir, out = []) {
  let ents;
  try { ents = readdirSync(dir); } catch { return out; }
  for (const name of ents) {
    if (SKIP_DIR.has(name)) continue;
    const p = join(dir, name);
    let st;
    try { st = statSync(p); } catch { continue; }
    if (st.isDirectory()) walk(p, out);
    else if (SCAN_EXT.has(extname(name))) out.push(p);
  }
  return out;
}

function scanTypos(files) {
  const hits = [];
  for (const f of files) {
    // The checker itself defines the bad patterns as regexes — never flag it.
    if (f.endsWith("link_check.mjs")) continue;
    let text;
    try { text = readFileSync(f, "utf8"); } catch { continue; }
    for (const [re, msg] of TYPOS) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(text)) !== null) {
        const line = text.slice(0, m.index).split("\n").length;
        hits.push({ file: f.replace(ROOT + "/", ""), line, match: m[0], msg });
        if (re.lastIndex === m.index) re.lastIndex++;
      }
    }
  }
  return hits;
}

function extractUrls(files) {
  const urls = new Set();
  const re = /https?:\/\/[^\s"'`)<>\\]+/g;
  for (const f of files) {
    if (![".html", ".md", ".py"].includes(extname(f))) continue;
    let text;
    try { text = readFileSync(f, "utf8"); } catch { continue; }
    let m;
    while ((m = re.exec(text)) !== null) {
      let u = m[0].replace(/[.,);:]+$/, "");
      // skip templated / placeholder / example URLs
      if (/[{}<>$]|example\.com|localhost|127\.0\.0\.1|\$\{/.test(u)) continue;
      urls.add(u);
    }
  }
  return [...urls];
}

// hosts that rate-limit or block HEAD from CI — timeouts here are warnings
const FLAKY_HOSTS = new Set(["nvd.nist.gov", "www.cisa.gov", "api.github.com", "huggingface.co", "doi.org", "zenodo.org"]);

async function check(url) {
  const ctrl = new AbortController();
  const to = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    let res = await fetch(url, { method: "HEAD", redirect: "follow", signal: ctrl.signal });
    if (res.status === 405 || res.status === 403 || res.status === 501) {
      res = await fetch(url, { method: "GET", redirect: "follow", signal: ctrl.signal });
    }
    return { url, status: res.status };
  } catch (e) {
    return { url, status: 0, error: String(e.name || e) };
  } finally {
    clearTimeout(to);
  }
}

async function pool(items, n, fn) {
  const out = [];
  let i = 0;
  await Promise.all(Array.from({ length: Math.min(n, items.length) }, async () => {
    while (i < items.length) { const idx = i++; out[idx] = await fn(items[idx]); }
  }));
  return out;
}

(async () => {
  const files = walk(ROOT);
  console.error(`[link-check] scanning ${files.length} files under ${ROOT}`);

  const typos = scanTypos(files);
  if (typos.length) {
    console.error(`\n[link-check] ✗ ${typos.length} typo(s) found:`);
    for (const t of typos) console.error(`  ${t.file}:${t.line}  "${t.match}"  — ${t.msg}`);
  } else {
    console.error("[link-check] ✓ no known org/domain typos");
  }

  let dead = [];
  if (REACH) {
    const urls = extractUrls(files);
    console.error(`[link-check] reachability over ${urls.length} unique URLs…`);
    const results = await pool(urls, CONCURRENCY, check);
    for (const r of results) {
      const host = (() => { try { return new URL(r.url).host; } catch { return ""; } })();
      const bad = r.status === 0 ? !FLAKY_HOSTS.has(host) : r.status >= 400;
      if (r.status === 0 && FLAKY_HOSTS.has(host)) {
        console.error(`  warn  (flaky) ${r.url}`);
      } else if (bad) {
        dead.push(r);
        console.error(`  DEAD  ${r.status || r.error} ${r.url}`);
      }
    }
    if (!dead.length) console.error("[link-check] ✓ no dead external links");
  }

  const fail = typos.length > 0 || dead.length > 0;
  console.error(`\n[link-check] ${fail ? "FAIL" : "PASS"} — typos=${typos.length} dead=${dead.length}`);
  if (fail && !SOFT) process.exit(1);
})();
