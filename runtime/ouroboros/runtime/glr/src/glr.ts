// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: ouroboros/glr  Thesis: TH8 (Graded Linear Receipts)
// Doctrine V6 preflight: ✓

import { type Receipt } from "@szl/ouroboros-types";

// ---------------------------------------------------------------------------
// Grade type — ordinal quality tier
// ---------------------------------------------------------------------------

export type Grade = "A" | "B" | "C" | "D";

/** Numeric weight of each grade for comparison */
const GRADE_WEIGHT: Record<Grade, number> = { A: 4, B: 3, C: 2, D: 1 };

export function gradeFromLambda(lambda: number): Grade {
  if (lambda >= 0.95) return "A";
  if (lambda >= 0.92) return "B";
  if (lambda >= 0.90) return "C";
  return "D";
}

export function gradeWeight(g: Grade): number {
  return GRADE_WEIGHT[g];
}

// ---------------------------------------------------------------------------
// Graded receipt wrapper
// ---------------------------------------------------------------------------

export interface GradedReceipt {
  receipt:  Receipt;
  grade:    Grade;
  consumed: boolean;
}

// ---------------------------------------------------------------------------
// Consumption ledger — linear-typing enforcement
// ---------------------------------------------------------------------------

export class ConsumptionLedger {
  private readonly ledger = new Map<string, GradedReceipt>();

  /** Register a new receipt into the ledger (unconsumed). */
  register(receipt: Receipt): GradedReceipt {
    const grade = gradeFromLambda(receipt.lambda);
    if (this.ledger.has(receipt.hash)) {
      throw new Error(`Receipt ${receipt.hash.slice(0, 16)} already registered`);
    }
    const gr: GradedReceipt = { receipt, grade, consumed: false };
    this.ledger.set(receipt.hash, gr);
    return gr;
  }

  /**
   * Consume a receipt exactly once.
   * Throws LinearityError if the receipt has already been consumed (use-after-free).
   */
  consume(hash: string): GradedReceipt {
    const gr = this.ledger.get(hash);
    if (!gr) throw new LinearityError(`Receipt ${hash.slice(0, 16)} not found in ledger`);
    if (gr.consumed) {
      throw new LinearityError(
        `Linearity violation: receipt ${hash.slice(0, 16)} has already been consumed`,
      );
    }
    gr.consumed = true;
    return gr;
  }

  /** Peek at a receipt without consuming it. */
  peek(hash: string): GradedReceipt | undefined {
    return this.ledger.get(hash);
  }

  /** List all receipts of a minimum grade (unconsumed only by default). */
  listAvailable(minGrade: Grade = "D"): GradedReceipt[] {
    return Array.from(this.ledger.values()).filter(
      (gr) => !gr.consumed && gradeWeight(gr.grade) >= gradeWeight(minGrade),
    );
  }

  /** Dump the full ledger (for auditing). */
  dump(): GradedReceipt[] {
    return Array.from(this.ledger.values());
  }
}

// ---------------------------------------------------------------------------
// LinearityError — distinct error class for violations
// ---------------------------------------------------------------------------

export class LinearityError extends Error {
  override readonly name = "LinearityError";
  constructor(msg: string) { super(msg); }
}

// ---------------------------------------------------------------------------
// Grade-composition rule: produce a composite grade from two consumed grades
// The composite is the LOWER of the two (weakest-link principle)
// ---------------------------------------------------------------------------

export function composeGrades(a: Grade, b: Grade): Grade {
  return gradeWeight(a) <= gradeWeight(b) ? a : b;
}
