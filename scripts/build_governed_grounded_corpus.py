#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Build the governed-grounded SFT corpus from this repository at a pinned commit.

No model writes any text here. Every ANSWER is copied from the source at the
pinned commit; every ABSTAIN pairs a real question with a context that does not
contain what it asks for. That makes the gate decision depend on the evidence
in the context, not on how the question is worded.

Item types
  section  quote what a named section says
  label    report the status label the source attaches to a statement
  lean     state a Lean declaration exactly as written

Splits are by source FILE (sha256 of the path), so no held-out file is ever a
question source or a context in train.

Usage:
  python3 scripts/build_governed_grounded_corpus.py --repo . --out OUT [--commit SHA]
Exit codes: 0 gate passed, 1 gate failed (nothing should be published), 2 usage.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

SCHEMA = "szl.governed-grounded-sft/v1"
REPO_NAME = "a11oy"
SYSTEM_PROMPT = (
    "You are an SZL governed assistant. Use only the CONTEXT. "
    "The first line of your reply is the gate decision: ANSWER or ABSTAIN. "
    "ANSWER only when the context contains what the question asks for; copy the "
    "source wording, keep its status labels unchanged, and end with the Source line. "
    "Otherwise ABSTAIN, say what is missing and what the context does cover, "
    "and do not answer from memory."
)
LABELS = ("MEASURED", "SAMPLE", "MODELED", "ROADMAP", "VERIFIED", "CONJECTURE",
          "PROPOSED", "UNSIGNED", "BLOCKED", "UNAVAILABLE", "DEGRADED")
LABEL_RE = re.compile(r"\b(" + "|".join(LABELS) + r")\b")
SKIP_PREFIXES = ("node_modules/", "static-vendor/", ".github/", "evidence/", "__tests__/",
                 "tests/", "console/assets/", "docs/papers/ouroboros-archive/", "docs/doctrine/")
# Files whose job is to enumerate banned tokens or hostile inputs are never sources.
SKIP_PARTS = ("adversarial", "RED_TEAM", "test-fixtures", "AGENT_DOCTRINE_ENFORCEMENT")
SKIP_NAMES = ("CHANGELOG.md", "FIX_LOG.md", "LICENSE", "NOTICE", "NOTICES.md")
SECRET_RE = re.compile(r"(hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
                       r"AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|xox[baprs]-[A-Za-z0-9-]{10,})")
HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
LEAN_DECL_RE = re.compile(
    r"^(?:@\[[^\]\n]*\]\s*)?(?:(?:private|protected|noncomputable)\s+)*(theorem|lemma)\s+([A-Za-z_][\w.']*)", re.M)
BARE_LEADING_RE = re.compile(r"\bleading\b", re.I)
MAX_CONTEXT = 2400
MAX_PER_FILE = {"section": 10, "label": 8, "lean": 8}
ABSTAIN_SHARE = 0.67          # share of positives that get an ABSTAIN twin
GATE = {"min_train_distinct_questions": 2000, "min_mode_share": 0.25, "min_heldout": 100}


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True).stdout


