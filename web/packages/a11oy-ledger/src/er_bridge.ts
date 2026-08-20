/**
 * ER-Bridge — Einstein-Rosen Reconciliation between the Two Tablets
 *
 * Source: Einstein & Rosen (1935), "The Particle Problem in the General
 *   Theory of Relativity", Phys. Rev. 48:73-77. Wald (1984), General
 *   Relativity, §6.4.
 *
 * The ER-bridge connects the two tablet roots. If both tablets recorded
 * the same governance history, their chainHash roots are identical and
 * the bridge "closes". If not, the bridge reports the first divergent seq.
 */
import type { Tablet } from './dual_tablets';
import { tabletRoot } from './dual_tablets';

export type BridgeReport = {
  closed: boolean;
  primaryRoot: string;
  secondaryRoot: string;
  divergedAtSeq: number | null;
  recommendation: 'continue' | 'halt-and-audit';
};

export function reconcile(primary: Tablet, secondary: Tablet): BridgeReport {
  const primaryRoot = tabletRoot(primary);
  const secondaryRoot = tabletRoot(secondary);
  if (primaryRoot === secondaryRoot && primary.entries.length === secondary.entries.length) {
    return {
      closed: true,
      primaryRoot,
      secondaryRoot,
      divergedAtSeq: null,
      recommendation: 'continue',
    };
  }
  const minLen = Math.min(primary.entries.length, secondary.entries.length);
  let divergedAt: number | null = null;
  for (let i = 0; i < minLen; i++) {
    if (primary.entries[i].chainHash !== secondary.entries[i].chainHash) {
      divergedAt = i;
      break;
    }
  }
  if (divergedAt === null && primary.entries.length !== secondary.entries.length) {
    divergedAt = minLen;
  }
  return {
    closed: false,
    primaryRoot,
    secondaryRoot,
    divergedAtSeq: divergedAt,
    recommendation: 'halt-and-audit',
  };
}
