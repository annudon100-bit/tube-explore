<script lang="ts">
  import { onMount } from 'svelte';
  import { listMissingArrItems, syncArrInstance, downloadForArr, listSonarrPlaylistMappings } from '$lib/api/arr';
  import { showToast } from '$lib/state/toast-state';
  import type { ArrInstanceResponse, ArrMissingItem } from '$lib/api/types';
  import type { PlaylistMappingResponse } from '$lib/api/arr';

  export let navigate: (page: string, data?: any) => void = () => {};
  export let instance: ArrInstanceResponse | null = null;

  let items: ArrMissingItem[] = [];
  let total = 0;
  let busy = false;
  let error: string | null = null;
  let searchTerm = '';
  let monFilter = 'all';
  let limit = 50;
  let offset = 0;
  let syncing = false;

  let modalItem: ArrMissingItem | null = null;
  let pasteUrl = '';
  let playlistMappings: PlaylistMappingResponse[] = [];
  let loadingMappings = false;

  onMount(() => { load(); loadPlaylistMappings(); });

  async function loadPlaylistMappings() {
    if (!instance) return;
    loadingMappings = true;
    try {
      const resp = await listSonarrPlaylistMappings(instance.id, { limit: 20, offset: 0 });
      playlistMappings = resp.mappings;
    } catch { playlistMappings = []; }
    finally { loadingMappings = false; }
  }

  async function load() {
    if (!instance) return;
    busy = true; error = null;
    try {
      const resp = await listMissingArrItems(instance.id, {
        limit,
        offset,
        search: searchTerm || undefined,
      });
      items = resp.items;
      total = resp.total;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load missing episodes';
      items = [];
      total = 0;
    } finally { busy = false; }
  }

  $: loadKey = `${instance?.id}:${limit}:${offset}:${searchTerm}:${monFilter}`;
  $: if (loadKey && instance) load();

  async function handleSync() {
    if (!instance) return;
    syncing = true;
    try {
      await syncArrInstance(instance.id);
      showToast(`Sync started for ${instance.name}`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Sync failed');
    } finally { syncing = false; }
  }

  function searchEpisode(item: ArrMissingItem) {
    navigate('sonarr-search-context', { instance, episode: item });
  }

  function openPasteModal(item: ArrMissingItem) {
    modalItem = item;
    pasteUrl = '';
  }

  function closePasteModal() {
    modalItem = null;
    pasteUrl = '';
  }

  async function submitPasteUrl() {
    if (!modalItem || !pasteUrl.trim()) return;
    try {
      await downloadForArr({
        url: pasteUrl,
        instanceId: instance?.id,
        itemId: modalItem.itemId,
        itemTitle: modalItem.title,
        kind: 'sonarr',
      });
      showToast('Download started for Sonarr');
      navigate('downloads');
      closePasteModal();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Download failed');
    }
  }

  function openSonarr(item: ArrMissingItem) {
    if (item.arrUrl) {
      window.open(item.arrUrl, '_blank', 'noopener,noreferrer');
    }
  }

  function prevPage() { offset = Math.max(0, offset - limit); }
  function nextPage() { offset += limit; }

  $: pageCount = Math.max(1, Math.ceil(total / limit));
  $: currentPageNum = Math.min(pageCount, Math.floor(offset / limit) + 1);
</script>

<div class="page">
  <header class="page-head">
    <div>
      <div class="crumbs">
        <span class="crumb">Sonarr</span> ›
        <b>{instance?.name || 'Instance'}</b> ›
        <span>Missing Episodes</span>
      </div>
      <h1 class="page-title">Missing Episodes</h1>
      <p class="page-subtitle">These episodes are missing from Sonarr and can be downloaded to your library.</p>
    </div>
    <div class="toolbar">
      <button class="secondary-btn" type="button" on:click={() => instance?.baseUrl && window.open(instance.baseUrl, '_blank', 'noopener,noreferrer')}>
        <svg width="18" height="18"><use href="#i-external"/></svg>
        Open in Sonarr
      </button>
      <button class="primary-btn" type="button" disabled={syncing} on:click={handleSync}>
        <svg width="18" height="18"><use href={syncing ? '#i-refresh' : '#i-refresh'}/></svg>
        {syncing ? 'Syncing…' : 'Sync Now'}
      </button>
    </div>
  </header>

  {#if error}
    <div class="error-box">{error}</div>
  {/if}

  <div class="split-layout">
    <div>
      {#if instance}
        <section class="top-strip">
          <div>
            <div class="summary-label">Sonarr Instance</div>
            <div class="item-title">{instance.name}</div>
          </div>
          <div>
            <div class="summary-label">Status</div>
            <span class="badge {instance.status === 'connected' ? 'green' : 'yellow'}">
              <span class="dot"></span>
              {instance.status === 'connected' ? 'Connected' : 'Warning'}
            </span>
            <div class="summary-sub">Last sync: {instance.lastSyncAt ? new Date(instance.lastSyncAt).toLocaleString() : 'never'}</div>
          </div>
          <div>
            <div class="summary-label">Version</div>
            <div>{instance.arrVersion || '—'}</div>
          </div>
          <div>
            <div class="summary-label">Missing Episodes</div>
            <div class="summary-number red">{total}</div>
          </div>
        </section>
      {/if}

      <section class="panel">
        <div class="filters">
          <label class="search-box">
            <svg width="18" height="18"><use href="#i-search"/></svg>
            <input type="search" placeholder="Search episodes..." bind:value={searchTerm} />
          </label>
          <label class="select-box">
            <select bind:value={monFilter}>
              <option value="all">Monitored: All</option>
              <option value="monitored">Monitored</option>
              <option value="unmonitored">Unmonitored</option>
            </select>
          </label>
        </div>

        {#if busy && items.length === 0}
          <div class="loading-state"><strong>Loading episodes…</strong></div>
        {:else if items.length === 0}
          <div class="empty-state"><strong>No missing episodes found</strong></div>
        {:else}
          <div class="table-wrap">
            <table class="table">
              <thead>
                <tr>
                  <th>Episode</th>
                  <th>Series</th>
                  <th>Season / Ep</th>
                  <th>Air Date</th>
                  <th>Status</th>
                  <th style="text-align:right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {#each items as item}
                  <tr>
                    <td>
                      <div class="episode-cell">
                        <div class="poster" style="background: linear-gradient(135deg, #1f5f99, #5b2ee8)"></div>
                        <div>
                          <div class="item-title">{item.title}</div>
                          <div class="sub">{item.overview ? item.overview.slice(0, 80) + '…' : ''}</div>
                        </div>
                      </div>
                    </td>
                    <td>{item.seriesTitle || '—'}</td>
                    <td>
                      <span class="badge blue">S{String(item.seasonNumber ?? '?').padStart(2, '0')}E{String(item.episodeNumber ?? '?').padStart(2, '0')}</span>
                    </td>
                    <td>{item.airDate ? new Date(item.airDate).toLocaleDateString() : '—'}</td>
                    <td>
                      <span class="badge {item.monitored ? 'green' : 'muted'}">{item.monitored ? 'Monitored' : 'Unmonitored'}</span>
                    </td>
                    <td>
                      <div class="actions">
                        <button class="primary-btn-sm" type="button" on:click={() => searchEpisode(item)}>
                          <svg width="16" height="16"><use href="#i-search"/></svg>
                          Search
                        </button>
                        <button class="secondary-btn-sm" type="button" on:click={() => openPasteModal(item)}>
                          <svg width="16" height="16"><use href="#i-link"/></svg>
                          Paste URL
                        </button>
                        <button class="icon-btn" type="button" title="Open in Sonarr" on:click={() => openSonarr(item)}>
                          <svg width="16" height="16"><use href="#i-external"/></svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <footer class="panel-footer">
            <span>Showing {offset + 1} to {Math.min(offset + limit, total)} of {total} results</span>
            <div class="pagination">
              <button class="page-btn" type="button" disabled={offset === 0} on:click={prevPage}>‹</button>
              <button class="page-btn active" type="button">{currentPageNum}</button>
              {#if pageCount > 1}
                <button class="page-btn" type="button" disabled={offset + limit >= total} on:click={nextPage}>›</button>
              {/if}
            </div>
          </footer>
        {/if}
      </section>

      <section class="panel" style="margin-top:18px">
        <div class="section-head">
          <h2>Playlist Mappings ({playlistMappings.length})</h2>
          <button class="primary-btn-sm" type="button" on:click={() => navigate('sonarr-playlist-mapping', {})}>
            <svg width="16" height="16"><use href="#i-plus"/></svg>
            New
          </button>
        </div>
        {#if loadingMappings}
          <div class="loading-state"><strong>Loading mappings…</strong></div>
        {:else if playlistMappings.length === 0}
          <div class="empty-state-sm"><strong>No playlist mappings yet</strong></div>
        {:else}
          <div class="map-list">
            {#each playlistMappings as pm}
              <div class="map-row">
                <div class="map-info">
                  <div class="map-name">{pm.name}</div>
                  <div class="map-meta">{pm.seriesTitle} — {new Date(pm.createdAt).toLocaleDateString()}</div>
                </div>
                <span class="badge {pm.status === 'completed' ? 'green' : pm.status === 'draft' ? 'yellow' : 'muted'}">{pm.status}</span>
                <div class="map-actions">
                  <button class="secondary-btn-sm" type="button" on:click={() => navigate('sonarr-playlist-mapping', { mapping: pm })}>Edit</button>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    </div>
  </div>
</div>

{#if modalItem}
  <div class="modal-backdrop" on:click|self={closePasteModal}>
    <div class="modal">
      <div class="modal-head">
        <div class="modal-title">Paste URL for {modalItem.title}</div>
        <button class="icon-btn" type="button" on:click={closePasteModal}>
          <svg width="18" height="18"><use href="#i-x"/></svg>
        </button>
      </div>
      <p class="page-subtitle">Download will be linked to <b>{modalItem.title}</b> and imported to {instance?.name}.</p>
      <label class="textarea-label">
        <textarea class="textarea" placeholder="https://..." bind:value={pasteUrl}></textarea>
      </label>
      <div class="modal-actions">
        <button class="secondary-btn" type="button" on:click={closePasteModal}>Cancel</button>
        <button class="primary-btn" type="button" disabled={!pasteUrl.trim()} on:click={submitPasteUrl}>Start Download</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page { min-width: 0; }
  .page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
  .page-title { margin: 8px 0 0; font-size: clamp(30px, 3.6vw, 42px); line-height: 1; letter-spacing: -0.055em; font-weight: 950; }
  .page-subtitle { margin: 10px 0 0; color: var(--muted); font-size: 15px; }
  .crumbs { margin-bottom: 4px; color: var(--muted); font-size: 14px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  .crumb { color: var(--purple-light); }
  .toolbar { display: flex; gap: 12px; align-items: center; }
  .secondary-btn { height: 48px; border-radius: 14px; padding: 0 18px; display: inline-flex; align-items: center; gap: 10px; color: white; background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.1); cursor: pointer; font-weight: 800; white-space: nowrap; transition: 180ms ease; }
  .secondary-btn:hover { background: rgba(255,255,255,.075); }
  .primary-btn { height: 48px; border: 0; border-radius: 15px; padding: 0 22px; display: inline-flex; align-items: center; gap: 10px; color: white; cursor: pointer; font-weight: 850; letter-spacing: -0.02em; font-size: 15px; background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%); box-shadow: 0 16px 30px rgba(99,49,255,.34), inset 0 1px 0 rgba(255,255,255,.38), inset 0 -8px 14px rgba(39,8,143,.44); transition: 180ms ease; white-space: nowrap; }
  .primary-btn:disabled { opacity: 0.5; cursor: default; }
  .error-box { margin-bottom: 16px; padding: 12px 18px; border-radius: 14px; background: rgba(255,77,126,.12); border: 1px solid rgba(255,77,126,.2); color: var(--red); font-size: 14px; font-weight: 750; }
  .split-layout { display: grid; grid-template-columns: 1fr; gap: 24px; align-items: start; }
  .top-strip { display: grid; grid-template-columns: 1.1fr 1fr 1fr 1fr; gap: 18px; padding: 18px; border-radius: 18px; background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(8,13,34,.64); border: 1px solid rgba(255,255,255,.105); margin-bottom: 18px; }
  .summary-label { color: var(--muted); font-size: 13px; font-weight: 750; margin-bottom: 6px; }
  .summary-number { font-size: 24px; font-weight: 950; letter-spacing: -0.04em; }
  .summary-number.red { color: var(--red); }
  .summary-sub { margin-top: 4px; color: #737b9f; font-size: 13px; }
  .item-title { font-weight: 850; font-size: 15px; }
  .badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 8px; font-size: 12px; font-weight: 850; }
  .badge.green { background: rgba(20,216,148,.16); color: var(--green); }
  .badge.blue { background: rgba(47,140,255,.16); color: var(--blue); }
  .badge.yellow { background: rgba(255,200,87,.16); color: #ffc857; }
  .badge.muted { background: rgba(169,175,208,.12); color: var(--muted); }
  .dot { width: 8px; height: 8px; border-radius: 999px; background: currentColor; }
  .panel { border-radius: 22px; overflow: hidden; background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(8,13,34,.64); border: 1px solid rgba(255,255,255,.105); box-shadow: 0 22px 60px rgba(0,0,0,.22); }
  .filters { display: flex; gap: 12px; align-items: center; padding: 14px 18px; border-bottom: 1px solid rgba(255,255,255,.08); flex-wrap: wrap; }
  .search-box, .select-box { height: 40px; border-radius: 10px; background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.1); color: white; display: flex; align-items: center; gap: 8px; padding: 0 12px; }
  .search-box { width: min(280px, 24vw); flex: 1; }
  .search-box input { width: 100%; border: 0; outline: 0; color: white; background: transparent; font-size: 14px; }
  .select-box select { border: 0; outline: 0; color: white; background: transparent; appearance: none; cursor: pointer; font-size: 13px; }
  .table { width: 100%; border-collapse: collapse; }
  .table th, .table td { padding: 12px 18px; border-bottom: 1px solid rgba(255,255,255,.07); text-align: left; }
  .table th { color: var(--muted); font-size: 13px; font-weight: 850; background: rgba(255,255,255,.025); white-space: nowrap; }
  .episode-cell { display: grid; grid-template-columns: 60px minmax(0, 1fr); gap: 12px; align-items: center; min-width: 0; }
  .poster { width: 60px; height: 82px; border-radius: 8px; overflow: hidden; border: 1px solid rgba(255,255,255,.08); flex: 0 0 auto; }
  .sub { color: var(--muted); font-size: 12px; margin-top: 3px; }
  .actions { display: flex; gap: 6px; justify-content: flex-end; flex-wrap: wrap; }
  .primary-btn-sm { height: 34px; padding: 0 12px; border: 0; border-radius: 9px; display: inline-flex; align-items: center; gap: 6px; color: white; cursor: pointer; font-weight: 800; font-size: 13px; background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%); white-space: nowrap; }
  .secondary-btn-sm { height: 34px; padding: 0 12px; border-radius: 9px; border: 1px solid rgba(255,255,255,.1); background: rgba(255,255,255,.045); color: white; cursor: pointer; font-weight: 800; font-size: 13px; white-space: nowrap; }
  .icon-btn { width: 34px; height: 34px; border-radius: 9px; border: 1px solid rgba(255,255,255,.09); background: rgba(255,255,255,.045); color: var(--muted); cursor: pointer; display: grid; place-items: center; transition: 180ms ease; }
  .icon-btn:hover { color: white; background: rgba(124,60,255,.18); }
  .panel-footer { padding: 14px 18px; display: flex; align-items: center; justify-content: space-between; color: var(--muted); font-size: 14px; }
  .pagination { display: flex; gap: 8px; align-items: center; }
  .page-btn { width: 34px; height: 34px; border-radius: 10px; border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.035); color: var(--muted); cursor: pointer; }
  .page-btn.active { color: white; background: var(--purple); }
  .page-btn:disabled { opacity: 0.3; cursor: default; }
  .loading-state, .empty-state { padding: 48px 20px; text-align: center; color: var(--muted); }
  .empty-state strong { display: block; color: white; font-size: 18px; margin-bottom: 6px; }
  .empty-state-sm { padding: 32px 20px; text-align: center; color: var(--muted); font-size: 14px; }
  .empty-state-sm strong { color: white; }
  .section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 18px; border-bottom: 1px solid rgba(255,255,255,.08); }
  .section-head h2 { margin: 0; font-size: 16px; letter-spacing: -0.03em; }
  .map-list { display: grid; padding: 6px 10px 14px; }
  .map-row { display: grid; grid-template-columns: 1fr auto auto; gap: 14px; align-items: center; padding: 10px 12px; border-radius: 12px; transition: 180ms ease; }
  .map-row:hover { background: rgba(255,255,255,.026); }
  .map-name { font-weight: 800; font-size: 14px; }
  .map-meta { color: var(--muted); font-size: 12px; margin-top: 2px; }
  .map-actions { display: flex; gap: 6px; }
  .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.7); display: grid; place-items: center; z-index: 100; padding: 20px; }
  .modal { width: 100%; max-width: 560px; border-radius: 22px; background: #0f142e; border: 1px solid rgba(255,255,255,.12); box-shadow: 0 40px 80px rgba(0,0,0,.5); padding: 24px; }
  .modal-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
  .modal-title { font-size: 18px; font-weight: 900; letter-spacing: -0.03em; }
  .textarea-label { display: block; margin-top: 14px; }
  .textarea { width: 100%; min-height: 80px; border-radius: 12px; padding: 12px 14px; border: 1px solid rgba(255,255,255,.12); background: rgba(255,255,255,.045); color: white; font-size: 14px; outline: 0; resize: vertical; font-family: inherit; }
  .textarea:focus { border-color: rgba(167,134,255,.4); }
  .modal-actions { margin-top: 18px; display: flex; justify-content: flex-end; gap: 12px; }
  @media (max-width: 1240px) { .top-strip { grid-template-columns: 1fr 1fr; } }
  @media (max-width: 900px) { .page-head { grid-template-columns: 1fr; } .top-strip { grid-template-columns: 1fr 1fr; } .table th:nth-child(2), .table td:nth-child(2) { display: none; } }
  @media (max-width: 680px) { .episode-cell { grid-template-columns: 48px 1fr; } .poster { width: 48px; height: 66px; } .actions { flex-wrap: wrap; } }
</style>
