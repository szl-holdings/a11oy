import { GENESIS, canonicalReceipt, sha256Hex } from "./crypto";

export const RECEIPT_SCHEMA = "szl.governed-c2-receipt/v1";
export const RECEIPT_STORE = "a11oy.command-center.receipts.v1";

export type ReceiptBody = {
  seq: number;
  prevDigest: string;
  verdict: string;
  hard: boolean;
  action: string;
  intent: string;
  reason: string;
  trust: number;
  at: string;
};

export type SealedReceipt = ReceiptBody & {
  schema: typeof RECEIPT_SCHEMA;
  digest: string;
  signer: "UNSIGNED-HONEST";
  doctrine: "v11";
  lambda: "Conjecture 1";
};

export async function sealReceipt(body: ReceiptBody): Promise<SealedReceipt> {
  const digest = await sha256Hex(canonicalReceipt(body));
  return {
    schema: RECEIPT_SCHEMA,
    ...body,
    digest,
    signer: "UNSIGNED-HONEST",
    doctrine: "v11",
    lambda: "Conjecture 1",
  };
}

export async function verifyReceipt(raw: unknown): Promise<{ ok: boolean; note: string; expected?: string }> {
  if (!raw || typeof raw !== "object") {
    return { ok: false, note: "Not a receipt object. Paste szl.governed-c2-receipt/v1 JSON." };
  }
  const obj = raw as Partial<SealedReceipt>;
  if (typeof obj.digest !== "string" || typeof obj.seq !== "number") {
    return { ok: false, note: "Missing digest or seq." };
  }
  const expected = await sha256Hex(
    canonicalReceipt({
      seq: Number(obj.seq),
      prevDigest: String(obj.prevDigest ?? GENESIS),
      verdict: String(obj.verdict ?? ""),
      hard: Boolean(obj.hard),
      action: String(obj.action ?? ""),
      intent: String(obj.intent ?? ""),
      reason: String(obj.reason ?? ""),
      trust: Number(obj.trust ?? 0),
      at: String(obj.at ?? ""),
    }),
  );
  if (expected === obj.digest) {
    return { ok: true, note: `MEASURED match · seq ${obj.seq} · ${obj.signer ?? "signer unnamed"}`, expected };
  }
  return {
    ok: false,
    note: `BREAK. computed ${expected.slice(0, 16)}… ≠ ${obj.digest.slice(0, 16)}…`,
    expected,
  };
}

export function loadChain(): SealedReceipt[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(RECEIPT_STORE);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SealedReceipt[];
    return Array.isArray(parsed) ? parsed.slice(0, 64) : [];
  } catch {
    return [];
  }
}

export function saveChain(rows: SealedReceipt[]) {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(RECEIPT_STORE, JSON.stringify(rows.slice(0, 64)));
}

export function previousDigest(rows: SealedReceipt[]): string {
  return rows[0]?.digest ?? GENESIS;
}
