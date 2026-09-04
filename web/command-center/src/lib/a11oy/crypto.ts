export const GENESIS = "0".repeat(64);

export async function sha256Hex(canonical: string): Promise<string> {
  const bytes = new TextEncoder().encode(canonical);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function canonicalReceipt(parts: {
  seq: number;
  prevDigest: string;
  verdict: string;
  hard: boolean;
  action: string;
  intent: string;
  reason: string;
  trust: number;
  at: string;
}): string {
  return [
    "szl.governed-c2-receipt/v1",
    `seq=${parts.seq}`,
    `prev=${parts.prevDigest}`,
    `verdict=${parts.verdict}`,
    `hard=${parts.hard ? "1" : "0"}`,
    `action=${parts.action}`,
    `intent=${parts.intent}`,
    `reason=${parts.reason}`,
    `trust=${parts.trust.toFixed(2)}`,
    "doctrine=v11",
    "lambda=Conjecture 1",
    `at=${parts.at}`,
  ].join("\n");
}

export function geometricMean(values: number[]): number {
  if (!values.length) return 0;
  if (values.some((v) => v <= 0)) return 0;
  const logSum = values.reduce((s, v) => s + Math.log(v), 0);
  return Math.min(0.97, Math.exp(logSum / values.length));
}
