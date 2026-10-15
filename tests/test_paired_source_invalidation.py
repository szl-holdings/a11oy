"""Synthetic-only contract tests for paired source invalidation."""

from dataclasses import replace

from scripts import paired_source_invalidation as experiment


def test_pairs_hold_proposals_fixed_and_keep_all_cases_out_of_training():
    pairs = experiment.fixture_pairs()
    assert len(pairs) == 120
    assert len({supported.pair_id for supported, _ in pairs}) == 120
    for supported, invalid in pairs:
        assert supported.proposal == invalid.proposal
        assert not supported.training_eligible
        assert not invalid.training_eligible
        assert supported.mutation == invalid.mutation


def test_all_four_mutations_flip_only_the_evidence_bound_gate():
    expected_reasons = {
        "missing_support_span": "NO_SELECTED_SUPPORT",
        "stale_proposal_hash": "PROPOSAL_HASH_MISMATCH",
        "conflicting_assertion": "CONFLICTING_ASSERTIONS",
        "relevant_but_insufficient": "NO_SELECTED_SUPPORT",
    }
    seen = {mode: 0 for mode in experiment.MUTATIONS}
    for supported, invalid in experiment.fixture_pairs():
        assert experiment.proposal_only(supported.proposal).action == "ANSWER"
        assert experiment.proposal_only(invalid.proposal).action == "ANSWER"
        assert experiment.source_bound_gate(supported) == experiment.Decision(
            "ANSWER", "LITERAL_SOURCE_MATCH"
        )
        assert experiment.source_bound_gate(invalid) == experiment.Decision(
            "ABSTAIN", expected_reasons[invalid.mutation]
        )
        seen[invalid.mutation] += 1
    assert seen == {mode: 30 for mode in experiment.MUTATIONS}


def test_gate_denies_unanchored_content_or_fabricated_selected_span():
    supported, _ = experiment.fixture_pairs(1)[0]
    original = supported.sources[0]
    tampered = replace(original, content=original.content + "\nadded")
    assert experiment.source_bound_gate(replace(supported, sources=(tampered,))) == (
        experiment.Decision("ABSTAIN", "SOURCE_HASH_MISMATCH")
    )
    fabricated = replace(original, selected_spans=(original.selected_spans[0] + "x",))
    assert experiment.source_bound_gate(replace(supported, sources=(fabricated,))) == (
        experiment.Decision("ABSTAIN", "SPAN_NOT_IN_SOURCE")
    )


def test_gate_denies_wrong_answer_duplicate_source_and_wrong_anchor_set():
    supported, _ = experiment.fixture_pairs(1)[0]
    wrong = replace(supported.proposal, answer="an-unrelated-answer")
    assert experiment.source_bound_gate(replace(supported, proposal=wrong)) == (
        experiment.Decision("ABSTAIN", "NO_SELECTED_SUPPORT")
    )
    assert experiment.source_bound_gate(replace(supported,
        sources=supported.sources * 2)) == experiment.Decision(
            "ABSTAIN", "SOURCE_SET_MISMATCH"
        )
    assert experiment.source_bound_gate(replace(supported,
        expected_hashes={})) == experiment.Decision(
            "ABSTAIN", "SOURCE_SET_MISMATCH"
        )


def test_gate_denies_conflict_hidden_outside_selected_spans():
    supported, invalid = next(
        pair for pair in experiment.fixture_pairs(1)
        if pair[0].mutation == "conflicting_assertion"
    )
    assert experiment.source_bound_gate(supported).action == "ANSWER"
    hidden = replace(invalid.sources[1], selected_spans=())
    hidden_conflict = replace(invalid, sources=(invalid.sources[0], hidden))
    assert experiment.source_bound_gate(hidden_conflict) == experiment.Decision(
        "ABSTAIN", "CONFLICTING_ASSERTIONS"
    )


def test_report_is_reproducible_with_explicit_denominators():
    report = experiment.run_experiment()
    assert report == experiment.run_experiment()
    assert report["evidence_class"] == "SIMULATED"
    assert report["denominators"] == {
        "pairs": 120, "supported": 120, "invalidated": 120,
    }
    assert report["proposal_only"] == {
        "supported_answers": 120, "invalidated_answers": 120,
    }
    assert report["source_bound_gate"]["supported_answers"] == 120
    assert report["source_bound_gate"]["invalidated_abstentions"] == 120
    assert report["source_bound_gate"]["paired_reversals"] == 120
    assert report["model_invocations"] == 0
    assert report["external_effects"] == 0
    assert report["fixture_sha256"] == (
        "de177b7289856e2e1f8a22ad6755d0a50b8691f657ddedd2f52480f7ff1555d9"
    )
