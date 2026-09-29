import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string | null | undefined) {
  if (!dateString) return "Never";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
  }).format(new Date(dateString));
}

export function formatDuration(ms: number | null | undefined) {
  if (ms == null) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Founder wash: a token at `pct`% over transparent — the only translucent colour form allowed. */
export function wash(color: string, pct: number) {
  return `color-mix(in srgb, ${color} ${pct}%, transparent)`;
}

/**
 * Categorical tones for identity MARKS (domain dots, chart series, node rings): founder
 * neutrals and silver in six lightness steps. Founder direction keeps identity neutral
 * (coral is the one node, teal is links/focus, gold is premium), so these never colour
 * text — the name beside the mark carries the identity, in --text-sub.
 */
export const CATEGORY_TONES = [
  'var(--text)',
  'var(--color-silver-300)',
  'var(--text-sub)',
  'var(--color-silver-500)',
  'var(--text-ghost)',
  'var(--color-silver-100)',
] as const;

/** SZL domain identities → categorical mark tones (shared by the Sovereign AI Hub pages). */
export const DOMAIN_TONES: Record<string, string> = {
  vessels: CATEGORY_TONES[1],
  terra: CATEGORY_TONES[4],
  prism: CATEGORY_TONES[0],
  aegis: CATEGORY_TONES[2],
  szl: CATEGORY_TONES[3],
  lyte: CATEGORY_TONES[5],
  sentra: CATEGORY_TONES[1],
};
