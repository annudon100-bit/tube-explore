import { apiRequest, jsonBody, qs } from './client';
import type { ConversionPresetCreateRequest, ConversionPresetResponse, ConversionPresetUpdateRequest, OkResponse, PageArgs } from './types';

export function listPresets(args: PageArgs = {}) {
  return apiRequest<ConversionPresetResponse[]>(`/api/convert-presets${qs({ limit: args.limit ?? 50, offset: args.offset ?? 0 })}`);
}

export function getPreset(name: string) {
  return apiRequest<ConversionPresetResponse>(`/api/convert-presets/${encodeURIComponent(name)}`);
}

export function createPreset(body: ConversionPresetCreateRequest) {
  return apiRequest<ConversionPresetResponse>('/api/convert-presets', { method: 'POST', ...jsonBody(body) });
}

export function patchPreset(name: string, body: ConversionPresetUpdateRequest) {
  return apiRequest<ConversionPresetResponse>(`/api/convert-presets/${encodeURIComponent(name)}`, { method: 'PATCH', ...jsonBody(body) });
}

export function deletePreset(name: string) {
  return apiRequest<OkResponse>(`/api/convert-presets/${encodeURIComponent(name)}`, { method: 'DELETE' });
}
