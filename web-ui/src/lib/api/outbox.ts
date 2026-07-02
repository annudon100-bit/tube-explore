import { apiRequest, jsonBody, qs } from './client';
import type { OkResponse, OutboxEntry, OutboxProcessRequest, PageArgs } from './types';

export function listOutbox(args: PageArgs = {}) {
  return apiRequest<OutboxEntry[]>(`/api/outbox${qs({ limit: args.limit ?? 50, offset: args.offset ?? 0 })}`);
}

export function deleteOutboxFile(fileId: string) {
  return apiRequest<OkResponse>(`/api/outbox/${encodeURIComponent(fileId)}`, { method: 'DELETE' });
}

export function processOutboxFile(fileId: string, body: OutboxProcessRequest) {
  return apiRequest<OkResponse>(`/api/outbox/${encodeURIComponent(fileId)}/process`, { method: 'POST', ...jsonBody(body) });
}
