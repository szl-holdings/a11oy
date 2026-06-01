"""kipu_qillqaq — KIPU receipt-cell substrate + QILLQAQ genome (config + module loading) engine.

HONEST NAMING (no mysticism):
  * KIPU is a content-addressed receipt-cell pool with LMDB (or JSON-file fallback)
    persistence, an in-process pub/sub event bus, and Reed-Solomon erasure coding for
    durability. It is NOT "holographic QEC". Reed-Solomon is the well-understood MDS
    erasure code used by RAID-6, CD/DVD, QR codes, and Backblaze. See coding.py.
  * QILLQAQ is a declarative engine: it reads organ `genome.toml` files (parsed with the
    stdlib `tomllib`), validates them against a schema, and boots `OrganAgent` instances.
    "DNA" here is shorthand for *config*; "boot from DNA" means *parse config + load a
    module/handler*. There is no biology and no magic.

Author: Yachay (SZL Holdings). License: Apache-2.0.
"""

__version__ = "0.1.0"

from .cell import ReceiptCell, content_address
from .pool import KipuPool
from .events import EventBus
from .coding import ReedSolomonCoder, encode_cell, decode_shards
from .genome import Genome, GenomeError, load_genome, validate_genome
from .transcribe import OrganAgent, QillqaqEngine

__all__ = [
    "__version__",
    "ReceiptCell",
    "content_address",
    "KipuPool",
    "EventBus",
    "ReedSolomonCoder",
    "encode_cell",
    "decode_shards",
    "Genome",
    "GenomeError",
    "load_genome",
    "validate_genome",
    "OrganAgent",
    "QillqaqEngine",
]
