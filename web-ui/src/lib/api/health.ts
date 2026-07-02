import { apiRequest } from './client';
import type { HealthResponse } from './types';

export function getHealth() {
  return apiRequest<HealthResponse>('/api/health');
}

export function getReady() {
  return apiRequest<HealthResponse>('/api/ready');
}
