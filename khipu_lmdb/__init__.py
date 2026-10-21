# VENDORED FROM szl-holdings/platform@a7071642fc902e0aa4af075cddb71626104ab6b1 — packages/khipu-lmdb/khipu_lmdb/__init__.py
# DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Yachay — Doctrine v11 LOCKED: 749 declarations / 14 unique axioms / 163 sorries.
# git trailer: Perplexity Computer Agent
"""khipu-lmdb — durable LMDB persistence backend for the Khipu hash-chained receipt log."""
from __future__ import annotations
from .core import KhipuLMDB  # noqa: F401

__all__ = ["KhipuLMDB"]
__version__ = "1.0.0"
