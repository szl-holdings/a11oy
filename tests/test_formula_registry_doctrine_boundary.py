# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import szl_formula_registry as registry


def test_f23_coverage_scope_states_the_non_theorem_boundary() -> None:
    scope = registry.PAYLOAD["coverage_scope"]
    assert scope == registry.EXPECTED_COVERAGE_SCOPE
    assert "F23 Lambda" in scope
    assert "Conjecture 1" in scope
    assert "not a theorem" in scope
    assert registry.LAMBDA_STATUS == "CONJECTURE_1_ADVISORY"
    assert registry.PAYLOAD["lambda"]["can_authorize"] is False
    assert registry.PAYLOAD["lambda"]["can_be_sole_allow_basis"] is False


def test_corrected_registry_digest_remains_self_consistent() -> None:
    document = registry.load_registry(verify=True)
    assert document["registry_digest"]["value"] == registry.compute_payload_digest(
        document["payload"]
    )
    assert len(document["registry_digest"]["value"]) == 64
