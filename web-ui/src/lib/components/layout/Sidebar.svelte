<script lang="ts">
  import type { HealthResponse } from '$lib/api/types';

  export let health: HealthResponse | null = null;
  export let onOpen: (key: string) => void = () => {};
  export let onToggle: () => void = () => {};
  export let collapsed = true;

  const items = [
    ['search', 'i-search', 'Search'],
    ['downloads', 'i-download', 'Downloads'],
    ['tasks', 'i-task', 'Tasks'],
    ['files', 'i-folder', 'Files'],
    ['profiles', 'i-user', 'Profiles'],
    ['presets', 'i-sliders', 'Presets'],
    ['outbox', 'i-box', 'Outbox'],
    ['settings', 'i-gear', 'Settings'],
    ['health', 'i-heart', 'Health'],
  ];

  $: healthy = !!health && health.status === 'ok' && health.hasFfmpeg && health.hasYtdlp &&
               health.workerRunning && health.downloadDirectoryWritable && health.tempDirectoryWritable;
</script>

<aside class="sidebar">
  <button class="collapse-btn" type="button" aria-label="Toggle sidebar"
    on:click={onToggle}>{collapsed ? '»' : '«'}</button>

  <div class="brand-mini">
    <svg width="34" height="34" viewBox="0 0 120 120" aria-hidden="true">
      <use href="#logo-symbol"></use>
    </svg>
    <span>Tube <strong>Explore</strong></span>
  </div>

  <nav class="nav" aria-label="Main navigation">
    {#each items as [key, icon, label]}
      <button class="nav-item" type="button"
        on:click={() => key === 'search' ? window.scrollTo({ top: 0, behavior: 'smooth' }) : onOpen(key)}
        title={label}>
        <span class="nav-icon"><svg width="24" height="24"><use href="#{icon}"/></svg></span>
        <span class="nav-label">{label}</span>
        <span class="tooltip">{label}</span>
      </button>
    {/each}
  </nav>

  <div class="health-pill" style="width:100%">
    <strong class={healthy ? 'ok' : 'bad'}>{healthy ? 'System Healthy' : 'Needs Attention'}</strong>
    <div class="health-line"><span>ffmpeg</span><b class={health?.hasFfmpeg ? 'ok' : 'bad'}>{health?.hasFfmpeg ? 'OK' : 'Missing'}</b></div>
    <div class="health-line"><span>Worker</span><b class={health?.workerRunning ? 'ok' : 'bad'}>{health?.workerRunning ? 'Running' : 'Stopped'}</b></div>
  </div>
</aside>