<script lang="ts">
  import NotificationDropdown from './NotificationDropdown.svelte';
  import type { TaskResponse } from '$lib/api/types';

  export let onNewDownload: () => void = () => {};
  export let onTask: (task: TaskResponse) => void = () => {};
  export let onViewAll: () => void = () => {};
</script>

<div class="topbar">
  <div class="page-title">
    <h1>What would you like to do today?</h1>
    <p>Search, inspect, and download media without clutter.</p>
  </div>
  <div class="top-actions">
    <NotificationDropdown {onTask} {onViewAll} />
    <button class="btn primary" type="button" on:click={onNewDownload}>＋ New Download</button>
  </div>
</div>