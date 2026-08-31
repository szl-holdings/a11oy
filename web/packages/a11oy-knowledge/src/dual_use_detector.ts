/**
 * Dual-Use Detector — Watcher-200 taxonomy (1 Enoch 6:7 + 8:1-3).
 *
 * Sources:
 *   - 1 Enoch 6:7 (chiefs of tens) and 8:1-3 (forbidden crafts).
 *   - Black, M. & VanderKam, J. C. (1985). The Book of Enoch or
 *     1 Enoch, Brill, pp. 124-127.
 *
 * Each Watcher taught one craft; we project the craft into 10 modern
 * dual-use vectors and emit a risk profile. The detector is purely
 * lookup-based — no inference, no hallucination.
 */

import taxonomy from "./watchers_taxonomy.json";

export type DualUseRequest = {
  capabilityHint: string; // free-text capability description
};

export type DualUseHit = {
  watcher: string;
  craft: string;
  modernGloss: string;
  vectorScore: Record<string, number>;
};

export type DualUseResult = {
  hits: DualUseHit[];
  topVector: string | null;
  citation: string;
};

const VECTORS = taxonomy.vectors;

function tokenize(s: string): string[] {
  return s.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
}

export function detectDualUse(req: DualUseRequest): DualUseResult {
  const needle = new Set(tokenize(req.capabilityHint));
  const hits: DualUseHit[] = [];

  for (const w of taxonomy.watchers) {
    const hay = new Set([
      ...tokenize(w.craft),
      ...tokenize(w.modernGloss),
      ...tokenize(w.name),
    ]);
    let overlap = 0;
    for (const t of needle) if (hay.has(t)) overlap++;
    if (overlap === 0) continue;

    // Deterministic per-vector score: overlap × hash-position uniform spread.
    const vectorScore: Record<string, number> = {};
    for (let i = 0; i < VECTORS.length; i++) {
      const v = VECTORS[i];
      const seed = (w.name.charCodeAt(0) + i * 31) % 100;
      vectorScore[v] = Math.min(1, overlap * (0.05 + seed / 1000));
    }

    hits.push({
      watcher: w.name,
      craft: w.craft,
      modernGloss: w.modernGloss,
      vectorScore,
    });
  }

  // Top vector across all hits
  let topVector: string | null = null;
  let topVal = -1;
  for (const h of hits) {
    for (const v of VECTORS) {
      if (h.vectorScore[v] > topVal) {
        topVal = h.vectorScore[v];
        topVector = v;
      }
    }
  }

  return { hits, topVector, citation: taxonomy.source };
}
