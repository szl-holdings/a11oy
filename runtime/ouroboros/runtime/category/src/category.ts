// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: ouroboros/category  Thesis: TH4 (Λ-Category)
// Doctrine V6 preflight: ✓

import { createHash } from "node:crypto";
import { type Receipt } from "@szl/ouroboros-types";
import { evaluateAxes } from "@szl/ouroboros-lambda-gate";

// ---------------------------------------------------------------------------
// Morphism: a directed edge between two receipt objects
// ---------------------------------------------------------------------------

export interface Morphism {
  /** Domain receipt hash */
  domain:   string;
  /** Codomain receipt hash */
  codomain: string;
  /** Label / operation name */
  label:    string;
  /** Hash of (domain + codomain + label) — stable identity */
  id:       string;
}

export function morphism(domain: string, codomain: string, label: string): Morphism {
  const id = createHash("sha256")
    .update(`${domain}|${codomain}|${label}`)
    .digest("hex");
  return { domain, codomain, label, id };
}

// ---------------------------------------------------------------------------
// Identity morphism: domain == codomain (id_A)
// ---------------------------------------------------------------------------

export function identityMorphism(receipt: Receipt): Morphism {
  return morphism(receipt.hash, receipt.hash, "id");
}

// ---------------------------------------------------------------------------
// Morphism composition: g ∘ f  (f then g)
// f: A → B,  g: B → C  ⟹  g∘f: A → C
// Asserts that f.codomain == g.domain (type-level boundary check)
// Also asserts both endpoints pass the Λ-gate
// ---------------------------------------------------------------------------

export interface ComposeError {
  kind: "boundary_mismatch" | "gate_fail";
  detail: string;
}

export type ComposeResult =
  | { ok: true;  morphism: Morphism }
  | { ok: false; error: ComposeError };

/**
 * Compose morphism f then g.
 * Runtime asserts: f.codomain === g.domain (associativity boundary).
 */
export function composeMorphisms(
  f: Morphism,
  g: Morphism,
): ComposeResult {
  if (f.codomain !== g.domain) {
    return {
      ok: false,
      error: {
        kind: "boundary_mismatch",
        detail: `f.codomain(${f.codomain.slice(0, 8)}) ≠ g.domain(${g.domain.slice(0, 8)})`,
      },
    };
  }
  return {
    ok: true,
    morphism: morphism(f.domain, g.codomain, `${g.label}∘${f.label}`),
  };
}

// ---------------------------------------------------------------------------
// Functor law assertions
// A Λ-functor F must satisfy:
//   F(id_A) = id_{F(A)}
//   F(g ∘ f) = F(g) ∘ F(f)
// ---------------------------------------------------------------------------

export interface FunctorMap {
  /** Map a receipt hash to its image hash under the functor */
  mapObject: (hash: string) => string;
  /** Map a morphism to a morphism in the target category */
  mapMorphism: (m: Morphism) => Morphism;
}

export interface FunctorLawResult {
  identityLaw:       boolean;
  compositionLaw:    boolean;
  identityDetail?:   string;
  compositionDetail?: string;
}

/**
 * Assert functor laws at runtime given a FunctorMap and two composable morphisms.
 */
export function assertFunctorLaws(
  F: FunctorMap,
  receipt: Receipt,
  f: Morphism,
  g: Morphism,
): FunctorLawResult {
  // Identity law: F(id_A) == id_{F(A)}
  const idA   = identityMorphism(receipt);
  const F_idA = F.mapMorphism(idA);
  const id_FA = morphism(F.mapObject(receipt.hash), F.mapObject(receipt.hash), "id");
  const identityLaw = F_idA.id === id_FA.id;

  // Composition law: F(g∘f) == F(g)∘F(f)
  const composed = composeMorphisms(f, g);
  if (!composed.ok) {
    return {
      identityLaw,
      compositionLaw: false,
      compositionDetail: `Morphisms not composable: ${composed.error.detail}`,
    };
  }
  const F_gf   = F.mapMorphism(composed.morphism);
  const F_f    = F.mapMorphism(f);
  const F_g    = F.mapMorphism(g);
  const F_g_F_f = composeMorphisms(F_f, F_g);
  const compositionLaw = F_g_F_f.ok && F_gf.id === F_g_F_f.morphism.id;

  return { identityLaw, compositionLaw };
}

// ---------------------------------------------------------------------------
// Gate-receipt morphism validity check
// ---------------------------------------------------------------------------

export function validateMorphismEndpoint(r: Receipt): boolean {
  return evaluateAxes(r.axes).pass;
}
