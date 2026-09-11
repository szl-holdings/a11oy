export type FrontierBand = "SHIPPED" | "REPLICA" | "REPORTED" | "CONJECTURE" | "ROADMAP" | "OUT-OF-SCOPE";

export type FrontierItem = {
  id: string;
  name: string;
  band: FrontierBand;
  honesty: "MEASURED" | "REPORTED" | "CONJECTURE" | "UNAVAILABLE";
  note: string;
};

export const ESTATE_SPLIT = [
  { role: "Product origin", value: "https://a-11-oy.com", rule: "Python Space + existing Pages. Do not flip DNS onto this folder." },
  { role: "Proof registry", value: "https://a11oy.net", rule: "Static RECORD. Do not host this UI there." },
  { role: "Runtime Space", value: "SZLHOLDINGS/a11oy", rule: "Canonical Docker runtime. Do not replace with this React app." },
  { role: "This package", value: "web/command-center/", rule: "Inspectable operator replica. Source only until a human cutover." },
  { role: "Factory / Lyte", value: "a11oy-factory · lyte-lattice", rule: "BIND hologram. Named frontiers do not grant execution." },
] as const;

export const GATES = [
  { id: "P1", name: "Deny by default", note: "Missing evidence is DENY, never ADMIT." },
  { id: "P2", name: "Zero-pin Λ", note: "Any zero positive-weight axis pins Λ to 0." },
  { id: "P3", name: "Hard cannot lift", note: "Human approval cannot override HARD DENY." },
  { id: "P4", name: "Signer disclosed", note: "UNSIGNED-honest unless independent verify passes." },
  { id: "P5", name: "No fake LIVE", note: "Opaque fetch is UNKNOWN. HTTP 200 is reachability, not ATO." },
  { id: "P6", name: "Estate split", note: "Product / proof / runtime / replica stay distinct." },
] as const;

export const FRONTIERS: FrontierItem[] = [
  { id: "N-LOCK8", name: "Locked-8 Lean kernel", band: "SHIPPED", honesty: "REPORTED", note: "F1 F4 F7 F11 F12 F18 F19 F22 @ c7c0ba17. Count stays exactly 8." },
  { id: "N-RECEIPT", name: "Browser receipt chain", band: "REPLICA", honesty: "MEASURED", note: "SHA-256 hash-linked, copyable, re-hashable here. Signer ABSENT on this replica." },
  { id: "N-IMMUNE", name: "Hukulla fail-closed", band: "REPLICA", honesty: "MEASURED", note: "Threat signatures + zero-pin consent deny locally. Not a production certificate." },
  { id: "N-LAMBDA", name: "Λ uniqueness", band: "CONJECTURE", honesty: "CONJECTURE", note: "Conjecture 1. Unconditional uniqueness machine-checked false as stated. Never 1.0." },
  { id: "N-BFT", name: "Khipu Byzantine safety", band: "CONJECTURE", honesty: "CONJECTURE", note: "Conjecture 2. Open. A faulty organ can equivocate." },
  { id: "N-LYTE", name: "Lyte named frontiers N1–N27", band: "REPORTED", honesty: "REPORTED", note: "Presentation hologram. Interfaces do not grant execution or promotion." },
  { id: "N-ENERGY", name: "Energy harvest joules", band: "ROADMAP", honesty: "UNAVAILABLE", note: "No RAPL energy_uj sample on this replica. Watts are not joules." },
  { id: "N-FULCIO", name: "Keyless Fulcio / Sigstore", band: "ROADMAP", honesty: "UNAVAILABLE", note: "Dev cosign keypair is not identity-bound verification." },
  { id: "N-POVM", name: "POVM verdict streaming", band: "ROADMAP", honesty: "UNAVAILABLE", note: "No live observation stream into the verdict head from this UI." },
  { id: "N-HW", name: "TPM / SEV-SNP attestation", band: "ROADMAP", honesty: "UNAVAILABLE", note: "No hardware attestation bound to the running binary here." },
  { id: "N-LEAN-POVM", name: "Formal POVM completeness", band: "ROADMAP", honesty: "UNAVAILABLE", note: "Locked-8 is not a POVM completeness proof. Stub remains later-roadmap." },
  { id: "N-MODEL", name: "Train / host an LLM", band: "OUT-OF-SCOPE", honesty: "REPORTED", note: "a11oy is a verdict layer. It does not train, fine-tune, or host models." },
];
