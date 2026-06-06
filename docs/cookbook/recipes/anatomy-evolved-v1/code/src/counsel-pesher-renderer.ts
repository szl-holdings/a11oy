/**
 * counsel-pesher-renderer.ts — DSS Pesher formula library renderer
 * Organ: counsel (WISDOM / EXPLAIN STAGE)
 * Source: 1QpHab (Israel Museum DSS Digital Library); 4QpNah, 4QpIsa
 *         R04 §3 dss_pesher_renderer.ts + dss_pesher_formulae.json
 * Author: Stephen P. Lutar Jr., SZL Holdings
 */

export type PesherFormulaId = "psh-01"|"psh-02"|"psh-03"|"psh-04"|"psh-05"|"psh-06"|"psh-07"|"psh-08";

export interface PesherFormula {
  id: PesherFormulaId;
  hebrew: string;
  transliteration: string;
  a11oyTemplate: string;
  requiresHumanApproval: boolean;
}

export const PESHER_FORMULAE: PesherFormula[] = [
  { id: "psh-01", hebrew: "פשרו", transliteration: "pishro",
    a11oyTemplate: "Its interpretation [of {observedPattern}] concerns {esotericMeaning}",
    requiresHumanApproval: false },
  { id: "psh-02", hebrew: "פשר הדבר", transliteration: "pesher hadavar",
    a11oyTemplate: "The interpretation of the matter is that {esotericMeaning}",
    requiresHumanApproval: false },
  { id: "psh-03", hebrew: "אשר אמר", transliteration: "asher amar",
    a11oyTemplate: "Which refers to {esotericMeaning} as stated in {peshatContext}",
    requiresHumanApproval: false },
  { id: "psh-04", hebrew: "פשרו על", transliteration: "pishro al",
    a11oyTemplate: "Its interpretation concerns {eschatologicalSignificance} — regarding {esotericMeaning}",
    requiresHumanApproval: false },
  { id: "psh-05", hebrew: "יש פשר", transliteration: "yesh pesher",
    a11oyTemplate: "There is an interpretation: {observedPattern} signifies {esotericMeaning}",
    requiresHumanApproval: false },
  { id: "psh-06", hebrew: "נחשב פשרו", transliteration: "nechshav pishro",
    a11oyTemplate: "Its interpretation is reckoned as follows: {esotericMeaning} per {peshatContext}",
    requiresHumanApproval: false },
  { id: "psh-07", hebrew: "פשר על הקץ", transliteration: "pesher al ha-qets",
    a11oyTemplate: "Interpretation concerning the end-time: {eschatologicalSignificance}",
    requiresHumanApproval: true },
  { id: "psh-08", hebrew: "פשר הקץ האחרון", transliteration: "pesher ha-qets ha-acharon",
    a11oyTemplate: "Interpretation of the last end: {eschatologicalSignificance} — REQUIRES PRINCIPAL APPROVAL",
    requiresHumanApproval: true },
];

export interface PesherDecision {
  formulaId: PesherFormulaId;
  observedPattern: string;
  esotericMeaning: string;
  eschatologicalSignificance: string;
  peshatContext: string;
  requiresHumanApproval: boolean;
  renderedText: string;
}

export function buildPesherDecision(params: {
  formulaId: PesherFormulaId;
  observedPattern: string;
  esotericMeaning: string;
  eschatologicalSignificance?: string;
  peshatContext?: string;
}): PesherDecision {
  const formula = PESHER_FORMULAE.find(f => f.id === params.formulaId);
  if (!formula) throw new Error(`Unknown formula: ${params.formulaId}`);
  const esc = params.eschatologicalSignificance ?? "ongoing governance matter";
  const psh = params.peshatContext ?? "SZL operational context";
  const rendered = formula.a11oyTemplate
    .replace("{observedPattern}", params.observedPattern)
    .replace("{esotericMeaning}", params.esotericMeaning)
    .replace("{eschatologicalSignificance}", esc)
    .replace("{peshatContext}", psh);
  return {
    formulaId: params.formulaId,
    observedPattern: params.observedPattern,
    esotericMeaning: params.esotericMeaning,
    eschatologicalSignificance: esc,
    peshatContext: psh,
    requiresHumanApproval: formula.requiresHumanApproval,
    renderedText: rendered,
  };
}

export function validatePesherDecision(d: PesherDecision): string[] {
  const errors: string[] = [];
  if (!PESHER_FORMULAE.find(f => f.id === d.formulaId)) errors.push("Unknown formula ID");
  if (!d.observedPattern) errors.push("observedPattern is required");
  if (!d.esotericMeaning) errors.push("esotericMeaning is required");
  if (!d.renderedText) errors.push("renderedText must be non-empty");
  return errors;
}

// ─── Usage Example ────────────────────────────────────────────────────────────
/*
const decision = buildPesherDecision({
  formulaId: "psh-04",
  observedPattern: "vessel dark_anchorage_1 last AIS ping 72h ago",
  esotericMeaning: "potential dark-fleet evasion activity",
});
console.log(decision.renderedText);
console.log("Requires approval:", decision.requiresHumanApproval); // false
*/