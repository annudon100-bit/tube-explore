import { apiRequest, qs } from './client';
import type { PlaylistResponse } from './types';

export function getPlaylist(url: string) {
  return apiRequest<PlaylistResponse>(`/api/playlist${qs({ url })}`);
}
