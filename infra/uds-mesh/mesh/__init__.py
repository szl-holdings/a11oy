"""UDS-Mesh package root (ADR-0001 canonical home).

Exposes the mesh SDK (`mesh.sdk`) and the operationalized thesis-v22 formulas
(`mesh.formulas`) wired into the cross-organ governance runtime.

ADR-0001 declared `src/mesh/` the canonical home for the WU-1 Byzantine quorum
(`mesh.quorum`) and the WU-3 OTLP bridge (`mesh.otlp_bridge`). PR #76 added the
PAC-Bayes / BLS / Welford formulas and the SDK under the repo-root `mesh/`
package. To present a *single* importable `mesh` namespace regardless of which
physical directory is first on ``sys.path`` (repo-root vs ``src``), we extend
this package's search path to include a sibling ``src/mesh`` if it exists.

This removes the dual-package ``sys.modules['mesh']`` collision that otherwise
made ``mesh.quorum`` / ``mesh.otlp_bridge`` un-importable once ``mesh.formulas``
had been imported (alphabetical test-collection order in the full suite).
"""
from __future__ import annotations

import os as _os

# Merge the canonical src/mesh home into this package's __path__ so that
# `mesh.quorum` and `mesh.otlp_bridge` (physically under src/mesh) resolve even
# when the repo-root `mesh/` package is bound first in sys.modules.
_here = _os.path.dirname(_os.path.abspath(__file__))
_repo_root = _os.path.dirname(_here)
_src_mesh = _os.path.join(_repo_root, "src", "mesh")
if _os.path.isdir(_src_mesh) and _src_mesh not in __path__:
    __path__.append(_src_mesh)
