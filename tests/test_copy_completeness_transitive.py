# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""Self-test for the TRANSITIVE COPY-completeness guard.

`.github/scripts/copy_completeness.py` fails CI when a Python module reachable
from a serve.py entrypoint is NOT present in the Dockerfile per-file COPY set.
The reusable HF deployer (szl-holdings/.github reusable-hf-deploy.yml) DERIVES
the exact file set pushed to the live Space straight from the Dockerfile COPY
sources, so a module missing from COPY is never shipped → ModuleNotFoundError →
silent 404. This is the recurring "forgot to COPY module X" class that has
bitten szl-holdings/a11oy 3x (canonical example: szl_energy_measured, imported
by a11oy_harvest_endpoints — a module registered in serve.py, NOT imported by
serve.py directly).

These network-free tests drive the REAL module against synthetic trees so a
future refactor can neither (a) stop catching the transitive missing-COPY case,
nor (b) start flagging modules that ARE covered by COPY. They also assert the
SHIPPED repo is clean under the transitive closure.
"""
import importlib.util
import os
import textwrap

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_MOD = os.path.join(_ROOT, ".github", "scripts", "copy_completeness.py")
_spec = importlib.util.spec_from_file_location("copy_completeness", _MOD)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

_STDLIB = cc._stdlib_names()


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(textwrap.dedent(body))
    return p


def _mk_synthetic_tree(tmp_path):
    """serve.py imports a registered submodule which transitively imports a leaf.

    Mirrors the real shape:
        serve.py                -> import a11oy_harvest_endpoints (registered)
        a11oy_harvest_endpoints -> from szl_energy_measured import measured_channel
    """
    _write(tmp_path, "serve.py", """
        try:
            import a11oy_harvest_endpoints as _h
            _h.register(app, ns="a11oy")
        except Exception as e:
            print("NOT registered", e)
    """)
    _write(tmp_path, "a11oy_harvest_endpoints.py", """
        from szl_energy_measured import measured_channel
        def register(app, ns="a11oy"):
            return {"ok": True}
    """)
    _write(tmp_path, "szl_energy_measured.py", "def measured_channel():\n    return {}\n")


def test_transitive_closure_includes_second_level_module(tmp_path):
    """The leaf szl_energy_measured must be discovered even though serve.py does
    not import it directly (it is imported by the registered submodule)."""
    _mk_synthetic_tree(tmp_path)
    closure = cc.collect_transitive_local_imports(
        ["serve.py"], str(tmp_path), _STDLIB
    )["serve.py"]
    assert "a11oy_harvest_endpoints" in closure
    assert "szl_energy_measured" in closure, (
        "transitive closure MUST reach the second-level import "
        "(the szl_energy_measured regression class)"
    )


def test_direct_only_mode_MISSES_the_transitive_module(tmp_path):
    """Guardrail: prove the legacy direct-only parse does NOT see the leaf, so we
    know the transitive closure is what closes the gap (not a coincidence)."""
    _mk_synthetic_tree(tmp_path)
    direct = cc.collect_local_imports(["serve.py"], str(tmp_path), _STDLIB)["serve.py"]
    assert "a11oy_harvest_endpoints" in direct
    assert "szl_energy_measured" not in direct


def test_guard_FAILS_when_transitive_module_missing_from_copy(tmp_path):
    """End-to-end: a Dockerfile that COPYs the entrypoint + submodule but FORGETS
    the transitively-required leaf must make the guard exit 1."""
    _mk_synthetic_tree(tmp_path)
    # Dockerfile deliberately OMITS szl_energy_measured.py
    _write(tmp_path, "Dockerfile", """
        FROM python:3.12-slim
        COPY serve.py a11oy_harvest_endpoints.py ./
        CMD ["python", "serve.py"]
    """)
    rc = cc.main([
        "--dockerfile", str(tmp_path / "Dockerfile"),
        "--root", str(tmp_path),
        "--entrypoints", "serve.py",
    ])
    assert rc == 1, "guard must FAIL when a transitively-required module is not COPY'd"


def test_guard_PASSES_when_transitive_module_present_in_copy(tmp_path):
    """The same tree PASSES once the leaf is added to the Dockerfile COPY."""
    _mk_synthetic_tree(tmp_path)
    _write(tmp_path, "Dockerfile", """
        FROM python:3.12-slim
        COPY serve.py a11oy_harvest_endpoints.py szl_energy_measured.py ./
        CMD ["python", "serve.py"]
    """)
    rc = cc.main([
        "--dockerfile", str(tmp_path / "Dockerfile"),
        "--root", str(tmp_path),
        "--entrypoints", "serve.py",
    ])
    assert rc == 0, "guard must PASS when every reachable module is COPY'd"


def test_direct_only_mode_would_let_the_bug_slip(tmp_path):
    """Regression witness: with --no-transitive, the SAME broken Dockerfile
    passes (exit 0) — documenting exactly the class of bug the closure fixes."""
    _mk_synthetic_tree(tmp_path)
    _write(tmp_path, "Dockerfile", """
        FROM python:3.12-slim
        COPY serve.py a11oy_harvest_endpoints.py ./
        CMD ["python", "serve.py"]
    """)
    rc = cc.main([
        "--dockerfile", str(tmp_path / "Dockerfile"),
        "--root", str(tmp_path),
        "--entrypoints", "serve.py",
        "--no-transitive",
    ])
    assert rc == 0, (
        "legacy direct-only mode does NOT catch the transitive miss — this is "
        "why the transitive closure is the default"
    )


def test_shipped_repo_is_clean_under_transitive_closure():
    """The REAL a11oy repo must PASS: every module reachable from serve.py is in
    the Dockerfile COPY set (including the szl_energy_measured transitive leaf)."""
    dockerfile = os.path.join(_ROOT, "Dockerfile")
    if not os.path.isfile(dockerfile):
        pytest.skip("Dockerfile not present in this checkout")
    rc = cc.main([
        "--dockerfile", dockerfile,
        "--root", _ROOT,
        "--entrypoints", "serve.py",
    ])
    assert rc == 0, "shipped a11oy Dockerfile COPY set is incomplete under the transitive closure"
