export const GENESIS = "0".repeat(64);

export async function sha256Hex(canonical: string): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) {
    throw new Error("Web Crypto unavailable. Cannot seal or verify.");
  }
  const bytes = new TextEncoder().encode(canonical);
  const digest = await subtle.digest("SHA-256", bytes);
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
