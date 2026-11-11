#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Isolated, in-memory acceptance tests for the governed graph executor.

These callbacks are synthetic local capabilities.  They never import the app,
call a provider, open a network connection, or produce an external effect.
"""

import copy
import json

import pytest

import szl_sgh_scheduler as scheduler
from routers.governed_graph_operations import GraphContractError, analyse_graph


def _node(node_id, *, role="worker", depends_on=(), control_after=(),
          consumes=(), produces=(), **extra):
    return {
        "id": node_id,
        "role": role,
        "depends_on": list(depends_on),
        "control_after": list(control_after),
        "consumes": list(consumes),
        "produces": list(produces),
        **extra,
    }


def _graph(nodes, *, external_inputs=("question",), terminals=None):
    if terminals is None:
        predecessors = {
            predecessor
            for node in nodes
            for predecessor in node.get("depends_on", ()) + node.get("control_after", ())
        }
        terminals = [node["id"] for node in nodes if node["id"] not in predecessors]
    return {
        "schema": "szl.governed-graph/v1",
        "graph_id": "local-test-graph",
        "goal": "Produce an inspectable local evidence result.",
        "external_inputs": list(external_inputs),
        "nodes": nodes,
        "anchors": [{
            "id": "source-evidence",
            "type": "source",
            "nodes": terminals,
            "required": True,
            "description": "Declared source evidence for terminal output.",
        }],
        "budget": {
            "max_nodes": 8,
            "max_parallel": 2,
            "max_depth": 8,
            "max_total_iterations": 8,
        },
    }


def _chain():
    return _graph([
        _node("scope", role="scope", consumes=("question",), produces=("scope",)),
        _node("collect", depends_on=("scope",), consumes=("scope",),
              produces=("evidence",)),
        _node("answer", role="synthesizer", depends_on=("collect",),
              consumes=("evidence",), produces=("answer",)),
    ])


def _diamond():
    return _graph([
        _node("scope", role="scope", consumes=("question",), produces=("scope",)),
        _node("papers", depends_on=("scope",), consumes=("scope",),
              produces=("paper",)),
        _node("repos", depends_on=("scope",), consumes=("scope",),
              produces=("repo",)),
        _node("reduce", role="reducer", depends_on=("papers", "repos"),
              consumes=("paper", "repo"), produces=("answer",)),
    ])


def _capabilities(outputs, *, observed=None):
    observed = observed if observed is not None else []
    admissions = {}
    implementations = {}
    verifiers = {}
    for node_id, node_outputs in outputs.items():
        def admit(context, current=node_id):
            observed.append(("admit", current, context["attempt"]))
            return True

        def run(context, current=node_id, result=node_outputs):
            observed.append(("run", current, context["attempt"],
                             copy.deepcopy(context["inputs"])))
            return {"status": "SUCCEEDED", "outputs": copy.deepcopy(result)}

        def verify(context, current=node_id):
            observed.append(("verify", current, context["attempt"]))
            return True

        admissions[node_id] = admit
        implementations[node_id] = run
        verifiers[node_id] = verify
    return admissions, implementations, verifiers


def _execute(contract, outputs, *, input_values=None, observed=None, digest=None,
             admissions=None, implementations=None, verifiers=None, **options):
    defaults = _capabilities(outputs, observed=observed)
    return scheduler.execute_governed_plan(
        contract,
        digest if digest is not None else analyse_graph(contract)["contract_digest"],
        input_values={"question": "What is supported?"} if input_values is None else input_values,
        admissions=defaults[0] if admissions is None else admissions,
        implementations=defaults[1] if implementations is None else implementations,
        verifiers=defaults[2] if verifiers is None else verifiers,
        **options,
    )


def _assert_no_dispatch(contract, outputs, *, digest=None, **options):
    observed = []
    capabilities = _capabilities(outputs, observed=observed)
    try:
        result = scheduler.execute_governed_plan(
            contract,
            digest if digest is not None else analyse_graph(contract)["contract_digest"],
            input_values={"question": "What is supported?"},
            admissions=capabilities[0],
            implementations=capabilities[1],
            verifiers=capabilities[2],
            **options,
        )
    except GraphContractError:
        assert observed == []
        return
    assert result["disposition"] == "NOT_INVOKED"
    assert observed == []


def test_executes_three_node_chain_once_in_dependency_order():
    observed = []
    result = _execute(_chain(), {
        "scope": {"scope": "read only"},
        "collect": {"evidence": ["source-1"]},
        "answer": {"answer": "supported by source-1"},
    }, observed=observed)
    assert result["disposition"] == "SUCCEEDED"
    assert [event[1] for event in observed if event[0] == "run"] == [
        "scope", "collect", "answer"
    ]
    assert [result["nodes"][node]["attempts"] for node in
            ("scope", "collect", "answer")] == [1, 1, 1]
    assert [event[3] for event in observed if event[0] == "run"] == [
        {"question": "What is supported?"},
        {"scope": "read only"},
        {"evidence": ["source-1"]},
    ]


@pytest.mark.parametrize("both_support", (True, False))
def test_executes_diamond_fan_in_after_both_verified_inputs(both_support):
    # Source identities are supplied by the caller. No callback fetches them.
    supplied = {
        "question": {
            "text": "Is the claim supported?",
            "permitted_sources": {
                "paper": {"source_id": "paper-1",
                          "url": "https://example.org/paper-1", "supports": True},
                "repo": {"source_id": "repo-1",
                         "url": "https://example.org/repo-1",
                         "supports": both_support},
            },
        }
    }
    observed = []
    admissions, implementations, verifiers = _capabilities({
        "scope": {}, "papers": {}, "repos": {}, "reduce": {}
    }, observed=observed)

    def local_run(node_id, context):
        inputs = context["inputs"]
        observed.append(("run", node_id, context["attempt"], copy.deepcopy(inputs)))
        if node_id == "scope":
            outputs = {"scope": inputs["question"]}
        elif node_id in {"papers", "repos"}:
            key = "paper" if node_id == "papers" else "repo"
            outputs = {key: inputs["scope"]["permitted_sources"][key]}
        else:
            findings = [inputs["paper"], inputs["repo"]]
            supported = all(finding["supports"] is True for finding in findings)
            outputs = {"answer": {
                "status": "CITED" if supported else "ABSTAIN",
                "text": "Supported by both sources." if supported else
                        "The supplied findings do not jointly support the claim.",
                "citations": [
                    {"source_id": finding["source_id"], "url": finding["url"]}
                    for finding in findings
                ] if supported else [],
            }}
        return {"status": "SUCCEEDED", "outputs": outputs}

    for node_id in implementations:
        implementations[node_id] = (
            lambda context, current=node_id: local_run(current, context)
        )

    def verify_answer(context):
        answer = context["outputs"]["answer"]
        findings = [context["inputs"]["paper"], context["inputs"]["repo"]]
        expected_citations = [
            {"source_id": finding["source_id"], "url": finding["url"]}
            for finding in findings
        ]
        if answer["status"] == "ABSTAIN":
            return answer["citations"] == [] and not all(
                finding["supports"] for finding in findings
            )
        return answer["status"] == "CITED" and answer["citations"] == expected_citations

    verifiers["reduce"] = verify_answer
    result = _execute(_diamond(), {}, input_values=supplied, observed=observed,
                      admissions=admissions, implementations=implementations,
                      verifiers=verifiers)
    assert result["disposition"] == "SUCCEEDED"
    assert [event[1] for event in observed if event[0] == "run"] == [
        "scope", "papers", "repos", "reduce"
    ]
    assert observed.index(("verify", "papers", 1)) < next(
        index for index, event in enumerate(observed)
        if event[0:2] == ("run", "reduce")
    )
    assert observed.index(("verify", "repos", 1)) < next(
        index for index, event in enumerate(observed)
        if event[0:2] == ("run", "reduce")
    )
    reduce_call = next(event for event in observed if event[0:2] == ("run", "reduce"))
    assert reduce_call[3] == supplied["question"]["permitted_sources"]
    answer = result["nodes"]["reduce"]["outputs"]["answer"]
    assert answer["status"] == ("CITED" if both_support else "ABSTAIN")
    assert {citation["url"] for citation in answer["citations"]} <= {
        source["url"] for source in supplied["question"]["permitted_sources"].values()
    }
    assert result["nodes"]["reduce"]["receipt_id"]
    assert result["transitions"][-1]["result"] == "SUCCEEDED"


def test_control_after_orders_without_fabricating_data():
    contract = _graph([
        _node("prepare", consumes=("question",), produces=("prepared",)),
        _node("review", control_after=("prepare",), consumes=("question",),
              produces=("answer",)),
    ])
    observed = []
    result = _execute(contract, {
        "prepare": {"prepared": "context"}, "review": {"answer": "done"}
    }, observed=observed)
    assert result["disposition"] == "SUCCEEDED"
    assert [event[1] for event in observed if event[0] == "run"] == [
        "prepare", "review"
    ]
    review_call = next(event for event in observed if event[0:2] == ("run", "review"))
    assert review_call[3] == {"question": "What is supported?"}


def test_same_contract_and_callbacks_produce_same_receipt_chain():
    graph = _chain()
    outputs = {
        "scope": {"scope": "rules"},
        "collect": {"evidence": ["paper"]},
        "answer": {"answer": "cited"},
    }
    first = _execute(graph, outputs)
    second = _execute(copy.deepcopy(graph), outputs)
    assert first["disposition"] == second["disposition"] == "SUCCEEDED"
    assert first["transitions"] == second["transitions"]
    assert {node: value["receipt_id"] for node, value in first["nodes"].items()} == {
        node: value["receipt_id"] for node, value in second["nodes"].items()
    }


def test_digest_mismatch_invokes_no_callback():
    _assert_no_dispatch(_chain(), {
        "scope": {"scope": "x"}, "collect": {"evidence": "x"},
        "answer": {"answer": "x"}
    }, digest="0" * 64)


@pytest.mark.parametrize("damage", ("duplicate", "missing_dependency", "cycle"))
def test_malformed_duplicate_missing_dependency_and_cycle_invoke_nothing(damage):
    graph = _chain()
    if damage == "duplicate":
        graph["nodes"][1]["id"] = "scope"
    elif damage == "missing_dependency":
        graph["nodes"][1]["depends_on"] = ["missing"]
    else:
        graph["nodes"][0]["depends_on"] = ["answer"]
    observed = []
    capabilities = _capabilities({node["id"]: {"answer": "x"} for node in graph["nodes"]},
                                 observed=observed)
    try:
        result = scheduler.execute_governed_plan(
            graph, "0" * 64, input_values={"question": "x"},
            admissions=capabilities[0], implementations=capabilities[1],
            verifiers=capabilities[2],
        )
    except GraphContractError:
        pass
    else:
        assert result["disposition"] == "NOT_INVOKED"
    assert observed == []


def test_analysis_blockers_invoke_no_callback():
    graph = _chain()
    graph["budget"]["max_nodes"] = 2
    _assert_no_dispatch(graph, {
        "scope": {"scope": "x"}, "collect": {"evidence": "x"},
        "answer": {"answer": "x"}
    })


@pytest.mark.parametrize("change", (
    {"writes": ["file:local"]},
    {"authority": "HUMAN"},
    {"authority": "WRITE_GOVERNED"},
    {"side_effecting": True, "authority": "WRITE_GOVERNED"},
))
def test_write_human_and_side_effecting_nodes_are_not_invoked(change):
    graph = _graph([_node("only", consumes=("question",), produces=("answer",),
                         **change)])
    if change.get("side_effecting"):
        graph["anchors"].append({
            "id": "write-receipt", "type": "receipt", "nodes": ["only"],
            "required": True, "description": "Declared write receipt anchor."
        })
    _assert_no_dispatch(graph, {"only": {"answer": "x"}})


@pytest.mark.parametrize("missing", ("admissions", "implementations", "verifiers"))
def test_missing_admission_or_callback_is_not_invoked(missing):
    graph = _chain()
    outputs = {
        "scope": {"scope": "x"}, "collect": {"evidence": "x"},
        "answer": {"answer": "x"}
    }
    observed = []
    capabilities = dict(zip(("admissions", "implementations", "verifiers"),
                            _capabilities(outputs, observed=observed)))
    del capabilities[missing]["scope"]
    result = _execute(graph, outputs, observed=observed, **capabilities)
    assert result["disposition"] == "NOT_INVOKED"
    assert not any(event[0] == "run" for event in observed)
    assert all(item["status"] == "NOT_INVOKED" and item["attempts"] == 0
               for item in result["nodes"].values())


def test_admission_is_rechecked_before_retry():
    graph = _graph([_node("only", consumes=("question",), produces=("answer",))])
    observed = []
    admissions, implementations, verifiers = _capabilities({
        "only": {"answer": "unused"}
    }, observed=observed)
    admissions["only"] = lambda context: (
        observed.append(("admit", context["attempt"])) or context["attempt"] == 1
    )
    implementations["only"] = lambda context: (
        observed.append(("run", context["attempt"])) or
        {"status": "RETRYABLE_FAILURE", "failure_kind": "SYNTHETIC"}
    )
    result = _execute(graph, {"only": {"answer": "unused"}}, observed=observed,
                      admissions=admissions, implementations=implementations,
                      verifiers=verifiers)
    assert result["disposition"] == "BLOCKED"
    assert ("admit", 1) in observed and ("admit", 2) in observed
    assert [event for event in observed if event[0] == "run"] == [("run", 1)]


def test_gate_denial_is_terminal_and_not_retried():
    graph = _chain()
    observed = []
    admissions, implementations, verifiers = _capabilities({
        "scope": {"scope": "x"}, "collect": {"evidence": "x"},
        "answer": {"answer": "x"}
    }, observed=observed)
    admissions["scope"] = lambda context: (
        observed.append(("deny", context["attempt"])) or False
    )
    result = _execute(graph, {}, observed=observed, admissions=admissions,
                      implementations=implementations, verifiers=verifiers,
                      max_attempts_per_node=5)
    assert result["disposition"] == "BLOCKED"
    assert [event for event in observed if event[0] == "deny"] == [("deny", 1)]
    assert not any(event[0] == "run" for event in observed)
    assert result["nodes"]["collect"]["status"] == "BLOCKED"


@pytest.mark.parametrize("failed_status", ("DENIED", "FAILED"))
def test_blocked_descendant_receipts_bind_terminal_predecessor(failed_status):
    graph = _chain()
    admissions, implementations, verifiers = _capabilities({
        "scope": {"scope": "x"}, "collect": {"evidence": "x"},
        "answer": {"answer": "x"}
    })
    if failed_status == "DENIED":
        admissions["scope"] = lambda _context: False
    else:
        implementations["scope"] = lambda _context: {
            "status": "UNKNOWN", "outputs": {"scope": "x"}
        }
    result = _execute(graph, {}, admissions=admissions,
                      implementations=implementations, verifiers=verifiers)
    assert result["disposition"] == "BLOCKED"
    assert result["nodes"]["scope"]["status"] == failed_status
    assert result["nodes"]["collect"]["status"] == "BLOCKED"
    assert result["nodes"]["answer"]["status"] == "BLOCKED"
    terminal_ids = {node_id: result["nodes"][node_id]["receipt_id"]
                    for node_id in ("scope", "collect", "answer")}
    assert all(terminal_ids.values())
    blocked_receipts = {
        item["node_id"]: item for item in result["transitions"]
        if item["result"] == "BLOCKED"
    }
    assert blocked_receipts["collect"]["predecessor_receipts"] == [
        {"node_id": "scope", "receipt_id": terminal_ids["scope"]}
    ]
    assert blocked_receipts["answer"]["predecessor_receipts"] == [
        {"node_id": "collect", "receipt_id": terminal_ids["collect"]}
    ]


def test_verifier_failure_blocks_all_descendants():
    graph = _chain()
    observed = []
    admissions, implementations, verifiers = _capabilities({
        "scope": {"scope": "x"}, "collect": {"evidence": "x"},
        "answer": {"answer": "x"}
    }, observed=observed)
    verifiers["scope"] = lambda context: False
    result = _execute(graph, {}, observed=observed, admissions=admissions,
                      implementations=implementations, verifiers=verifiers)
    assert result["disposition"] == "BLOCKED"
    assert [event[1] for event in observed if event[0] == "run"] == ["scope"]
    assert result["nodes"]["collect"]["status"] == "BLOCKED"
    assert result["nodes"]["answer"]["status"] == "BLOCKED"


def test_retryable_failure_recovers_only_within_node_and_run_budgets():
    graph = _chain()
    observed = []
    admissions, implementations, verifiers = _capabilities({
        "scope": {"scope": "rules"}, "collect": {"evidence": "paper"},
        "answer": {"answer": "cited"}
    }, observed=observed)
    original = implementations["scope"]

    def one_retry(context):
        if context["attempt"] == 1:
            observed.append(("retry", context["attempt"]))
            return {"status": "RETRYABLE_FAILURE", "failure_kind": "LOCAL"}
        return original(context)

    implementations["scope"] = one_retry
    recovered = _execute(graph, {}, observed=observed, admissions=admissions,
                         implementations=implementations, verifiers=verifiers,
                         max_attempts_per_node=2, max_total_attempts=4)
    assert recovered["disposition"] == "SUCCEEDED"
    assert recovered["nodes"]["scope"]["attempts"] == 2
    assert [event[1] for event in observed if event[0] == "run"] == [
        "scope", "collect", "answer"
    ]

    exhausted_observed = []
    exhausted_admissions, exhausted_implementations, exhausted_verifiers = _capabilities({
        "scope": {"scope": "rules"}, "collect": {"evidence": "paper"},
        "answer": {"answer": "cited"}
    }, observed=exhausted_observed)
    scope_success = exhausted_implementations["scope"]

    def exhausted_first_retry(context):
        if context["attempt"] == 1:
            exhausted_observed.append(("retry", context["attempt"]))
            return {"status": "RETRYABLE_FAILURE", "failure_kind": "LOCAL"}
        return scope_success(context)

    exhausted_implementations["scope"] = exhausted_first_retry
    exhausted = _execute(graph, {}, observed=exhausted_observed,
                         admissions=exhausted_admissions,
                         implementations=exhausted_implementations,
                         verifiers=exhausted_verifiers,
                         max_attempts_per_node=2, max_total_attempts=3)
    assert exhausted["disposition"] == "BLOCKED"
    assert exhausted["nodes"]["answer"]["status"] == "BLOCKED"
    assert exhausted["nodes"]["answer"]["reason"] == "ATTEMPT_BUDGET_EXHAUSTED"
    assert exhausted["attempts_used"] == 3
    assert [event[1] for event in exhausted_observed if event[0] == "run"] == [
        "scope", "collect"
    ]
    assert exhausted["nodes"]["scope"]["attempts"] == 2
    assert exhausted["nodes"]["collect"]["attempts"] == 1
    assert exhausted["nodes"]["answer"]["attempts"] == 0

    forever = {"only": lambda _context: {
        "status": "RETRYABLE_FAILURE", "failure_kind": "SYNTHETIC"
    }}
    single = _graph([_node("only", consumes=("question",), produces=("answer",))])
    bounded = _execute(single, {}, admissions={"only": lambda _context: True},
                       implementations=forever, verifiers={"only": lambda _context: True},
                       max_attempts_per_node=9, max_total_attempts=256)
    assert bounded["disposition"] == "BLOCKED"
    assert bounded["nodes"]["only"]["attempts"] <= 8
    invalid = _execute(single, {}, admissions={"only": lambda _context: True},
                       implementations=forever, verifiers={"only": lambda _context: True},
                       max_attempts_per_node=100_000, max_total_attempts=100_000)
    assert invalid["disposition"] == "NOT_INVOKED"
    assert invalid["nodes"]["only"]["attempts"] == 0


@pytest.mark.parametrize("outcome", (
    {"status": "SUCCEEDED", "outputs": {}},
    {"status": "SUCCEEDED", "outputs": {"scope": "x", "extra": "y"}},
    {"status": "RETRYABLE_FAILURE", "failure_kind": "NETWORK"},
    {"status": "MAYBE", "outputs": {"scope": "x"}},
    None,
))
def test_ambiguous_or_malformed_outcome_never_retries_or_releases_descendants(outcome):
    graph = _chain()
    observed = []
    admissions, implementations, verifiers = _capabilities({
        "scope": {"scope": "x"}, "collect": {"evidence": "x"},
        "answer": {"answer": "x"}
    }, observed=observed)
    implementations["scope"] = lambda context: (
        observed.append(("run", "scope", context["attempt"])) or copy.deepcopy(outcome)
    )
    result = _execute(graph, {}, observed=observed, admissions=admissions,
                      implementations=implementations, verifiers=verifiers,
                      max_attempts_per_node=5)
    assert result["disposition"] == "BLOCKED"
    assert [event for event in observed if event[0] == "run"] == [("run", "scope", 1)]
    assert result["nodes"]["collect"]["status"] == "BLOCKED"


def test_non_json_status_with_raising_comparison_fails_closed():
    class RaisingStatus:
        def __eq__(self, _other):
            raise RuntimeError("private callback details")

    graph = _chain()
    observed = []
    admissions, implementations, verifiers = _capabilities({
        "scope": {"scope": "x"}, "collect": {"evidence": "x"},
        "answer": {"answer": "x"}
    }, observed=observed)
    implementations["scope"] = lambda context: (
        observed.append(("run", "scope", context["attempt"])) or
        {"status": RaisingStatus(), "outputs": {"scope": "x"}}
    )
    result = _execute(graph, {}, observed=observed, admissions=admissions,
                      implementations=implementations, verifiers=verifiers,
                      max_attempts_per_node=5)
    assert result["disposition"] == "BLOCKED"
    assert result["reason"] == "AMBIGUOUS_OUTCOME"
    assert [event for event in observed if event[0] == "run"] == [
        ("run", "scope", 1)
    ]
    assert result["nodes"]["collect"]["status"] == "BLOCKED"
    assert "private callback details" not in json.dumps(result)


def test_cancellation_and_deadline_prevent_new_dispatch():
    graph = _chain()
    outputs = {
        "scope": {"scope": "x"}, "collect": {"evidence": "x"},
        "answer": {"answer": "x"}
    }
    cancelled = _execute(graph, outputs, cancelled=lambda: True)
    assert cancelled["disposition"] in {"NOT_INVOKED", "BLOCKED"}
    assert all(item["attempts"] == 0 for item in cancelled["nodes"].values())

    observed = []
    admissions, implementations, verifiers = _capabilities(outputs, observed=observed)
    original = implementations["scope"]
    stop = {"value": False}

    def first_then_cancel(context):
        result = original(context)
        stop["value"] = True
        return result

    implementations["scope"] = first_then_cancel
    result = _execute(graph, {}, observed=observed, admissions=admissions,
                      implementations=implementations, verifiers=verifiers,
                      cancelled=lambda: stop["value"])
    assert result["disposition"] == "BLOCKED"
    assert [event[1] for event in observed if event[0] == "run"] == ["scope"]
    assert result["nodes"]["collect"]["status"] == "BLOCKED"

    timed_out = _execute(graph, outputs, clock=lambda: 10.0, deadline=5.0)
    assert timed_out["disposition"] in {"NOT_INVOKED", "BLOCKED"}
    assert all(item["attempts"] == 0 for item in timed_out["nodes"].values())


def test_callback_mutation_does_not_change_admitted_plan_or_inputs():
    graph = _chain()
    supplied = {"question": {"text": "frozen"}}
    observed = []
    admissions, implementations, verifiers = _capabilities({
        "scope": {"scope": "rules"}, "collect": {"evidence": "paper"},
        "answer": {"answer": "cited"}
    }, observed=observed)
    original = implementations["scope"]

    def mutating_admission(context):
        graph["nodes"][1]["consumes"][:] = ["changed"]
        supplied["question"]["text"] = "changed"
        context["node"]["produces"][:] = ["changed"]
        context["inputs"]["question"]["text"] = "changed"
        return True

    def first(context):
        assert context["node"]["produces"] == ["scope"]
        assert context["inputs"] == {"question": {"text": "frozen"}}
        return original(context)

    admissions["scope"] = mutating_admission
    implementations["scope"] = first
    result = _execute(graph, {}, input_values=supplied, observed=observed,
                      admissions=admissions, implementations=implementations,
                      verifiers=verifiers)
    assert result["disposition"] == "SUCCEEDED"
    assert result["nodes"]["collect"]["outputs"] == {"evidence": "paper"}
    assert [event[1] for event in observed if event[0] == "run"] == [
        "scope", "collect", "answer"
    ]


def test_receipt_chain_binds_inputs_outputs_attempts_and_predecessors():
    graph = _chain()
    outputs = {
        "scope": {"scope": "rules"}, "collect": {"evidence": ["paper"]},
        "answer": {"answer": "cited"}
    }
    result = _execute(graph, outputs)
    transitions = result["transitions"]
    assert result["disposition"] == "SUCCEEDED"
    assert transitions
    for left, right in zip(transitions, transitions[1:]):
        assert right["previous_receipt_id"] == left["receipt_id"]
    assert all(len(item["receipt_id"]) == 64 for item in transitions)
    assert all(len(item["input_hash"]) == 64 for item in transitions)
    assert all(len(item["output_hash"]) == 64 for item in transitions)
    scope_receipt = result["nodes"]["scope"]["receipt_id"]
    assert any(item["node_id"] == "collect" and scope_receipt in
               json.dumps(item["predecessor_receipts"], sort_keys=True)
               for item in transitions)
    changed_input = _execute(graph, outputs, input_values={"question": "different"})
    assert changed_input["transitions"] != transitions
    changed_output = _execute(graph, {**outputs, "collect": {"evidence": ["other"]}})
    assert changed_output["transitions"] != transitions


def test_legacy_wrapper_remains_first_cycle_compatible():
    first = {"final_status": "converged", "cycle_chain_final_hash": "initial"}
    reexecutions = []
    legacy = scheduler.wrap_governed_cycle(
        first, lambda: reexecutions.append(True) or first,
        plan=scheduler.build_plan(("first", "second", "third")),
    )
    assert legacy["cycle"] is first
    assert legacy["sgh_final_state"] == "HALT"
    assert {item["node"] for item in legacy["node_state_trace"]} == {"first"}
    assert reexecutions == []
