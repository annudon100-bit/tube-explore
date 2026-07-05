import { apiRequest } from './client';
import type { DownloadTaskCreatedResponse, TaskResponse } from './types';

export function getTask(taskId: string) {
  return apiRequest<TaskResponse>(`/api/tasks/${encodeURIComponent(taskId)}`);
}

export function cancelTask(taskId: string) {
  return apiRequest<Record<string, unknown>>(`/api/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' });
}

export function pauseTask(taskId: string) {
  return apiRequest<Record<string, unknown>>(`/api/tasks/${encodeURIComponent(taskId)}/pause`, { method: 'POST' });
}

export function resumeTask(taskId: string) {
  return apiRequest<Record<string, unknown>>(`/api/tasks/${encodeURIComponent(taskId)}/resume`, { method: 'POST' });
}

export function retryTask(taskId: string) {
  return apiRequest<DownloadTaskCreatedResponse>(`/api/tasks/${encodeURIComponent(taskId)}/retry`, { method: 'POST' });
}