def h(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def frac(text):
    """Deterministic value in [0, 1) from text."""
    return int(h(text)[:12], 16) / float(16 ** 12)


def split_of(path):
    f = frac("split:" + path)
    return "train" if f < 0.8 else ("validation" if f < 0.9 else "heldout")


def load_allowlist(repo, commit):
    try:
        raw = git(repo, "show", commit + ":.doctrine-allowlist").decode("utf-8", "replace")
    except subprocess.CalledProcessError:
        return []
    return [l.strip() for l in raw.splitlines() if l.strip() and not l.startswith("#")]


def allowlisted(path, entries):
    for e in entries:
        if e.endswith("/"):
            if path.startswith(e):
                return True
        elif path == e or path.startswith(e + "/"):
            return True
    return False


def load_banned_regex(repo, commit):
    """Reuse the doctrine gate's own ban-list instead of copying it here."""
    src = git(repo, "show", commit + ":scripts/check_banned_tokens.py").decode("utf-8")
    m = re.search(r"^BANNED_NO_LEADING = re\.compile\((.*?)^\)", src, re.S | re.M)
    if not m:
        raise SystemExit("cannot locate BANNED_NO_LEADING in scripts/check_banned_tokens.py")
    ns = {"re": re}
    exec("R = re.compile(" + m.group(1) + ")", ns)  # own repo code at the pinned commit
    return ns["R"]


def clean_md(text):
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return text


def squash(text):
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def md_sections(text):
    """Yield (heading_path, body) for each heading with a prose body."""
    stack, cur, body = [], None, []
    out = []

    def flush():
        if cur is not None:
            out.append((" > ".join(t for _, t in cur), squash("\n".join(body))))

    for line in clean_md(text).splitlines():
        m = HEADING_RE.match(line)
        if m:
            flush()
            level, title = len(m.group(1)), re.sub(r"[*_`]", "", m.group(2)).strip()
            stack = [s for s in stack if s[0] < level] + [(level, title)]
            cur, body = list(stack), []
        elif cur is not None:
            body.append(line)
    flush()
    return [(p, b) for p, b in out if p]


def norm_ws(text):
    return " ".join(text.split())


def first_sentences(body, lo=120, hi=600):
    """Leading whole sentences of the first prose paragraph, or None.

    One paragraph only, so the extract is contiguous in the context (modulo whitespace).
    """
    for block in re.split(r"\n\s*\n", body):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines or any(l.startswith(("|", "- ", "* ", "+ ", ">")) or re.match(r"\d+[.)] ", l) for l in lines):
            continue
        flat = " ".join(lines)
        if len(flat) < lo or len(flat.split()) < 20:
            continue
        if len(flat) <= hi:
            return flat
        cut = flat[:hi]
        end = max(cut.rfind(". "), cut.rfind(".) "), cut.rfind("; "))
        if end >= lo:
            return cut[:end + 1].strip()
    return None


def source_tag(commit, path, where):
    return "%s@%s:%s § %s" % (REPO_NAME, commit[:7], path, where)


def context_block(tag, text):
    return "[source: %s]\n%s" % (tag, text[:MAX_CONTEXT].rstrip())


def harvest_md(path, text, commit):
    """Return (contexts, positives) for one markdown file."""
    contexts, positives = [], []
    n = {"section": 0, "label": 0}
    for hpath, body in md_sections(text):
        if len(body) < 200:
            continue
        tag = source_tag(commit, path, hpath)
        ctx = {"path": path, "where": hpath, "tag": tag, "text": context_block(tag, body), "kind": "md",
               "body_sha": h(norm_ws(body[:MAX_CONTEXT]))}
        contexts.append(ctx)
        extract = first_sentences(body)
        if extract and extract in norm_ws(ctx["text"]) and n["section"] < MAX_PER_FILE["section"]:
            n["section"] += 1
            positives.append({
                "item_type": "section", "ctx": ctx, "needle": hpath.split(" > ")[-1], "core": extract,
                "question": 'What does the section "%s" of %s say?' % (hpath, path),
                "answer": "ANSWER\n%s\nSource: %s" % (extract, tag),
                "missing": 'the section "%s" of %s' % (hpath, path)})
        for line in body.splitlines():
            if n["label"] >= MAX_PER_FILE["label"]:
                break
            stmt = re.sub(r"^[\s>*\-+\d.)]+", "", line).strip()
            found = LABEL_RE.findall(stmt)
            if len(found) != 1 or not 70 <= len(stmt) <= 320 or stmt.startswith("|") or stmt not in ctx["text"]:
                continue
            label = found[0]
            masked = LABEL_RE.sub("____", stmt)
            n["label"] += 1
            positives.append({
                "item_type": "label", "ctx": ctx, "needle": stmt, "core": stmt,
                "question": 'Which status label fills the blank in this statement from %s? "%s"' % (path, masked),
                "answer": 'ANSWER\n%s\nThe source reads: "%s"\nSource: %s' % (label, stmt, tag),
                "missing": "that statement"})
    return contexts, positives


def harvest_lean(path, text, commit):
    contexts, positives = [], []
    decls = list(LEAN_DECL_RE.finditer(text))
    for i, m in enumerate(decls):
        end = text.find(":=", m.start())
        if end < 0 or end - m.start() > 900:
            continue
        stmt = text[m.start():end].strip()
        lo = text.rfind("\n", 0, max(0, m.start() - 500)) + 1
        window = text[lo:lo + MAX_CONTEXT - 200]
        if stmt not in window:
            continue
        name = m.group(2)
        tag = source_tag(commit, path, name)
        ctx = {"path": path, "where": name, "tag": tag, "text": context_block(tag, window), "kind": "lean",
               "body_sha": h(name + "|" + norm_ws(window))}  # per declaration: short files share one window
        contexts.append(ctx)
        if len(positives) < MAX_PER_FILE["lean"]:
            positives.append({
                "item_type": "lean", "ctx": ctx, "needle": name, "core": stmt,
                "question": "State the Lean declaration `%s` from %s exactly as written, up to `:=`." % (name, path),
                "answer": "ANSWER\n%s\nSource: %s" % (stmt, tag),
                "missing": "a declaration named `%s`" % name})
    return contexts, positives


def pick_negative_context(pos, pool):
    """A context from the same split that cannot answer the question: same file first."""
    same_kind = [c for c in pool if c["kind"] == pos["ctx"]["kind"] and c is not pos["ctx"]
                 and pos["needle"] not in c["text"] and c["tag"] != pos["ctx"]["tag"]]
    if not same_kind:
        return None
    same_file = [c for c in same_kind if c["path"] == pos["ctx"]["path"]]
    cands = same_file or same_kind
    return min(cands, key=lambda c: h(pos["question"] + "|" + c["tag"]))


def record(question, ctx, answer, mode, pos, commit):
    user = "CONTEXT\n%s\n\nQUESTION\n%s" % (ctx["text"], question)
    return {
        "id": h(user)[:16],
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": user},
                     {"role": "assistant", "content": answer}],
        "gate_mode": mode, "item_type": pos["item_type"], "question": question,
        "source": {"repo": REPO_NAME, "commit": commit, "question_path": pos["ctx"]["path"],
                   "context_path": ctx["path"], "context_where": ctx["where"],
                   "context_sha256": h(ctx["text"])},
        "teacher": "none: extractive from source at pinned commit",
    }


