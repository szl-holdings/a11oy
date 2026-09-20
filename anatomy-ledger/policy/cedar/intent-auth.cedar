// Cedar denies requests by default when no permit policy matches.

forbid(
    principal is A11oy::WorkloadIdentity,
    action,
    resource is A11oy::ProtectedResource
) when {
    principal.disabled
};

forbid(
    principal is A11oy::WorkloadIdentity,
    action,
    resource is A11oy::ProtectedResource
) when {
    principal.tenantId != resource.tenantId
};

forbid(
    principal is A11oy::WorkloadIdentity,
    action,
    resource is A11oy::ProtectedResource
) when {
    context.riskScore > resource.maxRisk
};

forbid(
    principal is A11oy::WorkloadIdentity,
    action,
    resource is A11oy::ProtectedResource
) when {
    !resource.allowedPurposes.contains(context.purpose)
};

forbid(
    principal is A11oy::WorkloadIdentity,
    action,
    resource is A11oy::ProtectedResource
) when {
    !resource.allowedEffects.contains(context.intendedEffect)
};

forbid(
    principal is A11oy::WorkloadIdentity,
    action in [
        A11oy::Action::"WriteResource",
        A11oy::Action::"DeployArtifact",
        A11oy::Action::"ApproveDecision",
        A11oy::Action::"SignReceipt",
        A11oy::Action::"AdministerPolicy"
    ],
    resource is A11oy::ProtectedResource
) when {
    context.networkZone == "untrusted"
};

permit(
    principal is A11oy::WorkloadIdentity,
    action in [
        A11oy::Action::"ReadResource",
        A11oy::Action::"InvokeTool",
        A11oy::Action::"ExportEvidence"
    ],
    resource is A11oy::ProtectedResource
) when {
    !principal.disabled &&
    principal.tenantId == resource.tenantId &&
    principal.assurance >= resource.requiredAssurance &&
    context.riskScore <= resource.maxRisk &&
    resource.allowedPurposes.contains(context.purpose) &&
    resource.allowedEffects.contains(context.intendedEffect)
};

permit(
    principal is A11oy::WorkloadIdentity,
    action in [
        A11oy::Action::"WriteResource",
        A11oy::Action::"DeployArtifact",
        A11oy::Action::"ApproveDecision",
        A11oy::Action::"SignReceipt",
        A11oy::Action::"AdministerPolicy"
    ],
    resource is A11oy::ProtectedResource
) when {
    !principal.disabled &&
    principal.tenantId == resource.tenantId &&
    principal.assurance >= resource.requiredAssurance &&
    context.riskScore <= resource.maxRisk &&
    context.humanApproval &&
    context.mfa &&
    context.evidenceDigest != "" &&
    resource.allowedPurposes.contains(context.purpose) &&
    resource.allowedEffects.contains(context.intendedEffect)
};
