import { writable } from 'svelte/store';
import { API_BASE_URL } from '$lib/config/env';
import type { TaskResponse } from '$lib/api/types';

const _tasksMap = new Map<string, TaskResponse>();
export const tasks = writable<TaskResponse[]>([]);

let source: EventSource | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

function sortTasks(list: TaskResponse[]): TaskResponse[] {
  return list.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}

function updateTasks() {
  tasks.set(sortTasks(Array.from(_tasksMap.values())));
}

export function connectEventStream() {
  if (source) return;
  source = new EventSource(`${API_BASE_URL}/api/events`);

  source.addEventListener('snapshot', (e: MessageEvent) => {
    const data = JSON.parse(e.data);
    _tasksMap.clear();
    for (const task of data.tasks) {
      _tasksMap.set(task.id, task);
    }
    updateTasks();
  });

  source.addEventListener('task_created', (e: MessageEvent) => {
    const task = JSON.parse(e.data) as TaskResponse;
    _tasksMap.set(task.id, task);
    updateTasks();
  });

  source.addEventListener('task_updated', (e: MessageEvent) => {
    const task = JSON.parse(e.data) as TaskResponse;
    _tasksMap.set(task.id, task);
    updateTasks();
  });

  source.addEventListener('task_deleted', (e: MessageEvent) => {
    const { id } = JSON.parse(e.data);
    _tasksMap.delete(id);
    updateTasks();
  });

  source.onerror = () => {
    source?.close();
    source = null;
    reconnectTimer = setTimeout(connectEventStream, 3000);
  };
}

export function disconnectEventStream() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  source?.close();
  source = null;
}
