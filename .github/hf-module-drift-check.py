#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - Doctrine v11
"""
GitHub<->HF-Space module-drift guard.

The Dockerfile of this Space repo COPYs many feature modules (szl_*.py, *.html,
*.json, data dirs, ...). hf-sync.yml only mirrors README + the front-door
HTML/JS, so a feature module can silently diverge between the GitHub source of
truth (szl-holdings/<repo>) and the LIVE Hugging Face Space
(SZLHOLDINGS/<repo>) -- as happened when the Space ran a newer v1.1 of
szl_evidence_research.py that GitHub never received.

This script parses every `COPY` source in the Dockerfile, expands directories
and globs, then compares each file's content between the two sides by git-blob
SHA (no full download needed for the comparison). For every drifted file it
fetches the last-commit DATE on both sides and NAMES which side is ahead -- it
deliberately does NOT auto-overwrite, because drift can run either direction.

Comparison is cheap: HF's tree API and GitHub's git-tree both expose the git
blob OID (sha1), which is identical iff the content is identical.

Two run modes:
  * CI (default): GitHub side = the checked-out working tree (--repo-root .).
  * Test:        --github-remote pulls the GitHub side from the git-tree API,
                 so the check can run without a checkout.

Exit status: non-zero if any non-allowlisted drift is found, unless --warn-only.

stdlib only (no huggingface_hub / requests) so it runs on a bare runner.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HF_HOST = "https://huggingface.co"
GH_API = "https://api.github.com"
GH_RAW = "https://raw.githubusercontent.com"

UA = {"User-Agent": "hf-module-drift-check/1.0"}


# --------------------------------------------------------------------------- #
# HTTP helpers (stdlib, with retry + redirect following)
# --------------------------------------------------------------------------- #
def _http(url, headers=None, want_headers=False, retries=7):
    last = None
    hdrs = dict(UA)
    if headers:
        hdrs.update(headers)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = resp.read()
                if want_headers:
                    return resp.status, body, dict(resp.headers)
                return resp.status, body, None
        except urllib.error.HTTPError as e:
            # 404 is a real answer (file missing), not a transient error.
            if e.code in (404, 401, 403):
                if want_headers:
                    return e.code, b"", dict(e.headers or {})
                return e.code, b"", None
            last = e
            # 429 / 5xx are transient (HF rate-limits hard when sibling repos
            # poll at once). Honor Retry-After, else exponential backoff + jitter.
            if e.code == 429 or 500 <= e.code < 600:
                ra = (e.headers or {}).get("Retry-After")
                try:
                    delay = float(ra) if ra else min(60.0, 2.0 * (2 ** attempt))
                except ValueError:
                    delay = min(60.0, 2.0 * (2 ** attempt))
                time.sleep(delay + random.uniform(0, 1.5))
                continue
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        time.sleep(1.5 * (attempt + 1) + random.uniform(0, 0.75))
    raise RuntimeError(f"GET failed after {retries} tries: {url}: {last}")


def gh_headers():
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("SZL_GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


# --------------------------------------------------------------------------- #
# Dockerfile COPY parsing
# --------------------------------------------------------------------------- #
def parse_copy_sources(dockerfile_text):
    """Return the list of COPY/ADD *source* paths declared in the Dockerfile.

    Handles line continuations, --flag options, the JSON-array form, and skips
    multi-stage `COPY --from=<stage>` lines (those sources are not repo files).
    """
    # Join backslash line-continuations into single logical lines.
    logical = []
    buf = ""
    for raw in dockerfile_text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not buf and (stripped.startswith("#") or stripped == ""):
            continue
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
            continue
        buf += line
        logical.append(buf)
        buf = ""
    if buf:
        logical.append(buf)

    sources = []
    for line in logical:
        m = re.match(r"^\s*(COPY|ADD)\s+(.*)$", line, re.IGNORECASE)
        if not m:
            continue
        rest = m.group(2).strip()
        # Strip an inline comment that isn't part of a quoted path.
        # JSON-array form: COPY ["src", "dest"]
        if rest.startswith("["):
            try:
                arr = json.loads(rest)
            except json.JSONDecodeError:
                continue
            if len(arr) >= 2:
                sources.extend(arr[:-1])
            continue
        toks = rest.split()
        # Drop --flag options; skip the whole line if it's a build-stage copy.
        skip = False
        clean = []
        for t in toks:
            if t.startswith("--"):
                if t.lower().startswith("--from"):
                    skip = True
                continue
            clean.append(t)
        if skip or len(clean) < 2:
            continue
        # Last token is the destination.
        sources.extend(clean[:-1])
    # Normalise: drop leading "./", dedupe, keep order.
    out = []
    seen = set()
    for s in sources:
        s = s.strip().lstrip("./") or s.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


# --------------------------------------------------------------------------- #
# GitHub side: file -> git-blob-sha map
# --------------------------------------------------------------------------- #
def git_blob_sha1(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob " + str(len(data)).encode() + b"\0")
    h.update(data)
    return h.hexdigest()


def github_tree_local(repo_root):
    """Map repo-relative path -> git blob sha1, from the local checkout."""
    out = {}
    root = os.path.abspath(repo_root)
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirpath.split(os.sep):
            continue
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                with open(full, "rb") as fh:
                    data = fh.read()
            except OSError:
                continue
            out[rel] = git_blob_sha1(data)
    return out


def github_tree_remote(github_repo, ref="main"):
    """Map path -> git blob sha, from the GitHub git-tree API (test mode)."""
    url = f"{GH_API}/repos/{github_repo}/git/trees/{ref}?recursive=1"
    status, body, _ = _http(url, headers=gh_headers())
    if status != 200:
        raise RuntimeError(f"GitHub tree {github_repo}@{ref}: HTTP {status}")
    j = json.loads(body)
    if j.get("truncated"):
        print("::warning::GitHub git-tree response was truncated; "
              "some files may be missing from the remote comparison.")
    out = {}
    for e in j.get("tree", []):
        if e.get("type") == "blob":
            out[e["path"]] = e["sha"]
    return out


# --------------------------------------------------------------------------- #
# Hugging Face side: file -> {oid, lfs_oid, size}
# --------------------------------------------------------------------------- #
def _hf_paginated(url):
    """Yield every JSON entry across all `Link: rel=next` pages."""
    pages = 0
    while url:
        status, body, hdrs = _http(url, want_headers=True)
        if status != 200:
            raise RuntimeError(f"HF API {url}: HTTP {status}")
        for e in json.loads(body):
            yield e
        link = (hdrs or {}).get("Link") or (hdrs or {}).get("link") or ""
        nxt = None
        for part in link.split(","):
            if 'rel="next"' in part:
                m = re.search(r"<([^>]+)>", part)
                if m:
                    nxt = m.group(1)
        url = nxt
        pages += 1
        if pages > 500:  # safety valve
            break


def hf_tree(hf_repo, ref="main"):
    """Map path -> entry, from the HF Space tree API (recursive, paginated)."""
    out = {}
    url = (f"{HF_HOST}/api/spaces/{hf_repo}/tree/{ref}"
           f"?recursive=true&expand=false")
    for e in _hf_paginated(url):
        if e.get("type") == "file":
            lfs = e.get("lfs") or {}
            out[e["path"]] = {
                "oid": e.get("oid"),
                "lfs_oid": lfs.get("oid"),
                "size": e.get("size"),
            }
    return out


def hf_dir_dates(hf_repo, directory, ref="main"):
    """Map path -> last-commit ISO date for files directly in `directory`,
    via the expand=true tree API. Cached per directory by the caller."""
    d = directory.strip("/")
    sub = f"/{d}" if d else ""
    url = f"{HF_HOST}/api/spaces/{hf_repo}/tree/{ref}{sub}?expand=true"
    out = {}
    try:
        for e in _hf_paginated(url):
            if e.get("type") == "file":
                lc = e.get("lastCommit") or {}
                out[e["path"]] = lc.get("date")
    except RuntimeError:
        return {}
    return out


def github_file_date(github_repo, path, ref="main"):
    url = f"{GH_API}/repos/{github_repo}/commits?path={urllib.parse.quote(path)}&sha={ref}&per_page=1"
    try:
        status, body, _ = _http(url, headers=gh_headers())
    except RuntimeError:
        return None
    if status != 200:
        return None
    arr = json.loads(body)
    if not arr:
        return None
    commit = arr[0].get("commit", {})
    return (commit.get("committer") or commit.get("author") or {}).get("date")


# --------------------------------------------------------------------------- #
# Source expansion + exclusion
# --------------------------------------------------------------------------- #
def is_ignored(path, allow):
    for pat in allow.get("ignore_paths", []):
        if fnmatch.fnmatch(path, pat):
            return True
    _, ext = os.path.splitext(path)
    if ext.lower() in {e.lower() for e in allow.get("ignore_extensions", [])}:
        return True
    return False


def expand_targets(sources, gh_files, hf_files, allow):
    """Turn COPY sources (files, dirs, globs) into a concrete set of paths to
    compare. For a directory we take the UNION of files under it on both sides
    so HF-only additions are also caught."""
    gh_paths = set(gh_files)
    hf_paths = set(hf_files)
    targets = set()
    for src in sources:
        s = src.rstrip("/")
        if s in gh_paths or s in hf_paths:
            targets.add(s)
            continue
        # Directory?
        pref = s + "/"
        dir_members = {p for p in gh_paths | hf_paths if p.startswith(pref)}
        if dir_members:
            targets |= dir_members
            continue
        # Glob?
        if any(ch in s for ch in "*?["):
            globbed = {p for p in gh_paths | hf_paths if fnmatch.fnmatch(p, s)}
            targets |= globbed
            continue
        # Unresolved COPY source (present on neither side) -> still report.
        targets.add(s)
    # Drop ignored paths.
    return {t for t in targets if not is_ignored(t, allow)}


# --------------------------------------------------------------------------- #
# Main comparison
# --------------------------------------------------------------------------- #
def compare(args):
    if args.github_remote:
        status, body, _ = _http(
            f"{GH_RAW}/{args.github_repo}/{args.ref}/Dockerfile",
            headers=gh_headers())
        if status != 200:
            raise RuntimeError(f"fetch remote Dockerfile: HTTP {status}")
        dockerfile_text = body.decode("utf-8", "replace")
    else:
        with open(os.path.join(args.repo_root, "Dockerfile"), "rb") as fh:
            dockerfile_text = fh.read().decode("utf-8", "replace")
    sources = parse_copy_sources(dockerfile_text)

    if args.github_remote:
        gh_files = github_tree_remote(args.github_repo, args.ref)
    else:
        gh_files = github_tree_local(args.repo_root)

    hf_files = hf_tree(args.hf_repo, args.ref)

    allow = {}
    if args.allow and os.path.exists(args.allow):
        with open(args.allow) as fh:
            txt = fh.read().strip()
        if txt:
            allow = json.loads(txt)
    accepted = allow.get("accepted_divergences", {})

    targets = sorted(expand_targets(sources, gh_files, hf_files, allow))

    # Every finding carries a severity: "error" (real GitHub<->HF divergence,
    # fails the job) or "warn" (allowlisted backlog, or a COPY source absent on
    # BOTH sides -- the latter is dockerfile-copy-guard's domain, not drift).
    findings = []
    _hf_date_cache = {}

    def add(entry, base_severity):
        if entry["path"] in accepted:
            entry["severity"] = "warn"
            entry["reason"] = accepted.get(entry["path"])
        else:
            entry["severity"] = base_severity
        findings.append(entry)

    for path in targets:
        gh_sha = gh_files.get(path)
        hf = hf_files.get(path)

        if gh_sha is None and hf is None:
            # Present in neither -> not a GitHub<->HF drift; soft warn only.
            findings.append({"path": path, "kind": "missing-both", "severity": "warn",
                             "detail": "COPY source present on neither GitHub nor HF "
                                       "(dockerfile-copy-guard's domain, not drift)"})
            continue
        if gh_sha is not None and hf is None:
            add({"path": path, "kind": "missing-hf", "ahead": "github",
                 "detail": "present on GitHub, MISSING on the live HF Space"}, "error")
            continue
        if gh_sha is None and hf is not None:
            add({"path": path, "kind": "missing-github", "ahead": "huggingface",
                 "detail": "present on the live HF Space, MISSING on GitHub"}, "error")
            continue

        # Both present.
        if hf.get("lfs_oid"):
            # LFS on the Space: git-blob OID vs sha256 aren't comparable cheaply.
            # Source modules are never LFS, so this only fires for un-excluded
            # binary assets -> flag for manual review.
            add({"path": path, "kind": "lfs",
                 "detail": "stored as LFS on HF Space; not cheaply comparable "
                           "-- exclude via ignore_paths if it is a vendored asset"}, "error")
            continue

        if gh_sha == hf.get("oid"):
            continue  # byte-identical -> in sync

        # Content drift -> name which side is ahead by last-commit date.
        gh_date = github_file_date(args.github_repo, path, args.ref)
        d = os.path.dirname(path)
        if d not in _hf_date_cache:
            _hf_date_cache[d] = hf_dir_dates(args.hf_repo, d, args.ref)
        hf_date = _hf_date_cache[d].get(path)
        if gh_date and hf_date:
            ahead = "github" if gh_date > hf_date else ("huggingface" if hf_date > gh_date else "tied")
        elif gh_date and not hf_date:
            ahead = "github?"
        elif hf_date and not gh_date:
            ahead = "huggingface?"
        else:
            ahead = "unknown"
        add({"path": path, "kind": "drift", "ahead": ahead,
             "github_sha": gh_sha, "hf_oid": hf.get("oid"),
             "github_date": gh_date, "hf_date": hf_date}, "error")

    findings.sort(key=lambda e: (e["severity"] != "error", e["path"]))
    errors = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] == "warn"]

    report = {
        "schema": 1,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "github_repo": args.github_repo,
        "hf_repo": args.hf_repo,
        "ref": args.ref,
        "copy_sources": len(sources),
        "files_compared": len(targets),
        "error_count": len(errors),
        "warn_count": len(warns),
        "findings": findings,
    }
    return report, errors, warns


def fmt(entry):
    ahead = entry.get("ahead")
    tail = f"  ahead: {ahead}" if ahead else ""
    if entry["kind"] == "drift":
        return (f"  DRIFT  {entry['path']}{tail}\n"
                f"         (github {entry.get('github_date')} | hf {entry.get('hf_date')})")
    return f"  {entry.get('kind','?').upper():13} {entry['path']}{tail} -- {entry.get('detail','')}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", default=".", help="local checkout root (GitHub side in CI mode)")
    ap.add_argument("--github-repo", required=True, help="e.g. szl-holdings/a11oy")
    ap.add_argument("--hf-repo", required=True, help="e.g. SZLHOLDINGS/a11oy")
    ap.add_argument("--ref", default="main")
    ap.add_argument("--allow", default=".github/hf-module-drift-allow.json")
    ap.add_argument("--report-out", default="")
    ap.add_argument("--github-remote", action="store_true",
                    help="pull GitHub side from the git-tree API (test mode; no checkout)")
    ap.add_argument("--warn-only", action="store_true",
                    help="never exit non-zero (ratchet: land green over a backlog)")
    args = ap.parse_args()

    report, errors, warns = compare(args)

    print(f"== HF module-drift guard: {args.github_repo}  <->  {args.hf_repo} ({args.ref}) ==")
    print(f"   COPY sources: {report['copy_sources']}   files compared: {report['files_compared']}")
    print(f"   errors (drift): {len(errors)}   warnings (allowlisted/absent): {len(warns)}")

    if warns:
        print("\n-- warnings (allowlisted backlog or absent-on-both; do not fail) --")
        for e in warns:
            print(fmt(e))
            print(f"::warning title=HF module drift::{e['path']} ({e.get('kind')}) "
                  f"ahead={e.get('ahead','n/a')}")
    if errors:
        print("\n-- DRIFT requiring a human to pick the direction (GitHub vs live HF Space) --")
        for e in errors:
            print(fmt(e))
            print(f"::error title=HF module drift::{e['path']} ({e.get('kind')}) "
                  f"ahead={e.get('ahead','?')} -- reconcile then commit; do NOT blind-overwrite "
                  f"(allowlist intentional divergence in {os.path.basename(args.allow)})")

    if args.report_out:
        with open(args.report_out, "w") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"\nreport written: {args.report_out}")

    if errors and not args.warn_only:
        print(f"\nFAIL: {len(errors)} drifted/one-sided COPY'd module(s) between GitHub "
              "and the live HF Space. A human must pick which side is the source of truth, "
              "reconcile, and commit -- the guard never auto-overwrites.")
        return 1
    print("\nOK: no unaccepted module drift between GitHub and the live HF Space.")
    return 0


if __name__ == "__main__":
    import urllib.parse  # noqa: E402  (used by github_file_date)
    sys.exit(main())
