<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import EmptyState from '$lib/components/shared/EmptyState.svelte';
  import PaginationControls from '$lib/components/shared/PaginationControls.svelte';
  import StatusBadge from '$lib/components/shared/StatusBadge.svelte';
  import ProgressBar from '$lib/components/shared/ProgressBar.svelte';
  import TaskDetailDialog from './TaskDetailDialog.svelte';
  import { listTasks } from '$lib/api/tasks';
  import { API_BASE_URL } from '$lib/config/env';
  import type { TaskResponse } from '$lib/api/types';

  export let onClose: () => void = () => {};
  let tasks: TaskResponse[] = [];
  let selected: TaskResponse | null = null;
  let limit = 50;
  let offset = 0;
  let error: string | null = null;
  let busy = false;

  async function load() {
    busy = true; error = null;
    try { tasks = await listTasks({ limit, offset }); } catch (e) { error = e instanceof Error ? e.message : 'Unable to load tasks'; } finally { busy = false; }
  }
  $: loadKey = `${limit}:${offset}`;
  $: if (loadKey) load();
</script>

<ModalFrame title="Tasks" size="large" onClose={onClose}>
  <ErrorMessage message={error} />
  {#if busy}<div class="empty">Loading tasks…</div>{:else if tasks.length === 0}<EmptyState title="No tasks found" detail="Start a download to create a task." />{:else}
    <div class="simple-list">
      {#each tasks as task}
        <button class="row clickable" type="button" on:click={() => selected = task}>
          <div class="avatar">
            {#if task.thumbnailPath}
              <img src={`${API_BASE_URL}${task.thumbnailPath}`} alt="" class="avatar-img" />
            {:else}
              {task.type === 'playlist' ? '♫' : '▶'}
            {/if}
          </div>
          <div><div class="row-title">{task.type} · {task.id}</div><div class="row-sub">{task.url}</div></div>
          <div style="display:grid; gap:8px; justify-items:end"><StatusBadge status={task.status} /><ProgressBar value={task.progressPercent} /></div>
        </button>
      {/each}
    </div>
  {/if}
  <PaginationControls {limit} {offset} onChange={(l, o) => { limit = l; offset = o; }} />
  {#if selected}<TaskDetailDialog task={selected} onClose={() => selected = null} onChanged={load} />{/if}
</ModalFrame>
