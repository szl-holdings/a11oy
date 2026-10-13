#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Training answers must disclose the deployed audit's read-only boundary."""

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROMPT = "What are the three belief tiers for graph write-back?"


def _generator_answer():
    spec = importlib.util.spec_from_file_location(
        "anatomy_seed_builder", ROOT / "training" / "build_seed.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    examples = builder.build()
    return _matching_answer(examples)


def _matching_answer(examples):
    matches = [
        row
        for row in examples
        if any(
            message.get("role") == "user" and message.get("content") == PROMPT
            for message in row["messages"]
        )
    ]
    assert len(matches) == 1
    answers = [
        message["content"]
        for message in matches[0]["messages"]
        if message.get("role") == "assistant"
    ]
    assert len(answers) == 1
    return answers[0]


def test_generator_labels_audit_application_as_roadmap():
    answer = _generator_answer()
    assert "read-only preview of proposed demotions" in answer
    assert "does not change belief tiers or repair the receipt chain" in answer
    assert "separately authorized, receipted write path is ROADMAP" in answer
    assert "self-audit can DEMOTE" not in answer


@pytest.mark.parametrize("name", ["szl_seed.jsonl", "szl_seed_full.jsonl"])
def test_committed_training_answer_matches_current_generator(name):
    examples = [
        json.loads(line)
        for line in (ROOT / "training" / name).read_text(encoding="utf-8").splitlines()
    ]
    assert _matching_answer(examples) == _generator_answer()
