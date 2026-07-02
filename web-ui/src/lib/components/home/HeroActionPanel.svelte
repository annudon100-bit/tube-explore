<script lang="ts">
  export let onSearch: (query: string, limit: number) => void = () => {};
  export let onInspectMetadata: (url: string) => void = () => {};
  export let onInspectPlaylist: (url: string) => void = () => {};
  export let onDownloadVideo: (url: string) => void = () => {};
  export let onDownloadPlaylist: (url: string) => void = () => {};
  export let busy = false;

  type Mode = 'search' | 'media' | 'playlist';
  let mode: Mode = 'search';
  let value = '';

  $: placeholder = mode === 'search'
    ? 'Search for videos, channels, or anything...'
    : mode === 'media'
      ? 'Paste a video URL...'
      : 'Paste a playlist URL...';

  $: buttonLabel = mode === 'search' ? 'Search' : 'Inspect';

  function handlePrimary() {
    if (!value.trim()) return;
    if (mode === 'search') onSearch(value, 10);
    else if (mode === 'media') onInspectMetadata(value);
    else onInspectPlaylist(value);
  }

  function handleEnter(e: KeyboardEvent) {
    if (e.key === 'Enter') handlePrimary();
  }

  function handleDownload() {
    if (!value.trim()) return;
    if (mode === 'playlist') onDownloadPlaylist(value);
    else onDownloadVideo(value);
  }
</script>

<section class="search-card" aria-label="Search and download">
  <div class="tabs" role="tablist">
    <button class="tab {mode === 'search' ? 'active' : ''}" type="button" on:click={() => mode = 'search'}>
      <svg width="21" height="21"><use href="#i-search"/></svg>
      Search
    </button>
    <button class="tab {mode === 'media' ? 'active' : ''}" type="button" on:click={() => mode = 'media'}>
      <svg width="21" height="21"><use href="#i-link"/></svg>
      Video URL
    </button>
    <button class="tab {mode === 'playlist' ? 'active' : ''}" type="button" on:click={() => mode = 'playlist'}>
      <svg width="21" height="21"><use href="#i-list"/></svg>
      Playlist URL
    </button>
  </div>

  <div class="search-row">
    <label class="input-wrap">
      <svg width="24" height="24"><use href="#i-search"/></svg>
      <input type="text" bind:value placeholder={placeholder} aria-label={buttonLabel} on:keydown={handleEnter} disabled={busy} />
    </label>
    <button class="primary-btn" type="button" disabled={busy || !value.trim()} on:click={handlePrimary}>{buttonLabel}</button>
  </div>

  <div class="divider">or</div>

  <button class="download-btn" type="button" disabled={busy || !value.trim()} on:click={handleDownload}>
    <svg width="23" height="23"><use href="#i-download"/></svg>
    Download {mode === 'playlist' ? 'Playlist' : 'Video'}
  </button>
</section>