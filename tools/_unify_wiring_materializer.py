from pathlib import Path


serve = Path("serve.py")
text = serve.read_text(encoding="utf-8")
anchor = '''except Exception as _szl_lyte_e:  # pragma: no cover
    print(f"[a11oy] LYTE lattice BIND NOT registered: {_szl_lyte_e!r}; SPA + API unaffected", file=__import__("sys").stderr)

# -- KHIPU product organ — original cuts, duals Ari=GreenLight / Kay Pacha=Anatomy.
'''
replacement = '''except Exception as _szl_lyte_e:  # pragma: no cover
    print(f"[a11oy] LYTE lattice BIND NOT registered: {_szl_lyte_e!r}; SPA + API unaffected", file=__import__("sys").stderr)

# -- UNIFY flock ledger — one A11oy package surface, not a separate product Space. --
try:
    import szl_unify_flock as _szl_unify_flock
    _szl_unify_flock.register(app, ns="a11oy")
    print("[a11oy] Unify flock registered: /unify and /api/a11oy/v1/unify/status", file=__import__("sys").stderr)
except Exception as _szl_unify_e:  # pragma: no cover
    print(f"[a11oy] Unify flock NOT registered: {_szl_unify_e!r}; SPA + API unaffected", file=__import__("sys").stderr)

# -- KHIPU product organ — original cuts, duals Ari=GreenLight / Kay Pacha=Anatomy.
'''
if text.count(anchor) != 1:
    raise SystemExit("serve.py: Unify wiring anchor is not unique")
serve.write_text(text.replace(anchor, replacement, 1), encoding="utf-8", newline="\n")

allowlist = Path(".github/register-invocation-allowlist.txt")
allow = allowlist.read_text(encoding="utf-8")
stale = "a11oy_khipu_chat            # PRE-EXISTING unwired: /api/a11oy/v1/khipu chat lab not mounted in serve.py — backlog, wire-or-retire (follow-up)\n"
if allow.count(stale) != 1:
    raise SystemExit("allowlist: stale Khipu exemption anchor is not unique")
allowlist.write_text(allow.replace(stale, "", 1), encoding="utf-8", newline="\n")

Path("tests/test_unify_flock_runtime_wiring.py").write_text(
    '''# SPDX-License-Identifier: Apache-2.0
from pathlib import Path


def test_unify_flock_is_wired_in_the_early_registration_lane() -> None:
    serve = Path("serve.py").read_text(encoding="utf-8")
    block = "import szl_unify_flock as _szl_unify_flock"
    call = '_szl_unify_flock.register(app, ns="a11oy")'
    later_registration = "# -- KHIPU product organ"
    assert block in serve
    assert call in serve
    assert later_registration in serve
    assert serve.index(block) < serve.index(later_registration)


def test_stale_khipu_chat_exemption_is_pruned() -> None:
    allowlist = Path(".github/register-invocation-allowlist.txt").read_text(encoding="utf-8")
    assert "a11oy_khipu_chat" not in allowlist
''',
    encoding="utf-8",
    newline="\n",
)
