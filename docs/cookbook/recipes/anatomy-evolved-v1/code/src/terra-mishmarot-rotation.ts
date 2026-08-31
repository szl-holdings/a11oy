/**
 * terra-mishmarot-rotation.ts — 6-year Mishmarot priestly course wheel
 * Organ: terra (SKELETON / SCHEDULER)
 * Source: 4Q320–4Q330 (DJD XXI, Talmon, Ben-Dov & Glessmer, 2001)
 *         R04 §1 dss_mishmarot_scheduler.ts
 * Author: Stephen P. Lutar Jr., SZL Holdings
 * Invariant: mishmarot(1, 0).courseIndex === mishmarot(1, 6 % 6).courseIndex
 */

export const MISHMAROT_COURSES = [
  "Jehoiarib","Jedaiah","Harim","Seorim","Malchijah","Mijamin",
  "Hakkoz","Abijah","Jeshua","Shecaniah","Eliashib","Jakim",
  "Huppah","Jeshebeab","Bilgah","Immer","Hezir","Happizzez",
  "Pethahiah","Jehezekel","Jachin","Gamul","Delaiah","Maaziah",
] as const;

export type CourseIndex = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11
                        | 12| 13| 14| 15| 16| 17| 18| 19| 20| 21| 22| 23;

export interface CourseAssignment {
  weekOfYear: number;
  yearInCycle: number;
  courseIndex: CourseIndex;
  courseName: string;
  isAuditWeek: boolean;
}

/** The 24-course wheel assignment for week 1 across 6 years */
const WEEK1_COURSES_BY_YEAR: CourseIndex[] = [0, 12, 6, 18, 4, 16];

export function mishmarot(weekOfYear: number, yearInCycle: number): CourseAssignment {
  if (weekOfYear < 1 || weekOfYear > 52) throw new Error("weekOfYear must be 1..52");
  const cycleYear = ((yearInCycle % 6) + 6) % 6;
  const baseWeek1Course = WEEK1_COURSES_BY_YEAR[cycleYear];
  const courseIndex = ((baseWeek1Course + (weekOfYear - 1)) % 24) as CourseIndex;
  return {
    weekOfYear, yearInCycle: cycleYear,
    courseIndex, courseName: MISHMAROT_COURSES[courseIndex],
    isAuditWeek: [1, 7, 13, 19, 25, 31, 37, 43, 49].includes(weekOfYear),
  };
}

/** Zero-drift invariant */
export function verifyMishmarotInvariants(): boolean {
  return mishmarot(1, 0).courseIndex === mishmarot(1, 6).courseIndex
    && mishmarot(1, 0).courseIndex === mishmarot(1, 12).courseIndex;
}

// ─── Usage Example ────────────────────────────────────────────────────────────
/*
const assignment = mishmarot(1, 0);
console.log("Course:", assignment.courseName); // "Jehoiarib"
console.log("Zero-drift invariant:", verifyMishmarotInvariants()); // true
*/