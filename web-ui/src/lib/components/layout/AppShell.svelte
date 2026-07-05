<script lang="ts">
  import Sidebar from './Sidebar.svelte';
  import TopBar from './TopBar.svelte';
  import type { HealthResponse, TaskResponse } from '$lib/api/types';

  export let health: HealthResponse | null = null;
  export let onOpen: (key: string) => void = () => {};
  export let onTask: (task: TaskResponse) => void = () => {};
  export let activePage = 'home';
  export let navigate: (page: string) => void = () => {};

  let collapsed = true;

  function toggleSidebar() { collapsed = !collapsed; }
</script>

<div class="app-shell" class:sidebar-open={!collapsed}>
  <Sidebar {onOpen} {collapsed} onToggle={toggleSidebar} {activePage} {navigate} />
  <main class="main">
    <TopBar {health} {onTask} onHealth={() => onOpen('health')} />
    <slot />
  </main>
</div>
