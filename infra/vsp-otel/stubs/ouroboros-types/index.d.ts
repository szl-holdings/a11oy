export interface Axes {
  moralGrounding: number;
  measurabilityHonesty: number;
  epistemicHumility: number;
  harmAvoidance: number;
  logicalCoherence: number;
  citationIntegrity: number;
  noveltyContribution: number;
  reproducibility: number;
  stakeholderAlignment: number;
}

export interface Receipt {
  hash: string;
  timestamp: string;
  lambda: number;
  axes: Axes;
  payloadRef: string;
  doctrineVer: string;
  meta?: Record<string, unknown>;
}

export declare function parseReceipt(raw: unknown): Receipt;
