import { apiFetch } from '@szl-holdings/shared-ui/api-fetch';

export interface MaturityGate {
  payloadId: string;
  payloadName: string;
  allowed: boolean;
  compositeConfidence: number | null;
  detectionRate: number | null;
  requiredThreshold: number;
  regressionInLastRun: boolean;
  blockers: string[];
}

export const cpsApi = {
  payloads: {
    list: () => apiFetch<any[]>('/cps/payloads'),
    get: (id: string) => apiFetch<any>(`/cps/payloads/${id}`),
    updateMaturity: (id: string, mode: string) =>
      apiFetch<any>(`/cps/payloads/${id}/maturity`, {
        method: 'PATCH',
        body: JSON.stringify({ mode }),
      }),
    maturityGate: (id: string) =>
      apiFetch<MaturityGate>(`/cps/payloads/${id}/maturity-gate`),
    maturityGates: () =>
      apiFetch<{ gates: Record<string, MaturityGate> }>('/cps/maturity-gates'),
  },
  runs: {
    list: (params?: { payloadId?: string; status?: string }) => {
      const q = new URLSearchParams();
      if (params?.payloadId) q.set('payloadId', params.payloadId);
      if (params?.status) q.set('status', params.status);
      return apiFetch<any[]>(`/cps/runs${q.toString() ? `?${q}` : ''}`);
    },
    get: (id: string) => apiFetch<any>(`/cps/runs/${id}`),
    execute: (payloadId: string, maturityMode?: string) =>
      apiFetch<any>('/cps/runs', {
        method: 'POST',
        body: JSON.stringify({ payloadId, maturityMode }),
      }),
    rollback: (id: string) =>
      apiFetch<any>(`/cps/runs/${id}/rollback`, { method: 'POST', body: '{}' }),
    proofBundle: (id: string) => apiFetch<any>(`/cps/runs/${id}/proof-bundle`),
  },
  approvals: {
    list: (params?: { status?: string; runId?: string }) => {
      const q = new URLSearchParams();
      if (params?.status) q.set('status', params.status);
      if (params?.runId) q.set('runId', params.runId);
      return apiFetch<any[]>(`/cps/approvals${q.toString() ? `?${q}` : ''}`);
    },
    respond: (id: string, approved: boolean, reason?: string) =>
      apiFetch<any>(`/cps/approvals/${id}`, {
        method: 'POST',
        body: JSON.stringify({ approved, reason }),
      }),
  },
  executive: {
    status: () => apiFetch<any>('/cps/executive/status'),
  },
};
