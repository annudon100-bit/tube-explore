import { apiRequest, jsonBody, qs } from './client';
import type {
  RadarrInstanceResponse,
  RadarrInstanceUpsertRequest,
  RadarrInstanceTestRequest,
  RadarrInstanceTestResponse,
  RadarrSummaryResponse,
  RadarrMissingMovieListResponse,
  RadarrMovieDownloadRequest,
  RadarrTaskIntegrationResponse,
  RadarrRootFolder,
  RadarrQualityProfile,
  RadarrQueueItem,
  PageArgs,
} from './types';

export function listRadarrInstances(params?: PageArgs): Promise<RadarrInstanceResponse[]> {
  return apiRequest(`/api/radarr/instances${params ? qs(params as any) : ''}`);
}

export function getRadarrInstance(instanceId: string): Promise<RadarrInstanceResponse> {
  return apiRequest(`/api/radarr/instances/${encodeURIComponent(instanceId)}`);
}

export function createRadarrInstance(body: RadarrInstanceUpsertRequest): Promise<RadarrInstanceResponse> {
  return apiRequest(`/api/radarr/instances`, { method: 'POST', ...jsonBody(body) });
}

export function updateRadarrInstance(instanceId: string, body: Partial<RadarrInstanceUpsertRequest>): Promise<RadarrInstanceResponse> {
  return apiRequest(`/api/radarr/instances/${encodeURIComponent(instanceId)}`, { method: 'PATCH', ...jsonBody(body) });
}

export function deleteRadarrInstance(instanceId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/radarr/instances/${encodeURIComponent(instanceId)}`, { method: 'DELETE' });
}

export function testRadarrInstance(instanceId: string, body?: RadarrInstanceTestRequest): Promise<RadarrInstanceTestResponse> {
  return apiRequest(`/api/radarr/instances/${encodeURIComponent(instanceId)}/test`, { method: 'POST', ...jsonBody(body || {}) });
}

export function syncRadarrInstance(instanceId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/radarr/instances/${encodeURIComponent(instanceId)}/sync`, { method: 'POST' });
}

export function setDefaultRadarrInstance(instanceId: string): Promise<RadarrInstanceResponse> {
  return apiRequest(`/api/radarr/instances/${encodeURIComponent(instanceId)}/set-default`, { method: 'POST' });
}

export function getRadarrSummary(): Promise<RadarrSummaryResponse> {
  return apiRequest(`/api/radarr/summary`);
}

export function listMissingMovies(instanceId?: string, params?: PageArgs & { search?: string; monitored?: string }): Promise<RadarrMissingMovieListResponse> {
  let path = instanceId ? `/api/radarr/instances/${encodeURIComponent(instanceId)}/missing` : `/api/radarr/instances/missing`;
  const q = qs({ ...(params as any) });
  if (q) path += q;
  return apiRequest(path);
}

export function downloadForRadarrMovie(body: RadarrMovieDownloadRequest): Promise<{ taskId: string; status: string; statusUrl: string }> {
  return apiRequest(`/api/radarr/download`, { method: 'POST', ...jsonBody(body) });
}

export function getRadarrRootFolders(instanceId: string): Promise<RadarrRootFolder[]> {
  return apiRequest(`/api/radarr/instances/${encodeURIComponent(instanceId)}/root-folders`);
}

export function getRadarrQualityProfiles(instanceId: string): Promise<RadarrQualityProfile[]> {
  return apiRequest(`/api/radarr/instances/${encodeURIComponent(instanceId)}/quality-profiles`);
}

export function getRadarrQueue(instanceId: string): Promise<RadarrQueueItem[]> {
  return apiRequest(`/api/radarr/instances/${encodeURIComponent(instanceId)}/queue`);
}

export function getRadarrTaskIntegration(taskId: string): Promise<RadarrTaskIntegrationResponse> {
  return apiRequest(`/api/radarr/tasks/${encodeURIComponent(taskId)}`);
}

export function retryRadarrImport(taskId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/radarr/tasks/${encodeURIComponent(taskId)}/retry`, { method: 'POST' });
}

export function cancelRadarrImport(taskId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/radarr/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' });
}
