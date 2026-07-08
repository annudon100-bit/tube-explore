import { apiRequest, jsonBody, qs } from './client';
import type {
  ArrInstanceResponse,
  ArrInstanceUpsertRequest,
  ArrInstanceTestRequest,
  ArrInstanceTestResponse,
  ArrSummaryResponse,
  ArrMissingItemListResponse,
  ArrDownloadRequest,
  ArrTaskIntegrationResponse,
  SonarrSeries,
  SonarrEpisode,
  SonarrRootFolder,
  SonarrQualityProfile,
  SonarrQueueItem,
  PageArgs,
} from './types';

export function listSonarrInstances(params?: PageArgs): Promise<ArrInstanceResponse[]> {
  let path = `/api/arr/instances?kind=sonarr${params ? qs(params as any) : ''}`;
  return apiRequest(path);
}

export function getSonarrInstance(instanceId: string): Promise<ArrInstanceResponse> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}`);
}

export function createSonarrInstance(body: ArrInstanceUpsertRequest): Promise<ArrInstanceResponse> {
  return apiRequest(`/api/arr/instances`, { method: 'POST', ...jsonBody(body) });
}

export function updateSonarrInstance(instanceId: string, body: Partial<ArrInstanceUpsertRequest>): Promise<ArrInstanceResponse> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}`, { method: 'PATCH', ...jsonBody(body) });
}

export function deleteSonarrInstance(instanceId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}`, { method: 'DELETE' });
}

export function testSonarrInstance(instanceId: string, body?: ArrInstanceTestRequest): Promise<ArrInstanceTestResponse> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/test`, { method: 'POST', ...jsonBody(body || {}) });
}

export function syncSonarrInstance(instanceId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/sync`, { method: 'POST' });
}

export function setDefaultSonarrInstance(instanceId: string): Promise<ArrInstanceResponse> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/set-default`, { method: 'POST' });
}

export function getSonarrSummary(): Promise<ArrSummaryResponse> {
  return apiRequest(`/api/arr/summary?kind=sonarr`);
}

export function listMissingEpisodes(instanceId?: string, params?: PageArgs & { search?: string }): Promise<ArrMissingItemListResponse> {
  let path = instanceId ? `/api/arr/instances/${encodeURIComponent(instanceId)}/missing` : `/api/arr/instances/missing`;
  const q = qs({ ...(params as any) });
  if (q) path += q;
  return apiRequest(path);
}

export function downloadForSonarrEpisode(body: ArrDownloadRequest): Promise<{ taskId: string; status: string; statusUrl: string }> {
  return apiRequest(`/api/arr/download`, { method: 'POST', ...jsonBody(body) });
}

export function getSonarrRootFolders(instanceId: string): Promise<SonarrRootFolder[]> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/root-folders`);
}

export function getSonarrQualityProfiles(instanceId: string): Promise<SonarrQualityProfile[]> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/quality-profiles`);
}

export function getSonarrQueue(instanceId: string): Promise<SonarrQueueItem[]> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/queue`);
}

export function listSeries(instanceId: string): Promise<SonarrSeries[]> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/series`);
}

export function lookupSeries(instanceId: string, term: string): Promise<SonarrSeries[]> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/series/lookup?term=${encodeURIComponent(term)}`);
}

export function getSeries(instanceId: string, seriesId: number): Promise<SonarrSeries> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/series/${seriesId}`);
}

export function listEpisodes(instanceId: string, seriesId: number, seasonNumber?: number): Promise<SonarrEpisode[]> {
  let path = `/api/arr/instances/${encodeURIComponent(instanceId)}/series/${seriesId}/episodes`;
  if (seasonNumber !== undefined) path += `?seasonNumber=${seasonNumber}`;
  return apiRequest(path);
}

export function getEpisode(instanceId: string, seriesId: number, episodeId: number): Promise<SonarrEpisode> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/series/${seriesId}/episodes/${episodeId}`);
}

export function getSonarrTaskIntegration(taskId: string): Promise<ArrTaskIntegrationResponse> {
  return apiRequest(`/api/arr/tasks/${encodeURIComponent(taskId)}`);
}

export function retrySonarrImport(taskId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/arr/tasks/${encodeURIComponent(taskId)}/import/retry`, { method: 'POST' });
}

export function cancelSonarrImport(taskId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/arr/tasks/${encodeURIComponent(taskId)}/import/cancel`, { method: 'POST' });
}
