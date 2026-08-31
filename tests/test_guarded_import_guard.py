"""Self-test for the guarded-import liveness guard (silent-no-op dead imports).

`a11oy_guarded_import_guard.py` turns a `try: import <first-party-mod> ... except`
whose module file does NOT exist (and is not allowlisted) into a RED CI gate,
instead of the historical silent stderr no-op that let whole features
(`/code` v4, `/about/thesis`, the v3 kernels tab, ...) vanish from the live route
table with no signal.

This network-free test drives the REAL scan()/AST path against synthetic trees
so a future refactor can neither (a) stop catching a dead guarded import, nor
(b) start punishing a legitimate guarded import of an installed PACKAGE (the
`szl_substrate` optional-dep pattern). It also asserts the SHIPPED repo is clean
under its own allowlist.
"""
import importlib.util
import os
import textwrap

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_MOD = os.path.join(_ROOT, "a11oy_guarded_import_guard.py")
_spec = importlib.util.spec_from_file_location("gig", _MOD)
gig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gig)


def _mk(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(textwrap.dedent(body))
    return p


def test_dead_guarded_first_party_import_is_flagged(tmp_path):
    _mk(tmp_path, "serve.py", """
        try:
            import a11oy_ghost_feature as _g
            _g.register(app)
        except Exception as e:
            print(e)
    """)
    dead = gig.scan(str(tmp_path))
    assert any(m == "a11oy_ghost_feature" for _, _, m in dead), (
        "a guarded import of a non-existent first-party module must be flagged"
    )


def test_existing_module_not_flagged(tmp_path):
    _mk(tmp_path, "a11oy_real.py", "def register(app):\n    return {}\n")
    _mk(tmp_path, "serve.py", """
        try:
            import a11oy_real as _r
            _r.register(app)
        except Exception as e:
            print(e)
    """)
    assert gig.scan(str(tmp_path)) == []


def test_allowlisted_optional_package_not_flagged(tmp_path):
    _mk(tmp_path, "serve.py", """
        try:
            from szl_substrate import szl_dsse
        except Exception:
            import szl_dsse
    """)
    _mk(tmp_path, ".guarded-import-allowlist",
        "szl_substrate  # [OPTIONAL-PKG] installed package\n")
    assert gig.scan(str(tmp_path)) == [], (
        "a guarded import of an ALLOWLISTED installed package must PASS"
    )


def test_third_party_import_ignored(tmp_path):
    """Only first-party szl_/a11oy_ modules are in scope; a normal optional
    third-party dep behind try/except is not our concern."""
    _mk(tmp_path, "serve.py", """
        try:
            import lmdb
        except Exception:
            lmdb = None
    """)
    assert gig.scan(str(tmp_path)) == []


def test_import_outside_try_ignored(tmp_path):
    """An UNguarded import of a missing module would crash at import time (a
    loud failure) — it is out of scope for the *silent* no-op guard."""
    _mk(tmp_path, "serve.py", "import a11oy_missing_but_unguarded\n")
    assert gig.scan(str(tmp_path)) == []


def test_shipped_repo_is_clean_under_its_allowlist():
    """The real repo must pass its own guard (every dead stub is either fixed
    or consciously ledgered in .guarded-import-allowlist)."""
    assert gig.scan(_ROOT) == [], (
        "the shipped repo has an un-ledgered dead guarded import; "
        "fix it, remove it, or add it to .guarded-import-allowlist with a reason"
    )
