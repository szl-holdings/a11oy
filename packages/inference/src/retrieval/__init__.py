# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# Doctrine v11 LOCKED 749/14/163. Authored by Stephen Lutar.
# DCO: Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
# Co-Authored-By: Perplexity Computer Agent
"""
retrieval/__init__.py — retrieval-adjacent bridges for the inference package.

Currently contains only ``second_brain_bridge``: a fail-closed bridge to the
LIVE SZLHOLDINGS/second-brain HF Space. That Space's ``/api/v1/retrieve``
endpoint is a LEXICAL-OVERLAP ranker over the PUBLIC in-repo projection of
the corpus (``content_access: HANDLES_ONLY``). It returns citation HANDLES
(nodeId + short note + sha256 pointer), NOT document text, NOT semantic
retrieval, and NOT the private brain graph. Nothing in this package may
describe it as anything more.
"""
from __future__ import annotations

from .second_brain_bridge import (
    DEFAULT_TIMEOUT_S,
    DEFAULT_TOP_K,
    RESPONSE_SCHEMA,
    SECOND_BRAIN_RETRIEVE_URL,
    RetrievalResult,
    format_citation_context,
    retrieve_handles,
)

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "DEFAULT_TOP_K",
    "RESPONSE_SCHEMA",
    "SECOND_BRAIN_RETRIEVE_URL",
    "RetrievalResult",
    "format_citation_context",
    "retrieve_handles",
]
