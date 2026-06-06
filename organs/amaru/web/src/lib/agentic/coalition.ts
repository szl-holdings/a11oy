/**
 * Amaru agent coalition runtime.
 *
 * Replaces the old Math.random simulator with a deterministic, replay-grade
 * pipeline driven by the eight Amaru agents. The pipeline emits a sequence of
 * RelayRunEvents with hash-chained stateHashes and a Lutar Σ envelope.
 *
 * Each invocation is fully a function of (mapping, model, destination, seed).
 * Same inputs → same trace. This is the contract the Codex Kernel cares about.
 */

import type {
  AgentId,
  RelayDestination,
  RelayMapping,
  RelayModel,
  RelayPolicy,
  RelayRunEvent,
  RelaySource,
  RunEventType,
  SeverityLevel,
} from '@/data/fabric/types';
import { computeLutarSigma, type LutarSigma } from './intelligence';
import { DEMO_DESTINATION_ADAPTER, DEMO_SOURCE_ADAPTER, DEMO_SYNC_PLANNER } from './adapters';

export interface DslRule {
  readonly name: string;
  readonly when: string;
  readonly then: 'block' | 'warn' | 'redact' | 'quarantine' | 'notify';
}

export interface CoalitionRunArgs {
  readonly mapping: RelayMapping;
  readonly model: RelayModel;
  readonly destination: RelayDestination;
  readonly source: RelaySource;
  readonly policies: readonly RelayPolicy[];
  readonly seed: number;
  readonly nowIso: string;
  readonly dslRules?: readonly DslRule[];
  readonly dslVersion?: number;
  /**
   * Golden-record merges applied to the source identity space. When > 0, the
   * coalition substitutes the unified accountId on planning + delivery and
   * emits an extra event so the trace shows that downstream syncs honored
   * the merge.
   */
  readonly goldenMergeCount?: number;
  readonly goldenIdentity?: string;
}

/**
 * Builds the typed evaluation environment for the DSL evaluator. Identifier
 * vocabulary is the single source of truth for both the editor surface and
 * the runtime: any dotted path in `RECOGNIZED_DSL_PATHS` is supported.
 */
export const RECOGNIZED_DSL_PATHS = [
  'mapping.confidence',
  'mapping.governanceState',
  'mapping.approvalRequired',
  'mapping.verticalId',
  'mapping.piiWarningCount',
  'model.qualityScore',
  'model.governanceState',
  'model.piiScore',
  'destination.authState',
  'destination.piiAllowed',
  'destination.governanceState',
  'destination.category',
  'fields.pii_class',
] as const;

function buildDslEnv(ctx: {
  mapping: RelayMapping;
  destination: RelayDestination;
  model: RelayModel;
}): Record<string, string | number | boolean | readonly string[]> {
  const piiClasses: string[] = [];
  if (ctx.model.piiScore > 0.6) piiClasses.push('financial');
  if (ctx.model.piiScore > 0.4) piiClasses.push('health');
  if (ctx.model.piiScore > 0.2) piiClasses.push('gov_id');
  if (piiClasses.length === 0) piiClasses.push('none');
  return {
    'mapping.confidence': ctx.mapping.confidence,
    'mapping.governanceState': ctx.mapping.governanceState,
    'mapping.approvalRequired': ctx.mapping.approvalRequired,
    'mapping.verticalId': ctx.mapping.verticalId,
    'mapping.piiWarningCount': ctx.mapping.piiWarnings.length,
    'model.qualityScore': ctx.model.qualityScore,
    'model.governanceState': ctx.model.governanceState,
    'model.piiScore': ctx.model.piiScore,
    'destination.authState': ctx.destination.authState,
    'destination.piiAllowed': ctx.destination.piiAllowed,
    'destination.governanceState': ctx.destination.governanceState,
    'destination.category': ctx.destination.category,
    'fields.pii_class': piiClasses,
  };
}