def build(repo, commit):
    allow = load_allowlist(repo, commit)
    banned = load_banned_regex(repo, commit)
    paths = git(repo, "ls-tree", "-r", "--name-only", commit).decode("utf-8", "replace").splitlines()
    per_split = {s: {"contexts": [], "positives": []} for s in ("train", "validation", "heldout")}
    stats = {"files_seen": 0, "files_used": 0, "dropped_banned": 0, "dropped_secret": 0,
             "dropped_duplicate_context": 0, "dropped_duplicate_answer": 0,
             "allowlisted_files_read": 0}
    seen_ctx, seen_core = set(), set()   # global, so mirrored files cannot straddle splits
    for path in sorted(paths):
        ext = os.path.splitext(path)[1]
        if ext not in (".md", ".lean") or path.startswith(SKIP_PREFIXES) or "/node_modules/" in path:
            continue
        if os.path.basename(path) in SKIP_NAMES or any(part in path for part in SKIP_PARTS):
            continue
        stats["files_seen"] += 1
        stats["allowlisted_files_read"] += int(allowlisted(path, allow))
        try:
            text = git(repo, "show", "%s:%s" % (commit, path)).decode("utf-8")
        except (subprocess.CalledProcessError, UnicodeDecodeError):
            continue
        if len(text) > 400000:
            continue
        ctxs, poss = (harvest_md if ext == ".md" else harvest_lean)(path, text, commit)
        keep_ctx = []
        for c in ctxs:
            if SECRET_RE.search(c["text"]):
                stats["dropped_secret"] += 1
            elif banned.search(c["text"]) or BARE_LEADING_RE.search(c["text"]):
                stats["dropped_banned"] += 1
            elif c["body_sha"] in seen_ctx:
                stats["dropped_duplicate_context"] += 1
            else:
                seen_ctx.add(c["body_sha"])
                keep_ctx.append(c)
        kept = set(id(c) for c in keep_ctx)
        uniq_pos = []
        for p in poss:
            core = p["item_type"] + ":" + h(norm_ws(p["core"]))
            if id(p["ctx"]) not in kept:
                continue
            if core in seen_core:
                stats["dropped_duplicate_answer"] += 1
                continue
            seen_core.add(core)
            uniq_pos.append(p)
        poss = uniq_pos
        if poss:
            stats["files_used"] += 1
        bucket = per_split[split_of(path)]
        bucket["contexts"].extend(keep_ctx)
        bucket["positives"].extend(poss)
    out = {}
    for split, bucket in per_split.items():
        rows, seen = [], set()
        for pos in bucket["positives"]:
            rows.append(record(pos["question"], pos["ctx"], pos["answer"], "ANSWER", pos, commit))
            if frac("neg:" + pos["question"]) < ABSTAIN_SHARE:
                neg = pick_negative_context(pos, bucket["contexts"])
                if neg is not None:
                    answer = ("ABSTAIN\nThe context does not contain %s. It covers %s. "
                              "I will not answer from memory." % (pos["missing"], neg["tag"].split(":", 1)[1]))
                    rows.append(record(pos["question"], neg, answer, "ABSTAIN", pos, commit))
        uniq = []
        for r in sorted(rows, key=lambda r: r["id"]):
            if r["id"] not in seen:
                seen.add(r["id"])
                uniq.append(r)
        out[split] = uniq
    return out, stats


