#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""A11oy Proof-to-Discovery engine, v1.

An evidence-driven discovery loop with three-valued verdicts (PROVEN, REFUTED,
UNRESOLVED), fail-closed record verification, a cryptographic action gate, and
an EVSI-based recommender for the next authorized experiment.

Core invariant, enforced in ``policy``: no consequential action may be
authorized solely by a model-generated claim or an unverified evidence record.

This package is deliberately stdlib-only and offline. The Ed25519
implementation is pure Python and pinned to RFC 8032 test vectors. All numbers
produced by the recommender are declared estimates from the experiment
catalog; the engine never manufactures evidence or uncertainty.
"""

from .cases import CASE_COUNT, build_acceptance_manifest
from .experiments import Experiment, Recommendation, ScoredExperiment, recommend
from .graph import (
    ALL_VERDICTS,
    VERDICT_PROVEN,
    VERDICT_REFUTED,
    VERDICT_UNRESOLVED,
    Evaluation,
    Obligation,
    ObligationGraph,
    ObligationVerdict,
    evaluate,
)
from .policy import ActionDecision, AuthorizationGrant, TrustPolicy, evaluate_action
from .records import EvidenceRecord, RecordCheck, WitnessTier, check_record

__all__ = [
    "ALL_VERDICTS",
    "AcceptanceCase",
    "ActionDecision",
    "AuthorizationGrant",
    "CASE_COUNT",
    "Evaluation",
    "EvidenceRecord",
    "Experiment",
    "Obligation",
    "ObligationGraph",
    "ObligationVerdict",
    "RecordCheck",
    "Recommendation",
    "ScoredExperiment",
    "TrustPolicy",
    "VERDICT_PROVEN",
    "VERDICT_REFUTED",
    "VERDICT_UNRESOLVED",
    "WitnessTier",
    "build_acceptance_manifest",
    "check_record",
    "evaluate",
    "evaluate_action",
    "recommend",
]
