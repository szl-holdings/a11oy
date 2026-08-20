export type Receipt = {
  receipt_id: string;
  output_digest: string;
  timestamp_utc: string;
  signature: string;
  [key: string]: unknown;
};

function utf8(input: string): Uint8Array {
  return new TextEncoder().encode(input);
}

function canonical(payload: Receipt): string {
  const clone: Receipt = { ...payload };
  // In production this should canonicalize via a stable JSON serializer.
  return JSON.stringify(clone);
}

export async function verifyOffline(receipt: Receipt, secret: string): Promise<boolean> {
  const data = canonical(receipt);
  const key = await crypto.subtle.importKey(
    "raw",
    utf8(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, utf8(data));
  const actual = Array.from(new Uint8Array(signature))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return timingSafeEqual(actual, receipt.signature);
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) {
    out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return out === 0;
}
