<script lang="ts">
  export let onOpen: (key: string) => void = () => {};
  export let onToggle: () => void = () => {};
  export let collapsed = true;
  export let activePage = 'home';
  export let navigate: (page: string) => void = () => {};

  let instancesExpanded = false;
  let settingsExpanded = false;

  $: if (!collapsed) {
    instancesExpanded = activePage.startsWith('instances') || activePage === 'sonarr-instance-form' || activePage === 'sonarr-playlist-mapping' || activePage === 'missing-episodes' || activePage === 'sonarr-search-context';
    settingsExpanded = activePage.startsWith('settings') || activePage.startsWith('radarr-') || activePage === 'sonarr-instance-form';
  }

  const topItems = [
    ['search', 'i-search', 'Search'],
    ['downloads', 'i-download', 'Downloads'],
    ['files', 'i-folder', 'Files'],
    ['profiles', 'i-user', 'Profiles'],
  ];

  const instanceItems = [
    ['instances', 'i-grid', 'Overview'],
    ['instances-radarr', 'i-radarr', 'Radarr'],
    ['instances-sonarr', 'i-sonarr', 'Sonarr'],
  ];

  const settingsItems = [
    ['profiles', 'i-user', 'Download Profiles'],
    ['settings-integrations', 'i-box', 'Integrations'],
    ['health', 'i-heart', 'System'],
  ];

  function toggleGroup(group: string) {
    if (group === 'instances') instancesExpanded = !instancesExpanded;
    else if (group === 'settings') settingsExpanded = !settingsExpanded;
  }

  function handleNav(key: string) {
    if (key === 'search') {
      navigate('home');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else if (key === 'downloads') {
      navigate('downloads');
    } else if (key === 'files') {
      navigate('files');
    } else if (key === 'profiles') {
      onOpen('profiles');
    } else if (key === 'settings-integrations') {
      navigate('settings-integrations');
    } else if (key === 'health') {
      onOpen('health');
    } else if (key.startsWith('instances-') || key === 'instances') {
      navigate(key);
    }
  }

  function isActive(key: string): boolean {
    if (key === 'downloads') return activePage === 'downloads';
    if (key === 'files') return activePage === 'files';
    if (key === 'instances') return activePage === 'instances';
    if (key === 'instances-radarr') return activePage === 'instances-radarr' || activePage === 'radarr-instances' || activePage === 'radarr-instance-form' || activePage === 'missing-movies' || activePage === 'radarr-search-context';
    if (key === 'instances-sonarr') return activePage === 'instances-sonarr' || activePage === 'sonarr-instance-form' || activePage === 'missing-episodes' || activePage === 'sonarr-search-context' || activePage === 'sonarr-playlist-mapping';
    if (key === 'settings-integrations') return activePage === 'settings-integrations';
    return false;
  }

  function groupActive(items: Array<[string, string, string]>): boolean {
    return items.some(([key]) => isActive(key));
  }
</script>

<aside class="sidebar">
  <div class="brand">
    <svg class="brand-mark" viewBox="0 0 120 120" aria-hidden="true">
      <use href="#logo-symbol"></use>
    </svg>
    <div class="brand-name">Tube <strong>Explore</strong></div>
  </div>

  <nav class="nav" aria-label="Main navigation">
    {#each topItems as [key, icon, label]}
      <button class="nav-item" class:active={isActive(key)}
        type="button"
        on:click={() => handleNav(key)}
        title={label}>
        <span class="nav-icon"><svg width="24" height="24"><use href="#{icon}"/></svg></span>
        <span class="nav-label">{label}</span>
        <span class="tooltip">{label}</span>
      </button>
    {/each}

    {#if !collapsed}
      <div class="nav-group">
        <button class="nav-group-header" class:expanded={instancesExpanded} type="button" on:click={() => toggleGroup('instances')}>
          <span class="nav-group-icon"><svg width="20" height="20"><use href="#i-box"/></svg></span>
          <span class="nav-group-label">Instances</span>
          <svg class="nav-chevron" class:rotated={instancesExpanded} width="16" height="16"><use href="#i-chevron-down"/></svg>
        </button>
        {#if instancesExpanded}
          {#each instanceItems as [key, icon, label]}
            <button class="nav-item sub" class:active={isActive(key)}
              type="button"
              on:click={() => handleNav(key)}
              title={label}>
              <span class="nav-icon"><svg width="18" height="18"><use href="#{icon}"/></svg></span>
              <span class="nav-label">{label}</span>
            </button>
          {/each}
        {/if}
      </div>

      <div class="nav-group">
        <button class="nav-group-header" class:expanded={settingsExpanded} type="button" on:click={() => toggleGroup('settings')}>
          <span class="nav-group-icon"><svg width="20" height="20"><use href="#i-gear"/></svg></span>
          <span class="nav-group-label">Settings</span>
          <svg class="nav-chevron" class:rotated={settingsExpanded} width="16" height="16"><use href="#i-chevron-down"/></svg>
        </button>
        {#if settingsExpanded}
          {#each settingsItems as [key, icon, label]}
            <button class="nav-item sub" class:active={isActive(key)}
              type="button"
              on:click={() => handleNav(key)}
              title={label}>
              <span class="nav-icon"><svg width="18" height="18"><use href="#{icon}"/></svg></span>
              <span class="nav-label">{label}</span>
            </button>
          {/each}
        {/if}
      </div>
    {:else}
      {#if groupActive(instanceItems)}
        <button class="nav-item active" type="button" title="Instances">
          <span class="nav-icon"><svg width="24" height="24"><use href="#i-box"/></svg></span>
          <span class="tooltip">Instances</span>
        </button>
      {:else}
        <button class="nav-item" type="button" on:click={() => toggleGroup('instances')} title="Instances">
          <span class="nav-icon"><svg width="24" height="24"><use href="#i-box"/></svg></span>
          <span class="tooltip">Instances</span>
        </button>
      {/if}
      {#if groupActive(settingsItems) || activePage.startsWith('radarr-') || activePage.startsWith('settings-') || activePage === 'sonarr-playlist-mapping' || activePage === 'missing-episodes'}
        <button class="nav-item active" type="button" title="Settings">
          <span class="nav-icon"><svg width="24" height="24"><use href="#i-gear"/></svg></span>
          <span class="tooltip">Settings</span>
        </button>
      {:else}
        <button class="nav-item" type="button" on:click={() => toggleGroup('settings')} title="Settings">
          <span class="nav-icon"><svg width="24" height="24"><use href="#i-gear"/></svg></span>
          <span class="tooltip">Settings</span>
        </button>
      {/if}
    {/if}
  </nav>

  <div class="sidebar-footer">
    <button class="collapse-btn" type="button" aria-label="Toggle sidebar" on:click={onToggle}>
      <svg width="20" height="20"><use href={collapsed ? "#i-chevron-right" : "#i-chevron-left"}/></svg>
      <span class="collapse-label">Collapse</span>
    </button>
  </div>
</aside>

<style>
  .sidebar { /* inherited from AppShell — kept minimal */ }
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 18px 16px 14px;
    border-bottom: 1px solid rgba(255,255,255,.07);
  }
  .brand-mark { width: 34px; height: 34px; flex: 0 0 auto; }
  .brand-name { font-size: 23px; letter-spacing: -0.04em; font-weight: 400; white-space: nowrap; }
  .nav { padding: 10px 10px; display: flex; flex-direction: column; gap: 2px; flex: 1; overflow-y: auto; }
  .nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 11px 12px;
    border-radius: 14px;
    background: transparent;
    border: 0;
    color: var(--muted);
    cursor: pointer;
    font-size: 14px;
    font-weight: 800;
    width: 100%;
    text-align: left;
    transition: 180ms ease;
    position: relative;
    white-space: nowrap;
  }
  .nav-item:hover { color: white; background: rgba(255,255,255,.045); }
  .nav-item.active { color: white; background: rgba(124,60,255,.18); }
  .nav-item.sub { padding: 8px 12px 8px 42px; font-size: 13px; }
  .nav-item.sub .nav-icon { width: 18px; height: 18px; }
  .nav-icon { width: 24px; height: 24px; display: grid; place-items: center; flex: 0 0 auto; }
  .nav-label { flex: 1; overflow: hidden; text-overflow: ellipsis; }
  .tooltip {
    display: none;
    position: absolute;
    left: 60px;
    top: 50%;
    transform: translateY(-50%);
    background: #1a1f3a;
    color: white;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 800;
    white-space: nowrap;
    pointer-events: none;
    z-index: 10;
    box-shadow: 0 4px 16px rgba(0,0,0,.4);
  }
  .nav-group { display: flex; flex-direction: column; gap: 1px; margin-top: 4px; }
  .nav-group-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 14px;
    background: transparent;
    border: 0;
    color: var(--muted);
    cursor: pointer;
    font-size: 13px;
    font-weight: 750;
    width: 100%;
    text-align: left;
    transition: 180ms ease;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .nav-group-header:hover { color: white; background: rgba(255,255,255,.035); }
  .nav-group-header.expanded { color: white; }
  .nav-group-icon { width: 20px; height: 20px; display: grid; place-items: center; flex: 0 0 auto; color: var(--muted); }
  .nav-group-label { flex: 1; }
  .nav-chevron { transition: transform 200ms ease; color: var(--muted); }
  .nav-chevron.rotated { transform: rotate(180deg); }
  .sidebar-footer { padding: 10px 10px; border-top: 1px solid rgba(255,255,255,.07); }
  .collapse-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 14px;
    background: transparent;
    border: 0;
    color: var(--muted);
    cursor: pointer;
    font-size: 13px;
    font-weight: 700;
    width: 100%;
    transition: 180ms ease;
  }
  .collapse-btn:hover { color: white; background: rgba(255,255,255,.045); }
</style>
