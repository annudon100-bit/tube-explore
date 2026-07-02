<script lang="ts">
  import Sidebar from './Sidebar.svelte';
  import TopBar from './TopBar.svelte';
  import type { HealthResponse, TaskResponse } from '$lib/api/types';

  export let health: HealthResponse | null = null;
  export let onOpen: (key: string) => void = () => {};
  export let onTask: (task: TaskResponse) => void = () => {};
  export let onViewAll: () => void = () => {};

  let collapsed = true;

  function toggleSidebar() { collapsed = !collapsed; }
</script>

<div class="app-shell" class:sidebar-open={!collapsed}>
  <Sidebar {onOpen} {collapsed} onToggle={toggleSidebar} />
  <main class="main">
    <TopBar {health} {onTask} {onViewAll} onHealth={() => onOpen('health')} />
    <slot />
  </main>
</div>