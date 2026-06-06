const store = new Map();

const AXIS_WEIGHTS = {
  moralGrounding: 0.15,
  measurabilityHonesty: 0.12,
  epistemicHumility: 0.10,
  harmAvoidance: 0.13,
  logicalCoherence: 0.12,
  citationIntegrity: 0.10,
  noveltyContribution: 0.08,
  reproducibility: 0.10,
  stakeholderAlignment: 0.10,
};

const GATE_THRESHOLD = 0.85;

export function evaluateAxes(axes) {
  let lambda = 0;
  for (const [key, weight] of Object.entries(AXIS_WEIGHTS)) {
    lambda += (axes[key] ?? 0.9) * weight;
  }
  return { lambda, pass: lambda >= GATE_THRESHOLD, axes };
}

export function gateTransit(input) {
  const { hash, lambda, axes } = input;
  if (lambda < GATE_THRESHOLD) {
    throw new Error(`Gate rejection: lambda=${lambda} < threshold=${GATE_THRESHOLD}`);
  }
  store.set(hash, input);
}

export function getReceipt(hash) {
  return store.get(hash) ?? null;
}

export function verifyReceipt(receipt) {
  return receipt && typeof receipt.hash === 'string' && receipt.lambda >= GATE_THRESHOLD;
}
