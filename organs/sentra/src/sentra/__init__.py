# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""sentra — policy immune system: deny by default, allow with proof.

Spec-conformant provenance organs:
  - sentra.dsse     : DSSEv1 PAE + Ed25519 sign/verify.
  - sentra.rekor    : Sigstore Rekor fetch + RFC 6962 Merkle inclusion verify.
  - sentra.in_toto  : in-toto Statement + SLSA Provenance v1 attestation.
"""

__version__ = "0.1.0"
