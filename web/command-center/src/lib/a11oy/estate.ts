export const PRODUCT_ORIGIN = "https://a-11-oy.com";
export const PROOF_REGISTRY = "https://a11oy.net";
export const RUNTIME_SPACE = "https://szlholdings-a11oy.hf.space";
export const SOURCE_REPO = "https://github.com/szl-holdings/a11oy";
export const LEAN_REPO = "https://github.com/szl-holdings/lutar-lean";
export const ORCID = "0009-0001-0110-4173";
export const DOCTRINE = "v11";
export const KERNEL = "c7c0ba17";
export const TRUST_CEILING = 0.97;
export const LAMBDA_FLOOR = 0.9;
export const LOCKED_FORMULAS = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"] as const;

export const NAV = [
  { to: "/console", label: "Console" },
  { to: "/superpowers", label: "Superpowers" },
  { to: "/formulas", label: "Formulas" },
  { to: "/evidence", label: "Evidence" },
  { to: "/observability", label: "Observability" },
  { to: "/immune", label: "IMMUNE" },
] as const;

export const SURFACES = [
  { to: "/console", title: "Command Center", blurb: "Receipt integrity, disclosed signer state, self-doubt gate, genome registry, organ vitals." },
  { to: "/superpowers", title: "Five Superpowers", blurb: "What governed inference does that ungoverned models cannot — each tied to a live check." },
  { to: "/observability", title: "Observability", blurb: "MELT plus Λ-drift. Every span is a receipt, not an LLM opinion." },
  { to: "/wires", title: "Wires", blurb: "Which probe feeds which surface, and whether it answered this session." },
  { to: "/mesh", title: "Mesh", blurb: "BFT-quorum graph. Unreachable organs are reported, never painted green." },
  { to: "/formulas", title: "Formulas", blurb: "PURIQ genome. Locked-8 with truthful Lean refs — not inflated labels." },
  { to: "/evidence", title: "Evidence", blurb: "Theorem U vs Conjecture 1, SLSA posture, offline verify." },
  { to: "/immune", title: "IMMUNE", blurb: "Fail-closed Hukulla. Hunt / isolate / deceive — never strike people." },
  { to: "/verify", title: "Verify", blurb: "Re-hash a receipt in this browser. SHA-256 UNSIGNED-honest." },
] as const;

export const VERTICALS = [
  { id: "a11oy", name: "a11oy", sector: "Core · governed inference", blurb: "The platform itself — command center, receipts, disclosed signer state." },
  { id: "killinchu", name: "killinchu", sector: "Defense · counter-UAS", blurb: "Auditable interdiction: receipt per decision, 3-of-4 BFT." },
  { id: "insurance", name: "Insurance", sector: "David Leads · lead scoring", blurb: "Faithful scorer behind a non-compensatory consent gate." },
  { id: "finance", name: "Finance", sector: "Governed decisioning", blurb: "Reconstructable paths, receipt-bound, signed only when verified." },
  { id: "realestate", name: "Real estate", sector: "Governed workflows", blurb: "Workflow decisions enter the same one-chain ledger." },
] as const;

export const CONSOLE_VERTICALS = [
  { title: "Counter-UAS / killinchu", blurb: "Detection + classification governed, auditable, energy-bounded at the edge.", href: "https://szlholdings-killinchu.hf.space", link: "whHero →" },
  { title: "Maritime / Finance Intel", blurb: "Sovereign inference with energy receipts for operational accounting.", href: "/observability", link: "finm →" },
  { title: "Supply-chain / UDS", blurb: "Cryptographic audit traces survive chain-of-custody review — not log files.", href: "/mesh", link: "uds →" },
  { title: "Energy Harvest", blurb: "Soak wasted grid energy via live public feeds — honest joules, no free energy.", href: "/observability", link: "energy →" },
] as const;

export const LOCKED_CLAIMS = [
  {
    id: "F1",
    name: "replay-hash determinism",
    claim: "identical canonical input ⇒ identical receipt hash (NOT gate-pass ⇒ Λ ≥ 0.90)",
    lean: "Lutar/Puriq/Formulas/ProvedFormulas.lean::f1_replay_hash_determinism",
  },
  {
    id: "F19",
    name: "Bekenstein additive",
    claim: "s1 ≤ s1 + s2 entropy-budget monotonicity over Nat (NOT the 13-axis Λ geomean — that is Conjecture 1)",
    lean: "Lutar/Puriq/Formulas/ProvedFormulas.lean::f19_bekenstein_additive",
  },
  {
    id: "F11",
    name: "Ayni reciprocity conservation",
    claim: "reciprocity conservation — b + c balance over Int (NOT an STL robustness ρ envelope)",
    lean: "Lutar/Puriq/Formulas/ProvedFormulas.lean::f11_ayni_reciprocity_conservation",
  },
  {
    id: "F18",
    name: "Reed-Solomon parity count",
    claim: "(10−6 : Nat) = 4 erasure-tolerance arithmetic (NOT a DSSE seal binding)",
    lean: "Lutar/Puriq/Formulas/ProvedFormulas.lean::f18_reed_solomon_parity_count",
  },
  {
    id: "F12",
    name: "Kuramoto additive",
    claim: "phase additivity p1 + p2 over k phases (NOT deny-by-default gate monotonicity)",
    lean: "Lutar/Puriq/Formulas/ProvedFormulas.lean::f12_kuramoto_additive",
  },
  {
    id: "F4",
    name: "Gauss-Yuyay aggregation",
    claim: "locked kernel theorem — induction (NOT a live Λ reading)",
    lean: "lutar-lean locked-8",
  },
  {
    id: "F7",
    name: "Inverse-square / zeta provenance",
    claim: "locked kernel theorem — rewrite (NOT a traction metric)",
    lean: "lutar-lean locked-8",
  },
  {
    id: "F22",
    name: "Feynman-Puriq path integral",
    claim: "locked kernel theorem — induction (NOT actuation authority)",
    lean: "lutar-lean locked-8",
  },
] as const;

