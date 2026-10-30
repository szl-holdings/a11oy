// VENDORED FROM szl-holdings/platform@4dadb116cbafc8dbde9ffc9df183db2205dc73ca — artifacts/sentra/src/data/darpa-witness-boundary.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/** Honesty boundary for the Sentra DARPA page.

Public program names are references. This module does not assert an award,
a measurement, a model verdict, or a signature.
*/
export const DARPA_WITNESS_BOUNDARY = {
  schema: "szl.nemo.triad.v1",
  szlAward: "NONE_ASSERTED",
  nemotronRole: "PROPOSAL_ONLY",
  energy: "NVML joules or null",
  lambda:
    "Conjecture 1: unconditional uniqueness under A1-A5 is false as stated (maxAgg). Theorem U is conditional. Not authorization.",
  receipt: "UNSIGNED_HONEST",
  sentence:
    "SZL asserts no DARPA award on this page. Named programs are public references. A model reply stays a proposal. Energy is an NVML joule reading or null. Lambda is not a proof and not a signature.",
} as const;
