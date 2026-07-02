import { apiRequest, jsonBody, qs } from './client';
import type { OkResponse, PageArgs, ProfileCreateRequest, ProfileResponse, ProfileUpdateRequest } from './types';

export function listProfiles(args: PageArgs = {}) {
  return apiRequest<ProfileResponse[]>(`/api/profiles${qs({ limit: args.limit ?? 50, offset: args.offset ?? 0 })}`);
}

export function getProfile(id: number) {
  return apiRequest<ProfileResponse>(`/api/profiles/${id}`);
}

export function createProfile(body: ProfileCreateRequest) {
  return apiRequest<ProfileResponse>('/api/profiles', { method: 'POST', ...jsonBody(body) });
}

export function patchProfile(id: number, body: ProfileUpdateRequest) {
  return apiRequest<ProfileResponse>(`/api/profiles/${id}`, { method: 'PATCH', ...jsonBody(body) });
}

export function deleteProfile(id: number) {
  return apiRequest<OkResponse>(`/api/profiles/${id}`, { method: 'DELETE' });
}
