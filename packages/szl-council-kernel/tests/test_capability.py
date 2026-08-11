from dataclasses import replace

import pytest

from szl_council_kernel.canary import FIXED_EXPIRY, FIXED_TIME
from szl_council_kernel.capability import BudgetAccount, authorize_action, normalize_target, pattern_is_subset, target_matches, validate_attenuation
from szl_council_kernel.enums import ActionKind
from szl_council_kernel.errors import AuthorizationError, ValidationError
from szl_council_kernel.models import ActionRequest, BudgetLimits, BudgetUsage, CapabilityGrant


def action(envelope, grant, target="workspace/test.txt"):
    return ActionRequest(action_id="action-test",case_id=envelope.case_id,grant_id=grant.grant_id,kind=ActionKind.FILE_WRITE,tool="sandbox_fs",target=target,content="ok",expected_before_digest=None,idempotency_key=envelope.idempotency_key,postconditions=envelope.postconditions)


def test_normalize_target_rejects_absolute_and_parent():
    for value in ("/tmp/x", "../x", "a/../x", "a\\b"):
        with pytest.raises(ValidationError): normalize_target(value)


def test_recursive_target_pattern():
    assert target_matches("workspace/**", "workspace/a/b.txt")
    assert not target_matches("workspace/**", "other/a.txt")


def test_pattern_subset_conservative():
    assert pattern_is_subset("workspace/a/**", "workspace/**")
    assert pattern_is_subset("workspace/a.txt", "workspace/**")
    assert not pattern_is_subset("workspace/*.txt", "workspace/**")


def test_valid_attenuation(grant):
    child=CapabilityGrant(grant_id="child",parent_grant_id=grant.grant_id,principal=grant.principal,capabilities=("file:write",),target_patterns=("workspace/test.txt",),tools=("sandbox_fs",),budgets=BudgetLimits(max_tool_calls=1,max_mutations=1,max_branches=1,max_recursion=1),issued_at=FIXED_TIME,expires_at=FIXED_EXPIRY)
    validate_attenuation(grant,child)


def test_capability_expansion_rejected(grant):
    child=CapabilityGrant(grant_id="child",parent_grant_id=grant.grant_id,principal=grant.principal,capabilities=("file:delete",),target_patterns=("workspace/test.txt",),tools=("sandbox_fs",),budgets=grant.budgets,issued_at=FIXED_TIME,expires_at=FIXED_EXPIRY)
    with pytest.raises(AuthorizationError): validate_attenuation(grant,child)


def test_budget_expansion_rejected(grant):
    child=CapabilityGrant(grant_id="child",parent_grant_id=grant.grant_id,principal=grant.principal,capabilities=("file:write",),target_patterns=("workspace/test.txt",),tools=("sandbox_fs",),budgets=BudgetLimits(max_mutations=2),issued_at=FIXED_TIME,expires_at=FIXED_EXPIRY)
    with pytest.raises(AuthorizationError): validate_attenuation(grant,child)


def test_action_authorized(envelope,grant):
    authorize_action(grant,envelope,action(envelope,grant),BudgetUsage(tool_calls=1,mutations=1),now=FIXED_TIME)


def test_exact_target_required(envelope,grant):
    with pytest.raises(AuthorizationError): authorize_action(grant,envelope,action(envelope,grant,"workspace/other.txt"),BudgetUsage(tool_calls=1,mutations=1),now=FIXED_TIME)


def test_expired_grant_rejected(envelope,grant):
    with pytest.raises(AuthorizationError): authorize_action(grant,envelope,action(envelope,grant),BudgetUsage(tool_calls=1,mutations=1),now=FIXED_EXPIRY)


def test_budget_account_fails_closed():
    account=BudgetAccount(BudgetLimits(max_tool_calls=1,max_mutations=1))
    account.consume(tool_calls=1,mutations=1)
    with pytest.raises(AuthorizationError): account.consume(tool_calls=1)
