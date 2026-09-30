// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
// Typed reference policy. Applications must schema-validate requests/entities,
// authenticate attributes, and bind verified evidence before granting authority.

forbid(
    principal is A11oy::WorkloadIdentity,
    action,
    resource is A11oy::ProtectedResource
) when {
    principal.disabled ||
    principal.tenantId == "" ||
    resource.tenantId == "" ||
    principal.tenantId != resource.tenantId ||
    principal.assurance < 0 ||
    resource.requiredAssurance < 0 ||
    resource.classification < 0 ||
    context.riskScore < 0 ||
    resource.maxRisk < 0 ||
    context.riskScore > resource.maxRisk ||
    context.purpose == "" ||
    context.intendedEffect == "" ||
    !resource.allowedPurposes.contains(context.purpose) ||
    !resource.allowedEffects.contains(context.intendedEffect)
};

forbid(
    principal is A11oy::WorkloadIdentity,
    action,
    resource is A11oy::ProtectedResource
) when {
    (resource.requiresApproval ||
        [
            A11oy::Action::"InvokeTool",
            A11oy::Action::"WriteResource",
            A11oy::Action::"DeployArtifact",
            A11oy::Action::"ApproveDecision",
            A11oy::Action::"SignReceipt",
            A11oy::Action::"AdministerPolicy"
        ].contains(action)
    ) &&
    (!["command-surface", "trusted-ci", "trusted"].contains(context.networkZone) ||
        !context.humanApproval || !context.mfa || context.evidenceDigest == "")
};

permit(
    principal is A11oy::WorkloadIdentity,
    action in [
        A11oy::Action::"ReadResource",
        A11oy::Action::"ExportEvidence",
        A11oy::Action::"InvokeTool",
        A11oy::Action::"WriteResource",
        A11oy::Action::"DeployArtifact",
        A11oy::Action::"ApproveDecision",
        A11oy::Action::"SignReceipt",
        A11oy::Action::"AdministerPolicy"
    ],
    resource is A11oy::ProtectedResource
) when {
    !principal.disabled &&
    principal.kind != "" &&
    resource.kind != "" &&
    principal.tenantId != "" &&
    principal.tenantId == resource.tenantId &&
    principal.assurance >= resource.requiredAssurance &&
    context.riskScore <= resource.maxRisk &&
    context.networkZone != "" &&
    resource.allowedPurposes.contains(context.purpose) &&
    resource.allowedEffects.contains(context.intendedEffect)
};
