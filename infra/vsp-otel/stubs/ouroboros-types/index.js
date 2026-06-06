export function parseReceipt(raw) {
  if (!raw || typeof raw !== 'object') throw new Error('Invalid receipt');
  return raw;
}
