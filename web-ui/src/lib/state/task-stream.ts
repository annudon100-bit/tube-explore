import { taskStreamUrl } from '$lib/api/tasks';
import type { TaskResponse } from '$lib/api/types';

export function connectTaskStream(taskId: string, onUpdate: (task: TaskResponse) => void, onError?: (error: Event) => void) {
  const source = new EventSource(taskStreamUrl(taskId));
  source.onmessage = (event) => {
    try {
      const task = JSON.parse(event.data) as TaskResponse;
      onUpdate(task);
      if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') source.close();
    } catch {
      // keepalive or non-JSON events are ignored
    }
  };
  source.onerror = (event) => {
    onError?.(event);
    source.close();
  };
  return () => source.close();
}
