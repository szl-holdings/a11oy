"""
szl_bounties.py — Open-Problem Bounty Board layer (a11oy console tab)
====================================================================

Renders the **genuinely OPEN** problem bounties — Conjecture 1 (Λ-aggregator
unconditional uniqueness) and Conjecture 2 (Khipu Byzantine quorum safety) —
on a public surface (the a11oy console), turning the board into a recruiting
funnel for proofs that links straight to the lambda-bounty intake webhook.

Single source of truth
----------------------
The page is *generated from* the canonical YAML in ``bounties/*.yaml`` (copied
byte-identical from ``szl-holdings/lutar-lean`` and kept in lockstep by the
``bounties-drift.yml`` CI guard). Nothing here is hand-authored bounty prose,
so the rendered page cannot drift from the kernel repo. Only bounties whose
``status`` is ``OPEN`` are surfaced.

Honesty doctrine (v11)
----------------------
Λ unconditional uniqueness is **Conjecture 1 — NOT a theorem** (machine-checked
FALSE under the bare axioms via the maxAgg/min counterexample). Khipu
unconditional BFT safety is **Conjecture 2**. The reward is always the literal
label **"founder-set"** — this board never invents a figure. The ``honesty``
line from each YAML is surfaced verbatim, and any numeric reward value is
defensively coerced back to ``founder-set``.

This module is **stdlib-only** (no PyYAML in the a11oy image): it ships a small,
faithful YAML-subset reader for exactly the constructs the bounty files use
(top-level scalars, ``|``/``>`` block scalars, nested mappings, scalar lists,
and lists of mappings).

Pattern mirrors szl_readiness.py / szl_contracting.py::

    import szl_bounties
    szl_bounties.register(app, ns="a11oy")

Endpoints (per namespace ns)::

    GET /api/{ns}/v1/bounties
        -> { layer, honest, doctrine, source, board, count, bounties:[...] }
           one entry per OPEN bounty with statement, the gap, acceptance
           criteria, reward label ("founder-set"), submission/claim links,
           and the verbatim honesty line.
    GET /api/{ns}/v1/bounties/{bounty_id}
        -> a single OPEN bounty (404 if unknown / not OPEN).
"""
from __future__ import annotations

import os
import re
import threading
from typing import Any, Dict, List, Optional

_HONEST = (
    "These are the genuinely OPEN problems — honest open conjectures under public "
    "axiom audit, NOT theorems. \u039b unconditional uniqueness is Conjecture 1 "
    "(machine-checked FALSE under the bare axioms); unconditional Khipu BFT safety "
    "is Conjecture 2. A bounty clears ONLY when the kernel verifies the proof (REAL): "
    "kernel-checked, zero `sorry`, in-policy axioms. The reward is founder-set; this "
    "board never invents a figure."
)
_DOCTRINE = "v11"
_SOURCE = "szl-holdings/lutar-lean — bounties/*.yaml (single source of truth)"
_BOARD_URL = "https://github.com/szl-holdings/lutar-lean/tree/main/bounties"
_DOCS_URL = "https://github.com/szl-holdings/lutar-lean/blob/main/docs/bounties.md"

_LOCK = threading.Lock()
_CACHE: Optional[List[Dict[str, Any]]] = None


# ---------------------------------------------------------------------------
# Minimal, faithful YAML-subset reader (stdlib only).
# Handles exactly what the bounty files use; not a general YAML parser.
# ---------------------------------------------------------------------------
def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _first_sig(lines: List[str], i: int) -> int:
    """Index of the next significant (non-blank, non-comment) line, or len."""
    while i < len(lines):
        s = lines[i].strip()
        if s == "" or s.startswith("#"):
            i += 1
            continue
        return i
    return i


def _dequote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        inner = s[1:-1]
        if s[0] == '"':
            inner = (inner.replace('\\"', '"').replace("\\n", "\n")
                     .replace("\\t", "\t").replace("\\\\", "\\"))
        else:
            inner = inner.replace("''", "'")
        return inner
    return s


def _scalar(s: str) -> Any:
    s = s.strip()
    if s == "":
        return ""
    if s in ("null", "~", "Null", "NULL"):
        return None
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    if re.fullmatch(r"-?\d+", s):
        try:
            return int(s)
        except ValueError:
            pass
    return _dequote(s)


