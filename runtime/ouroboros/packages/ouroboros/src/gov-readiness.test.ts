/**
 * SZL Holdings government-readiness module tests — pin every cardinal
 * fact from the April 30, 2026 NYSTEC pre-briefing audit so future edits
 * cannot silently drift the public scorecard.
 */

import { describe, expect, it } from 'vitest';
import {
  PLATFORM_READINESS,
  NIST_RMF_ALIGNMENT,
  DOD_TENETS,
  GSAR_552_239_7001_READINESS,
  RECOMMENDED_NAICS_CODES,
  SAM_GOV_REGISTRATION_STEPS,
  NEW_YORK_STATE_REGISTRATION_STEPS,
  PRE_MEETING_ACTION_ITEMS,
  COMPETITIVE_POSITIONING_STATEMENT,
  GOV_READINESS_MANIFEST,
  getPlatformReadiness,
  listGapsAcrossPlatforms,
  actionItemsByGroup,
} from './index.js';

describe('Platform readiness scores (audit scorecard)', () => {
  it('A11oy scores 72/100', () => {
    expect(PLATFORM_READINESS.A11oy.readinessScore).toBe(72);
  });
  it('Sentra scores 68/100', () => {
    expect(PLATFORM_READINESS.Sentra.readinessScore).toBe(68);
  });
  it('Amaru scores 65/100', () => {
    expect(PLATFORM_READINESS.Amaru.readinessScore).toBe(65);
  });
  it('all platforms have certPath = in_progress (none yet certified)', () => {
    for (const id of ['A11oy', 'Sentra', 'Amaru'] as const) {
      expect(PLATFORM_READINESS[id].scorecard.certPath).toBe('in_progress');
    }
  });
  it('cert notes pin the audit verbiage exactly', () => {
    expect(PLATFORM_READINESS.A11oy.scorecard.certNote).toBe('In progress');
    expect(PLATFORM_READINESS.Sentra.scorecard.certNote).toBe('Needs SOC 2');
    expect(PLATFORM_READINESS.Amaru.scorecard.certNote).toBe('Needs privacy docs');
  });
  it('every platform has at least one strength and one gap', () => {
    for (const id of ['A11oy', 'Sentra', 'Amaru'] as const) {
      expect(PLATFORM_READINESS[id].strengths.length).toBeGreaterThan(0);
      expect(PLATFORM_READINESS[id].gaps.length).toBeGreaterThan(0);
    }
  });
});

describe('NIST AI RMF alignment matrix', () => {
  it('declares the four NIST functions in canonical order', () => {
    expect(NIST_RMF_ALIGNMENT.map((r) => r.fn)).toEqual([
      'GOVERN',
      'MAP',
      'MEASURE',
      'MANAGE',
    ]);
  });
  it('every row has coverage entries for all three platforms', () => {
    for (const row of NIST_RMF_ALIGNMENT) {
      for (const p of ['A11oy', 'Sentra', 'Amaru'] as const) {
        expect(row.coverage[p]).toBeTruthy();
      }
    }
  });
});

describe('DoD Responsible AI Tenets', () => {
  it('declares all five DoD tenets in canonical order', () => {
    expect(DOD_TENETS.map((r) => r.tenet)).toEqual([
      'Responsible',
      'Equitable',
      'Traceable',
      'Reliable',
      'Governable',
    ]);
  });
  it('Equitable is the only tenet flagged as a gap', () => {
    const gaps = DOD_TENETS.filter((r) => r.status === 'gap').map((r) => r.tenet);
    expect(gaps).toEqual(['Equitable']);
  });
  it('Traceable, Reliable, Governable, Responsible are covered', () => {
    const covered = DOD_TENETS.filter((r) => r.status === 'covered').map((r) => r.tenet);
    expect(covered).toEqual(['Responsible', 'Traceable', 'Reliable', 'Governable']);
  });
});

describe('GSAR 552.239-7001 readiness', () => {
  it('declares all 10 audit-cited requirements', () => {
    expect(GSAR_552_239_7001_READINESS).toHaveLength(10);
  });
  it('5 requirements are covered, 5 are gaps', () => {
    const covered = GSAR_552_239_7001_READINESS.filter((r) => r.status === 'covered');
    const gaps = GSAR_552_239_7001_READINESS.filter((r) => r.status === 'gap');
    expect(covered).toHaveLength(5);
    expect(gaps).toHaveLength(5);
  });
  it('the 5 covered items are the canonical platform-strong rows', () => {
    expect(
      GSAR_552_239_7001_READINESS.filter((r) => r.status === 'covered').map(
        (r) => r.requirement,
      ),
    ).toEqual([
      'Human oversight and intervention mechanism',
      'Summarized intermediate processing actions',
      'Model routing decisions with rationale',
      'RAG source attribution with direct links',
      'Complete audit trail on demand',
    ]);
  });
});

