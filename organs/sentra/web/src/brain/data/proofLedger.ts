export interface ProofEntry {
  id: string;
  timestamp: string;
  problemId: string;
  problemLabel: string;
  constitutionVersion: string;
  /** Whether guardrails came from the live A11oy API or seeded fallback. */
  constitutionSource: 'live' | 'fallback' | 'seed';
  inputsHash: string;
  outcome: 'optimal' | 'sub-optimal' | 'infeasible' | 'blocked';
  objectiveScore: number;
  guardrailsChecked: number;
  guardrailsViolated: number;
  solveTimeMs: number;
  notes?: string;
}

const STORAGE_KEY = 'rosie-proof-ledger';

/** SHA-256 via Web Crypto — returns "sha256:<hex>" */
async function hashInputs(inputs: unknown): Promise<string> {
  const str = JSON.stringify(inputs);
  const encoded = new TextEncoder().encode(str);
  const buf = await crypto.subtle.digest('SHA-256', encoded);
  const hexArr = Array.from(new Uint8Array(buf));
  return 'sha256:' + hexArr.map(b => b.toString(16).padStart(2, '0')).join('');
}

export function loadProofEntries(): ProofEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ProofEntry[]) : [];
  } catch {
    return [];
  }
}

/**
 * Appends a proof entry to localStorage.
 * Hashing is done with Web Crypto SHA-256 (async).
 * Constitution provenance (version + source) is recorded verbatim from
 * the runtime state used by the solver — not a static constant.
 */
export async function appendProofEntry(
  entry: Omit<ProofEntry, 'id' | 'timestamp' | 'inputsHash'> & { inputs: unknown },
): Promise<ProofEntry> {
  const inputsHash = await hashInputs(entry.inputs);
  const newEntry: ProofEntry = {
    id: `proof-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    timestamp: new Date().toISOString(),
    inputsHash,
    constitutionVersion: entry.constitutionVersion,
    constitutionSource: entry.constitutionSource,
    problemId: entry.problemId,
    problemLabel: entry.problemLabel,
    outcome: entry.outcome,
    objectiveScore: entry.objectiveScore,
    guardrailsChecked: entry.guardrailsChecked,
    guardrailsViolated: entry.guardrailsViolated,
    solveTimeMs: entry.solveTimeMs,
    notes: entry.notes,
  };
  const entries = loadProofEntries();
  const updated = [newEntry, ...entries].slice(0, 50);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // storage unavailable — entry still returned
  }
  return newEntry;
}

export function clearProofLedger(): void {
  localStorage.removeItem(STORAGE_KEY);
}
