# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163. Λ = Conjecture 1 (NOT a theorem; 163 sorries).
# Authored by Stephen Lutar. DCO: Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent
"""
second_brain_bridge.py — fail-closed citation-HANDLE bridge to the LIVE
SZLHOLDINGS/second-brain Hugging Face Space.

WHAT THE UPSTREAM API ACTUALLY IS (read this before touching the file)::

    POST https://szlholdings-second-brain.hf.space/api/v1/retrieve
    body: {"query": "<text>", "top_k": <int, default 6>}
    -> response schema "szl.second-brain.retrieve/v1":
       {"schema", "query", "k",
        "handles": [{"nodeId", "nodeKind", "label", "note", "source", "sha256"}],
        "scores": [float, ...], "corpus_n", "ready", "kind",
        "content_access": "HANDLES_ONLY",
        "index_is_model_weights": false,
        "raw_graph_nodes_admitted_to_gradients": 0,
        "honesty": "Lexical rank over the PUBLIC in-repo projection (575 chunks).
                    Score is overlap, never correctness. Content stays in the
                    controller. Not LIVE retrieval. ..."}

It is a LEXICAL-OVERLAP ranker over the PUBLIC in-repo projection of the
second-brain corpus (575 chunks when this bridge was written; the live count
arrives verbatim as ``corpus_n``). It returns HANDLES — a nodeId, a short
note, and a sha256 content pointer. It does NOT return document text or
chunks, it is NOT semantic/vector retrieval, and it does NOT expose the
private 9464-node brain graph. Bridge code, docstrings, and labels MUST say
exactly that — never "RAG chunks", never "semantic retrieval", never "the
brain graph". The API's own ``honesty`` string is carried through VERBATIM so
the claim can never be upgraded downstream.

Honest status contract (Doctrine v11 — fail-closed, no fabrication):

* ``status="LIVE"``        — only on HTTP 200 + a well-formed
  ``szl.second-brain.retrieve/v1`` payload (a JSON object with a list-valued
  ``"handles"`` key). Every field is then passed through VERBATIM: never
  invented, never paraphrased, never padded.
* ``status="UNAVAILABLE"`` — on ANY failure (timeout, non-2xx, malformed
  JSON, missing ``"handles"`` key, empty query). ``handles``/``scores`` are
  EMPTY — never fabricated — ``error`` names the failure class, and an empty
  or partial response is NEVER treated as success.

``retrieve_handles`` NEVER raises: the sovereign inference path it augments
must survive any bridge outage.
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SECOND_BRAIN_RETRIEVE_URL = "https://szlholdings-second-brain.hf.space/api/v1/retrieve"
RESPONSE_SCHEMA = "szl.second-brain.retrieve/v1"
DEFAULT_TOP_K = 6
DEFAULT_TIMEOUT_S = 3.0

# The one honest description of what this endpoint returns. Shared so no
# caller paraphrases it into a stronger claim.
CITATION_HANDLE_LABEL = (
    "citation handles from a public lexical index — lexical-overlap ranking, "
    "not semantic retrieval, not the full brain graph"
)

_USER_AGENT = "szl-a11oy-second-brain-bridge/1.0 (citation-handle ranker client)"


@dataclass
class RetrievalResult:
    """Honest outcome of one second-brain ``/retrieve`` call.

    When ``status == "LIVE"`` every payload field below is VERBATIM from the
    API (handles are citation handles — nodeId + short note + sha256 pointer,
    never document text). When ``status == "UNAVAILABLE"`` the handle/score
    lists are empty and ``error`` names the failure class. Either way, nothing
    is fabricated.
    """

    status: str  # "LIVE" | "UNAVAILABLE"
    schema: Optional[str] = None  # verbatim when LIVE
    query: str = ""
    k: Optional[int] = None  # verbatim when LIVE
    handles: List[Dict[str, Any]] = field(default_factory=list)  # verbatim
    scores: List[float] = field(default_factory=list)  # verbatim
    honesty: str = ""  # the API's own honesty string, verbatim
    corpus_n: Optional[int] = None  # verbatim public-projection chunk count
    ready: Optional[bool] = None  # verbatim
    kind: Optional[str] = None  # verbatim (e.g. "SOFTWARE")
    content_access: Optional[str] = None  # verbatim (e.g. "HANDLES_ONLY")
    error: Optional[str] = None  # failure class when UNAVAILABLE
    url: str = SECOND_BRAIN_RETRIEVE_URL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "schema": self.schema,
            "query": self.query,
            "k": self.k,
            "handles": self.handles,
            "scores": self.scores,
            "honesty": self.honesty,
            "corpus_n": self.corpus_n,
            "ready": self.ready,
            "kind": self.kind,
            "content_access": self.content_access,
            "error": self.error,
            "url": self.url,
        }


def _unavailable(query: str, error: str) -> RetrievalResult:
    """The ONLY failure constructor: empty handles, named error, never raises."""
    return RetrievalResult(status="UNAVAILABLE", query=query, error=error)


def retrieve_handles(query: str, top_k: int = DEFAULT_TOP_K,
                     timeout_s: float = DEFAULT_TIMEOUT_S) -> RetrievalResult:
    """POST ``query`` to the LIVE second-brain ``/retrieve`` endpoint.

    Args:
        query: the operator/user query text. Empty -> UNAVAILABLE (nothing is
            posted; an empty query must not fake a retrieval).
        top_k: number of citation handles to ask for (API default 6).
        timeout_s: hard bound on the outbound call (default 3.0s) so the
            inference path is never stalled by a slow Space.

    Returns:
        RetrievalResult with ``status="LIVE"`` + verbatim handles/scores/
        honesty on HTTP 200 + a well-formed ``szl.second-brain.retrieve/v1``
        payload, else ``status="UNAVAILABLE"`` with empty handles and a named
        error. NEVER raises; NEVER fabricates a handle.
    """
    query = (query or "").strip()
    if not query:
        return _unavailable("", "empty query — nothing posted to second-brain /retrieve")
    try:
        k = max(1, int(top_k))
    except (TypeError, ValueError):
        k = DEFAULT_TOP_K
    try:
        timeout = float(timeout_s)
        if timeout <= 0:
            timeout = DEFAULT_TIMEOUT_S
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT_S

    body = json.dumps({"query": query, "top_k": k}).encode("utf-8")
    req = urllib.request.Request(
        SECOND_BRAIN_RETRIEVE_URL, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            http_status = getattr(resp, "status", None)
            raw = resp.read()
    except urllib.error.HTTPError as exc:  # non-2xx from the Space
        return _unavailable(query, "HTTP %s from second-brain /retrieve" % exc.code)
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        return _unavailable(query, "%s: %s" % (type(exc).__name__, exc))
    except Exception as exc:  # fail-closed catch-all — this function NEVER raises
        return _unavailable(query, "%s: %s" % (type(exc).__name__, exc))

    if http_status is not None and http_status != 200:
        return _unavailable(query, "HTTP %s from second-brain /retrieve" % http_status)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return _unavailable(query, "malformed JSON in second-brain /retrieve response")
    if not isinstance(payload, dict):
        return _unavailable(query, "non-object JSON in second-brain /retrieve response")
    handles = payload.get("handles")
    if not isinstance(handles, list):
        # Missing/misshaped "handles" is a failure, NOT an empty success.
        return _unavailable(
            query, "missing 'handles' key in %s payload" % RESPONSE_SCHEMA)
    scores = payload.get("scores")
    honesty = payload.get("honesty")
    schema = payload.get("schema")
    k_echo = payload.get("k")
    corpus_n = payload.get("corpus_n")
    ready = payload.get("ready")
    kind = payload.get("kind")
    content_access = payload.get("content_access")
    return RetrievalResult(
        status="LIVE",
        schema=schema if isinstance(schema, str) else None,
        query=query,
        k=k_echo if isinstance(k_echo, int) else None,
        handles=handles,  # VERBATIM citation handles — never edited
        scores=scores if isinstance(scores, list) else [],  # VERBATIM
        honesty=honesty if isinstance(honesty, str) else "",  # VERBATIM
        corpus_n=corpus_n if isinstance(corpus_n, int) else None,
        ready=ready if isinstance(ready, bool) else None,
        kind=kind if isinstance(kind, str) else None,
        content_access=content_access if isinstance(content_access, str) else None,
    )


def format_citation_context(result: RetrievalResult, max_handles: int = 6) -> str:
    """Render a LIVE RetrievalResult as prompt-ready CITATION context.

    The text leads with the honest label — these are citation handles from a
    public lexical-overlap index, NOT semantic retrieval and NOT the full
    brain graph — then the API's own honesty string VERBATIM, then each
    handle's own fields VERBATIM (nodeId, nodeKind, label, source, sha256,
    note). Returns "" for anything that is not a LIVE result with handles, so
    a caller can never accidentally prepend an empty or fabricated block.
    """
    if result is None or result.status != "LIVE" or not result.handles:
        return ""
    if isinstance(result.corpus_n, int):
        label = ("citation handles from a public %d-chunk lexical index"
                 % result.corpus_n)
    else:
        label = "citation handles from a public lexical index"
    lines = [
        "SECOND-BRAIN CITATION CONTEXT (%s)." % (result.schema or RESPONSE_SCHEMA),
        ("The following are %s — lexical-overlap ranking only, not semantic "
         "retrieval, not the full brain graph. Each handle is a nodeId with a "
         "short note and a sha256 content pointer; the underlying content "
         "stays in the controller and is NOT included here. Treat every "
         "handle as a candidate citation to verify, never as ground truth, "
         "and say plainly when a handle does not back a claim.") % label,
    ]
    if result.honesty:
        lines.append("Upstream API honesty note (verbatim): " + result.honesty)
    try:
        limit = max(0, int(max_handles))
    except (TypeError, ValueError):
        limit = DEFAULT_TOP_K
    lines.append("Handles (verbatim, in the API's overlap-ranked order):")
    for i, handle in enumerate(result.handles[:limit], 1):
        if isinstance(handle, dict):
            lines.append(
                "%d. nodeId=%s | nodeKind=%s | label=%s | source=%s | sha256=%s | note=%s"
                % (i, handle.get("nodeId"), handle.get("nodeKind"),
                   handle.get("label"), handle.get("source"),
                   handle.get("sha256"), handle.get("note")))
        else:  # pragma: no cover — defensive; the API returns dicts
            lines.append("%d. %r" % (i, handle))
    return "\n".join(lines)
