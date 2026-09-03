export function copyrightLine(year?: number): string {
  const resolvedYear = year ?? new Date().getFullYear();
  return `© ${resolvedYear} SZL Holdings Inc. All rights reserved.`;
}
