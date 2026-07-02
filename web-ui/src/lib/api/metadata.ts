import { apiRequest, qs } from './client';
import type { MetadataResponse } from './types';

export function getMetadata(url: string) {
  return apiRequest<MetadataResponse>(`/api/metadata${qs({ url })}`);
}