def _read_block_scalar(lines: List[str], i: int, parent_indent: int, style: str) -> Any:
    """Read a `|` (literal) or `>` (folded) block scalar; return (text, next_i)."""
    block: List[str] = []
    base: Optional[int] = None
    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            block.append("")
            i += 1
            continue
        ind = _indent_of(line)
        if ind <= parent_indent:
            break
        if base is None:
            base = ind
        block.append(line[base:] if len(line) >= base else line.lstrip(" "))
        i += 1
    while block and block[-1] == "":
        block.pop()
    if style == "|":
        text = ("\n".join(block) + "\n") if block else ""
        return text, i
    # folded ">": single newlines -> spaces; blank lines -> paragraph breaks
    paras: List[str] = []
    cur: List[str] = []
    for ln in block:
        if ln == "":
            paras.append(" ".join(cur))
            cur = []
        else:
            cur.append(ln.strip())
    paras.append(" ".join(cur))
    text = "\n".join(p for p in paras).strip("\n")
    return (text + "\n") if text else "", i


_BLOCK_MARKERS = ("|", ">", "|-", ">-", "|+", ">+")


def _parse(lines: List[str], i: int, floor: int):
    i = _first_sig(lines, i)
    if i >= len(lines):
        return None, i
    line = lines[i]
    ind = _indent_of(line)
    if ind < floor:
        return None, i
    s = line.strip()
    if s == "-" or s.startswith("- "):
        return _parse_list(lines, i, ind)
    return _parse_map(lines, i, ind)


def _parse_map(lines: List[str], i: int, indent: int):
    node: Dict[str, Any] = {}
    while i < len(lines):
        i = _first_sig(lines, i)
        if i >= len(lines):
            break
        line = lines[i]
        ind = _indent_of(line)
        if ind != indent:
            break
        s = line.strip()
        m = re.match(r"^([^:]+):(.*)$", s)
        if not m:
            break
        key = _dequote(m.group(1).strip())
        rest = m.group(2).strip()
        i += 1
        if rest in _BLOCK_MARKERS:
            node[key], i = _read_block_scalar(lines, i, indent, rest[0])
        elif rest == "":
            j = _first_sig(lines, i)
            if j < len(lines) and _indent_of(lines[j]) > indent:
                node[key], i = _parse(lines, i, indent + 1)
            else:
                node[key] = None
        else:
            node[key] = _scalar(rest)
    return node, i


def _parse_list(lines: List[str], i: int, indent: int):
    items: List[Any] = []
    while i < len(lines):
        j = _first_sig(lines, i)
        if j >= len(lines):
            i = j
            break
        line = lines[j]
        ind = _indent_of(line)
        s = line.strip()
        if ind != indent or not (s == "-" or s.startswith("- ")):
            i = j
            break
        rest = line[ind + 1:]
        content_indent = ind + 1 + (len(rest) - len(rest.lstrip(" ")))
        first = rest.strip()
        block: List[str] = []
        if first != "":
            block.append(" " * content_indent + first)
        k = j + 1
        while k < len(lines):
            ll = lines[k]
            if ll.strip() == "" or ll.strip().startswith("#"):
                block.append(ll)
                k += 1
                continue
            if _indent_of(ll) < content_indent:
                break
            block.append(ll)
            k += 1
        if not block:
            items.append(None)
        else:
            bs = block[0].strip()
            if re.match(r"^[^:'\"]+:(\s|$)", bs):
                val, _ = _parse_map(block, 0, content_indent)
                items.append(val)
            else:
                items.append(_scalar(bs))
        i = k
    return items, i


