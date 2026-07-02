<script lang="ts">
  import HealthPill from './HealthPill.svelte';
  import type { HealthResponse } from '$lib/api/types';
  export let health: HealthResponse | null = null;
  export let onOpen: (key: string) => void = () => {};

  const items = [
    ['home', '⌂', 'Home'],
    ['tasks', '☷', 'Tasks'],
    ['files', '▣', 'Files'],
    ['profiles', '♙', 'Profiles'],
    ['presets', '⚙', 'Presets'],
    ['outbox', '▱', 'Outbox'],
    ['settings', '◌', 'Settings']
  ];
</script>

<aside class="sidebar">
  <div class="brand">
    <div class="brand-mark">▶</div>
    <span>Tube <span>Explore</span></span>
  </div>
  <nav class="nav" aria-label="Main">
    {#each items as [key, icon, label]}
      <button class="nav-btn {key === 'home' ? 'active' : ''}" type="button" on:click={() => key === 'home' ? window.scrollTo({ top: 0, behavior: 'smooth' }) : onOpen(key)}>
        <span>{icon}</span><span>{label}</span>
      </button>
    {/each}
  </nav>
  <div class="sidebar-footer">
    <HealthPill {health} onOpen={() => onOpen('health')} />
  </div>
</aside>
