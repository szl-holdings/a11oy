# VENDORED FROM szl-holdings/platform@d16b702ebe63042e05f41eacea4853afc59c7ab3 — packages/khipu-lmdb/khipu_lmdb/__init__.py
# DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Yachay — Doctrine v11 LOCKED: 749 declarations / 14 unique axioms / 163 sorries.
# git trailer: Perplexity Computer Agent
"""khipu-lmdb — durable LMDB persistence backend for the Khipu hash-chained receipt log."""
from __future__ import annotations
from .core import KhipuLMDB  # noqa: F401

__all__ = ["KhipuLMDB"]
__version__ = "1.0.0"
