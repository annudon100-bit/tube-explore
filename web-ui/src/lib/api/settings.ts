import { apiRequest, jsonBody } from './client';
import type { SettingsResponse, SettingsUpdateRequest } from './types';

export function getSettings() {
  return apiRequest<SettingsResponse>('/api/settings');
}

export function patchSettings(body: SettingsUpdateRequest) {
  return apiRequest<SettingsResponse>('/api/settings', { method: 'PATCH', ...jsonBody(body) });
}
