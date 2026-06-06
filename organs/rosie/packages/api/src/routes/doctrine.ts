/**
 * @file packages/api/src/routes/doctrine.ts
 * @description GET /v1/doctrine/sweep — doctrine v7 sweep checker.
 *
 * Backs the Gradio "Doctrine Sweep" tab. Scans operator-facing text for
 * doctrine v7 banned terms (marketing language is disallowed under the founder
 * standard) and reports line+column locations. The stub sweeps an empty corpus
 * (clean); the real impl sweeps the configured docs set.
 */

import { Hono } from 'hono';
import type { AppEnv } from '../lib/env.ts';
import type { DoctrineSweep, DoctrineViolation } from '../types/index.ts';

export const doctrineRoute = new Hono<AppEnv>();

/** Doctrine v7 banned terms — marketing superlatives and hype words. */
export const BANNED_TERMS = [
  'revolutionary',
  'world-class',
  'best-in-class',
  'cutting-edge',
  'game-changer',
  'seamless',
  'turnkey',
  'synergy',
  'paradigm-shift',
];

/** Scan a corpus of named text blobs for banned terms. */
export function sweepCorpus(corpus: { name: string; text: string }[]): DoctrineViolation[] {
  const violations: DoctrineViolation[] = [];
  for (const doc of corpus) {
    const lines = doc.text.split('\n');
    lines.forEach((line, i) => {
      for (const term of BANNED_TERMS) {
        const idx = line.toLowerCase().indexOf(term);
        if (idx >= 0) {
          violations.push({ term, line: i + 1, column: idx + 1 });
        }
      }
    });
  }
  return violations;
}

doctrineRoute.get('/sweep', (c) => {
  // The stub sweeps an empty corpus; wired impl pulls the configured doc set.
  const violations = sweepCorpus([]);
  const body: DoctrineSweep = {
    doctrine_version: 'v7',
    clean: violations.length === 0,
    violations,
  };
  return c.json(body);
});
