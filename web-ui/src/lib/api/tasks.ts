import { apiRequest, qs } from './client';
import type { DownloadTaskCreatedResponse, OkResponse, PageArgs, TaskResponse, TaskResultResponse } from './types';

export function listTasks(args: PageArgs = {}) {
  return apiRequest<TaskResponse[]>(`/api/tasks${qs({ limit: args.limit ?? 50, offset: args.offset ?? 0 })}`);
}

export function getTask(taskId: string) {
  return apiRequest<TaskResponse>(`/api/tasks/${encodeURIComponent(taskId)}`);
}

export function getTaskResult(taskId: string) {
  return apiRequest<TaskResultResponse>(`/api/tasks/${encodeURIComponent(taskId)}/result`);
}

export function cancelTask(taskId: string) {
  return apiRequest<Record<string, unknown>>(`/api/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' });
}

export function retryTask(taskId: string) {
  return apiRequest<DownloadTaskCreatedResponse>(`/api/tasks/${encodeURIComponent(taskId)}/retry`, { method: 'POST' });
}

export function deleteTask(taskId: string) {
  return apiRequest<OkResponse>(`/api/tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' });
}

