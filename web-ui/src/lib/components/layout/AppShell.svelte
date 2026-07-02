<script lang="ts">
  import Sidebar from './Sidebar.svelte';
  import TopBar from './TopBar.svelte';
  import type { HealthResponse } from '$lib/api/types';

  export let health: HealthResponse | null = null;
  export let onOpen: (key: string) => void = () => {};
  export let onNewDownload: () => void = () => {};
</script>

<div class="app-shell">
  <Sidebar {health} {onOpen} />
  <main class="main">
    <TopBar {onNewDownload} />
    <slot />
  </main>
</div>