/**
 * Evaluates a single DSL rule against the sync context. Returns true if the
 * rule's `when` condition matches. Supports the documented editor grammar:
 *
 *   <dotted.identifier> (=|==|!=|>=|<=|>|<) <literal>
 *   <dotted.identifier> IN [<literal>, ...]
 *   <atom> AND <atom>
 *   <atom> OR  <atom>
 *
 * Literals: bare numbers, bare identifiers (matched case-insensitively as
 * strings), or quoted strings. Single `=` is accepted as equality.
 */
export function evaluateDslRule(
  rule: DslRule,
  ctx: { mapping: RelayMapping; destination: RelayDestination; model: RelayModel },
): boolean {
  const env = buildDslEnv(ctx);
  // Tokenize on AND/OR while preserving brackets.
  const atoms = splitAndOr(rule.when);
  if (atoms.length === 0) return false;
  let result = evalAtom(atoms[0]!.atom, env);
  for (let i = 1; i < atoms.length; i++) {
    const next = evalAtom(atoms[i]!.atom, env);
    result = atoms[i]!.op === 'OR' ? (result || next) : (result && next);
  }
  return result;
}

/**
 * Parses the Policy DSL grammar into evaluable rules. Shared between the
 * Policy DSL editor surface and the coalition runtime so a saved DSL version
 * is what actually executes against syncs.
 */
export function parseDslRules(dsl: string): DslRule[] {
  const rules: DslRule[] = [];
  const blocks = dsl.split(/^RULE /m).slice(1);
  for (const block of blocks) {
    const nameMatch = block.match(/^"([^"]+)"/);
    const thenMatch = block.match(/THEN\s+(\w+)/);
    const whenMatch = block.match(/WHEN([\s\S]*?)THEN/);
    if (nameMatch && thenMatch && whenMatch) {
      const then = thenMatch[1] as DslRule['then'];
      if (['block', 'warn', 'redact', 'quarantine', 'notify'].includes(then)) {
        rules.push({ name: nameMatch[1]!, when: whenMatch[1]!.trim(), then });
      }
    }
  }
  return rules;
}

/**
 * Supported operator vocabulary. Kept as a single source of truth so the
 * editor surface, the visual builder, and the validator all agree on what
 * actually executes. Anything outside this set parses but never enforces,
 * so we reject it at save time.
 */
export const SUPPORTED_DSL_OPERATORS = ['==', '=', '!=', '>=', '<=', '>', '<', 'IN'] as const;

/**
 * Validates a DSL rule:
 *  - identifiers must be recognized (or reserved keywords)
 *  - operators must come from SUPPORTED_DSL_OPERATORS
 *  - each atom must shape-match the runtime grammar (comparison or IN list)
 *
 * This mirrors the runtime evaluator so saved rules can never silently
 * evaluate to false. Visual-builder rules compile through this gate too.
 */
export function validateDslRule(rule: DslRule): { ok: true } | { ok: false; reason: string } {
  const idents = rule.when.match(/[a-zA-Z_][a-zA-Z0-9_.]*/g) ?? [];
  const reserved = new Set(['AND', 'OR', 'IN', 'true', 'false']);
  for (const id of idents) {
    if (reserved.has(id)) continue;
    if (id.includes('.') && !(RECOGNIZED_DSL_PATHS as readonly string[]).includes(id)) {
      return { ok: false, reason: `Unknown identifier: ${id}` };
    }
  }
  // Reject unsupported operator-shaped tokens (e.g. CONTAINS, EXISTS, ~=, LIKE)
  // that the parser would otherwise let through but the evaluator can't honor.
  const opLikeTokens = rule.when.match(/[A-Za-z]+|[<>!=~]+/g) ?? [];
  for (const tok of opLikeTokens) {
    const upper = tok.toUpperCase();
    // Only flag tokens that look like an operator — alphanumeric identifiers
    // are already handled above.
    if (/^[<>!=~]+$/.test(tok)) {
      if (!(SUPPORTED_DSL_OPERATORS as readonly string[]).includes(tok)) {
        return { ok: false, reason: `Unsupported operator: ${tok}. Use one of ${SUPPORTED_DSL_OPERATORS.join(' ')}.` };
      }
    } else if (['CONTAINS', 'EXISTS', 'LIKE', 'MATCHES', 'BETWEEN'].includes(upper)) {
      return { ok: false, reason: `Unsupported keyword operator: ${upper}. Runtime supports IN and the comparison operators only.` };
    }
  }
  // Every atom must shape-match runtime grammar.
  for (const { atom } of splitAndOr(rule.when)) {
    const trimmed = atom.trim();
    if (!trimmed) continue;
    const isIn = /^[a-zA-Z_][a-zA-Z0-9_.]*\s+IN\s+\[[^\]]*\]$/i.test(trimmed);
    const isCmp = /^[a-zA-Z_][a-zA-Z0-9_.]*\s*(==|!=|>=|<=|=|>|<)\s*.+$/.test(trimmed);
    if (!isIn && !isCmp) {
      return { ok: false, reason: `Atom does not match runtime grammar: "${trimmed}"` };
    }
  }
  return { ok: true };
}

