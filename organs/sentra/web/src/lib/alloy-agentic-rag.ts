/**
 * Sentra — Alloy Agentic RAG client.
 *
 * Replaces the ad-hoc threat analysis RAG call with the unified
 * Alloy Agentic RAG platform. One SDK, one API.
 */
import { apiFetch } from '@szl-holdings/shared-ui/api-fetch';
import type { AgenticRagRequest, AgenticRagResponse } from '@szl-holdings/alloy-client';

export interface SentraThreatAnalysisInput {
  query: string;
  domain?: string;
  sessionId?: string;
}

export interface AgenticRagRun {
  response: AgenticRagResponse;
}

/**
 * Run an agentic RAG query for Sentra threat/cyber analysis.
 * Routes through the unified /alloy/agentic-rag/run API endpoint
 * which fans out to Knowledge, Web Research, and Cloud Ops specialists.
 */
export async function runSentraAgenticRag(
  input: SentraThreatAnalysisInput,
): Promise<AgenticRagResponse> {
  const request: AgenticRagRequest = {
    query: input.query,
    context: {
      domain: input.domain ?? 'sentra',
      sessionId: input.sessionId,
    },
    policy: {
      plannerMode: 'cot-decompose',
      maxSpecialists: 3,
      topK: 10,
      enabledMcpClasses: ['local-data', 'search-engine', 'cloud-engine'],
    },
  };

  return apiFetch<AgenticRagResponse>('/alloy/agentic-rag/run', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Retrieve the trace for a completed run (for evidence inspector UI).
 */
export async function getSentraAgenticRagTrace(runId: string): Promise<unknown> {
  return apiFetch<unknown>(`/alloy/agentic-rag/runs/${runId}/trace`);
}
