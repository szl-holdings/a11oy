import type { Axes, Receipt } from '@szl/ouroboros-types';

export interface EvalResult {
  lambda: number;
  pass: boolean;
  axes: Axes;
}

export interface GateTransitInput {
  hash: string;
  timestamp: string;
  lambda: number;
  axes: Axes;
  payloadRef: string;
  doctrineVer: string;
  meta?: Record<string, unknown>;
}

export declare function evaluateAxes(axes: Axes): EvalResult;
export declare function gateTransit(input: GateTransitInput): void;
export declare function getReceipt(hash: string): Receipt | null;
export declare function verifyReceipt(receipt: Receipt): boolean;
