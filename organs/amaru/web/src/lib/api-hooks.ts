import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from './api';

export const useStats = () => useQuery({ queryKey: ['stats'], queryFn: api.getStats });

export const useAdminUsage = (params?: { plan?: string; org?: string; limit?: number; offset?: number }) =>
  useQuery({
    queryKey: ['admin-usage', params],
    queryFn: () => api.getAdminUsage(params),
  });

export const useOrgQuotaViolations = (
  orgId: number | null,
  params?: { limit?: number; offset?: number; type?: 'soft' | 'hard'; feature?: string },
) =>
  useQuery({
    queryKey: ['admin-org-quota-violations', orgId, params],
    queryFn: () => api.getOrgQuotaViolations(orgId as number, params),
    enabled: orgId != null,
  });

export const useConnections = () => useQuery({ queryKey: ['connections'], queryFn: api.listConnections });
export const useConnection = (id: string) => useQuery({ queryKey: ['connections', id], queryFn: () => api.getConnection(id), enabled: !!id });
export const useCreateConnection = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createConnection,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['connections'] }),
  });
};
export const useUpdateConnection = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; credentials?: Record<string, string> }) => api.updateConnection(id, body),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['connections'] });
      queryClient.invalidateQueries({ queryKey: ['connections', id] });
    },
  });
};
export const useDeleteConnection = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteConnection,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['connections'] }),
  });
};
export const useTestConnection = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.testConnection,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['connections'] }),
  });
};
export const useValidateCredentials = () => useMutation({ mutationFn: api.validateCredentials });

export const useSyncs = () => useQuery({ queryKey: ['syncs'], queryFn: api.listSyncs });
export const useSync = (id: string) => useQuery({ queryKey: ['syncs', id], queryFn: () => api.getSync(id), enabled: !!id });
export const useCreateSync = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createSync,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['syncs'] }),
  });
};
export const useUpdateSync = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Partial<Omit<api.Sync, 'id' | 'tenantId' | 'createdAt' | 'updatedAt'>>) => api.updateSync(id, body),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['syncs'] });
      queryClient.invalidateQueries({ queryKey: ['syncs', id] });
    },
  });
};
export const useDeleteSync = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteSync,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['syncs'] }),
  });
};
export const useRunSync = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.runSync,
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['syncs'] });
      queryClient.invalidateQueries({ queryKey: ['syncs', id] });
      queryClient.invalidateQueries({ queryKey: ['runs'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
};

export const useSyncMappings = (syncId: string) => useQuery({ queryKey: ['syncs', syncId, 'mappings'], queryFn: () => api.getSyncMappings(syncId), enabled: !!syncId });
export const usePutSyncMappings = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ syncId, mappings }: { syncId: string; mappings: Array<Omit<api.SyncMapping, 'id' | 'syncId'>> }) => api.putSyncMappings(syncId, mappings),
    onSuccess: (_, { syncId }) => queryClient.invalidateQueries({ queryKey: ['syncs', syncId, 'mappings'] }),
  });
};

export const useSyncRuns = (params?: { syncId?: string; status?: api.RunStatus; limit?: number; offset?: number }) => useQuery({
  queryKey: ['runs', params],
  queryFn: () => api.listSyncRuns(params),
});
export const useSyncRun = (id: string) => useQuery({ queryKey: ['runs', id], queryFn: () => api.getSyncRun(id), enabled: !!id });
export const useSyncRunRows = (runId: string, params?: { limit?: number; offset?: number }) => useQuery({
  queryKey: ['runs', runId, 'rows', params],
  queryFn: () => api.listSyncRunRows(runId, params),
  enabled: !!runId,
});
export const useRetrySyncRunRow = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, rowId }: { runId: string; rowId: string }) => api.retrySyncRunRow(runId, rowId),
    onSuccess: (_, { runId }) => {
      queryClient.invalidateQueries({ queryKey: ['runs', runId] });
      queryClient.invalidateQueries({ queryKey: ['runs', runId, 'rows'] });
    },
  });
};

export const useTemplates = () => useQuery({ queryKey: ['templates'], queryFn: api.listTemplates });
export const useApplyTemplate = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, connectionId, name }: { id: string; connectionId: string; name?: string }) => api.applyTemplate(id, { connectionId, name }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['syncs'] }),
  });
};

export const useDestinationObjects = (destination: string) => useQuery({
  queryKey: ['destinations', destination, 'objects'],
  queryFn: () => api.listDestinationObjects(destination),
  enabled: !!destination,
});
export const useDestinationFields = (destination: string, objectType: string) => useQuery({
  queryKey: ['destinations', destination, 'objects', objectType, 'fields'],
  queryFn: () => api.listDestinationFields(destination, objectType),
  enabled: !!destination && !!objectType,
});

export const usePreviewSource = () => useMutation({ mutationFn: api.previewSource });