def gate_check(splits):
    """The relaunch gate from cto-decision-20261119-hold-distill-lanes, as code."""
    train = splits["train"]
    modes = {}
    for r in train:
        modes[r["gate_mode"]] = modes.get(r["gate_mode"], 0) + 1
    total = max(1, len(train))
    paths = {s: set(p for r in rows for p in (r["source"]["question_path"], r["source"]["context_path"]))
             for s, rows in splits.items()}
    ids = [r["id"] for rows in splits.values() for r in rows]
    checks = {
        "train_distinct_questions": len(set(r["question"] for r in train)),
        "train_rows": len(train),
        "mode_counts_train": modes,
        "min_mode_share_train": round(min([modes.get("ANSWER", 0), modes.get("ABSTAIN", 0)]) / total, 4),
        "heldout_rows": len(splits["heldout"]),
        "path_overlap_train_heldout": len(paths["train"] & paths["heldout"]),
        "path_overlap_train_validation": len(paths["train"] & paths["validation"]),
        "duplicate_prompts": len(ids) - len(set(ids)),
        "context_overlap_train_heldout": len(
            set(r["source"]["context_sha256"] for r in train)
            & set(r["source"]["context_sha256"] for r in splits["heldout"])),
        "answer_overlap_train_heldout": len(
            set(r["messages"][2]["content"].split("\nSource:")[0] for r in train if r["gate_mode"] == "ANSWER")
            & set(r["messages"][2]["content"].split("\nSource:")[0] for r in splits["heldout"]
                  if r["gate_mode"] == "ANSWER")),
        "teacher": "none (extractive); the teacher-capability condition does not apply",
    }
    failures = []
    if checks["train_distinct_questions"] < GATE["min_train_distinct_questions"]:
        failures.append("fewer than %d distinct train questions" % GATE["min_train_distinct_questions"])
    if checks["min_mode_share_train"] < GATE["min_mode_share"]:
        failures.append("ANSWER or ABSTAIN below %.0f%% of train" % (100 * GATE["min_mode_share"]))
    if checks["heldout_rows"] < GATE["min_heldout"]:
        failures.append("held-out split too small")
    if checks["path_overlap_train_heldout"] or checks["path_overlap_train_validation"]:
        failures.append("a source file appears in more than one split")
    if checks["duplicate_prompts"]:
        failures.append("duplicate prompts")
    if checks["context_overlap_train_heldout"] or checks["answer_overlap_train_heldout"]:
        failures.append("train and held-out share a context or an answer")
    checks["failures"] = failures
    checks["passed"] = not failures
    return checks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--commit", default="HEAD")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    commit = git(a.repo, "rev-parse", a.commit).decode().strip()
    splits, stats = build(a.repo, commit)
    checks = gate_check(splits)
    os.makedirs(a.out, exist_ok=True)
    files = {}
    for split, rows in splits.items():
        name = split + ".jsonl"
        data = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
        with open(os.path.join(a.out, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
        by_type = {}
        for r in rows:
            k = r["item_type"] + "/" + r["gate_mode"]
            by_type[k] = by_type.get(k, 0) + 1
        files[name] = {"rows": len(rows), "sha256": h(data), "by_type_and_mode": by_type}
    with open(__file__, "rb") as f:
        builder_sha = hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()
    manifest = {"schema": SCHEMA, "source": {"repo": "szl-holdings/" + REPO_NAME, "commit": commit},
                "builder": {"path": "scripts/build_governed_grounded_corpus.py", "sha256": builder_sha},
                "system_prompt_sha256": h(SYSTEM_PROMPT), "files": files, "harvest": stats, "gate": checks}
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"files": {k: v["rows"] for k, v in files.items()}, "gate": checks}, indent=1))
    return 0 if checks["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
