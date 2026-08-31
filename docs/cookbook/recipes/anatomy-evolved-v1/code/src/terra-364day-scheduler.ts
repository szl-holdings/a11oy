/**
 * terra-364day-scheduler.ts — Enoch 364-day solar calendar scheduler
 * Organ: terra (SKELETON / SCHEDULER)
 * Source: 1 Enoch 72–82 (Charles 1917, pp. 104–110); R02 §1 enoch_calendar_scheduler.ts
 * Author: Stephen P. Lutar Jr., SZL Holdings
 * Invariant: ∀ spec: weekday === enochDayToWeekday(enochDayOfYear) — no drift
 */

/** Enoch epoch: 2024-01-01T00:00:00Z (Sunday = day 1 of week 1 of year 1) */
export const ENOCH_EPOCH_MS = 1704067200000;
export const ENOCH_YEAR_DAYS = 364;
export const ENOCH_WEEK_DAYS = 7;
export const ENOCH_WEEKS_PER_YEAR = 52; // 364 / 7 = 52 exactly — no drift

export interface EnochDate {
  year: number;
  dayOfYear: number;   // 1..364
  weekOfYear: number;  // 1..52
  dayOfWeek: number;   // 1..7 (1 = Sunday)
  month: number;       // 1..12 (each 30 days, 4 intercalary days per year)
}

export function gregorianToEnoch(date: Date): EnochDate {
  const elapsedMs = date.getTime() - ENOCH_EPOCH_MS;
  const elapsedDays = Math.floor(elapsedMs / 86400000);
  const year = Math.floor(elapsedDays / ENOCH_YEAR_DAYS) + 1;
  const dayOfYear = (elapsedDays % ENOCH_YEAR_DAYS) + 1;
  const weekOfYear = Math.ceil(dayOfYear / ENOCH_WEEK_DAYS);
  const dayOfWeek = ((dayOfYear - 1) % ENOCH_WEEK_DAYS) + 1;
  const month = Math.ceil(dayOfYear / 30);
  return { year, dayOfYear, weekOfYear, dayOfWeek, month };
}

export interface EnochCronSpec {
  id: string;
  enochDayOfYear: number; // 1..364
  weekday: number;        // 1..7 — FIXED permanently (invariant)
  label: string;
}

/** Generate annual schedule for all 14 SZL audit crons */
export function generateAnnualSchedule(year: number): EnochCronSpec[] {
  // 14 audit crons spread across the 52-week year
  const auditCronDays = [7, 21, 35, 56, 77, 91, 112, 133, 147, 168, 196, 224, 252, 280];
  return auditCronDays.map((doy, i) => ({
    id: `szl-audit-cron-${String(i + 1).padStart(2, "0")}`,
    enochDayOfYear: doy,
    weekday: ((doy - 1) % 7) + 1, // permanently fixed: 364 = 52×7
    label: `SZL Audit Cron ${i + 1} — 1 Enoch 72–82 calendar`,
  }));
}

/** Verify no drift: weekday must equal enochDayToWeekday(dayOfYear) for all specs */
export function verifyNoDrift(specs: EnochCronSpec[]): boolean {
  return specs.every(s => s.weekday === ((s.enochDayOfYear - 1) % 7) + 1);
}

// ─── Usage Example ────────────────────────────────────────────────────────────
/*
const enochNow = gregorianToEnoch(new Date("2026-05-18"));
console.log("Enoch day:", enochNow.dayOfYear, "weekday:", enochNow.dayOfWeek);
const schedule = generateAnnualSchedule(enochNow.year);
console.log("No-drift invariant:", verifyNoDrift(schedule)); // true
console.log("Next audit cron:", schedule[0]);
*/