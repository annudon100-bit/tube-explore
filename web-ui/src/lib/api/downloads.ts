import { apiRequest, jsonBody } from './client';
import type { DownloadPlaylistRequest, DownloadTaskCreatedResponse, DownloadVideoRequest } from './types';

export function startVideoDownload(body: DownloadVideoRequest) {
  return apiRequest<DownloadTaskCreatedResponse>('/api/download/video', { method: 'POST', ...jsonBody(body) });
}

export function startPlaylistDownload(body: DownloadPlaylistRequest) {
  return apiRequest<DownloadTaskCreatedResponse>('/api/download/playlist', { method: 'POST', ...jsonBody(body) });
}
