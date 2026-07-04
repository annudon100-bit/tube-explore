<script lang="ts">
  import type { TaskResponse } from '$lib/api/types';
  import { dateTime } from '$lib/utils/format';
  import ProgressBar from '$lib/components/shared/ProgressBar.svelte';
  import StatusBadge from '$lib/components/shared/StatusBadge.svelte';
  import { API_BASE_URL } from '$lib/config/env';

  export let tasks: TaskResponse[] = [];
  export let onTask: (task: TaskResponse) => void = () => {};
  export let onViewAll: () => void = () => {};
</script>

<section class="panel card">
  <div class="card-header">
    <h2>Recent Activity</h2>
    <button class="link-btn" type="button" on:click={onViewAll}>View all</button>
  </div>
  {#if tasks.length === 0}
    <div class="empty">No tasks yet. Start a download to see activity.</div>
  {:else}
    <div class="activity-list">
      {#each tasks.slice(0, 5) as task}
        <button class="row clickable" type="button" on:click={() => onTask(task)}>
          <div class="avatar">
            {#if task.thumbnailPath}
              <img src={`${API_BASE_URL}${task.thumbnailPath}`} alt="" class="avatar-img" />
            {:else}
              {task.type === 'playlist' ? '♫' : '▶'}
            {/if}
          </div>
          <div>
            <div class="row-title">{task.type === 'playlist' ? 'Playlist Download' : 'Video Download'}</div>
            <div class="row-sub">{task.url}</div>
            <div class="row-sub">{dateTime(task.createdAt)}</div>
          </div>
          <div style="display:grid; gap:8px; justify-items:end;">
            <StatusBadge status={task.status} />
            <ProgressBar value={task.progressPercent} />
          </div>
        </button>
      {/each}
    </div>
  {/if}
</section>
