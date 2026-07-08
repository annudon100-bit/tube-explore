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
  ArrKind,
  SonarrSeries,
  SonarrEpisode,
  SonarrRootFolder,
  SonarrQualityProfile,
  SonarrQueueItem,
  PageArgs,
} from './types';

export function listArrInstances(kind?: ArrKind, params?: PageArgs): Promise<ArrInstanceResponse[]> {
  let path = `/api/arr/instances${params ? qs(params as any) : ''}`;
  if (kind) {
    const sep = path.includes('?') ? '&' : '?';
    path += `${sep}kind=${kind}`;
  }
  return apiRequest(path);
}

export function getArrInstance(instanceId: string): Promise<ArrInstanceResponse> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}`);
}

export function createArrInstance(body: ArrInstanceUpsertRequest): Promise<ArrInstanceResponse> {
  return apiRequest(`/api/arr/instances`, { method: 'POST', ...jsonBody(body) });
}

export function updateArrInstance(instanceId: string, body: Partial<ArrInstanceUpsertRequest>): Promise<ArrInstanceResponse> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}`, { method: 'PATCH', ...jsonBody(body) });
}

export function deleteArrInstance(instanceId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}`, { method: 'DELETE' });
}

export function testArrInstance(instanceId: string, body?: ArrInstanceTestRequest): Promise<ArrInstanceTestResponse> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/test`, { method: 'POST', ...jsonBody(body || {}) });
}

export function syncArrInstance(instanceId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/sync`, { method: 'POST' });
}

export function setDefaultArrInstance(instanceId: string): Promise<ArrInstanceResponse> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/set-default`, { method: 'POST' });
}

export function getArrSummary(): Promise<ArrSummaryResponse> {
  return apiRequest(`/api/arr/summary`);
}

export function listMissingArrItems(instanceId: string, params?: PageArgs & { search?: string }): Promise<ArrMissingItemListResponse> {
  let path = `/api/arr/instances/${encodeURIComponent(instanceId)}/missing`;
  const q = qs({ ...(params as any) });
  if (q) path += q;
  return apiRequest(path);
}

export function downloadForArr(body: ArrDownloadRequest): Promise<{ taskId: string; status: string; statusUrl: string }> {
  return apiRequest(`/api/arr/download`, { method: 'POST', ...jsonBody(body) });
}

export function getArrRootFolders(instanceId: string): Promise<SonarrRootFolder[]> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/root-folders`);
}

export function getArrQualityProfiles(instanceId: string): Promise<SonarrQualityProfile[]> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/quality-profiles`);
}

export function getArrQueue(instanceId: string): Promise<SonarrQueueItem[]> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/queue`);
}

export function getArrTaskIntegration(taskId: string): Promise<ArrTaskIntegrationResponse> {
  return apiRequest(`/api/arr/tasks/${encodeURIComponent(taskId)}`);
}

export function retryArrImport(taskId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/arr/tasks/${encodeURIComponent(taskId)}/import/retry`, { method: 'POST' });
}

export function cancelArrImport(taskId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/arr/tasks/${encodeURIComponent(taskId)}/import/cancel`, { method: 'POST' });
}

// ── Sonarr-specific ──────────────────────────────────────────────

export function listSonarrSeries(instanceId: string): Promise<SonarrSeries[]> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/series`);
}

export function lookupSonarrSeries(instanceId: string, term: string): Promise<SonarrSeries[]> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/series/lookup?term=${encodeURIComponent(term)}`);
}

export function getSonarrSeries(instanceId: string, seriesId: number): Promise<SonarrSeries> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/series/${seriesId}`);
}

export function listSonarrEpisodes(instanceId: string, seriesId: number, seasonNumber?: number): Promise<SonarrEpisode[]> {
  let path = `/api/arr/instances/${encodeURIComponent(instanceId)}/series/${seriesId}/episodes`;
  if (seasonNumber !== undefined) path += `?seasonNumber=${seasonNumber}`;
  return apiRequest(path);
}

export function getSonarrEpisode(instanceId: string, seriesId: number, episodeId: number): Promise<SonarrEpisode> {
  return apiRequest(`/api/arr/instances/${encodeURIComponent(instanceId)}/series/${seriesId}/episodes/${episodeId}`);
}

// ── Sonarr Playlist Mapping ──────────────────────────────────────

export interface PlaylistEntryInfo {
  index: number;
  title: string;
  url: string;
  duration?: number | null;
  thumbnail?: string | null;
}

export interface PlaylistInspectResponse {
  entries: PlaylistEntryInfo[];
  episodes: Record<string, any>[];
  seriesTitle?: string | null;
}

