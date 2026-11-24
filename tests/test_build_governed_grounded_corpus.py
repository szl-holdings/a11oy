#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Golden cases for scripts/build_governed_grounded_corpus.py."""
import importlib.util
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "build_governed_grounded_corpus", os.path.join(ROOT, "scripts", "build_governed_grounded_corpus.py"))
b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b)

PROSE = ("The receipt chain is hash-linked so that changing one byte breaks verification. "
         "Each entry carries the digest of the one before it and is written only on a state change. "
         "A reader recomputes the chain from the first entry and compares the final digest.")


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check_banned_tokens.py").write_text(
        'import re\nBANNED_NO_LEADING = re.compile(\n    r"\\bzzbanned\\b",\n    re.IGNORECASE,\n)\n')
    docs = tmp_path / "docs"
    docs.mkdir()
    for i in range(40):
        (docs / ("d%02d.md" % i)).write_text(
            "# Doc %d\n\n## Alpha %d\n\n%s Variant %d.\n\n## Beta %d\n\n"
            "Energy for lane %d is MEASURED only when a fresh exporter delta exists, never assumed. Variant %d.\n"
            "%s Other %d.\n" % (i, i, PROSE, i, i, i, i, PROSE, i))
    (docs / "mirror.md").write_text("# Doc 0\n\n## Alpha 0\n\n%s Variant 0.\n" % PROSE)
    (docs / "bad.md").write_text("# Bad\n\n## Hype\n\n%s This zzbanned text must never be a source.\n" % PROSE)
    (tmp_path / "T.lean").write_text(
        "theorem foo_bar (n : Nat) :\n    n + 0 = n := by\n  simp\n\n"
        "private lemma baz' (a b : Nat) : a + b = b + a := by\n  omega\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "fixture")
    return tmp_path


def _rows(repo):
    commit = b.git(str(repo), "rev-parse", "HEAD").decode().strip()
    splits, stats = b.build(str(repo), commit)
    return splits, stats, [r for rows in splits.values() for r in rows]


def test_answers_are_copied_from_their_context(repo):
    _, _, rows = _rows(repo)
    answers = [r for r in rows if r["gate_mode"] == "ANSWER"]
    assert answers
    for r in answers:
        user, reply = r["messages"][1]["content"], r["messages"][2]["content"]
        assert reply.startswith("ANSWER\n")
        core = reply.split("\n")[2 if r["item_type"] == "label" else 1]
        assert b.norm_ws(core.replace('The source reads: "', "").rstrip('"')[:80]) in b.norm_ws(user)


def test_abstain_contexts_do_not_contain_the_answer(repo):
    _, _, rows = _rows(repo)
    abstains = [r for r in rows if r["gate_mode"] == "ABSTAIN"]
    assert abstains
    by_question = {r["question"]: r for r in rows if r["gate_mode"] == "ANSWER"}
    for r in abstains:
        assert r["messages"][2]["content"].startswith("ABSTAIN\n")
        twin = by_question[r["question"]]
        assert twin["source"]["context_sha256"] != r["source"]["context_sha256"]


def test_no_file_or_content_crosses_splits(repo):
    splits, stats, _ = _rows(repo)
    checks = b.gate_check(splits)
    assert checks["path_overlap_train_heldout"] == 0
    assert checks["path_overlap_train_validation"] == 0
    assert checks["context_overlap_train_heldout"] == 0
    assert checks["duplicate_prompts"] == 0
    assert stats["dropped_duplicate_context"] >= 1   # docs/mirror.md


def test_banned_text_is_never_a_source(repo):
    _, stats, rows = _rows(repo)
    assert stats["dropped_banned"] >= 1
    assert not any("zzbanned" in m["content"] for r in rows for m in r["messages"])


def test_lean_declarations_with_modifiers_are_found(repo):
    _, _, rows = _rows(repo)
    lean = [r["messages"][2]["content"] for r in rows if r["item_type"] == "lean" and r["gate_mode"] == "ANSWER"]
    assert any("theorem foo_bar (n : Nat) :" in a for a in lean)
    assert any("private lemma baz' (a b : Nat) : a + b = b + a" in a for a in lean)


def test_lean_statement_ends_at_the_definitional_assignment():
    """A `:=` in a `let`, a binder default or a structure literal does not end the statement."""
    text = ("theorem with_let (a b : Nat) :\n    let s := a + b\n    s = b + a := by\n  omega\n\n"
            "theorem with_default (n : Nat := 0) (p : P { x := n }) : n = n := rfl\n\n"
            "-- note := not here\ntheorem after_comment : True := trivial\n")
    _, positives = b.harvest_lean("T.lean", text, "0" * 40)
    cores = {p["needle"]: p["core"] for p in positives}
    assert cores["with_let"].endswith("s = b + a")
    assert "let s := a + b" in cores["with_let"]
    assert cores["with_default"].endswith(": n = n")
    assert cores["after_comment"] == "theorem after_comment : True"


def test_lean_statement_never_runs_into_the_next_declaration():
    """A declaration with no `:=` of its own is skipped, not merged with the one after it."""
    text = ("theorem by_cases : (n : Nat) -> n = n\n  | 0 => rfl\n  | _ + 1 => rfl\n\n"
            "def helper : Nat := 3\n\n"
            "theorem plain (n : Nat) : n = n := rfl\n")
    _, positives = b.harvest_lean("T.lean", text, "0" * 40)
    assert [p["needle"] for p in positives] == ["plain"]


def test_sentence_extract_preserves_parenthesized_punctuation():
    prefix = ("Evidence remains source-bound across separate receipt paths and "
              "cannot be treated as a live deployment claim. ") * 2
    # Force truncation after the sentence ending in '.) ', before the
    # surrounding paragraph ends.
    prefix = prefix.replace(". ", " ")
    body = prefix + "(This observation is not admission.) " + ("Further audited context remains unavailable. " * 8)
    hi = len(prefix) + len("(This observation is not admission.) ") + 2
    extracted = b.first_sentences(body, lo=120, hi=hi)
    assert extracted is not None
    assert extracted.endswith("admission.)")
    assert extracted in b.norm_ws(body)


def test_small_corpus_fails_the_gate(repo):
    """Doctrine negative: a stub-sized corpus must be refused, not published."""
    splits, _, _ = _rows(repo)
    checks = b.gate_check(splits)
    assert checks["passed"] is False
    assert any("distinct train questions" in f for f in checks["failures"])
    assert b.main(["--repo", str(repo), "--out", str(repo / "out")]) == 1


def test_build_is_deterministic(repo):
    a, _, _ = _rows(repo)
    c, _, _ = _rows(repo)
    assert a == c