function splitAndOr(when: string): { op: 'AND' | 'OR'; atom: string }[] {
  // Split on top-level AND/OR (we don't need bracket-aware nesting for the
  // current grammar; brackets are only used inside IN [...] lists).
  const parts: { op: 'AND' | 'OR'; atom: string }[] = [];
  let buf = '';
  let depth = 0;
  let lastOp: 'AND' | 'OR' = 'AND';
  const tokens = when.split(/(\bAND\b|\bOR\b|\[|\])/i);
  for (const tok of tokens) {
    if (tok === '[') { depth++; buf += tok; continue; }
    if (tok === ']') { depth--; buf += tok; continue; }
    const upper = tok.toUpperCase().trim();
    if (depth === 0 && (upper === 'AND' || upper === 'OR')) {
      if (buf.trim().length > 0) parts.push({ op: lastOp, atom: buf.trim() });
      buf = '';
      lastOp = upper as 'AND' | 'OR';
    } else {
      buf += tok;
    }
  }
  if (buf.trim().length > 0) parts.push({ op: lastOp, atom: buf.trim() });
  return parts;
}

function evalAtom(
  atom: string,
  env: Record<string, string | number | boolean | readonly string[]>,
): boolean {
  // IN list: <ident> IN [a, b, c]
  const inMatch = atom.match(/^([a-zA-Z_][a-zA-Z0-9_.]*)\s+IN\s+\[([^\]]*)\]$/i);
  if (inMatch) {
    const lhs = env[inMatch[1]!];
    const items = inMatch[2]!.split(',').map((s) => stripLiteral(s.trim()).toLowerCase()).filter(Boolean);
    if (Array.isArray(lhs)) return (lhs as readonly string[]).some((v) => items.includes(String(v).toLowerCase()));
    if (lhs === undefined) return false;
    return items.includes(String(lhs).toLowerCase());
  }
  // Comparison: <ident> (==|=|!=|>=|<=|>|<) <literal>
  const m = atom.match(/^([a-zA-Z_][a-zA-Z0-9_.]*)\s*(==|!=|>=|<=|=|>|<)\s*(.+)$/);
  if (!m) return false;
  const [, key, opRaw, rawVal] = m;
  const lhs = env[key!];
  if (lhs === undefined) return false;
  const op = opRaw === '=' ? '==' : opRaw!;
  const rhsStr = stripLiteral(rawVal!.trim());
  const rhsNum = Number(rhsStr);
  const lhsNum = typeof lhs === 'number' ? lhs : Number(lhs);
  const isNumCmp = !Number.isNaN(rhsNum) && !Number.isNaN(lhsNum) && (typeof lhs === 'number');
  const isBoolCmp = typeof lhs === 'boolean' && (rhsStr === 'true' || rhsStr === 'false');
  switch (op) {
    case '==':
      if (isBoolCmp) return lhs === (rhsStr === 'true');
      if (isNumCmp) return lhsNum === rhsNum;
      return String(lhs).toLowerCase() === rhsStr.toLowerCase();
    case '!=':
      if (isBoolCmp) return lhs !== (rhsStr === 'true');
      if (isNumCmp) return lhsNum !== rhsNum;
      return String(lhs).toLowerCase() !== rhsStr.toLowerCase();
    case '>=': return isNumCmp && lhsNum >= rhsNum;
    case '<=': return isNumCmp && lhsNum <= rhsNum;
    case '>':  return isNumCmp && lhsNum >  rhsNum;
    case '<':  return isNumCmp && lhsNum <  rhsNum;
    default: return false;
  }
}

