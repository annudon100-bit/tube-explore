<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import StatusBadge from '$lib/components/shared/StatusBadge.svelte';
  import ProgressBar from '$lib/components/shared/ProgressBar.svelte';
  import { dateTime } from '$lib/utils/format';
  import type { TaskResponse } from '$lib/api/types';
  import { tasks } from '$lib/state/event-stream';
  import { API_BASE_URL } from '$lib/config/env';

  export let onTask: (task: TaskResponse) => void = () => {};
  export let onViewAll: () => void = () => {};

  let open = false;
  let container: HTMLDivElement;

  $: recent = $tasks.slice(0, 5);
  $: activeCount = recent.filter(t => ['pending', 'running', 'failed', 'paused'].includes(t.status)).length;

  function toggle() {
    open = !open;
  }

  function handleClickOutside(e: MouseEvent) {
    if (container && !container.contains(e.target as Node)) {
      open = false;
    }
  }

  onMount(() => {
    document.addEventListener('click', handleClickOutside);
  });

  onDestroy(() => {
    document.removeEventListener('click', handleClickOutside);
  });
</script>

<div class="notification-container" bind:this={container}>
  <button class="btn icon-btn" type="button" on:click={toggle} aria-label="Notifications">
    <span class="bell">🔔</span>
    {#if activeCount > 0}
      <span class="badge">{activeCount}</span>
    {/if}
  </button>

  {#if open}
    <div class="dropdown-panel">
      <div class="dropdown-header">
        <strong>Recent Activity</strong>
        <button class="link-btn" type="button" on:click={() => { open = false; onViewAll(); }}>View all</button>
      </div>
      {#if recent.length === 0}
        <div class="empty">No tasks yet.</div>
      {:else}
        <div class="dropdown-list">
          {#each recent as task}
            <button class="row clickable" type="button" on:click={() => { open = false; onTask(task); }}>
              <div class="avatar">
                {#if task.thumbnailPath}
                  <img src={`${API_BASE_URL}${task.thumbnailPath}`} alt="" class="avatar-img" />
                {:else}
                  {task.type === 'playlist' ? '♫' : '▶'}
                {/if}
              </div>
              <div>
                <div class="row-title">{task.type === 'playlist' ? 'Playlist' : 'Video'}</div>
                <div class="row-sub">{task.url}</div>
                <div class="row-sub">{dateTime(task.createdAt)}</div>
              </div>
              <div style="display:grid; gap:6px; justify-items:end;">
                <StatusBadge status={task.status} />
                <ProgressBar value={task.progressPercent} />
              </div>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>
