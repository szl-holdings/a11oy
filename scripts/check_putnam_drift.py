#!/usr/bin/env python3
"""check_putnam_drift.py — keep a11oy's Putnam 2025 claims page honest.

a11oy ships an *embedded, transcribed* verdict for the canonical Putnam 2025 set
(``szl_putnam.py`` ``_PUTNAM``/``_SZL`` + the console ``putnam-2025-tab-patch``
fallback ``FB_PROBS``/``FB_SZL``) plus headline ``N REAL / M DEMO / K OPEN``
counts in prose. The single source of truth is the immutable
``szl-holdings/lutar-lean`` commit recorded in ``DEFAULT_REF``: each
``Lutar/Putnam/P_*.lean`` carries an
``**Honest status: REAL|DEMO|OPEN**`` label (A6 uses a multi-line block whose
*general theorem* line carries the status), and the three
``Lutar/Putnam/SZL/*.lean`` originals declare ``All proofs are REAL`` in their
docstrings.

This guard fails loud when the a11oy embedded data drifts from that canonical
source — any per-problem label mismatch, any REAL/DEMO/OPEN count mismatch (in
the loader block, the console fallback, the literal count phrases, or the named
"X and Y are OPEN" prose), any missing/extra problem file, or any disagreement
between the loader and the console fallback.

Network: the canonical Lean labels are fetched from lutar-lean (public, no token
needed; ``GITHUB_TOKEN`` used if present to dodge rate limits). For the offline
negative-fixture self-test, set ``PUTNAM_DRIFT_FIXTURE=<dir>`` to read the
canonical ``Lutar/Putnam`` tree from a local directory instead of the network.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from types import ModuleType
from typing import Dict, List, Optional, Set, Tuple

REPO = "szl-holdings/lutar-lean"
PUTNAM_DIR = "Lutar/Putnam"
DEFAULT_REF = "baf483be3c832b64da47161b558e283d68da6650"
# Backward-compatible import for older guard tests. This value is an immutable
# commit, not a mutable branch.
DEFAULT_BRANCH = DEFAULT_REF

# A canonical Putnam problem file: P_A1.lean .. P_B6.lean (NOT the SZL/ or other
# non-Putnam .lean files that may share the directory).
PUTNAM_FILE_RE = re.compile(r"^P_[AB][1-6]\.lean$")
STATUS_RE = r"(REAL|DEMO|OPEN)"
VALID_STATUS = {"REAL", "DEMO", "OPEN"}
DILIGENCE_REL = os.path.join("docs", "SERIES_A_DILIGENCE.md")
DILIGENCE_BEGIN = "<!-- BEGIN GENERATED PUTNAM STATUS -->"
DILIGENCE_END = "<!-- END GENERATED PUTNAM STATUS -->"
TRUSTED_AXIOMS = {"propext", "Quot.sound", "Classical.choice"}


# ---------------------------------------------------------------------------
# Canonical source (lutar-lean) — live over HTTP, or a local fixture dir.
# ---------------------------------------------------------------------------
class Canonical:
    """Reads the canonical Lutar/Putnam tree from lutar-lean or a fixture dir."""

    def __init__(self, branch: str, fixture: Optional[str]) -> None:
        self.branch = branch
        self.fixture = fixture

    # -- listing -----------------------------------------------------------
    def _list_dir(self, rel: str) -> List[str]:
        """List file names in Lutar/Putnam/<rel> (rel='' = the Putnam dir).

        In fixture mode the fixture dir mirrors Lutar/Putnam itself.
        """
        if self.fixture:
            d = os.path.join(self.fixture, *rel.split("/")) if rel else self.fixture
            return sorted(os.listdir(d)) if os.path.isdir(d) else []
        path = PUTNAM_DIR + ("/" + rel if rel else "")
        url = "https://api.github.com/repos/%s/contents/%s?ref=%s" % (
            REPO, path, self.branch)
        data = json.loads(self._http(url, accept="application/vnd.github+json"))
        return sorted(e["name"] for e in data if e.get("type") == "file")

    # -- reading -----------------------------------------------------------
    def read(self, rel: str) -> str:
        """Read Lutar/Putnam/<rel> (rel may be 'P_A1.lean' or 'SZL/Foo.lean')."""
        full = "%s/%s" % (PUTNAM_DIR, rel)
        if self.fixture:
            p = os.path.join(self.fixture, *rel.split("/"))
            with open(p, "r", encoding="utf-8") as fh:
                return fh.read()
        url = "https://raw.githubusercontent.com/%s/%s/%s" % (
            REPO, self.branch, full)
        return self._http(url)

    def _http(self, url: str, accept: str = "text/plain") -> str:
        req = urllib.request.Request(url, headers={"Accept": accept})
        tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if tok:
            req.add_header("Authorization", "Bearer %s" % tok)
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return resp.read().decode("utf-8")

    # -- derived sets ------------------------------------------------------
    def putnam_files(self) -> List[str]:
        return [n for n in self._list_dir("") if PUTNAM_FILE_RE.match(n)]

    def szl_files(self) -> List[str]:
        names = self._list_dir("SZL")
        return ["SZL/%s" % n for n in names if n.endswith(".lean")]


# ---------------------------------------------------------------------------
# Canonical status extraction from a single .lean file.
# ---------------------------------------------------------------------------
def canonical_putnam_status(text: str) -> Optional[str]:
    """Derive the honest status of a canonical Putnam file.

    Single-token form: ``**Honest status: DEMO**``.
    Multi-line form (A6): ``**Honest status.**`` followed by a bullet naming the
    *general theorem* and its status, e.g.
    ``putnam_A6_correct_pow (the general theorem) — OPEN``.
    """
    m = re.search(r"Honest status:\s*\*{0,2}\s*" + STATUS_RE + r"\b", text)
    if m:
        return m.group(1)
    idx = text.find("Honest status")
    if idx == -1:
        return None
    tail = text[idx:idx + 1500]
    m2 = re.search(r"general theorem\).{0,40}?" + STATUS_RE + r"\b", tail, re.S)
    if m2:
        return m2.group(1)
    return None


def canonical_szl_status(text: str) -> Optional[str]:
    """SZL originals declare 'All proofs are REAL' in their docstring.

    The phrase may wrap across a line ('All proofs\\nare REAL'), so allow any
    whitespace between the words.
    """
    m = re.search(r"All proofs\s+are\s+" + STATUS_RE + r"\b", text)
    return m.group(1) if m else None


def strip_lean_comments_and_strings(text: str) -> str:
    """Remove Lean comments and string contents while preserving newlines."""
    out: List[str] = []
    i = 0
    block_depth = 0
    in_string = False
    while i < len(text):
        pair = text[i:i + 2]
        char = text[i]
        if block_depth:
            if pair == "/-":
                block_depth += 1
                out.extend("  ")
                i += 2
            elif pair == "-/":
                block_depth -= 1
                out.extend("  ")
                i += 2
            else:
                out.append("\n" if char == "\n" else " ")
                i += 1
            continue
        if in_string:
            if char == "\\" and i + 1 < len(text):
                out.extend("  ")
                i += 2
            elif char == '"':
                in_string = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if char == "\n" else " ")
                i += 1
            continue
        if pair == "/-":
            block_depth = 1
            out.extend("  ")
            i += 2
        elif pair == "--":
            while i < len(text) and text[i] != "\n":
                out.append(" ")
                i += 1
        elif char == '"':
            in_string = True
            out.append(" ")
            i += 1
        else:
            out.append(char)
            i += 1
    return "".join(out)


def mask_lean_attributes(rel: str, text: str, errors: List[str]) -> str:
    """Blank balanced ``@[...]`` attributes while preserving source offsets."""
    out = list(text)
    cursor = 0
    while True:
        start = text.find("@[", cursor)
        if start < 0:
            break
        depth = 0
        end = start + 1
        while end < len(text):
            char = text[end]
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    end += 1
                    break
            end += 1
        if depth != 0:
            errors.append(
                "canonical REAL %s: unterminated attribute syntax" % rel
            )
            end = len(text)
        for index in range(start, end):
            if out[index] != "\n":
                out[index] = " "
        cursor = end
    return "".join(out)


def instance_name_tail(tail: str) -> str:
    """Skip a balanced optional ``(priority := ...)`` instance prefix."""
    stripped = tail.lstrip()
    if not re.match(r"^\(\s*priority\s*:=", stripped):
        return stripped
    depth = 0
    for index, char in enumerate(stripped):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return stripped[index + 1:].lstrip()
    return stripped


def real_lean_declarations(rel: str, text: str, errors: List[str]) -> List[str]:
    """Return every externally auditable proof declaration in a REAL source."""
    clean = strip_lean_comments_and_strings(text)
    command_text = mask_lean_attributes(rel, clean, errors)
    forbidden = []
    if re.search(r"\b(?:sorry|sorryAx|admit)\b", clean):
        forbidden.append("sorry/sorryAx/admit")
    if re.search(
        r"(?m)^[ \t]*"
        r"(?:(?:private|public|protected|noncomputable|unsafe|partial|nonrec|"
        r"local|scoped)\s+)*"
        r"(?:axiom|constant)\b",
        command_text,
    ):
        forbidden.append("new axiom/constant declaration")
    if re.search(r"\bnative_decide\b", clean):
        forbidden.append("native_decide")
    for item in forbidden:
        errors.append("canonical REAL %s: forbidden %s" % (rel, item))

    declarations: List[str] = []
    scopes: List[Tuple[str, Optional[str]]] = []
    command_re = re.compile(
        r"(?m)^[ \t]*"
        r"(?P<modifiers>"
        r"(?:(?:private|public|protected|noncomputable|unsafe|partial|nonrec|"
        r"local|scoped)\s+)*)"
        r"(?P<kind>namespace|section|end|theorem|lemma|instance)\b"
    )
    commands = list(command_re.finditer(command_text))
    lean_name_part = r"(?:«[^»\r\n]+»|[^\s:({\[\],.]+)"
    lean_name = lean_name_part + r"(?:\." + lean_name_part + r")*"

    for index, command in enumerate(commands):
        kind = command.group("kind")
        stop = (
            commands[index + 1].start()
            if index + 1 < len(commands)
            else len(command_text)
        )
        tail = command_text[command.end():stop]
        same_line = tail.splitlines()[0] if tail else ""

        if kind == "namespace":
            name_match = re.match(r"[ \t]+(" + lean_name + r")", same_line)
            if name_match:
                scopes.append(("namespace", name_match.group(1)))
            continue
        if kind == "section":
            name_match = re.match(r"[ \t]+(" + lean_name + r")", same_line)
            scopes.append(("section", name_match.group(1) if name_match else None))
            continue
        if kind == "end":
            if scopes:
                scopes.pop()
            continue

        modifiers = set(command.group("modifiers").split())
        name_tail = instance_name_tail(tail) if kind == "instance" else tail.lstrip()
        name_match = re.match(r"(" + lean_name + r")", name_tail)
        if not name_match:
            if kind == "instance" and name_tail.startswith((":", "(", "[", "{")):
                # Anonymous instances receive generated names that cannot be
                # referenced from the separate imported audit module. Their
                # public dependents remain part of the external axiom audit.
                continue
            errors.append(
                "canonical REAL %s: %s declaration has no parseable name"
                % (rel, kind)
            )
            continue
        if modifiers & {"private", "local"}:
            # Private/local declarations are inaccessible to the imported
            # audit. Their public dependents remain covered by that audit.
            continue
        name = name_match.group(1)
        namespaces = [
            scope_name
            for scope_kind, scope_name in scopes
            if scope_kind == "namespace" and scope_name
        ]
        if name.startswith("_root_."):
            name = name[len("_root_."):]
        elif namespaces:
            name = ".".join(namespaces + [name])
        declarations.append(name)
    if not declarations:
        errors.append(
            "canonical REAL %s: no externally auditable public "
            "theorem/lemma/named-instance declarations found" % rel
        )
    return declarations


def module_name(rel: str) -> str:
    stem = rel[:-5] if rel.endswith(".lean") else rel
    return "Lutar.Putnam." + stem.replace("/", ".").replace("\\", ".")


def render_axiom_audit(real_sources: Dict[str, List[str]]) -> str:
    """Render a Lean audit that reports the axiom footprint of every REAL proof."""
    imports = [f"import {module_name(rel)}" for rel in sorted(real_sources)]
    prints = [
        f"#print axioms {decl}"
        for rel in sorted(real_sources)
        for decl in real_sources[rel]
    ]
    return "\n".join(
        ["-- Generated by a11oy scripts/check_putnam_drift.py."]
        + imports
        + [""]
        + prints
        + [""]
    )


def validate_axiom_report(
    report: str,
    declarations: List[str],
    errors: List[str],
) -> None:
    """Require one kernel axiom result per REAL declaration and no extra axioms."""
    for decl in declarations:
        quoted = re.escape("'" + decl + "'")
        none_pattern = re.compile(
            quoted + r"\s+does not depend on any axioms",
            re.IGNORECASE,
        )
        deps_pattern = re.compile(
            quoted + r"\s+depends on axioms:\s*\[([^\]]*)\]",
            re.IGNORECASE,
        )
        none_hits = none_pattern.findall(report)
        dep_hits = deps_pattern.findall(report)
        if len(none_hits) + len(dep_hits) != 1:
            errors.append(
                "axiom report: expected exactly one result for REAL declaration %s"
                % decl
            )
            continue
        if dep_hits:
            axioms = {item.strip() for item in dep_hits[0].split(",") if item.strip()}
            extra = sorted(axioms - TRUSTED_AXIOMS)
            if extra:
                errors.append(
                    "axiom report: REAL declaration %s depends on extra axioms %s"
                    % (decl, extra)
                )


# ---------------------------------------------------------------------------
# a11oy embedded data — loader module + console fallback.
# ---------------------------------------------------------------------------
def load_loader(path: str):
    """Execute the current loader source without trusting timestamped bytecode.

    The negative fixtures deliberately replace same-length status labels within
    one filesystem timestamp tick. A normal import can therefore reuse a stale
    ``__pycache__`` entry and report a false green. Compiling the source bytes
    directly makes every validation run observe the file it was given.
    """
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    mod = ModuleType("szl_putnam_under_test")
    mod.__file__ = path
    exec(compile(source, path, "exec", dont_inherit=True), mod.__dict__)
    return mod


def parse_js_rows(html: str, var_name: str) -> List[Tuple[str, str, str]]:
    """Extract (id, file, status) rows from a JS array literal `var X=[ ... ];`.

    Each row looks like ``['A1','P_A1.lean','DEMO','note…']`` — we take the first
    three single-quoted fields.
    """
    m = re.search(r"var\s+" + re.escape(var_name) + r"\s*=\s*\[(.*?)\]\s*;",
                  html, re.S)
    if not m:
        return []
    body = m.group(1)
    rows: List[Tuple[str, str, str]] = []
    for rm in re.finditer(
        r"\[\s*'((?:[^'\\]|\\.)*)'\s*,\s*'((?:[^'\\]|\\.)*)'\s*,\s*'"
        + STATUS_RE + r"'",
        body,
    ):
        rows.append((rm.group(1), rm.group(2), rm.group(3)))
    return rows


def literal_count_phrases(text: str) -> List[Tuple[int, int, int]]:
    """All literal ``N REAL / M DEMO / K OPEN`` phrases (skips %d templates)."""
    out: List[Tuple[int, int, int]] = []
    for m in re.finditer(
        r"(\d+)\s*REAL\s*/\s*(\d+)\s*DEMO\s*/\s*(\d+)\s*OPEN", text):
        out.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return out


def named_open_sets(text: str) -> List[Set[str]]:
    """Find 'X and Y are … OPEN' prose constructs and return each named id set.

    Locates each 'are … OPEN' clause, then reads the short window just before
    'are' (within the same clause — no '.'/';' crossed) for problem ids. Only
    yields a set when ids are actually named there, so generic 'are … OPEN'
    sentences (e.g. 'the problems are … OPEN') never produce a false failure.
    Survives 'A3 and A6' and HTML markup ('<b>A3</b> and <b>A6</b>').
    """
    out: List[Set[str]] = []
    for m in re.finditer(r"\bare\b[^.;]{0,80}?OPEN", text):
        pre = text[max(0, m.start() - 48):m.start()]
        pre = re.split(r"[.;]", pre)[-1]
        ids = set(re.findall(r"[AB][1-6]", pre))
        if ids:
            out.append(ids)
    return out


# ---------------------------------------------------------------------------
# Main check.
# ---------------------------------------------------------------------------
def diligence_block(
    branch: str,
    total: int,
    real: int,
    demo: int,
    open_count: int,
) -> str:
    """Render the only allowed public Putnam count for the diligence packet."""
    return (
        f"{DILIGENCE_BEGIN}\n"
        f"| Putnam 2025 Lean | **{real}/{total} PROVED** — "
        f"{real} of {total} Putnam problems currently carry a Lean `REAL` "
        f"status; the complete canonical tally is {real} REAL / {demo} DEMO / "
        f"{open_count} OPEN at `lutar-lean@{branch}`. This row is generated and "
        "checked only after the pinned `lake build PutnamSet` job succeeds, by "
        "`scripts/check_putnam_drift.py`. |\n"
        f"{DILIGENCE_END}"
    )


def sync_diligence(
    root: str,
    expected: str,
    write_diligence: bool,
    errors: List[str],
) -> None:
    """Write or verify the generated diligence block without touching prose."""
    path = os.path.join(root, DILIGENCE_REL)
    if not os.path.isfile(path):
        errors.append("%s not found" % path)
        return
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    pattern = re.compile(
        re.escape(DILIGENCE_BEGIN) + r".*?" + re.escape(DILIGENCE_END),
        re.S,
    )
    begin_count = text.count(DILIGENCE_BEGIN)
    end_count = text.count(DILIGENCE_END)
    matches = list(pattern.finditer(text))
    if begin_count != 1 or end_count != 1 or len(matches) != 1:
        errors.append(
            "%s: expected exactly one generated Putnam status marker block "
            "(found %d begin marker(s), %d end marker(s), %d block(s))"
            % (DILIGENCE_REL, begin_count, end_count, len(matches))
        )
        return
    if write_diligence:
        rendered = pattern.sub(expected, text)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(rendered)
        return
    actual = matches[0]
    if actual.group(0) != expected:
        errors.append(
            "%s: generated Putnam status is stale; run "
            "`python scripts/check_putnam_drift.py --write-diligence`"
            % DILIGENCE_REL
        )


def run(
    root: str,
    branch: str,
    fixture: Optional[str],
    write_diligence: bool = False,
    write_axiom_audit: Optional[str] = None,
    axiom_report: Optional[str] = None,
) -> int:
    errors: List[str] = []

    loader_path = os.path.join(root, "szl_putnam.py")
    console_path = os.path.join(root, "pages", "console.html")
    if not os.path.isfile(loader_path):
        print("ERROR: %s not found" % loader_path)
        return 2
    if not os.path.isfile(console_path):
        print("ERROR: %s not found" % console_path)
        return 2

    mod = load_loader(loader_path)
    loader_putnam = {p["id"]: p for p in mod._PUTNAM}
    loader_szl = {s["id"]: s for s in mod._SZL}
    with open(console_path, "r", encoding="utf-8") as fh:
        html = fh.read()
    with open(loader_path, "r", encoding="utf-8") as fh:
        loader_src = fh.read()

    fb_probs = parse_js_rows(html, "FB_PROBS")
    fb_szl = parse_js_rows(html, "FB_SZL")
    if not fb_probs:
        errors.append("console.html: FB_PROBS fallback array not found/parseable")
    if not fb_szl:
        errors.append("console.html: FB_SZL fallback array not found/parseable")

    canon = Canonical(branch, fixture)

    # ---- canonical labels per file --------------------------------------
    try:
        canon_putnam_files = canon.putnam_files()
        canon_szl_files = canon.szl_files()
    except (urllib.error.URLError, OSError) as exc:
        print("ERROR: cannot reach canonical source (%s)" % exc)
        return 2

    canon_putnam: Dict[str, str] = {}      # file -> status
    canon_sources: Dict[str, str] = {}
    for f in canon_putnam_files:
        source = canon.read(f)
        canon_sources[f] = source
        st = canonical_putnam_status(source)
        if st is None:
            errors.append("canonical %s: no parseable Honest status label" % f)
        else:
            canon_putnam[f] = st
    canon_szl: Dict[str, str] = {}         # 'SZL/X.lean' -> status
    for f in canon_szl_files:
        source = canon.read(f)
        canon_sources[f] = source
        st = canonical_szl_status(source)
        if st is None:
            errors.append("canonical %s: no parseable REAL/DEMO/OPEN claim" % f)
        else:
            canon_szl[f] = st

    # ---- every REAL source is sorry-free and axiom-audited --------------
    real_sources: Dict[str, List[str]] = {}
    for rel, status in {**canon_putnam, **canon_szl}.items():
        if status == "REAL":
            real_sources[rel] = real_lean_declarations(
                rel,
                canon_sources[rel],
                errors,
            )
    real_declarations = [
        decl
        for rel in sorted(real_sources)
        for decl in real_sources[rel]
    ]
    if write_axiom_audit:
        with open(write_axiom_audit, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render_axiom_audit(real_sources))
    if axiom_report:
        try:
            with open(axiom_report, "r", encoding="utf-8") as fh:
                report = fh.read()
        except OSError as exc:
            errors.append("cannot read axiom report %s: %s" % (axiom_report, exc))
        else:
            validate_axiom_report(report, real_declarations, errors)

    # ---- file-set completeness ------------------------------------------
    loader_putnam_files = {p["file"] for p in mod._PUTNAM}
    if loader_putnam_files != set(canon_putnam_files):
        miss = set(canon_putnam_files) - loader_putnam_files
        extra = loader_putnam_files - set(canon_putnam_files)
        if miss:
            errors.append("loader is MISSING canonical Putnam files: %s"
                          % sorted(miss))
        if extra:
            errors.append("loader has STALE/unknown Putnam files: %s"
                          % sorted(extra))
    loader_szl_files = {s["file"] for s in mod._SZL}
    if loader_szl_files != set(canon_szl_files):
        miss = set(canon_szl_files) - loader_szl_files
        extra = loader_szl_files - set(canon_szl_files)
        if miss:
            errors.append("loader is MISSING canonical SZL files: %s"
                          % sorted(miss))
        if extra:
            errors.append("loader has STALE/unknown SZL files: %s"
                          % sorted(extra))

    # ---- per-problem label: loader vs canonical -------------------------
    for p in mod._PUTNAM:
        c = canon_putnam.get(p["file"])
        if c is not None and c != p["status"]:
            errors.append("loader %s = %s but canonical %s = %s"
                          % (p["id"], p["status"], p["file"], c))
    for s in mod._SZL:
        c = canon_szl.get(s["file"])
        if c is not None and c != s["status"]:
            errors.append("loader %s = %s but canonical %s = %s"
                          % (s["id"], s["status"], s["file"], c))

    # ---- console fallback must equal the loader (id, file, status) ------
    def cmp_rows(rows, loader_map, kind):
        rmap = {r[0]: r for r in rows}
        if set(rmap) != set(loader_map):
            errors.append("console %s ids %s != loader ids %s"
                          % (kind, sorted(rmap), sorted(loader_map)))
        for rid, row in rmap.items():
            lp = loader_map.get(rid)
            if not lp:
                continue
            if row[1] != lp["file"]:
                errors.append("console %s %s file %r != loader %r"
                              % (kind, rid, row[1], lp["file"]))
            if row[2] != lp["status"]:
                errors.append("console %s %s status %s != loader %s"
                              % (kind, rid, row[2], lp["status"]))

    cmp_rows(fb_probs, loader_putnam, "FB_PROBS")
    cmp_rows(fb_szl, loader_szl, "FB_SZL")

    # ---- aggregate counts -----------------------------------------------
    c_real = sum(1 for v in canon_putnam.values() if v == "REAL")
    c_demo = sum(1 for v in canon_putnam.values() if v == "DEMO")
    c_open = sum(1 for v in canon_putnam.values() if v == "OPEN")
    c_szl_real = sum(1 for v in canon_szl.values() if v == "REAL")
    canon_counts = (c_real, c_demo, c_open)
    canon_open_ids = {f[2:5] for f, v in canon_putnam.items() if v == "OPEN"}
    # f is 'P_A3.lean' -> id 'A3' at [2:4]; normalise robustly below.
    canon_open_ids = {re.sub(r"^P_|\.lean$", "", f) for f, v in
                      canon_putnam.items() if v == "OPEN"}

    pb = mod._putnam_block()
    if (pb["real"], pb["demo"], pb["open"]) != canon_counts:
        errors.append("loader putnam block %d/%d/%d != canonical %d/%d/%d"
                      % (pb["real"], pb["demo"], pb["open"], *canon_counts))
    sb = mod._szl_block()
    if sb["real"] != c_szl_real:
        errors.append("loader SZL real %d != canonical %d"
                      % (sb["real"], c_szl_real))

    # literal count phrases in loader source + console must match canonical
    for src, label in ((loader_src, "szl_putnam.py"), (html, "console.html")):
        for trip in literal_count_phrases(src):
            if trip != canon_counts:
                errors.append("%s: count phrase %d REAL / %d DEMO / %d OPEN "
                              "!= canonical %d/%d/%d"
                              % (label, trip[0], trip[1], trip[2], *canon_counts))

    # named "X and Y are OPEN" prose must name exactly the canonical OPEN set
    for src, label in ((loader_src, "szl_putnam.py"), (html, "console.html")):
        for named in named_open_sets(src):
            if named != canon_open_ids:
                errors.append("%s: prose names %s as OPEN but canonical OPEN "
                              "set is %s"
                              % (label, sorted(named), sorted(canon_open_ids)))

    expected_diligence = diligence_block(
        branch,
        len(canon_putnam),
        c_real,
        c_demo,
        c_open,
    )
    sync_diligence(root, expected_diligence, write_diligence, errors)

    # ---- verdict --------------------------------------------------------
    if errors:
        print("PUTNAM DRIFT — a11oy Putnam 2025 page is OUT OF SYNC with "
              "lutar-lean@%s:" % branch)
        for e in errors:
            print("  ::error:: %s" % e)
        print("\nRe-transcribe szl_putnam.py (_PUTNAM/_SZL) and the console "
              "putnam-2025-tab-patch fallback from the canonical Lean labels.")
        return 1

    print("OK: a11oy Putnam 2025 page matches lutar-lean@%s — %d Putnam "
          "(%d REAL / %d DEMO / %d OPEN), %d SZL REAL; loader == console "
          "fallback; %d count phrase(s) consistent."
          % (branch, len(canon_putnam), c_real, c_demo, c_open, c_szl_real,
             len(literal_count_phrases(loader_src))
             + len(literal_count_phrases(html))))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="a11oy repo root")
    ap.add_argument(
        "--branch",
        "--ref",
        dest="branch",
        default=DEFAULT_REF,
        help="immutable canonical lutar-lean commit",
    )
    ap.add_argument(
        "--write-diligence",
        action="store_true",
        help="refresh only the generated Putnam row in the diligence packet",
    )
    ap.add_argument(
        "--write-axiom-audit",
        metavar="PATH",
        help="write Lean #print axioms commands for every REAL theorem",
    )
    ap.add_argument(
        "--axiom-report",
        metavar="PATH",
        help="require a complete in-policy #print axioms report",
    )
    args = ap.parse_args()
    fixture = os.environ.get("PUTNAM_DRIFT_FIXTURE") or None
    return run(
        args.root,
        args.branch,
        fixture,
        args.write_diligence,
        args.write_axiom_audit,
        args.axiom_report,
    )


if __name__ == "__main__":
    sys.exit(main())
