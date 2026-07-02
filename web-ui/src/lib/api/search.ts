import { apiRequest, qs } from './client';
import type { SearchResponse } from './types';

export function searchMedia(q: string, limit = 10) {
  return apiRequest<SearchResponse>(`/api/search${qs({ q, limit })}`);
}
