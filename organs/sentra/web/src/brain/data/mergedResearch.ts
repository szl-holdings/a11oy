/**
 * Merged research library — fuses the static curated RESEARCH_LIBRARY
 * seed with mutable research log entries appended by the incident
 * pipeline. UI surfaces (ResearchPage, GuardDogBrainPanel) read from
 * here so newly-evolved heuristics show up immediately after a
 * governance-approved pipeline run.
 */
import { RESEARCH_LIBRARY, type ResearchEntry } from './researchLibrary';
import { loadResearchLog } from './researchLog';

export function getMergedResearchLibrary(): ResearchEntry[] {
  const log = loadResearchLog();
  const evolved: ResearchEntry[] = log.map((entry) => ({
    id: entry.id,
    title: entry.title,
    org: 'NIST',
    year: new Date(entry.timestamp).getFullYear(),
    link: `/sentra/brain/proofs?proof=${entry.proofId}`,
    tags: ['governance', 'optimization'],
    distillation: entry.distillation,
    influencedSolves: 1,
  }));
  return [...evolved, ...RESEARCH_LIBRARY];
}
