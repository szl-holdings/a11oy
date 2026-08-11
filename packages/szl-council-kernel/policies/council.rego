package szl.council

# OPA 1.x reference policy. The deterministic Python kernel remains the final
# authority and verifies the exact policy bundle digest before using a decision.

default allow := false

deny contains "COUNCIL_NOT_VERIFIED" if {
  input.council.state != "QUORUM_VERIFIED"
}

deny contains "GATE_NOT_ACT" if {
  input.gate.decision != "ACT"
}

deny contains "TARGET_OUTSIDE_ENVELOPE" if {
  not input.action.target in input.envelope.exact_targets
}

deny contains "CAPABILITY_MISSING" if {
  not input.action.required_capability in input.envelope.capabilities
}

deny contains "TOOL_NOT_ALLOWED" if {
  not input.action.tool in input.envelope.tools
}

deny contains "BUDGET_EXCEEDED" if {
  input.usage.mutations > input.envelope.budgets.max_mutations
}

deny contains "EXPIRED" if {
  input.now_unix >= input.envelope.expires_unix
}

allow if {
  count(deny) == 0
}

decision := {
  "allow": allow,
  "deny": sort([reason | reason := deny[_]]),
  "policy": "szl.council.reference/v1",
}
