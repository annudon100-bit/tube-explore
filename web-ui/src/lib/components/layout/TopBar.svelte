<script lang="ts">
  import NotificationDropdown from './NotificationDropdown.svelte';
  import type { HealthResponse, TaskResponse } from '$lib/api/types';

  export let health: HealthResponse | null = null;
  export let onTask: (task: TaskResponse) => void = () => {};
  export let onHealth: () => void = () => {};

  $: healthy = !!health && health.status === 'ok' && health.hasFfmpeg && health.hasYtdlp &&
               health.downloadDirectoryWritable && health.tempDirectoryWritable;
</script>

<div class="topbar">
  <NotificationDropdown {onTask} />
  <button class="status-pill" type="button" title="Open health details" on:click={onHealth}>
    <span class="status-dot" class:status-dot={healthy}></span>
    {healthy ? 'All systems ready' : 'Needs attention'}
  </button>
</div>