describe('SAM.gov registration + NAICS', () => {
  it('declares the 5-step SAM.gov registration sequence', () => {
    expect(SAM_GOV_REGISTRATION_STEPS).toHaveLength(5);
    expect(SAM_GOV_REGISTRATION_STEPS.map((s) => s.order)).toEqual([1, 2, 3, 4, 5]);
  });
  it('declares the 5 recommended NAICS codes for SZL Consulting LTD', () => {
    expect(RECOMMENDED_NAICS_CODES).toHaveLength(5);
    expect(RECOMMENDED_NAICS_CODES.map((c) => c.code)).toEqual([
      '541511',
      '541512',
      '541519',
      '541690',
      '541715',
    ]);
  });
  it('NY state registration list includes Contract Reporter, MWBE, SDVOB notes', () => {
    expect(NEW_YORK_STATE_REGISTRATION_STEPS).toHaveLength(3);
    expect(NEW_YORK_STATE_REGISTRATION_STEPS[0]).toContain('NY Contract Reporter');
    expect(NEW_YORK_STATE_REGISTRATION_STEPS[1]).toContain('MWBE');
    expect(NEW_YORK_STATE_REGISTRATION_STEPS[2]).toContain('SDVOB');
  });
});

describe('Pre-meeting action items', () => {
  it('declares 5 critical, 5 for-meeting, and 6 thirty-day items', () => {
    expect(actionItemsByGroup('critical')).toHaveLength(5);
    expect(actionItemsByGroup('for_meeting')).toHaveLength(5);
    expect(actionItemsByGroup('thirty_day')).toHaveLength(6);
  });
  it('every action item belongs to one of the three canonical groups', () => {
    const valid = new Set(['critical', 'for_meeting', 'thirty_day']);
    for (const item of PRE_MEETING_ACTION_ITEMS) {
      expect(valid.has(item.group)).toBe(true);
    }
  });
});

describe('Competitive positioning statement', () => {
  it('mentions the three platforms by name', () => {
    expect(COMPETITIVE_POSITIONING_STATEMENT).toContain('A11oy');
    expect(COMPETITIVE_POSITIONING_STATEMENT).toContain('Sentra');
    expect(COMPETITIVE_POSITIONING_STATEMENT).toContain('Amaru');
  });
  it('cites NIST AI RMF and DoD Responsible AI tenets', () => {
    expect(COMPETITIVE_POSITIONING_STATEMENT).toContain('NIST AI RMF');
    expect(COMPETITIVE_POSITIONING_STATEMENT).toContain('Responsible AI');
  });
  it('cites the NY DIGIT agency and S.B. 7599', () => {
    expect(COMPETITIVE_POSITIONING_STATEMENT).toContain('DIGIT');
    expect(COMPETITIVE_POSITIONING_STATEMENT).toContain('S.B. 7599');
  });
});

describe('Manifest summary + helpers', () => {
  it('manifest pins audit metadata exactly', () => {
    expect(GOV_READINESS_MANIFEST.auditDate).toBe('2026-04-30');
    expect(GOV_READINESS_MANIFEST.preparedBy).toContain('Stephen P. Lutar Jr.');
    expect(GOV_READINESS_MANIFEST.meeting).toContain('NYSTEC');
  });
  it('manifest counts match the underlying registries', () => {
    expect(GOV_READINESS_MANIFEST.counts.platforms).toBe(
      Object.keys(PLATFORM_READINESS).length,
    );
    expect(GOV_READINESS_MANIFEST.counts.nistRows).toBe(NIST_RMF_ALIGNMENT.length);
    expect(GOV_READINESS_MANIFEST.counts.dodTenets).toBe(DOD_TENETS.length);
    expect(GOV_READINESS_MANIFEST.counts.gsarRequirements).toBe(
      GSAR_552_239_7001_READINESS.length,
    );
    expect(GOV_READINESS_MANIFEST.counts.naicsCodes).toBe(RECOMMENDED_NAICS_CODES.length);
    expect(GOV_READINESS_MANIFEST.counts.samSteps).toBe(SAM_GOV_REGISTRATION_STEPS.length);
    expect(GOV_READINESS_MANIFEST.counts.actionItems).toBe(
      PRE_MEETING_ACTION_ITEMS.length,
    );
  });
  it('overallScores match per-platform readinessScore', () => {
    expect(GOV_READINESS_MANIFEST.overallScores.A11oy).toBe(72);
    expect(GOV_READINESS_MANIFEST.overallScores.Sentra).toBe(68);
    expect(GOV_READINESS_MANIFEST.overallScores.Amaru).toBe(65);
  });
  it('readinessByGroup totals are internally consistent', () => {
    expect(
      GOV_READINESS_MANIFEST.readinessByGroup.gsarCovered +
        GOV_READINESS_MANIFEST.readinessByGroup.gsarGaps,
    ).toBe(GSAR_552_239_7001_READINESS.length);
    expect(
      GOV_READINESS_MANIFEST.readinessByGroup.dodCovered +
        GOV_READINESS_MANIFEST.readinessByGroup.dodGaps,
    ).toBe(DOD_TENETS.length);
  });
  it('getPlatformReadiness returns the full record for known IDs and null for unknown', () => {
    expect(getPlatformReadiness('A11oy')?.readinessScore).toBe(72);
    expect(getPlatformReadiness('Bogus')).toBeNull();
  });
  it('listGapsAcrossPlatforms aggregates every per-platform gap once', () => {
    const all = listGapsAcrossPlatforms();
    const totalExpected =
      PLATFORM_READINESS.A11oy.gaps.length +
      PLATFORM_READINESS.Sentra.gaps.length +
      PLATFORM_READINESS.Amaru.gaps.length;
    expect(all).toHaveLength(totalExpected);
  });
});
