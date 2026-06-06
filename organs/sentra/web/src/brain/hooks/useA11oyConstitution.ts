// doctrine-scanner-exempt: legacy live-product surface; rename tracked as separate engineering debt — see scripts/check-doctrine-v6.mjs header.
/**
 * useA11oyConstitution — live A11oy doctrine fetch with local fallback
 *
 * ROSIE reads its active constitution from A11oy's governance fabric.
 * At runtime, ROSIE first attempts to load the active constitution from
 * A11oy's doctrine API (/a11oy/api/doctrine/constitution/active). If the
 * endpoint is unreachable or returns an error, ROSIE falls back to the
 * locally-seeded clauses that mirror A11oy's ConstitutionClause schema
 * from artifacts/a11oy/src/data/mythosDoctrine.ts.
 *
 * Status values:
 *   'loading'  — initial fetch in progress
 *   'live'     — constitution loaded from A11oy API
 *   'fallback' — A11oy API not available; using local seeds
 */

import { useState, useEffect } from 'react';
import {
  ACTIVE_CONSTITUTION,
  ACTIVE_PLAYBOOKS,
  CONSTITUTION_VERSION,
  type RosieGuardrailClause,
} from '../data/a11oyConstitution';

export type ConstitutionStatus = 'loading' | 'live' | 'fallback';

export interface A11oyConstitutionState {
  clauses: RosieGuardrailClause[];
  playbooks: typeof ACTIVE_PLAYBOOKS;
  status: ConstitutionStatus;
  constitutionVersion: string;
}

/**
 * Maps a raw A11oy ConstitutionClause (from the API) to ROSIE's
 * RosieGuardrailClause, adding optimizer implication fields.
 */
function adaptApiClause(raw: {
  id: string;
  text: string;
  category: string;
}): RosieGuardrailClause {
  const existing = ACTIVE_CONSTITUTION.find(c => c.id === raw.id);
  return {
    id: raw.id,
    text: raw.text,
    category: raw.category as RosieGuardrailClause['category'],
    binding: existing?.binding ?? 'default',
    optimizerImplication:
      existing?.optimizerImplication ??
      'Applies to all ROSIE optimizer runs per A11oy governance mandate.',
    // If the API returns a clause we already have a checkKind for, use it;
    // otherwise mark it 'unmapped-fail-closed' so the solver TREATS IT AS A
    // HARD VIOLATION rather than silently passing. The operator extending
    // ROSIE must add an executable check for new clauses before they certify.
    checkKind: existing?.checkKind ?? 'unmapped-fail-closed',
    checkParam: existing?.checkParam,
  };
}

export function useA11oyConstitution(): A11oyConstitutionState {
  const [state, setState] = useState<A11oyConstitutionState>({
    clauses: ACTIVE_CONSTITUTION,
    playbooks: ACTIVE_PLAYBOOKS,
    status: 'loading',
    constitutionVersion: CONSTITUTION_VERSION,
  });

  useEffect(() => {
    let cancelled = false;
    const A11OY_ENDPOINT = '/a11oy/api/doctrine/constitution/active';

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);

    fetch(A11OY_ENDPOINT, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
      .then(async r => {
        clearTimeout(timeout);
        if (!r.ok) throw new Error(`A11oy API returned ${r.status}`);
        return r.json() as Promise<{
          version: string;
          clauses: Array<{ id: string; text: string; category: string }>;
        }>;
      })
      .then(data => {
        if (cancelled) return;
        const adapted = (data.clauses ?? []).map(adaptApiClause);
        if (adapted.length === 0) throw new Error('Empty clause set from A11oy');
        setState({
          clauses: adapted,
          playbooks: ACTIVE_PLAYBOOKS,
          status: 'live',
          constitutionVersion: data.version ?? CONSTITUTION_VERSION,
        });
      })
      .catch(() => {
        clearTimeout(timeout);
        if (cancelled) return;
        // Documented fallback: A11oy API not available, use seeded clauses.
        setState({
          clauses: ACTIVE_CONSTITUTION,
          playbooks: ACTIVE_PLAYBOOKS,
          status: 'fallback',
          constitutionVersion: CONSTITUTION_VERSION,
        });
      });

    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(timeout);
    };
  }, []);

  return state;
}
