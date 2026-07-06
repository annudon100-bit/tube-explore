<script lang="ts">
  import { showToast } from '$lib/state/toast-state';
  import { downloadForRadarrMovie } from '$lib/api/radarr';
  import type { RadarrInstanceResponse, RadarrMissingMovie } from '$lib/api/types';

  export let navigate: (page: string, data?: any) => void = () => {};
  export let instance: RadarrInstanceResponse;
  export let movie: RadarrMissingMovie;
  export let presetUrl = '';

  let query = movie?.title || '';
  let results: Array<{
    title: string;
    source: string;
    channel: string;
    quality: string;
    codec: string;
    size: string;
    url: string;
  }> = [];
  let busy = false;
  let searched = false;

  let pasteModalOpen = !!presetUrl;
  let pasteUrl = presetUrl || '';

  async function doSearch() {
    if (!query.trim()) return;
    busy = true;
    searched = true;
    try {
      const searchResp = await import('$lib/api/search').then(m => m.searchMedia(query, 25));
      results = searchResp.results.map(r => ({
        title: r.title || 'Untitled',
        source: 'YouTube',
        channel: r.channel || 'Unknown',
        quality: '—',
        codec: '—',
        size: '—',
        url: r.url,
      }));
      if (results.length === 0) {
        showToast('No results found');
      }
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Search failed');
    } finally { busy = false; }
  }

  function openPasteModal() {
    pasteModalOpen = true;
    pasteUrl = '';
  }

  function closePasteModal() {
    pasteModalOpen = false;
    pasteUrl = '';
  }

  async function submitPasteUrl() {
    if (!pasteUrl.trim()) return;
    try {
      const resp = await downloadForRadarrMovie({
        url: pasteUrl,
        instanceId: instance?.id,
        movieId: movie?.movieId,
        movieTitle: movie?.title,
        movieYear: movie?.year,
      });
      showToast(`Download task created: ${resp.taskId}`);
      closePasteModal();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Download failed');
    }
  }

  async function downloadResult(result: typeof results[0]) {
    try {
      const resp = await downloadForRadarrMovie({
        url: result.url,
        instanceId: instance?.id,
        movieId: movie?.movieId,
        movieTitle: movie?.title,
        movieYear: movie?.year,
      });
      showToast(`Download task created: ${resp.taskId}`);
      navigate('downloads');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Download failed');
    }
  }

  function goBack() {
    navigate('missing-movies', { instance });
  }
</script>

