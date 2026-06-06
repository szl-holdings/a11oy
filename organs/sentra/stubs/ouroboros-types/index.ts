import { z } from 'zod';

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
  parentHash?: string;
  doctrineVer: string;
  meta?: Record<string, unknown>;
}

export function parseReceipt(input: {
  hash: string;
  timestamp: string;
  lambda: number;
  axes: Axes;
  payloadRef: string;
  parentHash?: string;
  doctrineVer: string;
  meta?: Record<string, unknown>;
}): Receipt {
  return { ...input };
}

export const ReceiptSchema = z.object({
  hash: z.string(),
  timestamp: z.string(),
  lambda: z.number(),
  axes: z.object({
    moralGrounding: z.number(),
    measurabilityHonesty: z.number(),
    epistemicHumility: z.number(),
    harmAvoidance: z.number(),
    logicalCoherence: z.number(),
    citationIntegrity: z.number(),
    noveltyContribution: z.number(),
    reproducibility: z.number(),
    stakeholderAlignment: z.number(),
  }),
  payloadRef: z.string(),
  parentHash: z.string().optional(),
  doctrineVer: z.string(),
  meta: z.record(z.unknown()).optional(),
});
