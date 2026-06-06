/**
 * Proof-route resolver — implementation of the missing piece
 * `proof_route_resolver` from `docs/research/ouroboros-runtime-contract.v2.json`.
 *
 * Responsibility: given an emitted claim or proposed action, deterministically
 * select the proof route that governs the artifacts the runtime must bind to
 * the decision receipt before the loop is allowed to halt successfully.
 *
 * The three canonical routes mirror the payload contract:
 *   - PRF_SYSTEM_CLAIMS   (system-design / informational claims)
 *   - PRF_SECURITY_ACTIONS (security / threat-response actions)
 *   - PRF_DATA_SYNC        (data merge / synchronization actions)
 *
 * Pure module: no I/O, no clock dependency. The resolver is fully replayable.
 */

export type ProofRouteId =
  | 'PRF_SYSTEM_CLAIMS'
  | 'PRF_SECURITY_ACTIONS'
  | 'PRF_DATA_SYNC';

export type ProofArtifactKind =
  | 'source_binding'
  | 'trace_locator'
  | 'receipt'
  | 'validator_result'
  | 'risk_tier'
  | 'escalation_check'
  | 'source_priority_record'
  | 'delta_log'
  | 'consistency_score';

export interface ProofRoute {
  readonly routeId: ProofRouteId;
  readonly appliesTo: string;
  readonly requiredArtifacts: readonly ProofArtifactKind[];
}

function freezeRoute(r: ProofRoute): ProofRoute {
  return Object.freeze({ ...r, requiredArtifacts: Object.freeze([...r.requiredArtifacts]) });
}

export const PROOF_ROUTES: Readonly<Record<ProofRouteId, ProofRoute>> = Object.freeze({
  PRF_SYSTEM_CLAIMS: freezeRoute({
    routeId: 'PRF_SYSTEM_CLAIMS',
    appliesTo: 'system_design_claims',
    requiredArtifacts: ['source_binding', 'trace_locator', 'receipt'],
  }),
  PRF_SECURITY_ACTIONS: freezeRoute({
    routeId: 'PRF_SECURITY_ACTIONS',
    appliesTo: 'security_or_threat_actions',
    requiredArtifacts: ['validator_result', 'risk_tier', 'escalation_check', 'receipt'],
  }),
  PRF_DATA_SYNC: freezeRoute({
    routeId: 'PRF_DATA_SYNC',
    appliesTo: 'data_merge_or_sync_actions',
    requiredArtifacts: ['source_priority_record', 'delta_log', 'consistency_score', 'receipt'],
  }),
});

/**
 * The smallest contract a caller must produce so the resolver can route.
 * `kind` is the abstract category; `domainPack` and `actionType` add
 * disambiguation when the same kind appears across multiple packs.
 */
export interface ClaimOrAction {
  kind: 'claim' | 'action';
  category:
    | 'system_design'
    | 'informational'
    | 'security'
    | 'threat_response'
    | 'data_merge'
    | 'data_sync';
  domainPack?: string;
  actionType?: string;
}

/**
 * Resolve a claim/action to its governing proof route. Returns `null` when
 * the input does not match any known category — callers must treat that as
 * a hard failure (`VAL_PROOF_REQUIRED`) for high-consequence outputs.
 */
export function resolveProofRoute(input: ClaimOrAction): ProofRoute | null {
  switch (input.category) {
    case 'system_design':
    case 'informational':
      return PROOF_ROUTES.PRF_SYSTEM_CLAIMS;
    case 'security':
    case 'threat_response':
      return PROOF_ROUTES.PRF_SECURITY_ACTIONS;
    case 'data_merge':
    case 'data_sync':
      return PROOF_ROUTES.PRF_DATA_SYNC;
    default:
      return null;
  }
}

/**
 * Validate that all required artifacts for the resolved route are present
 * on the receipt before halt is allowed. Returns the missing-artifact list;
 * an empty array means the receipt satisfies the proof-route contract.
 */
export function validateProofArtifacts(
  route: ProofRoute,
  presentArtifacts: ReadonlySet<ProofArtifactKind>,
): ProofArtifactKind[] {
  const missing: ProofArtifactKind[] = [];
  for (const required of route.requiredArtifacts) {
    if (!presentArtifacts.has(required)) missing.push(required);
  }
  return missing;
}