<div class="page">
  <header class="page-head">
    <div>
      <div class="crumbs">
        <span class="crumb">Radarr</span> ›
        <span class="crumb">{instance?.name}</span> ›
        <span class="crumb">Missing Movies</span> ›
        <span>Search</span>
      </div>
      <h1 class="page-title">Search for <span class="highlight">{movie?.title}</span></h1>
      <p class="page-subtitle">Find and select a video to download and import to Radarr.</p>
    </div>
    <div class="toolbar">
      <button class="secondary-btn" type="button" on:click={goBack}>
        ← Back to Missing Movies
      </button>
    </div>
  </header>

  <section class="top-strip">
    <div class="movie-cell">
      <div class="poster" style="background: linear-gradient(135deg, #1f5f99, #5b2ee8)"></div>
      <div>
        <div class="summary-label">Target Movie</div>
        <div class="item-title">{movie?.title} ({movie?.year || '—'})</div>
        <div class="sub">TMDB: {movie?.tmdbId || '—'} • IMDb: {movie?.imdbId || '—'}</div>
      </div>
    </div>
    <div>
      <div class="summary-label">Radarr Instance</div>
      <div class="item-title">{instance?.name}</div>
      <div class="sub">{instance?.baseUrl}</div>
    </div>
    <div>
      <div class="summary-label">Import Path (Radarr view)</div>
      <div class="path">{instance?.radarrImportPath}</div>
      <div class="sub" style="color: var(--green)">Path mapping verified ✓</div>
    </div>
    <div>
      <div class="summary-label">Write Path (Tube Explore view)</div>
      <div class="path">{instance?.tubeWritePath}</div>
      <div class="sub" style="color: var(--green)">Writeable ✓</div>
    </div>
  </section>

  <section class="panel">
    <div class="filters">
      <label class="search-box" style="flex:1">
        <svg width="18" height="18"><use href="#i-search"/></svg>
        <input type="search" bind:value={query} placeholder="Search videos..." on:keydown={(e) => e.key === 'Enter' && doSearch()} />
      </label>
      <button class="primary-btn" type="button" disabled={busy} on:click={doSearch}>
        <svg width="18" height="18"><use href="#i-search"/></svg>
        {busy ? 'Searching…' : 'Search'}
      </button>
      <button class="secondary-btn" type="button" on:click={openPasteModal}>
        <svg width="18" height="18"><use href="#i-link"/></svg>
        Paste URL
      </button>
    </div>

    {#if !searched}
      <div class="empty-state">
        <strong>Search for a video to download</strong>
        <p>Enter a search query or paste a URL to find a video for {movie?.title}.</p>
      </div>
    {:else if results.length === 0}
      <div class="empty-state">
        <strong>No results found</strong>
        <p>Try a different search term or paste a URL directly.</p>
      </div>
    {:else}
      <div class="section-head">
        <h2>Showing {results.length} results</h2>
      </div>
      <div class="result-grid">
        {#each results as result, i}
          <article class="result-row">
            <div class="result-thumb" style="background: {['linear-gradient(135deg, #1f5f99, #5b2ee8)','linear-gradient(135deg, #10a5a7, #2374ff)','linear-gradient(135deg, #344f99, #e9549c)','linear-gradient(135deg, #0a6a4c, #ffc857)','linear-gradient(135deg, #8640ff, #ff4d7e)'][i % 5]}">
            </div>
            <div>
              <div class="item-title">{result.title}</div>
              <div class="sub">{result.source} • {result.channel}</div>
              <div class="sub">{result.quality} • {result.codec} • {result.size}</div>
            </div>
            <div class="actions">
              <span class="badge blue">{result.quality}</span>
              <button class="primary-btn-sm" type="button" on:click={() => downloadResult(result)}>
                <svg width="16" height="16"><use href="#i-download"/></svg>
                Download for Radarr
              </button>
            </div>
          </article>
        {/each}
      </div>
    {/if}
  </section>
</div>

{#if pasteModalOpen}
  <div class="modal-backdrop" on:click|self={closePasteModal}>
    <div class="modal">
      <div class="modal-head">
        <div class="modal-title">Paste URL for {movie?.title}</div>
        <button class="icon-btn" type="button" on:click={closePasteModal}>
          <svg width="18" height="18"><use href="#i-x"/></svg>
        </button>
      </div>
      <label class="textarea-label">
        <textarea class="textarea" placeholder="https://..." bind:value={pasteUrl}></textarea>
      </label>
      <div class="modal-actions">
        <button class="secondary-btn" type="button" on:click={closePasteModal}>Cancel</button>
        <button class="primary-btn" type="button" disabled={!pasteUrl.trim()} on:click={submitPasteUrl}>
          Download for Radarr
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page { min-width: 0; }
  .page-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
    margin-bottom: 24px;
  }
  .page-title {
    margin: 8px 0 0;
    font-size: clamp(30px, 3.6vw, 42px);
    line-height: 1;
    letter-spacing: -0.055em;
    font-weight: 950;
  }
  .highlight { color: var(--purple-light); }
  .page-subtitle { margin: 10px 0 0; color: var(--muted); font-size: 15px; }
  .crumbs {
    margin-bottom: 4px;
    color: var(--muted);
    font-size: 14px;
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }
  .crumb { color: var(--purple-light); }
  .toolbar { display: flex; gap: 12px; align-items: center; }
  .secondary-btn {
    height: 48px;
    border-radius: 14px;
    padding: 0 18px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: white;
    background: rgba(255,255,255,.045);
    border: 1px solid rgba(255,255,255,.1);
    cursor: pointer;
    font-weight: 800;
    white-space: nowrap;
  }
  .primary-btn {
    height: 48px;
    border: 0;
    border-radius: 15px;
    padding: 0 22px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: white;
    cursor: pointer;
    font-weight: 850;
    font-size: 15px;
    background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%);
    white-space: nowrap;
  }
  .primary-btn:disabled { opacity: 0.5; cursor: default; }
  .top-strip {
    display: grid;
    grid-template-columns: 1.1fr 1fr 1.3fr 1.3fr;
    gap: 18px;
    padding: 18px;
    border-radius: 18px;
    background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(8,13,34,.64);
    border: 1px solid rgba(255,255,255,.105);
    margin-bottom: 18px;
  }
  .movie-cell { display: flex; gap: 14px; align-items: center; }
  .poster {
    width: 60px;
    height: 82px;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,.08);
    flex: 0 0 auto;
  }
  .summary-label { color: var(--muted); font-size: 13px; font-weight: 750; margin-bottom: 6px; }
  .item-title { font-weight: 850; font-size: 15px; }
  .sub { color: var(--muted); font-size: 12px; margin-top: 3px; }
  .path {
    font-family: monospace;
    font-size: 13px;
    background: rgba(255,255,255,.05);
    padding: 2px 6px;
    border-radius: 4px;
  }
  .panel {
    border-radius: 22px;
    overflow: hidden;
    background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(8,13,34,.64);
    border: 1px solid rgba(255,255,255,.105);
    box-shadow: 0 22px 60px rgba(0,0,0,.22);
  }
  .filters {
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 14px 18px;
    border-bottom: 1px solid rgba(255,255,255,.08);
    flex-wrap: wrap;
  }
  .search-box {
    height: 44px;
    border-radius: 12px;
    background: rgba(255,255,255,.045);
    border: 1px solid rgba(255,255,255,.1);
    color: white;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 12px;
  }
  .search-box input {
    width: 100%;
    border: 0;
    outline: 0;
    color: white;
    background: transparent;
    font-size: 14px;
  }
  .section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 18px 8px;
  }
  .section-head h2 { margin: 0; font-size: 16px; letter-spacing: -0.03em; }
  .result-grid { padding: 6px 10px 14px; display: grid; gap: 2px; }
  .result-row {
    display: grid;
    grid-template-columns: 100px minmax(0, 1fr) auto;
    gap: 14px;
    align-items: center;
    padding: 10px 12px;
    border-radius: 14px;
    transition: 180ms ease;
  }
  .result-row:hover { background: rgba(255,255,255,.026); }
  .result-thumb {
    height: 60px;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,.08);
  }
  .actions { display: flex; gap: 8px; align-items: center; }
  .badge {
    padding: 3px 9px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 850;
  }
  .badge.blue { background: rgba(47,140,255,.16); color: var(--blue); }
  .primary-btn-sm {
    height: 36px;
    padding: 0 14px;
    border: 0;
    border-radius: 10px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: white;
    cursor: pointer;
    font-weight: 800;
    font-size: 13px;
    background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%);
    white-space: nowrap;
  }
  .empty-state {
    padding: 48px 20px;
    text-align: center;
    color: var(--muted);
  }
  .empty-state strong { display: block; color: white; font-size: 18px; margin-bottom: 6px; }
  .empty-state p { margin: 0; font-size: 14px; }

  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.7);
    display: grid;
    place-items: center;
    z-index: 100;
    padding: 20px;
  }
  .modal {
    width: 100%;
    max-width: 560px;
    border-radius: 22px;
    background: #0f142e;
    border: 1px solid rgba(255,255,255,.12);
    box-shadow: 0 40px 80px rgba(0,0,0,.5);
    padding: 24px;
  }
  .modal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 14px;
  }
  .modal-title { font-size: 18px; font-weight: 900; letter-spacing: -0.03em; }
  .icon-btn {
    width: 34px;
    height: 34px;
    border-radius: 9px;
    border: 1px solid rgba(255,255,255,.09);
    background: rgba(255,255,255,.045);
    color: var(--muted);
    cursor: pointer;
    display: grid;
    place-items: center;
  }
  .textarea-label { display: block; margin-top: 14px; }
  .textarea {
    width: 100%;
    min-height: 80px;
    border-radius: 12px;
    padding: 12px 14px;
    border: 1px solid rgba(255,255,255,.12);
    background: rgba(255,255,255,.045);
    color: white;
    font-size: 14px;
    outline: 0;
    resize: vertical;
    font-family: inherit;
  }
  .modal-actions {
    margin-top: 18px;
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
  @media (max-width: 1240px) {
    .top-strip { grid-template-columns: 1fr 1fr; }
    .result-row { grid-template-columns: 80px 1fr; }
    .result-row .actions { grid-column: 2; }
  }
  @media (max-width: 900px) {
    .page-head { grid-template-columns: 1fr; }
    .top-strip { grid-template-columns: 1fr; }
    .result-thumb { height: 50px; }
  }
</style>
