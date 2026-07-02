import { API_BASE_URL } from '$lib/config/env';
import type { ApiErrorPayload, ValidationError } from './types';

export class ApiError extends Error {
  status: number;
  details?: ApiErrorPayload;

  constructor(message: string, status: number, details?: ApiErrorPayload) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

export function qs(params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  });
  const out = search.toString();
  return out ? `?${out}` : '';
}

function validationMessage(detail: ValidationError[]) {
  return detail.map((item) => `${item.loc.join('.')}: ${item.msg}`).join('\n');
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  const contentType = response.headers.get('content-type') || '';
  const canJson = contentType.includes('application/json');
  const payload = canJson ? await response.json().catch(() => null) : await response.text().catch(() => null);

  if (!response.ok) {
    const detail = payload?.detail;
    const message = Array.isArray(detail)
      ? validationMessage(detail)
      : typeof detail === 'string'
        ? detail
        : `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, payload || undefined);
  }

  return payload as T;
}

export function jsonBody<T extends object>(body: T): RequestInit {
  return { body: JSON.stringify(clean(body)) };
}

export function clean<T>(value: T): T {
  if (Array.isArray(value)) return value.map(clean) as T;
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).filter(([, v]) => v !== undefined && v !== '')
    ) as T;
  }
  return value;
}

export function fileDownloadUrl(fileId: string) {
  return `${API_BASE_URL}/api/files/${encodeURIComponent(fileId)}/download`;
}
