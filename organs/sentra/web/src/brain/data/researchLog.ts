/**
 * Research log — localStorage-backed mutable extension to the static
 * RESEARCH_LIBRARY. Each completed governance-approved incident pipeline
 * appends an "evolved heuristic" entry capturing what the brain learned.
 */

export interface ResearchLogEntry {
  id: string;
  timestamp: string;
  title: string;
  source: 'incident-pipeline';
  incidentId: string;
  problemId: string;
  distillation: string;
  proofId: string;
}

const STORAGE_KEY = 'sentra-brain-research-log';

export function loadResearchLog(): ResearchLogEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ResearchLogEntry[]) : [];
  } catch {
    return [];
  }
}

export function appendResearchLogEntry(
  entry: Omit<ResearchLogEntry, 'id' | 'timestamp'>,
): ResearchLogEntry {
  const newEntry: ResearchLogEntry = {
    ...entry,
    id: `rlog-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    timestamp: new Date().toISOString(),
  };
  const entries = loadResearchLog();
  const updated = [newEntry, ...entries].slice(0, 50);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // storage unavailable — entry still returned
  }
  return newEntry;
}

export function clearResearchLog(): void {
  localStorage.removeItem(STORAGE_KEY);
}