export interface PlaylistMappingItemData {
  playlistIndex: number;
  episodeId?: number | null;
  seasonNumber?: number | null;
  episodeNumber?: number | null;
  episodeTitle?: string;
  videoTitle?: string;
  videoUrl?: string;
  videoDuration?: number | null;
  action?: 'download' | 'skip';
  confidence?: 'high' | 'medium' | 'low' | 'none' | 'manual';
}

export interface PlaylistMappingItemResponse {
  id: string;
  mappingId: string;
  playlistIndex: number;
  videoTitle: string;
  videoUrl: string;
  videoDuration?: number | null;
  episodeId?: number | null;
  seasonNumber?: number | null;
  episodeNumber?: number | null;
  episodeTitle: string;
  action: string;
  confidence: string;
  status: string;
  downloadTaskId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface PlaylistMappingListResponse {
  mappings: PlaylistMappingResponse[];
  total: number;
}

export interface PlaylistMappingResponse {
  id: string;
  name: string;
  arrInstanceId: string;
  seriesId: number;
  seriesTitle: string;
  seasonNumber?: number | null;
  playlistUrl: string;
  status: string;
  autoDownload: boolean;
  qualityProfileId?: number | null;
  rootFolderPath?: string | null;
  items: PlaylistMappingItemResponse[];
  createdAt: string;
  updatedAt: string;
}

export interface AutoMapResult {
  itemId: string;
  playlistIndex: number;
  episodeId?: number | null;
  episodeLabel: string;
  confidence: string;
  warning?: string | null;
}

export interface AutoMapResponse {
  results: AutoMapResult[];
  mappedCount: number;
  totalCount: number;
}

export function inspectSonarrPlaylist(instanceId: string, body: { seriesId: number; seasonNumber?: number; playlistUrl: string }): Promise<PlaylistInspectResponse> {
  return apiRequest(`/api/arr/sonarr/instances/${encodeURIComponent(instanceId)}/playlist/inspect`, { method: 'POST', ...jsonBody(body) });
}

export function createSonarrPlaylistMapping(instanceId: string, body: {
  name: string;
  seriesId: number;
  seasonNumber?: number;
  playlistUrl: string;
  qualityProfileId?: number;
  rootFolderPath?: string;
  autoDownload?: boolean;
  items?: PlaylistMappingItemData[];
}): Promise<PlaylistMappingResponse> {
  return apiRequest(`/api/arr/sonarr/instances/${encodeURIComponent(instanceId)}/playlist/mappings`, { method: 'POST', ...jsonBody(body) });
}

export function listSonarrPlaylistMappings(instanceId?: string, params?: { limit?: number; offset?: number }): Promise<PlaylistMappingListResponse> {
  const q = new URLSearchParams();
  if (instanceId) q.set('instanceId', instanceId);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  return apiRequest(`/api/arr/sonarr/playlist/mappings?${q}`);
}

export function getSonarrPlaylistMapping(mappingId: string): Promise<PlaylistMappingResponse> {
  return apiRequest(`/api/arr/sonarr/playlist/mappings/${encodeURIComponent(mappingId)}`);
}

export function updateSonarrPlaylistMapping(mappingId: string, body: {
  name?: string;
  qualityProfileId?: number;
  rootFolderPath?: string;
  autoDownload?: boolean;
  status?: 'draft' | 'ready' | 'cancelled';
  items?: PlaylistMappingItemData[];
}): Promise<PlaylistMappingResponse> {
  return apiRequest(`/api/arr/sonarr/playlist/mappings/${encodeURIComponent(mappingId)}`, { method: 'PATCH', ...jsonBody(body) });
}

export function autoMapSonarrPlaylist(mappingId: string): Promise<AutoMapResponse> {
  return apiRequest(`/api/arr/sonarr/playlist/mappings/${encodeURIComponent(mappingId)}/auto-map`, { method: 'POST' });
}

export function downloadSonarrPlaylistMapping(mappingId: string): Promise<{ taskId: string; status: string; statusUrl: string } | { taskIds: string[]; count: number; status: string; statusUrl: string }> {
  return apiRequest(`/api/arr/sonarr/playlist/mappings/${encodeURIComponent(mappingId)}/download`, { method: 'POST' });
}

export function deleteSonarrPlaylistMapping(mappingId: string): Promise<{ ok: boolean }> {
  return apiRequest(`/api/arr/sonarr/playlist/mappings/${encodeURIComponent(mappingId)}`, { method: 'DELETE' });
}
