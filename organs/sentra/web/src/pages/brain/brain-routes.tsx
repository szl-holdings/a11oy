/**
 * Brain route wrappers — bridge ROSIE pages (which use a local AppPage
 * navigator) into Sentra's wouter router under /brain/*.
 *
 * The slug map is the single source of truth for the public URLs.
 */
import { useCallback } from 'react';
import { useLocation } from 'wouter';
import type { AppPage } from '@/brain/App';
import { IdentityPage } from '@/brain/pages/IdentityPage';
import { OptimizerPage } from '@/brain/pages/OptimizerPage';
import { FabricPage } from '@/brain/pages/FabricPage';
import { ResearchPage } from '@/brain/pages/ResearchPage';
import { ProofPage } from '@/brain/pages/ProofPage';
import { EvidenceBenchPage } from '@/brain/pages/EvidenceBenchPage';

const APP_PAGE_TO_SLUG: Record<AppPage, string> = {
  identity: 'constitution',
  optimizer: 'optimizer',
  fabric: 'evolution',
  research: 'research',
  proof: 'proofs',
  bench: 'bench',
};

function useBrainNavigate(): (p: AppPage) => void {
  const [, setLocation] = useLocation();
  return useCallback(
    (p: AppPage) => setLocation(`/brain/${APP_PAGE_TO_SLUG[p]}`),
    [setLocation],
  );
}

export function BrainConstitutionPage() {
  const navigate = useBrainNavigate();
  return <IdentityPage onNavigate={navigate} />;
}

export function BrainOptimizerPage() {
  const navigate = useBrainNavigate();
  return <OptimizerPage onNavigate={navigate} />;
}

export function BrainEvolutionPage() {
  return <FabricPage />;
}

export function BrainResearchPage() {
  return <ResearchPage />;
}

export function BrainProofsPage() {
  return <ProofPage />;
}

export function BrainBenchPage() {
  return <EvidenceBenchPage />;
}