def parse_yaml(text: str) -> Dict[str, Any]:
    """Parse the YAML-subset used by the bounty files into a dict."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    node, _ = _parse(lines, 0, 0)
    return node if isinstance(node, dict) else {}


# ---------------------------------------------------------------------------
# Bounty loading + honest shaping
# ---------------------------------------------------------------------------
def _bounty_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "bounties"), os.path.join(os.getcwd(), "bounties")):
        if os.path.isdir(cand):
            return cand
    return os.path.join(here, "bounties")


def _reward_label(reward: Any) -> str:
    """Always a non-numeric label. This board never invents a figure."""
    if isinstance(reward, dict):
        amt = reward.get("amount")
    else:
        amt = reward
    label = str(amt).strip() if amt is not None else "founder-set"
    if label == "" or re.search(r"\d", label):
        return "founder-set"
    return label


def _claim_links(b: Dict[str, Any]) -> Dict[str, Any]:
    sub = b.get("submission") or {}
    if not isinstance(sub, dict):
        sub = {}
    out: Dict[str, Any] = {
        "intake_repo": sub.get("intake_repo"),
        "pull_request": sub.get("pull_request"),
    }
    if sub.get("webhook"):
        out["webhook"] = sub.get("webhook")
    if sub.get("template"):
        out["template"] = sub.get("template")
    if sub.get("schema"):
        out["schema"] = sub.get("schema")
    return out


def _shape(b: Dict[str, Any]) -> Dict[str, Any]:
    reward = b.get("reward") or {}
    reward_note = reward.get("note") if isinstance(reward, dict) else None
    reward_extras = reward.get("extras") if isinstance(reward, dict) else None
    crit = []
    for c in (b.get("acceptance_criteria") or []):
        if isinstance(c, dict):
            crit.append({"id": c.get("id"), "check": c.get("check")})
        elif c is not None:
            crit.append({"id": None, "check": str(c)})
    verification = b.get("verification") or {}
    target = b.get("target") or {}
    return {
        "id": b.get("id"),
        "title": b.get("title"),
        "status": b.get("status"),
        "conjecture": b.get("conjecture"),
        "formula": b.get("formula"),
        "doctrine": b.get("doctrine") or _DOCTRINE,
        "summary": (b.get("summary") or "").strip(),
        "problem_statement": (b.get("problem_statement") or "").strip(),
        "the_gap": (b.get("the_gap") or "").strip(),
        "missing_assumption": b.get("missing_assumption"),
        "already_proven_do_not_reclaim": (b.get("already_proven_do_not_reclaim") or "").strip() or None,
        "target": {
            "theorem_name": target.get("theorem_name"),
            "file": target.get("file"),
            "repo": target.get("repo"),
        } if target else None,
        "acceptance_criteria": crit,
        "verification": {
            "arbiter": verification.get("arbiter"),
            "must_become_real": verification.get("must_become_real"),
            "signal": verification.get("signal"),
        } if verification else None,
        "reward": {
            "label": _reward_label(reward),
            "note": (reward_note or "").strip() or None,
            "extras": reward_extras if isinstance(reward_extras, list) else None,
        },
        "submission": _claim_links(b),
        "references": b.get("references") if isinstance(b.get("references"), list) else None,
        "honesty": (b.get("honesty") or "").strip(),
    }


def _load(force: bool = False) -> List[Dict[str, Any]]:
    global _CACHE
    with _LOCK:
        if _CACHE is not None and not force:
            return _CACHE
        out: List[Dict[str, Any]] = []
        d = _bounty_dir()
        try:
            names = sorted(f for f in os.listdir(d)
                           if f.endswith((".yaml", ".yml")) and not f.startswith("."))
        except OSError:
            names = []
        for name in names:
            try:
                with open(os.path.join(d, name), "r", encoding="utf-8") as fh:
                    parsed = parse_yaml(fh.read())
            except Exception:  # noqa: BLE001  (a malformed file must never crash the board)
                continue
            if not isinstance(parsed, dict) or not parsed.get("id"):
                continue
            parsed["_file"] = name
            out.append(parsed)
        _CACHE = out
        return out


def _open_bounties() -> List[Dict[str, Any]]:
    return [_shape(b) for b in _load()
            if str(b.get("status", "")).strip().upper() == "OPEN"]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> None:
    """Attach the OPEN-bounty board endpoints for namespace ns to a FastAPI app."""
    try:
        from fastapi.responses import JSONResponse
    except Exception:  # pragma: no cover
        return

    base = "/api/%s/v1/bounties" % ns

    def _now_iso() -> str:
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @app.get(base)
    async def _bounties_index():  # noqa: ANN202
        bounties = _open_bounties()
        return JSONResponse({
            "layer": "%s open-problem bounty board" % ns,
            "honest": _HONEST,
            "doctrine": _DOCTRINE,
            "source": _SOURCE,
            "board": _BOARD_URL,
            "docs": _DOCS_URL,
            "count": len(bounties),
            "bounties": bounties,
            "checked_at": _now_iso(),
        })

    @app.get(base + "/{bounty_id}")
    async def _bounty_one(bounty_id: str):  # noqa: ANN202
        for b in _open_bounties():
            if b.get("id") == bounty_id:
                return JSONResponse({
                    "layer": "%s open-problem bounty" % ns,
                    "honest": _HONEST,
                    "doctrine": _DOCTRINE,
                    "source": _SOURCE,
                    "bounty": b,
                    "checked_at": _now_iso(),
                })
        return JSONResponse(
            {"error": "unknown or non-OPEN bounty", "bounty_id": bounty_id,
             "open": [b.get("id") for b in _open_bounties()]},
            status_code=404,
        )
