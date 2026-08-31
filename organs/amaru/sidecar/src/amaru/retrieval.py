# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749/14/163 @ c7c0ba17 · Λ = Conjecture 1
"""
amaru.retrieval — real knowledge-base retrieval for the cortex RAG path.

DOCTRINE: HONESTY OVER CHECKLIST. When a reasoning request arrives WITHOUT
caller-supplied citations, the cortex must still ground its answer in *real*
primary sources — or honestly abstain. This module queries the **public arXiv
Atom API** (https://export.arxiv.org/api/query), a real, first-party scholarly
index, and returns canonical ``https://arxiv.org/abs/<id>`` URLs that resolve to
HTTP 200. We NEVER fabricate a URL: if the index is unreachable or returns no
match, we return an empty list and the caller abstains.

No heavyweight deps (no faiss / sentence-transformers needed for this path) —
just the stdlib over a real network call. A tiny in-process curated index of the
cortex's first-party field-leader sources (the same arXiv IDs Amaru's reasoning
patterns are built on) is used as a deterministic fallback / re-rank seed, but
every URL in it is a genuine, resolvable arXiv abstract page.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

ARXIV_API = "https://export.arxiv.org/api/query"
_UA = {"User-Agent": "amaru-cortex/1.0 (+https://github.com/szl-holdings/amaru)"}

# First-party curated field-leader sources — real, resolvable arXiv abstracts.
# These are the primary sources the Amaru cortex's reasoning patterns are built
# on (mirrors AMARU_FIELD_LEADERS.md). Used to seed/re-rank retrieval.
FIELD_LEADERS: list[dict[str, str]] = [
    {"arxiv": "2309.11495", "title": "Chain-of-Verification Reduces Hallucination in LLMs",
     "authors": "Dhuliawala et al.", "topic": "chain-of-verification cove hallucination verify"},
    {"arxiv": "2310.03714", "title": "DSPy: Compiling Declarative LM Calls into Self-Improving Pipelines",
     "authors": "Khattab et al.", "topic": "dspy declarative reasoning program signature compile"},
    {"arxiv": "2305.10601", "title": "Tree of Thoughts: Deliberate Problem Solving with LLMs",
     "authors": "Yao et al.", "topic": "tree of thoughts tot deliberate search branch reasoning"},
    {"arxiv": "2303.11366", "title": "Reflexion: Language Agents with Verbal Reinforcement Learning",
     "authors": "Shinn et al.", "topic": "reflexion self-reflection verbal reinforcement memory agent"},
    {"arxiv": "2201.11903", "title": "Chain-of-Thought Prompting Elicits Reasoning in LLMs",
     "authors": "Wei et al.", "topic": "chain of thought cot prompting reasoning step by step"},
    {"arxiv": "2212.08073", "title": "Constitutional AI: Harmlessness from AI Feedback",
     "authors": "Bai et al.", "topic": "constitutional ai harmlessness feedback principles honesty"},
    {"arxiv": "2005.11401", "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP",
     "authors": "Lewis et al.", "topic": "retrieval augmented generation rag knowledge retrieval"},
]


@dataclass
class RetrievedSource:
    title: str
    authors: str
    url: str
    arxiv_id: str
    score: float
    origin: str  # "arxiv-api" | "field-leader"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "authors": self.authors,
            "url": self.url,
            "arxiv_id": self.arxiv_id,
            "score": round(self.score, 4),
            "origin": self.origin,
        }


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2}


def _abs_url(arxiv_id: str) -> str:
    # Strip any version suffix for the canonical abstract page.
    base = re.sub(r"v\d+$", "", arxiv_id.strip())
    return f"https://arxiv.org/abs/{base}"


def _rank_field_leaders(question: str, k: int) -> list[RetrievedSource]:
    q = _tokens(question)
    scored: list[RetrievedSource] = []
    for fl in FIELD_LEADERS:
        overlap = q & _tokens(fl["topic"] + " " + fl["title"])
        if not overlap:
            continue
        score = len(overlap) / (len(q) or 1)
        scored.append(RetrievedSource(
            title=fl["title"], authors=fl["authors"], url=_abs_url(fl["arxiv"]),
            arxiv_id=fl["arxiv"], score=score, origin="field-leader",
        ))
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:k]


def search_arxiv(question: str, k: int = 3, timeout: float = 12.0) -> list[RetrievedSource]:
    """Query the real public arXiv Atom API. Returns resolvable arxiv.org URLs.

    Never raises into the caller and never fabricates — on any failure returns
    an empty list so the cortex abstains honestly.
    """
    params = urllib.parse.urlencode({
        "search_query": f"all:{question}",
        "start": 0,
        "max_results": max(1, min(k, 10)),
        "sortBy": "relevance",
        "sortOrder": "descending",
    })
    url = f"{ARXIV_API}?{params}"
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except Exception:
        return []

    ns = {"a": "http://www.w3.org/2005/Atom"}
    out: list[RetrievedSource] = []
    try:
        root = ET.fromstring(raw)
    except Exception:
        return []
    for i, entry in enumerate(root.findall("a:entry", ns)):
        eid = (entry.findtext("a:id", default="", namespaces=ns) or "").strip()
        m = re.search(r"arxiv\.org/abs/([^v\s]+(?:v\d+)?)", eid)
        if not m:
            continue
        arxiv_id = m.group(1)
        title = " ".join((entry.findtext("a:title", default="", namespaces=ns) or "").split())
        authors = ", ".join(
            (a.findtext("a:name", default="", namespaces=ns) or "").strip()
            for a in entry.findall("a:author", ns)
        )[:200]
        out.append(RetrievedSource(
            title=title, authors=authors or "arXiv", url=_abs_url(arxiv_id),
            arxiv_id=re.sub(r"v\d+$", "", arxiv_id),
            score=1.0 - (i * 0.05), origin="arxiv-api",
        ))
    return out


def retrieve(question: str, k: int = 3, timeout: float = 12.0) -> list[RetrievedSource]:
    """Real RAG retrieval: live arXiv API first, curated field-leaders as a
    deterministic re-rank/fallback. De-duplicates by arXiv id. Returns [] if
    nothing real is found (-> honest abstention upstream)."""
    live = search_arxiv(question, k=k, timeout=timeout)
    seed = _rank_field_leaders(question, k=k)
    merged: dict[str, RetrievedSource] = {}
    for r in live + seed:
        if r.arxiv_id not in merged:
            merged[r.arxiv_id] = r
    ranked = sorted(merged.values(), key=lambda r: r.score, reverse=True)
    return ranked[:k]


def retrieve_urls(question: str, k: int = 3, timeout: float = 12.0) -> list[str]:
    """Convenience: just the resolvable URLs for the citation guard."""
    return [r.url for r in retrieve(question, k=k, timeout=timeout)]


__all__ = [
    "RetrievedSource", "FIELD_LEADERS",
    "search_arxiv", "retrieve", "retrieve_urls",
]
