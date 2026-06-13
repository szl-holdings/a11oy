"""Evidence tab auto-refresh surface regression test (Task #878).

The Evidence & Research tab carries a subtle "auto-refreshing" pill plus a
GENUINE 180s background source re-probe (marker ``evidence-autorecheck-539``).
It is a pure front-end patch that lives inside a large, concurrently-edited
console file on BOTH organs:

  * a11oy    -> ``pages/console.html``           (inside the appended IIFE)
  * killinchu -> ``killinchu_elite_console.py``  (inline in its evidence tab)

Because that file is rebuilt and hand-edited by many siblings, a careless edit
or a regenerating rebuild could silently drop the feature — the exact class of
regression the operator/reason surface tests (``test_operator_reason_envelope``)
already guard against. This module locks the auto-refresh feature in with a
network-free, dependency-free string-surface check, deployed BYTE-IDENTICAL to
both repos (each repo ships exactly one of the candidate console files).

It guards that the console still ships:
  1. the feature marker ``evidence-autorecheck-539``,
  2. the ``#ev-autostat`` pill + its ``.ev-autodot`` pulsing dot,
  3. the ``__ev_recheck`` background re-probe ``setInterval`` timer + ``ev_sweep``,
  4. the ``visibilitychange`` / ``document.hidden`` pause-when-hidden handler
     (bound once via ``__ev_vis_bound``).

A negative-fixture self-test proves the check actually FAILS LOUD when the
feature is stripped, so the guard cannot rot into a silent always-pass.
"""
import os

import pytest

# Repo-relative candidate console files. Each organ ships exactly one of these;
# the byte-identical guard probes both names so the SAME file works in either repo.
CONSOLE_CANDIDATES = (
    "pages/console.html",            # a11oy console
    "killinchu_elite_console.py",    # killinchu /elite console
)

# Every token below must be present in a console that ships the auto-refresh
# feature. Dropping any one of them is a regression of the feature.
REQUIRED_TOKENS = (
    "evidence-autorecheck-539",   # the feature marker
    'id="ev-autostat"',           # the auto-refresh status pill element
    "ev-autodot",                 # the pulsing status dot class
    "ev-autolbl",                 # the pill label ("auto-refreshing" / "paused")
    "auto-refreshing",            # honest pill text
    "__ev_recheck",               # the background re-probe timer handle
    "setInterval",                # the re-probe is a real interval timer
    "ev_sweep",                   # the genuine source re-probe sweep
    "visibilitychange",           # pause/resume on tab visibility change
    "__ev_vis_bound",             # the visibilitychange bind guard (bound once)
    "document.hidden",            # honesty: pause the timer while the tab is hidden
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _missing_tokens(text):
    """Return the sorted list of REQUIRED_TOKENS absent from ``text``."""
    return sorted(t for t in REQUIRED_TOKENS if t not in text)


def _existing_consoles():
    """(path, text) for each candidate console file that exists in this repo."""
    out = []
    for rel in CONSOLE_CANDIDATES:
        p = os.path.join(_REPO_ROOT, rel)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                out.append((rel, fh.read()))
    return out


def test_at_least_one_console_present():
    """Guard the guard: if neither console file exists the surface moved/renamed
    and the feature check below would vacuously pass — fail loud instead."""
    found = [rel for rel, _ in _existing_consoles()]
    assert found, (
        "no console file found in this repo; expected one of "
        f"{CONSOLE_CANDIDATES} relative to {_REPO_ROOT}"
    )


@pytest.mark.parametrize("rel,text", _existing_consoles(),
                         ids=[rel for rel, _ in _existing_consoles()] or ["none"])
def test_console_ships_autorefresh_feature(rel, text):
    """The shipped console must still carry every auto-refresh feature token."""
    missing = _missing_tokens(text)
    assert not missing, (
        f"{rel} dropped the Evidence auto-refresh feature "
        f"(marker evidence-autorecheck-539); missing tokens: {missing}"
    )


# --- negative-fixture self-test: the check must FAIL LOUD when stripped --------

_SYNTH_POSITIVE = "\n".join([
    "/* evidence-autorecheck-539 — auto-refresh pill + background re-probe */",
    '<div id="ev-autostat"><span class="ev-autodot"></span>'
    '<span class="ev-autolbl">auto-refreshing</span></div>',
    "window.__ev_recheck=setInterval(function(){ window.ev_sweep(); },180000);",
    "if(!window.__ev_vis_bound){window.__ev_vis_bound=true;"
    "document.addEventListener('visibilitychange',function(){"
    "if(!document.hidden) window.ev_sweep();});}",
])

_SYNTH_STRIPPED = (
    "/* evidence tab without the auto-refresh background re-probe */\n"
    "<div id=\"ev-sources\">curated sources only</div>\n"
)


def test_self_test_positive_sample_passes():
    """A synthetic console carrying the feature must report nothing missing."""
    assert _missing_tokens(_SYNTH_POSITIVE) == []


def test_self_test_stripped_sample_is_caught():
    """A console with the feature removed must be flagged on EVERY token, so the
    guard cannot silently degrade into an always-pass."""
    missing = _missing_tokens(_SYNTH_STRIPPED)
    assert sorted(missing) == sorted(REQUIRED_TOKENS), (
        "negative fixture should flag every required token as missing; "
        f"got {missing}"
    )
