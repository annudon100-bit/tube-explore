<script lang="ts">
  export let onOpen: (key: string) => void = () => {};
  export let onToggle: () => void = () => {};
  export let collapsed = true;
  export let activePage = 'home';
  export let navigate: (page: string) => void = () => {};

  const items = [
    ['search', 'i-search', 'Search'],
    ['downloads', 'i-download', 'Downloads'],
    ['files', 'i-folder', 'Files'],
    ['profiles', 'i-user', 'Profiles'],
    ['settings', 'i-gear', 'Settings'],
    ['health', 'i-heart', 'Health'],
  ];

  function handleNav(key: string) {
    if (key === 'search') {
      navigate('home');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else if (key === 'downloads') {
      navigate('downloads');
    } else {
      onOpen(key);
    }
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
    {#each items as [key, icon, label]}
      <button class="nav-item" class:active={key === 'downloads' ? activePage === 'downloads' : false}
        type="button"
        on:click={() => handleNav(key)}
        title={label}>
        <span class="nav-icon"><svg width="24" height="24"><use href="#{icon}"/></svg></span>
        <span class="nav-label">{label}</span>
        <span class="tooltip">{label}</span>
      </button>
    {/each}
  </nav>

  <div class="sidebar-footer">
    <button class="collapse-btn" type="button" aria-label="Toggle sidebar" on:click={onToggle}>
      <svg width="20" height="20"><use href={collapsed ? "#i-chevron-right" : "#i-chevron-left"}/></svg>
      <span class="collapse-label">Collapse</span>
    </button>
  </div>
</aside>
