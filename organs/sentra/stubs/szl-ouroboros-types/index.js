export function parseReceipt(raw) {
  if (!raw.hash || typeof raw.hash !== 'string' || !/^[0-9a-f]{64}$/.test(raw.hash)) {
    throw new Error(`Invalid receipt hash: ${raw.hash}`);
  }
  return {
    hash: raw.hash,
    timestamp: raw.timestamp,
    lambda: raw.lambda,
    axes: raw.axes,
    payloadRef: raw.payloadRef,
    parentHash: raw.parentHash ?? undefined,
    doctrineVer: raw.doctrineVer,
    meta: raw.meta ?? undefined,
  };
}