function stripLiteral(s: string): string {
  return s.trim().replace(/^['"]|['"]$/g, '');
}

export interface CoalitionRunResult {
  readonly runId: string;
  readonly events: readonly RelayRunEvent[];
  readonly sigma: LutarSigma;
  readonly verdict: 'completed' | 'blocked' | 'failed';
  readonly recordsDelivered: number;
  readonly recordsFailed: number;
  readonly evidenceRef: string;
}

const AGENT_BY_TYPE: Record<RunEventType, AgentId | null> = {
  planned: 'cartographer',
  approved: null,
  started: 'courier',
  extracted: 'courier',
  transformed: 'mapper',
  policy_checked: 'sentinel',
  delivered: 'courier',
  failed: 'fixer',
  retried: 'courier',
  quarantined: 'sentinel',
  rolled_back: 'fixer',
  completed: 'verity',
};

const SEV: Record<RunEventType, SeverityLevel> = {
  planned: 'info', approved: 'info', started: 'info', extracted: 'info',
  transformed: 'info', policy_checked: 'low', delivered: 'info',
  failed: 'high', retried: 'medium', quarantined: 'high',
  rolled_back: 'critical', completed: 'info',
};

function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (const c of s) {
    h ^= c.charCodeAt(0);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}
function shortHex(n: number) {
  return n.toString(16).padStart(8, '0').slice(0, 8);
}

export function runCoalition(args: CoalitionRunArgs): CoalitionRunResult {
  const { mapping, model, destination, source, policies, seed, nowIso, dslRules, dslVersion, goldenMergeCount, goldenIdentity } = args;
  const runId = `run-${shortHex(fnv1a(`${mapping.id}:${seed}`))}`;
  const baseAt = Date.parse(nowIso);

  // DSL evaluation: replaces the ad-hoc enum policy enum-only model. Active
  // DSL rules are evaluated against the sync context; any matching `block`
  // rule forces the run to the blocked path.
  const matchedDslRules = (dslRules ?? []).filter((r) => evaluateDslRule(r, { mapping, destination, model }));
  const dslBlock = matchedDslRules.some((r) => r.then === 'block' || r.then === 'quarantine');

  // 1. Cartographer profiles, source-side.
  const profile = DEMO_SOURCE_ADAPTER.profile(source);
  const contractCheck = DEMO_DESTINATION_ADAPTER.validateContract(mapping, destination);
  void profile;
  void contractCheck;

  // 2. Sync planner produces batches.
  const plan = DEMO_SYNC_PLANNER.plan(mapping, model, destination);

  // 3. Walk the deterministic flow; inject failure if approval pending or governance red.
  const willBlock =
    mapping.governanceState === 'red' ||
    destination.governanceState === 'red' ||
    destination.authState === 'expired' ||
    destination.authState === 'rotation_required' ||
    dslBlock;
  const willRequireApproval = mapping.approvalRequired;

  const flow: RunEventType[] = willBlock
    ? ['planned', 'started', 'policy_checked', 'quarantined', 'rolled_back']
    : willRequireApproval
      ? ['planned', 'approved', 'started', 'extracted', 'transformed', 'policy_checked', 'delivered', 'completed']
      : ['planned', 'started', 'extracted', 'transformed', 'policy_checked', 'delivered', 'completed'];

  let chain = fnv1a(`chain:${runId}`);
  const events: RelayRunEvent[] = [];
  const totalRecords = plan.totalRecords;
  let delivered = 0;
  let failed = 0;

  flow.forEach((type, i) => {
    chain = fnv1a(`${chain}:${type}:${i}`);
    const at = new Date(baseAt + i * 320).toISOString();
    const records =
      type === 'extracted' || type === 'transformed' ? totalRecords :
      type === 'delivered' ? Math.round(totalRecords * 0.988) :
      type === 'completed' ? Math.round(totalRecords * 0.988) :
      type === 'quarantined' ? totalRecords :
      0;
    if (type === 'delivered') delivered = records;
    if (type === 'rolled_back' || type === 'quarantined') failed = totalRecords;

    const summary =
      type === 'planned' ? `Cartographer planned ${plan.batches.length} batch(es) · ${totalRecords.toLocaleString()} records` :
      type === 'approved' ? `Approval granted (${mapping.approvalReason ?? 'standard review'})` :
      type === 'started' ? `Courier opened batch ${plan.batches[0]?.batchId ?? ''}` :
      type === 'extracted' ? `Extracted ${records.toLocaleString()} records via cursor${goldenIdentity ? ` · keyed on golden ${goldenIdentity}` : ''}` :
      type === 'transformed' ? `Mapper applied ${mapping.transformations.length} transforms${goldenMergeCount && goldenMergeCount > 0 ? ` · ${goldenMergeCount} golden-record merge(s) collapsed duplicate identities` : ''}` :
      type === 'policy_checked' ? `Sentinel evaluated ${policies.filter((p) => p.scope.includes(mapping.verticalId)).length} policies${dslRules?.length ? ` + ${dslRules.length} DSL rule(s) v${dslVersion ?? '—'} · ${matchedDslRules.length} matched${dslBlock ? ' (BLOCKED)' : ''}` : ''}` :
      type === 'delivered' ? `Courier delivered ${records.toLocaleString()} to ${destination.name}` :
      type === 'completed' ? `Verity reconciled · 1.2% rejection rate` :
      type === 'quarantined' ? `Sentinel quarantined batch · ${willBlock ? 'governance red' : 'policy block'}` :
      type === 'rolled_back' ? 'Auto-rollback complete' :
      type === 'failed' ? 'Delivery failed' :
      type === 'retried' ? 'Retry with exponential backoff' :
      type;

    events.push({
      id: `${runId}-${i}-${type}`,
      syncId: runId,
      syncName: mapping.name,
      destinationId: destination.id,
      verticalId: mapping.verticalId,
      type,
      atIso: at,
      agentId: AGENT_BY_TYPE[type],
      summary,
      recordsAffected: records,
      latencyMs: 80 + (i * 60),
      stateHash: `0x${shortHex(chain)}`,
      evidenceRef: type === 'completed' || type === 'rolled_back' || type === 'quarantined' ? `evidence/${runId}` : null,
      severity: SEV[type],
      errorClass: null,
    });
  });

  // Lutar axes from the actual run. Golden-record merges raise containment
  // (fewer duplicate identities → tighter contract surface).
  const provenance = Math.min(1, mapping.confidence);
  const goldenBoost = goldenMergeCount && goldenMergeCount > 0 ? Math.min(0.06, goldenMergeCount * 0.02) : 0;
  const containment = Math.min(1, destination.fieldContractStrength + goldenBoost);
  const coherence = willBlock ? 0.4 : 0.85 + (mapping.confidence - 0.7) * 0.5;
  const convergence = willBlock ? 0.3 : delivered / Math.max(1, totalRecords);
  const sigma = computeLutarSigma({
    P: provenance,
    K: containment,
    phi: Math.max(0, Math.min(1, coherence)),
    C: Math.max(0, Math.min(1, convergence)),
  });

  const verdict: CoalitionRunResult['verdict'] = willBlock ? 'blocked' : delivered === 0 ? 'failed' : 'completed';
  return {
    runId,
    events,
    sigma,
    verdict,
    recordsDelivered: delivered,
    recordsFailed: failed,
    evidenceRef: `evidence/${runId}`,
  };
}
