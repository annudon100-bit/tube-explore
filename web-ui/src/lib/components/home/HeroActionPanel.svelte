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
  let limit = 10;

  $: placeholder = mode === 'search'
    ? 'Search for videos, channels, or anything...'
    : mode === 'media'
      ? 'Paste a media URL...'
      : 'Paste a playlist URL...';
</script>

<section class="panel hero-panel">
  <div class="mode-tabs">
    <button class="mode-tab {mode === 'search' ? 'active' : ''}" type="button" on:click={() => mode = 'search'}>⌕ Search</button>
    <button class="mode-tab {mode === 'media' ? 'active' : ''}" type="button" on:click={() => mode = 'media'}>🔗 Media URL</button>
    <button class="mode-tab {mode === 'playlist' ? 'active' : ''}" type="button" on:click={() => mode = 'playlist'}>☷ Playlist URL</button>
  </div>

  <div class="input-row">
    <input class="input" bind:value placeholder={placeholder} on:keydown={(e) => { if (e.key === 'Enter') { mode === 'search' ? onSearch(value, limit) : mode === 'media' ? onInspectMetadata(value) : onInspectPlaylist(value); } }} />
    {#if mode === 'search'}
      <select class="select" bind:value={limit}>
        <option value={5}>5</option>
        <option value={10}>10</option>
        <option value={25}>25</option>
        <option value={50}>50</option>
      </select>
      <button class="btn primary" disabled={busy || !value.trim()} type="button" on:click={() => onSearch(value, limit)}>Search</button>
    {:else if mode === 'media'}
      <span></span>
      <button class="btn primary" disabled={busy || !value.trim()} type="button" on:click={() => onInspectMetadata(value)}>Inspect</button>
    {:else}
      <span></span>
      <button class="btn primary" disabled={busy || !value.trim()} type="button" on:click={() => onInspectPlaylist(value)}>Inspect</button>
    {/if}
  </div>

  <div class="action-row">
    {#if mode !== 'playlist'}
      <button class="btn blue" disabled={busy || !value.trim()} type="button" on:click={() => onInspectMetadata(value)}>ⓘ Inspect Metadata</button>
      <button class="btn red" disabled={busy || !value.trim()} type="button" on:click={() => onDownloadVideo(value)}>⇩ Download Video</button>
    {/if}
    {#if mode !== 'media'}
      <button class="btn green" disabled={busy || !value.trim()} type="button" on:click={() => onInspectPlaylist(value)}>♫ Inspect Playlist</button>
      <button class="btn" disabled={busy || !value.trim()} type="button" on:click={() => onDownloadPlaylist(value)}>⇩ Download Playlist</button>
    {/if}
  </div>
</section>
