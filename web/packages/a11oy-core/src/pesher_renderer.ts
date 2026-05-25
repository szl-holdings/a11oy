/**
 * Pesher Audit-Trail Renderer
 *
 * Source: 1QpHab (Habakkuk Pesher); 4QpNah (Nahum Pesher); Berrin (2004),
 *   The Pesher Nahum Scroll from Qumran, Brill.
 *
 * Renders a governance decision into a pesher record: lemma → pishro al
 * → referent → testable claim → witness SHA-256. The pesher form is the
 * Qumran community's exegetical structure (a verbatim lemma followed by
 * "its interpretation concerns..."). Every record carries a witnessHash
 * so the audit chain can be replayed bit-for-bit.
 */
import formulae from '../../a11oy-knowledge/src/pesher_formulae.json' with { type: 'json' };

export type PesherKind = 'PSH-DENY' | 'PSH-ADMIT' | 'PSH-ELEVATE' | 'PSH-DIVERGE';

export type PesherInput = {
  kind: PesherKind;
  verdict: string;
  ruleId?: string;
  policyId?: string;
  escalationId?: string;
  primaryAxis?: string;
  secondaryAxis?: string;
  capabilityClass?: string;
  guardrailSet?: string;
  reviewerQuorum?: string;
  counterfactual?: string;
  invariantHeld?: string;
  quorumReached?: string;
  deltaBound?: string;
  witnessHash: string;
};

export type PesherRecord = {
  kind: PesherKind;
  rendered: string;
  witnessHash: string;
  ts: string;
};

export function renderPesher(input: PesherInput): PesherRecord {
  if (!input.witnessHash || input.witnessHash.length !== 64) {
    throw new Error('Pesher record requires a 64-char SHA-256 witnessHash');
  }
  const template = formulae.templates.find((t) => t.id === input.kind);
  if (!template) throw new Error(`Unknown pesher kind: ${input.kind}`);
  const rendered = template.form.replace(/\{(\w+)\}/g, (_m, key: string) => {
    const value = (input as unknown as Record<string, string | undefined>)[key];
    if (value === undefined) {
      throw new Error(`Pesher template ${input.kind} missing field ${key}`);
    }
    return value;
  });
  return { kind: input.kind, rendered, witnessHash: input.witnessHash, ts: new Date().toISOString() };
}

export const PESHER_FORMULAE = formulae;