export const GENOME = [
  { id: "F1", name: "Euler-Khipu DAG Identity", status: "LOCKED-PROVEN", lean: "rfl" },
  { id: "F2", name: "Egyptian-Kallpa Allocation", status: "SKELETON", lean: "UNATTEMPTED" },
  { id: "F3", name: "Noether-Khipu Conservation", status: "SORRY", lean: "UNATTEMPTED" },
  { id: "F4", name: "Gauss-Yuyay Aggregation", status: "LOCKED-PROVEN", lean: "induction" },
  { id: "F5", name: "Euler-Lagrange Agency", status: "SKELETON", lean: "UNATTEMPTED" },
  { id: "F6", name: "Newton Risk-Velocity Tripwire", status: "SKELETON", lean: "UNATTEMPTED" },
  { id: "F7", name: "Inverse-Square/Zeta Provenance", status: "LOCKED-PROVEN", lean: "rw" },
  { id: "F8", name: "Newton-Parsimony Pick", status: "SKELETON", lean: "UNATTEMPTED" },
  { id: "F9", name: "Sulba Yuyay Mass-Conservation", status: "SORRY", lean: "UNATTEMPTED" },
  { id: "F10", name: "Baudhayana Orthogonality Bound", status: "SORRY", lean: "UNATTEMPTED" },
  { id: "F11", name: "Frustum A-Shrink Law", status: "LOCKED-PROVEN", lean: "simp" },
  { id: "F12", name: "CRT-Hukulla Schedule", status: "LOCKED-PROVEN", lean: "rfl" },
  { id: "F13", name: "Gauss-Bonnet Spine Curvature", status: "CONJECTURE", lean: "UNATTEMPTED" },
  { id: "F14", name: "Ramanujan A-Partition Bound", status: "CONJECTURE", lean: "UNATTEMPTED" },
  { id: "F15", name: "Grothendieck Organ Functor", status: "SKELETON", lean: "UNATTEMPTED" },
  { id: "F16", name: "von-Neumann-Hukulla Minimax", status: "SKELETON", lean: "UNATTEMPTED" },
  { id: "F17", name: "Shannon-Kallpa Capacity", status: "SKELETON", lean: "UNATTEMPTED" },
  { id: "F18", name: "Kolmogorov A-Description Cap", status: "LOCKED-PROVEN", lean: "rfl" },
  { id: "F19", name: "Turing-Fuel Halting Safety", status: "LOCKED-PROVEN", lean: "rfl" },
  { id: "F20", name: "Schrodinger Action Superposition", status: "SORRY", lean: "UNATTEMPTED" },
  { id: "F21", name: "Dirac-Commit Projection", status: "SORRY", lean: "UNATTEMPTED" },
  { id: "F22", name: "Feynman-Puriq Path Integral", status: "LOCKED-PROVEN", lean: "induction" },
  { id: "F23", name: "Bekenstein A-Cap", status: "CONJECTURE", lean: "CONJECTURE_1" },
] as const;

export const PUBLIC_CREDS = [
  { label: "OpenAI GPT-5.5 Bio Bounty Cohort", href: "https://openai.smapply.org/prog/gpt-5-5-safety-bio-bounty-program/" },
  { label: "Hugging Face Kernel-Publish", href: "https://huggingface.co/kernels-community" },
  { label: "Defense Unicorns Warhacker", href: "https://defenseunicorns.com/warhacker/" },
] as const;

export const PULSE_ENDPOINTS = [
  { id: "health", label: "Platform health", url: `${PRODUCT_ORIGIN}/healthz` },
  { id: "tabs", label: "Tab contract", url: `${PRODUCT_ORIGIN}/api/a11oy/v1/readiness/tab-matrix` },
  { id: "ledger", label: "Receipt ledger", url: `${PRODUCT_ORIGIN}/api/a11oy/v1/ledger` },
  { id: "mesh", label: "Sovereign mesh", url: `${PRODUCT_ORIGIN}/api/a11oy/v1/mesh/state` },
] as const;
