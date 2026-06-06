export async function registerWithA11oy(_opts: {
  product: string;
  displayName: string;
  basePath: string;
  accentColor: string;
  capabilities: Array<{ id: string; label: string; governanceClass: string }>;
}): Promise<void> {}

export async function emitProof(_opts: {
  product: string;
  kind: string;
  summary: string;
  deepLink: string;
  payload: Record<string, unknown>;
}): Promise<void> {}

export async function crossProductHandoff(_opts: {
  fromProduct: string;
  toProduct: string;
  refId: string;
  reason: string;
  deepLink: string;
}): Promise<void> {}

export interface FabricProofEntry {
  id: string;
  product: string;
  kind: string;
  summary: string;
  deepLink: string;
  payload: Record<string, unknown>;
  ts: string;
}

export async function listFabricProofs(): Promise<FabricProofEntry[]> {
  return [];
}
