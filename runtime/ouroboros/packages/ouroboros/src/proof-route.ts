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
  // v2 routes (kept for backwards compatibility — see ouroboros-runtime-contract.v2.json)
  | 'PRF_SYSTEM_CLAIMS'
  | 'PRF_SECURITY_ACTIONS'
  | 'PRF_DATA_SYNC'
  // v3 routes (added per ouroboros-runtime-contract.v3.json).
  // PRF_SECURITY_ACTION and PRF_DATA_CONVERGENCE are v3 renames of the
  // v2 IDs PRF_SECURITY_ACTIONS and PRF_DATA_SYNC respectively. Both IDs
  // are registered with identical artifact contracts so v2 callers keep
  // working while v3 receipts can use the canonical v3 names.
  | 'PRF_CLAIM_BOUND_RESEARCH'
  | 'PRF_OPERATIONAL_ACTION'
  | 'PRF_SECURITY_ACTION'
  | 'PRF_DATA_CONVERGENCE';

export type ProofArtifactKind =
  | 'source_binding'
  | 'trace_locator'
  | 'receipt'
  | 'validator_result'
  | 'risk_tier'
  | 'escalation_check'
  | 'source_priority_record'
  | 'delta_log'
  | 'consistency_score'
  // v3 artifact kinds — required by ouroboros-runtime-contract.v3.json.
  // PRF_CLAIM_BOUND_RESEARCH binds a research claim to a `locator` (where
  // the source lives) AND a separate `trace_reference` (the loop trace
  // pointer). Kept distinct from `trace_locator` so the v2 routes are not
  // disturbed. PRF_SECURITY_ACTION (v3) additionally requires the
  // `approval_if_required` artifact in place of `risk_tier`.
  | 'locator'
  | 'trace_reference'
  | 'approval_if_required';

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
  PRF_CLAIM_BOUND_RESEARCH: freezeRoute({
    routeId: 'PRF_CLAIM_BOUND_RESEARCH',
    appliesTo: 'research_claims_or_thesis_assertions',
    // Matches v3 contract exactly: source_binding + locator + trace_reference + receipt.
    requiredArtifacts: ['source_binding', 'locator', 'trace_reference', 'receipt'],
  }),
  PRF_OPERATIONAL_ACTION: freezeRoute({
    routeId: 'PRF_OPERATIONAL_ACTION',
    appliesTo: 'operational_or_client_actions',
    requiredArtifacts: ['validator_result', 'risk_tier', 'receipt'],
  }),
  // v3-canonical aliases. Identical artifact contracts to their v2 siblings;
  // both IDs are accepted so v2 receipts and v3 receipts both validate.
  PRF_SECURITY_ACTION: freezeRoute({
    routeId: 'PRF_SECURITY_ACTION',
    appliesTo: 'security_or_threat_actions',
    // Matches v3 contract exactly. Note: drops `risk_tier` from the v2
    // PRF_SECURITY_ACTIONS list and adds `approval_if_required`.
    requiredArtifacts: ['validator_result', 'escalation_check', 'receipt', 'approval_if_required'],
  }),
  PRF_DATA_CONVERGENCE: freezeRoute({
    routeId: 'PRF_DATA_CONVERGENCE',
    appliesTo: 'data_merge_or_sync_actions',
    requiredArtifacts: ['source_priority_record', 'delta_log', 'consistency_score', 'receipt'],
  }),
});

/**
 * Maps each v3-canonical route ID to its v2 alias (or itself when there
 * is no rename). Useful for receipt normalization and replay tooling that
 * needs to compare v2 and v3 receipts.
 */
export const ROUTE_ID_V2_ALIASES: Readonly<Record<ProofRouteId, ProofRouteId>> = Object.freeze({
  PRF_SYSTEM_CLAIMS: 'PRF_SYSTEM_CLAIMS',
  PRF_SECURITY_ACTIONS: 'PRF_SECURITY_ACTIONS',
  PRF_DATA_SYNC: 'PRF_DATA_SYNC',
  PRF_CLAIM_BOUND_RESEARCH: 'PRF_CLAIM_BOUND_RESEARCH',
  PRF_OPERATIONAL_ACTION: 'PRF_OPERATIONAL_ACTION',
  PRF_SECURITY_ACTION: 'PRF_SECURITY_ACTIONS',
  PRF_DATA_CONVERGENCE: 'PRF_DATA_SYNC',
});

/**
 * v4 short-name aliases per ouroboros-runtime-contract.v4.json. The v4
 * payload labels routes with shorter ids (PRF_RESEARCH, PRF_SECURITY,
 * PRF_DATA_SYNC, PRF_OPERATIONAL); each maps to a canonical v3 route
 * with the same artifact contract semantics. Receipt normalization
 * tooling can resolve any v4 label back to its canonical PROOF_ROUTES
 * entry via this map.
 */
export type ProofRouteIdV4 =
  | 'PRF_RESEARCH'
  | 'PRF_SECURITY'
  | 'PRF_DATA_SYNC'
  | 'PRF_OPERATIONAL';

export const ROUTE_ID_V4_ALIASES: Readonly<Record<ProofRouteIdV4, ProofRouteId>> =
  Object.freeze({
    PRF_RESEARCH: 'PRF_CLAIM_BOUND_RESEARCH',
    PRF_SECURITY: 'PRF_SECURITY_ACTION',
    PRF_DATA_SYNC: 'PRF_DATA_CONVERGENCE',
    PRF_OPERATIONAL: 'PRF_OPERATIONAL_ACTION',
  });

/**
 * Resolve a v4 short label (or v3 canonical id) to its canonical
 * `ProofRouteId`. Returns `undefined` if the input is neither a v4
 * alias nor a known proof route id.
 */
export function resolveV4ProofRouteId(label: string): ProofRouteId | undefined {
  if (Object.hasOwn(ROUTE_ID_V4_ALIASES, label)) {
    return ROUTE_ID_V4_ALIASES[label as ProofRouteIdV4];
  }
  if (Object.hasOwn(PROOF_ROUTES, label)) {
    return label as ProofRouteId;
  }
  return undefined;
}

/**
 * The smallest contract a caller must produce so the resolver can route.
 * `kind` is the abstract category; `domainPack` and `actionType` add
 * disambiguation when the same kind appears across multiple packs.
 */
export type ClaimOrActionCategory =
  // v2 categories
  | 'system_design'
  | 'informational'
  | 'security'
  | 'threat_response'
  | 'data_merge'
  | 'data_sync'
  // v3 categories — needed so the resolver can return the v3 routes.
  | 'research_claim'
  | 'thesis_assertion'
  | 'operational_action'
  | 'client_action';

export interface ClaimOrAction {
  kind: 'claim' | 'action';
  category: ClaimOrActionCategory;
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
    case 'research_claim':
    case 'thesis_assertion':
      return PROOF_ROUTES.PRF_CLAIM_BOUND_RESEARCH;
    case 'operational_action':
    case 'client_action':
      return PROOF_ROUTES.PRF_OPERATIONAL_ACTION;
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
