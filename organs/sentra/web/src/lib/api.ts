import { apiFetch } from '@szl-holdings/shared-ui/api-fetch';

export const api = {
  scenarios: {
    list: () => apiFetch<any[]>('/aegis/scenarios'),
    get: (id: number) => apiFetch<any>(`/aegis/scenarios/${id}`),
    create: (data: any) =>
      apiFetch<any>('/aegis/scenarios', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: any) =>
      apiFetch<any>(`/aegis/scenarios/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number) => apiFetch<void>(`/aegis/scenarios/${id}`, { method: 'DELETE' }),
  },
  assessments: {
    list: () => apiFetch<any[]>('/aegis/assessments'),
    get: (id: number) => apiFetch<any>(`/aegis/assessments/${id}`),
    create: (data: any) =>
      apiFetch<any>('/aegis/assessments', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: any) =>
      apiFetch<any>(`/aegis/assessments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number) => apiFetch<void>(`/aegis/assessments/${id}`, { method: 'DELETE' }),
  },
  simulations: {
    list: () => apiFetch<any[]>('/aegis/simulations'),
    get: (id: number) => apiFetch<any>(`/aegis/simulations/${id}`),
    create: (data: any) =>
      apiFetch<any>('/aegis/simulations', { method: 'POST', body: JSON.stringify(data) }),
  },
  findings: {
    list: (assessmentId?: number) =>
      apiFetch<any[]>(`/aegis/findings${assessmentId ? `?assessmentId=${assessmentId}` : ''}`),
    get: (id: number) => apiFetch<any>(`/aegis/findings/${id}`),
    create: (data: any) =>
      apiFetch<any>('/aegis/findings', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: any) =>
      apiFetch<any>(`/aegis/findings/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  },
  riskScores: {
    list: (assessmentId?: number) =>
      apiFetch<any[]>(`/aegis/risk-scores${assessmentId ? `?assessmentId=${assessmentId}` : ''}`),
    create: (data: any) =>
      apiFetch<any>('/aegis/risk-scores', { method: 'POST', body: JSON.stringify(data) }),
  },
  reports: {
    get: (assessmentId: number) => apiFetch<any>(`/aegis/reports/${assessmentId}`),
  },
  incidents: {
    list: () => apiFetch<any[]>('/aegis/incidents'),
    get: (id: number) => apiFetch<any>(`/aegis/incidents/${id}`),
    create: (data: any) =>
      apiFetch<any>('/aegis/incidents', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: any) =>
      apiFetch<any>(`/aegis/incidents/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number) => apiFetch<void>(`/aegis/incidents/${id}`, { method: 'DELETE' }),
  },
  compliance: {
    list: (framework?: string) =>
      apiFetch<any[]>(`/aegis/compliance${framework ? `?framework=${framework}` : ''}`),
  },
  alerts: {
    list: (status?: string) => apiFetch<any[]>(`/aegis/alerts${status ? `?status=${status}` : ''}`),
    create: (data: any) =>
      apiFetch<any>('/aegis/alerts', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: any) =>
      apiFetch<any>(`/aegis/alerts/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  },
  socDashboard: {
    get: () => apiFetch<any>('/aegis/soc-dashboard'),
  },
  cves: {
    list: (keyword?: string) =>
      apiFetch<any[]>(`/aegis/cves${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''}`),
  },
  assets: {
    list: (params?: { type?: string; owner?: string; exposureLevel?: string }) => {
      const q = new URLSearchParams();
      if (params?.type) q.set('type', params.type);
      if (params?.owner) q.set('owner', params.owner);
      if (params?.exposureLevel) q.set('exposureLevel', params.exposureLevel);
      return apiFetch<any[]>(`/aegis/assets${q.toString() ? `?${q}` : ''}`);
    },
    get: (id: number) => apiFetch<any>(`/aegis/assets/${id}`),
    create: (data: any) =>
      apiFetch<any>('/aegis/assets', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: any) =>
      apiFetch<any>(`/aegis/assets/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  },
  vulnerabilities: {
    list: (params?: { severity?: string; status?: string; asset?: string }) => {
      const q = new URLSearchParams();
      if (params?.severity) q.set('severity', params.severity);
      if (params?.status) q.set('status', params.status);
      if (params?.asset) q.set('asset', params.asset);
      return apiFetch<any[]>(`/aegis/vulnerabilities${q.toString() ? `?${q}` : ''}`);
    },
    get: (id: number) => apiFetch<any>(`/aegis/vulnerabilities/${id}`),
    update: (id: number, data: any) =>
      apiFetch<any>(`/aegis/vulnerabilities/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  },
  workflowActions: {
    list: (entityType?: string, entityId?: number) => {
      const q = new URLSearchParams();
      if (entityType) q.set('entityType', entityType);
      if (entityId) q.set('entityId', String(entityId));
      return apiFetch<any[]>(`/aegis/workflow-actions${q.toString() ? `?${q}` : ''}`);
    },
    create: (data: any) =>
      apiFetch<any>('/aegis/workflow-actions', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: any) =>
      apiFetch<any>(`/aegis/workflow-actions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
  },
  cases: {
    list: (params?: { status?: string; priority?: string }) => {
      const q = new URLSearchParams();
      if (params?.status) q.set('status', params.status);
      if (params?.priority) q.set('priority', params.priority);
      return apiFetch<any[]>(`/aegis/cases${q.toString() ? `?${q}` : ''}`);
    },
    get: (id: number) => apiFetch<any>(`/aegis/cases/${id}`),
    create: (data: any) =>
      apiFetch<any>('/aegis/cases', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: any) =>
      apiFetch<any>(`/aegis/cases/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  },
  mitreDetections: {
    list: () => apiFetch<any[]>('/aegis/mitre-detections'),
    get: (techniqueId: string) => apiFetch<any>(`/aegis/mitre-detections/${techniqueId}`),
  },
  live: {
    nvdCves: (severity?: string, keyword?: string, limit?: number) => {
      const params = new URLSearchParams();
      if (severity) params.set('severity', severity);
      if (keyword) params.set('keyword', keyword);
      if (limit) params.set('limit', String(limit));
      return apiFetch<any>(`/aegis/live/nvd-cves${params.toString() ? `?${params}` : ''}`);
    },
    cisaKev: (ransomwareOnly?: boolean, limit?: number) => {
      const params = new URLSearchParams();
      if (ransomwareOnly) params.set('ransomware', 'true');
      if (limit) params.set('limit', String(limit));
      return apiFetch<any>(`/aegis/live/cisa-kev${params.toString() ? `?${params}` : ''}`);
    },
    mitreAttack: (tactic?: string) =>
      apiFetch<any>(
        `/aegis/live/mitre-attack${tactic ? `?tactic=${encodeURIComponent(tactic)}` : ''}`,
      ),
    threatNews: () => apiFetch<any>('/aegis/live/threat-news'),
    threatIndicators: (type?: string) =>
      apiFetch<any>(`/aegis/live/threat-indicators${type ? `?type=${type}` : ''}`),
    certAdvisories: (certId?: string) =>
      apiFetch<any>(`/aegis/live/cert-advisories${certId ? `?cert=${certId}` : ''}`),
    feedStatus: () => apiFetch<any>('/aegis/live/feed-status'),
    gpuMetrics: () => apiFetch<any>('/integrations/nvidia-dcgm/gpus'),
    gpuCluster: () => apiFetch<any>('/integrations/nvidia-dcgm/cluster'),
    taxiiCollections: () => apiFetch<any>('/integrations/misp-taxii/collections'),
    taxiiIndicators: (collectionId?: string, limit?: number) => {
      const params = new URLSearchParams();
      if (collectionId) params.set('collectionId', collectionId);
      if (limit) params.set('limit', String(limit));
      return apiFetch<any>(
        `/integrations/misp-taxii/indicators${params.toString() ? `?${params}` : ''}`,
      );
    },
  },
  hardeningControls: {
    list: (params?: { category?: string; status?: string }) => {
      const q = new URLSearchParams();
      if (params?.category) q.set('category', params.category);
      if (params?.status) q.set('status', params.status);
      return apiFetch<any[]>(`/aegis/hardening-controls${q.toString() ? `?${q}` : ''}`);
    },
    get: (id: number) => apiFetch<any>(`/aegis/hardening-controls/${id}`),
    update: (id: number, data: any) =>
      apiFetch<any>(`/aegis/hardening-controls/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    summary: () => apiFetch<any>('/aegis/hardening-summary'),
  },
  reportsList: {
    list: () => apiFetch<any[]>('/aegis/reports'),
  },
  ingest: {
    webhook: (payload: any) =>
      apiFetch<any>('/aegis/ingest/webhook', { method: 'POST', body: JSON.stringify(payload) }),
    syslog: (payload: any) =>
      apiFetch<any>('/aegis/ingest/syslog', { method: 'POST', body: JSON.stringify(payload) }),
  },
  soar: {
    playbooks: () => apiFetch<any>('/aegis/soar/playbooks'),
    execute: (playbookId: string, alertId?: string, context?: any) =>
      apiFetch<any>('/aegis/soar/execute', {
        method: 'POST',
        body: JSON.stringify({ playbookId, alertId, context }),
      }),
  },
  stix: {
    objects: (type?: string) => apiFetch<any>(`/aegis/stix/objects${type ? `?type=${type}` : ''}`),
    export: (objectIds: string[], bundleName?: string) =>
      apiFetch<any>('/aegis/stix/export', {
        method: 'POST',
        body: JSON.stringify({ objectIds, bundleName }),
      }),
  },
  taxii: {
    feeds: () => apiFetch<any>('/aegis/taxii/feeds'),
  },
  mitre: {
    coverage: () => apiFetch<any>('/aegis/mitre/coverage'),
  },
  liveData: {
    threatSummary: () => apiFetch<any>('/aegis/live/threat-summary'),
    complianceSummary: () => apiFetch<any>('/aegis/live/compliance-summary'),
    assetRisk: () => apiFetch<any>('/aegis/live/asset-risk'),
    /**
     * Single-call CISO Executive Dashboard headline KPIs. Returns
     * { aggregateRisk, activeThreats, openCriticals, meanTimeToRespondMin,
     *   compliancePct, generatedAt } with each metric independently
     *   nullable when its underlying source is unavailable.
     */
    cisoKpis: () => apiFetch<any>('/aegis/ciso-kpis'),
  },
  tradecraft: {
    decisions: (params?: string) =>
      apiFetch<any[]>(`/aegis/tradecraft/decisions${params ? `?${params}` : ''}`),
    getDecision: (objectId: string) => apiFetch<any>(`/aegis/tradecraft/decisions/${objectId}`),
    createDecision: (data: unknown) =>
      apiFetch<any>('/aegis/tradecraft/decisions', { method: 'POST', body: JSON.stringify(data) }),
    updateDecision: (objectId: string, data: unknown) =>
      apiFetch<any>(`/aegis/tradecraft/decisions/${objectId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    notebook: (params?: string) =>
      apiFetch<any[]>(`/aegis/tradecraft/notebook${params ? `?${params}` : ''}`),
    createNote: (data: unknown) =>
      apiFetch<any>('/aegis/tradecraft/notebook', { method: 'POST', body: JSON.stringify(data) }),
    updateNote: (noteId: string, data: unknown) =>
      apiFetch<any>(`/aegis/tradecraft/notebook/${noteId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    deleteNote: (noteId: string) =>
      apiFetch<void>(`/aegis/tradecraft/notebook/${noteId}`, { method: 'DELETE' }),
    caseMemory: (caseId: string) => apiFetch<any>(`/aegis/tradecraft/case-memory/${caseId}`),
    createCaseMemory: (data: unknown) =>
      apiFetch<any>('/aegis/tradecraft/case-memory', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    updateCaseMemory: (caseId: string, data: unknown) =>
      apiFetch<any>(`/aegis/tradecraft/case-memory/${caseId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    evidenceIndex: (params?: string) =>
      apiFetch<any>(`/aegis/tradecraft/evidence-index${params ? `?${params}` : ''}`),
    evidenceQuery: (data: {
      query: string;
      caseId?: string;
      incidentId?: string;
      sourceTypes?: string[];
      maxResults?: number;
      minRelevance?: number;
    }) =>
      apiFetch<any>('/aegis/tradecraft/evidence-index/query', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },
  otIcs: {
    assets: () => apiFetch<any[]>('/aegis/ot-ics/assets'),
    frames: (params?: {
      protocol?: string;
      assetId?: string;
      severity?: string;
      limit?: number;
    }) => {
      const q = new URLSearchParams();
      if (params?.protocol) q.set('protocol', params.protocol);
      if (params?.assetId) q.set('assetId', params.assetId);
      if (params?.severity) q.set('severity', params.severity);
      if (params?.limit) q.set('limit', String(params.limit));
      return apiFetch<any[]>(`/aegis/ot-ics/frames${q.toString() ? `?${q}` : ''}`);
    },
    conversations: (sessionId?: string) =>
      apiFetch<any[]>(
        `/aegis/ot-ics/conversations${sessionId ? `?sessionId=${encodeURIComponent(sessionId)}` : ''}`,
      ),
    anomalyScores: (params?: { assetId?: string; hours?: number }) => {
      const q = new URLSearchParams();
      if (params?.assetId) q.set('assetId', params.assetId);
      if (params?.hours) q.set('hours', String(params.hours));
      return apiFetch<any[]>(`/aegis/ot-ics/anomaly-scores${q.toString() ? `?${q}` : ''}`);
    },
    recomputeBaselines: () =>
      apiFetch<{
        updatedAssets: number;
        baselines: Array<{ assetId: string; baseline: number; sampleCount: number }>;
      }>('/aegis/ot-ics/baseline/recompute', { method: 'POST' }),
    acknowledgeFrame: (frameId: string, body?: { acknowledgedBy?: string }) =>
      apiFetch<{ frameId: string; triageStatus: string }>(
        `/aegis/ot-ics/frames/${encodeURIComponent(frameId)}/acknowledge`,
        { method: 'POST', body: JSON.stringify(body ?? {}) },
      ),
    markFalsePositive: (frameId: string, body?: { acknowledgedBy?: string }) =>
      apiFetch<{ frameId: string; triageStatus: string }>(
        `/aegis/ot-ics/frames/${encodeURIComponent(frameId)}/false-positive`,
        { method: 'POST', body: JSON.stringify(body ?? {}) },
      ),
    feedStatus: () =>
      apiFetch<{
        running: boolean;
        stats: {
          tickCount: number;
          framesInserted: number;
          conversationRowsInserted: number;
          scoreUpdates: number;
          lastTickAt: string | null;
          startedAt: string;
        };
      }>('/aegis/ot-ics/feed/status'),
    openIncident: (frameId: string, body?: { acknowledgedBy?: string; incidentRef?: string }) =>
      apiFetch<{ frameId: string; triageStatus: string; incidentRef?: string }>(
        `/aegis/ot-ics/frames/${encodeURIComponent(frameId)}/open-incident`,
        { method: 'POST', body: JSON.stringify(body ?? {}) },
      ),
  },
  digitalTwin: {
    topology: () => apiFetch<any>('/aegis/digital-twin/topology'),
    sync: () => apiFetch<any>('/aegis/digital-twin/sync', { method: 'POST' }),
    scenarios: () => apiFetch<any>('/aegis/digital-twin/scenarios'),
    runScenario: (id: string) =>
      apiFetch<any>(`/aegis/digital-twin/scenarios/${id}/run`, { method: 'POST' }),
    pauseScenario: (id: string) =>
      apiFetch<any>(`/aegis/digital-twin/scenarios/${id}/pause`, { method: 'POST' }),
    resumeScenario: (id: string) =>
      apiFetch<any>(`/aegis/digital-twin/scenarios/${id}/resume`, { method: 'POST' }),
  },
  deception: {
    honeypots: () => apiFetch<any>('/aegis/deception/honeypots'),
    deployHoneypot: (data?: any) =>
      apiFetch<any>('/aegis/deception/honeypots', {
        method: 'POST',
        body: JSON.stringify(data ?? {}),
      }),
    events: () => apiFetch<any>('/aegis/deception/events'),
    pushIoc: (eventId: string) =>
      apiFetch<any>(`/aegis/deception/events/${eventId}/push-ioc`, {
        method: 'POST',
        body: JSON.stringify({}),
      }),
  },
  actionQueue: {
    list: (params?: { status?: string; priority?: string; type?: string }) => {
      const q = new URLSearchParams();
      if (params?.status) q.set('status', params.status);
      if (params?.priority) q.set('priority', params.priority);
      if (params?.type) q.set('type', params.type);
      return apiFetch<any>(`/aegis/action-queue${q.toString() ? `?${q}` : ''}`);
    },
    complete: (id: string, note?: string) =>
      apiFetch<any>(`/aegis/action-queue/${id}/complete`, {
        method: 'POST',
        body: JSON.stringify({ note }),
      }),
    escalate: (id: string, note?: string) =>
      apiFetch<any>(`/aegis/action-queue/${id}/escalate`, {
        method: 'POST',
        body: JSON.stringify({ note }),
      }),
    create: (data: any) =>
      apiFetch<any>('/aegis/action-queue', { method: 'POST', body: JSON.stringify(data) }),
  },
  soarBuilder: {
    playbooks: () => apiFetch<any>('/aegis/soar-builder/playbooks'),
    getPlaybook: (id: string) => apiFetch<any>(`/aegis/soar-builder/playbooks/${id}`),
    createPlaybook: (data: any) =>
      apiFetch<any>('/aegis/soar-builder/playbooks', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    updatePlaybook: (id: string, data: any) =>
      apiFetch<any>(`/aegis/soar-builder/playbooks/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    deletePlaybook: (id: string) =>
      apiFetch<void>(`/aegis/soar-builder/playbooks/${id}`, { method: 'DELETE' }),
    runs: (playbookId?: string) =>
      apiFetch<any>(`/aegis/soar-builder/runs${playbookId ? `?playbookId=${playbookId}` : ''}`),
    execute: (playbookId: string, incidentId?: string, triggeredBy?: string) =>
      apiFetch<any>('/aegis/soar-builder/execute', {
        method: 'POST',
        body: JSON.stringify({ playbookId, incidentId, triggeredBy }),
      }),
  },
  command: {
    posture: () => apiFetch<any>('/aegis/command/posture'),
    investigations: () => apiFetch<any>('/aegis/command/investigations'),
    addNote: (note: string, caseId?: number) =>
      apiFetch<any>('/aegis/command/investigations', {
        method: 'POST',
        body: JSON.stringify({ type: 'note', content: note, caseId }),
      }),
    decisions: () => apiFetch<any>('/aegis/command/decisions'),
    approveDecision: (id: string, note: string, stepUpToken: string) =>
      apiFetch<any>(`/aegis/command/decisions/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ approvalNote: note }),
        headers: { 'X-Step-Up-Token': stepUpToken },
      }),
    playbooks: () => apiFetch<any>('/firestorm/command/response/playbooks'),
    executePlaybook: (actionType: string, targetId: string, stepUpToken: string, notes?: string) =>
      apiFetch<any>('/aegis/command/response/execute', {
        method: 'POST',
        body: JSON.stringify({ actionType, targetId, notes }),
        headers: { 'X-Step-Up-Token': stepUpToken },
      }),
    contain: (
      containmentType: string,
      assetId: string,
      justification: string,
      stepUpToken: string,
    ) =>
      apiFetch<any>('/aegis/command/response/contain', {
        method: 'POST',
        body: JSON.stringify({ containmentType, assetId, justification }),
        headers: { 'X-Step-Up-Token': stepUpToken },
      }),
    executivePosture: () => apiFetch<any>('/aegis/command/executive/posture'),
    executiveCompliance: () => apiFetch<any>('/aegis/command/executive/compliance'),
  },
  adaptiveDefense: {
    decisions: (limit = 50) =>
      apiFetch<{ decisions: any[]; stats: any }>(`/aegis/adaptive-defense/decisions?limit=${limit}`),
    recordDecision: (data: {
      agentName: string;
      domain: string;
      action: string;
      actionType: string;
      decision: string;
      policyRule: string;
      riskScore?: number;
      details?: string;
    }) =>
      apiFetch<any>('/aegis/adaptive-defense/decisions', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },
  threatEngine: {
    incidents: (params?: { status?: string; severity?: string; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.status) q.set('status', params.status);
      if (params?.severity) q.set('severity', params.severity);
      if (params?.limit) q.set('limit', String(params.limit));
      return apiFetch<{ incidents: any[] }>(`/aegis/threat-engine/incidents${q.toString() ? `?${q}` : ''}`);
    },
    updateStatus: (id: string, status: string) =>
      apiFetch<any>(`/aegis/threat-engine/incidents/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      }),
  },
  predictiveIntel: {
    threats: (limit = 20) =>
      apiFetch<{ predictions: any[] }>(`/aegis/predictive/threats?limit=${limit}`),
  },
  narrativeEngine: {
    narratives: (limit = 20) =>
      apiFetch<{ narratives: any[] }>(`/aegis/narrative-engine/narratives?limit=${limit}`),
    getById: (id: string) =>
      apiFetch<{ narrative: any }>(`/aegis/narrative-engine/narratives/${id}`),
  },
  cortex: {
    predictions: () =>
      apiFetch<any>('/internal/sentra/cortex/predictions'),
    swarmStatus: () =>
      apiFetch<any>('/internal/sentra/cortex/swarm-status'),
    layeredIntercept: () =>
      apiFetch<any>('/internal/sentra/layered-intercept'),
    cyberLobe: () =>
      apiFetch<any>('/internal/a11oy/cyber-lobe'),
    approveCountermove: (pathId: string, action: 'approve' | 'deny' | 'stage') =>
      apiFetch<any>(`/internal/sentra/cortex/countermoves/${pathId}/${action}`, { method: 'POST' }),
    proofLog: () => apiFetch<any>('/internal/sentra/cortex/proof-log'),
  },
  redTeam: {
    launch: (scenarioId: string, scenarioName?: string) =>
      apiFetch<any>('/internal/sentra/red-team/launch', {
        method: 'POST',
        body: JSON.stringify({ scenario_id: scenarioId, scenario_name: scenarioName }),
      }),
  },
};
