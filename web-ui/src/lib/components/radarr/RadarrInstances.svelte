<script lang="ts">
  import { onMount } from 'svelte';
  import { listRadarrInstances, deleteRadarrInstance, getRadarrSummary, syncRadarrInstance } from '$lib/api/radarr';
  import { showToast } from '$lib/state/toast-state';
  import type { RadarrInstanceResponse, RadarrSummaryResponse } from '$lib/api/types';

  export let navigate: (page: string, data?: any) => void = () => {};

  let instances: RadarrInstanceResponse[] = [];
  let summary: RadarrSummaryResponse | null = null;
  let busy = false;
  let error: string | null = null;
  let searchTerm = '';
  let statusFilter = 'all';
  let syncing = new Set<string>();

  async function load() {
    busy = true; error = null;
    try {
      const [instResp, sumResp] = await Promise.all([
        listRadarrInstances(),
        getRadarrSummary(),
      ]);
      instances = instResp;
      summary = sumResp;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load Radarr instances';
    } finally { busy = false; }
  }

  onMount(load);

  $: filtered = instances.filter(i => {
    const matchesSearch = !searchTerm.trim() || i.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || i.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  async function handleDelete(instance: RadarrInstanceResponse) {
    if (!confirm(`Delete Radarr instance "${instance.name}"?`)) return;
    try {
      await deleteRadarrInstance(instance.id);
      showToast(`Deleted ${instance.name}`);
      load();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Delete failed');
    }
  }

  async function handleSync(instance: RadarrInstanceResponse) {
    syncing.add(instance.id);
    try {
      await syncRadarrInstance(instance.id);
      showToast(`Sync started for ${instance.name}`);
      load();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Sync failed');
    } finally { syncing.delete(instance.id); }
  }

  function editInstance(instance: RadarrInstanceResponse) {
    navigate('radarr-instance-form', { instance });
  }

  function addInstance() {
    navigate('radarr-instance-form', {});
  }

  function openSettings() {
    navigate('radarr-settings', {});
  }

  function viewMissing(instance: RadarrInstanceResponse) {
    navigate('missing-movies', { instance });
  }

  function statusBadge(status: string): string {
    if (status === 'connected') return 'green';
    if (status === 'warning') return 'yellow';
    if (status === 'error') return 'red';
    return 'muted';
  }
</script>

<div class="page">
  <header class="page-head">
    <div>
      <h1 class="page-title">Radarr</h1>
      <p class="page-subtitle">Manage multiple Radarr instances and download missing movies.</p>
    </div>
    <div class="toolbar">
      <button class="secondary-btn" type="button" on:click={openSettings}>
        <svg width="18" height="18"><use href="#i-gear"/></svg>
        <span class="btn-label">Radarr Settings</span>
      </button>
      <button class="primary-btn" type="button" on:click={addInstance}>
        <svg width="18" height="18"><use href="#i-plus"/></svg>
        <span class="btn-label">Add Radarr Instance</span>
      </button>
    </div>
  </header>

  {#if error}
    <div class="error-box">{error}</div>
  {/if}

  {#if summary}
    <section class="summary-grid">
      <article class="summary-card">
        <div class="summary-icon purple">
          <svg width="26" height="26"><use href="#i-radarr"/></svg>
        </div>
        <div>
          <div class="summary-label">Total Instances</div>
          <div class="summary-number">{summary.totalInstances}</div>
          <div class="summary-sub">Active connections</div>
        </div>
      </article>
      <article class="summary-card">
        <div class="summary-icon red">
          <svg width="26" height="26"><use href="#i-video"/></svg>
        </div>
        <div>
          <div class="summary-label">Missing Movies</div>
          <div class="summary-number">{summary.missingMovies}</div>
          <div class="summary-sub">Across all instances</div>
        </div>
      </article>
      <article class="summary-card">
        <div class="summary-icon green">
          <svg width="26" height="26"><use href="#i-check"/></svg>
        </div>
        <div>
          <div class="summary-label">Monitored</div>
          <div class="summary-number">{summary.monitoredMovies}</div>
          <div class="summary-sub">Total monitored</div>
        </div>
      </article>
      <article class="summary-card">
        <div class="summary-icon blue">
          <svg width="26" height="26"><use href="#i-refresh"/></svg>
        </div>
        <div>
          <div class="summary-label">Last Sync</div>
          <div class="summary-number">{summary.lastSyncAt ? new Date(summary.lastSyncAt).toLocaleString() : '—'}</div>
          <div class="summary-sub">All instances</div>
        </div>
      </article>
      <article class="summary-card">
        <div class="summary-icon purple">
          <svg width="26" height="26"><use href="#i-download"/></svg>
        </div>
        <div>
          <div class="summary-label">Imports (24h)</div>
          <div class="summary-number">{summary.imports24h}</div>
          <div class="summary-sub">Successful imports</div>
        </div>
      </article>
    </section>
  {/if}

  <section class="panel">
    <div class="section-head">
      <h2>Radarr Instances <span class="muted">({filtered.length})</span></h2>
      <div class="toolbar">
        <label class="search-box">
          <svg width="18" height="18"><use href="#i-search"/></svg>
          <input type="search" placeholder="Search instances..." bind:value={searchTerm} />
        </label>
        <label class="select-box">
          <svg width="18" height="18"><use href="#i-filter"/></svg>
          <select bind:value={statusFilter}>
            <option value="all">All Statuses</option>
            <option value="connected">Connected</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
        </label>
      </div>
    </div>

    {#if busy && instances.length === 0}
      <div class="loading-state"><strong>Loading instances…</strong></div>
    {:else if filtered.length === 0}
      <div class="empty-state">
        <strong>No Radarr instances found</strong>
        <p>Add a Radarr instance to get started.</p>
      </div>
    {:else}
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>URL</th>
              <th>Status</th>
              <th>Version</th>
              <th>Missing</th>
              <th>Last Sync</th>
              <th style="text-align:right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each filtered as instance}
              <tr>
                <td>
                  <div class="instance-cell">
                    <div class="instance-icon">
                      <svg width="24" height="24"><use href="#i-radarr"/></svg>
                    </div>
                    <div>
                      <div class="item-title">
                        {instance.name}
                        {#if instance.isDefault}
                          <span class="badge blue">Default</span>
                        {/if}
                      </div>
                      <div class="sub">
                        <span class="path">{instance.tubeWritePath}</span> <b>(Tube)</b>
                      </div>
                      <div class="sub">
                        <span class="path">{instance.radarrImportPath}</span> <b>(Radarr)</b>
                      </div>
                    </div>
                  </div>
                </td>
                <td><span class="url-cell">{instance.baseUrl}</span></td>
                <td>
                  <span class="badge {statusBadge(instance.status)}">
                    <span class="dot"></span>
                    {instance.status === 'connected' ? 'Connected' : instance.status === 'warning' ? 'Warning' : instance.status === 'error' ? 'Error' : 'Unknown'}
                  </span>
                  {#if instance.healthMessage}
                    <div class="sub">{instance.healthMessage}</div>
                  {/if}
                </td>
                <td>{instance.radarrVersion || '—'}</td>
                <td>
                  <b class="missing-count">{'—'}</b>
                  <div class="sub">Monitored: —</div>
                </td>
                <td>
                  {instance.lastSyncAt ? new Date(instance.lastSyncAt).toLocaleString() : '—'}
                  <div class="sub">Path {instance.status === 'connected' ? 'verified' : 'warning'}</div>
                </td>
                <td>
                  <div class="actions">
                    <button class="icon-btn" title="Missing movies" on:click={() => viewMissing(instance)}>
                      <svg width="18" height="18"><use href="#i-search"/></svg>
                    </button>
                    <button class="icon-btn" title="Edit" on:click={() => editInstance(instance)}>
                      <svg width="18" height="18"><use href="#i-gear"/></svg>
                    </button>
                    <button class="icon-btn" title="Sync" disabled={syncing.has(instance.id)} on:click={() => handleSync(instance)}>
                      <svg width="18" height="18"><use href="#i-refresh"/></svg>
                    </button>
                    <button class="icon-btn" title="Delete" on:click={() => handleDelete(instance)}>
                      <svg width="18" height="18"><use href="#i-trash"/></svg>
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>

</div>

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
    margin: 0;
    font-size: clamp(30px, 3.6vw, 42px);
    line-height: 1;
    letter-spacing: -0.055em;
    font-weight: 950;
  }
  .page-subtitle {
    margin: 10px 0 0;
    color: var(--muted);
    font-size: 15px;
  }
  .toolbar {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
  }
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
    transition: 180ms ease;
  }
  .secondary-btn:hover {
    background: rgba(255,255,255,.075);
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
    letter-spacing: -0.02em;
    font-size: 15px;
    background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%);
    box-shadow: 0 16px 30px rgba(99, 49, 255, 0.34), inset 0 1px 0 rgba(255, 255, 255, 0.38), inset 0 -8px 14px rgba(39, 8, 143, 0.44);
    transition: 180ms ease;
    white-space: nowrap;
  }
  .primary-btn:hover {
    transform: translateY(-1px);
  }
  .error-box {
    margin-bottom: 16px;
    padding: 12px 18px;
    border-radius: 14px;
    background: rgba(255,77,126,.12);
    border: 1px solid rgba(255,77,126,.2);
    color: var(--red);
    font-size: 14px;
    font-weight: 750;
  }
  .summary-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 14px;
    margin-bottom: 18px;
  }
  .summary-card {
    min-height: 100px;
    padding: 18px;
    border-radius: 18px;
    background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(255,255,255,.035);
    border: 1px solid rgba(255,255,255,.095);
    display: flex;
    align-items: center;
    gap: 15px;
  }
  .summary-icon {
    width: 50px;
    height: 50px;
    border-radius: 16px;
    display: grid;
    place-items: center;
    flex: 0 0 auto;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.28);
  }
  .summary-icon.purple { background: rgba(124, 60, 255, 0.2); color: var(--purple-light); }
  .summary-icon.red { background: rgba(255, 77, 126, 0.14); color: var(--red); }
  .summary-icon.green { background: rgba(20, 216, 148, 0.14); color: var(--green); }
  .summary-icon.blue { background: rgba(47, 140, 255, 0.14); color: var(--blue); }
  .summary-number { font-size: 26px; line-height: 1; font-weight: 950; letter-spacing: -0.05em; }
  .summary-label { margin-top: 4px; color: var(--muted); font-size: 14px; font-weight: 700; }
  .summary-sub { margin-top: 4px; color: #737b9f; font-size: 13px; }
  .panel {
    border-radius: 22px;
    overflow: hidden;
    background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(8, 13, 34, 0.64);
    border: 1px solid rgba(255, 255, 255, 0.105);
    box-shadow: 0 22px 60px rgba(0,0,0,.22);
  }
  .section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 16px 18px;
  }
  .section-head h2 {
    margin: 0;
    font-size: 18px;
    letter-spacing: -0.03em;
  }
  .muted { color: var(--muted); }
  .search-box, .select-box {
    height: 44px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: white;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 12px;
  }
  .search-box { width: min(240px, 20vw); }
  .search-box input {
    width: 100%;
    border: 0;
    outline: 0;
    color: white;
    background: transparent;
    font-size: 14px;
  }
  .search-box input::placeholder { color: rgba(210, 212, 238, 0.55); }
  .select-box select {
    border: 0;
    outline: 0;
    color: white;
    background: transparent;
    appearance: none;
    cursor: pointer;
    font-size: 13px;
  }
  .table { width: 100%; border-collapse: collapse; }
  .table th, .table td {
    padding: 13px 18px;
    border-bottom: 1px solid rgba(255,255,255,.07);
    text-align: left;
  }
  .table th {
    color: var(--muted);
    font-size: 13px;
    font-weight: 850;
    background: rgba(255,255,255,.025);
    white-space: nowrap;
  }
  .instance-cell {
    display: grid;
    grid-template-columns: 40px minmax(0, 1fr);
    gap: 12px;
    align-items: center;
    min-width: 0;
  }
  .instance-icon {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: rgba(124,60,255,.16);
    color: var(--purple-light);
    display: grid;
    place-items: center;
  }
  .item-title {
    font-weight: 850;
    font-size: 15px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .sub {
    margin-top: 3px;
    color: var(--muted);
    font-size: 12px;
  }
  .path {
    font-family: monospace;
    font-size: 12px;
    background: rgba(255,255,255,.05);
    padding: 1px 5px;
    border-radius: 4px;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 9px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 850;
  }
  .badge.green { background: rgba(20,216,148,.16); color: var(--green); }
  .badge.blue { background: rgba(47,140,255,.16); color: var(--blue); }
  .badge.yellow { background: rgba(255,200,87,.16); color: #ffc857; }
  .badge.red { background: rgba(255,77,126,.16); color: var(--red); }
  .badge.muted { background: rgba(169,175,208,.12); color: var(--muted); }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: currentColor;
  }
  .url-cell {
    color: #62a8ff;
    font-size: 13px;
  }
  .missing-count {
    color: var(--red);
    font-size: 18px;
  }
  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
  .icon-btn {
    width: 38px;
    height: 38px;
    border-radius: 11px;
    border: 1px solid rgba(255,255,255,.09);
    background: rgba(255,255,255,.045);
    color: var(--muted);
    cursor: pointer;
    display: grid;
    place-items: center;
    transition: 180ms ease;
  }
  .icon-btn:hover { color: white; background: rgba(124,60,255,.18); border-color: rgba(167,134,255,.25); }
  .icon-btn:disabled { opacity: 0.4; cursor: default; }
  .loading-state, .empty-state {
    padding: 48px 20px;
    text-align: center;
    color: var(--muted);
  }
  .empty-state strong { display: block; color: white; font-size: 18px; margin-bottom: 6px; }
  .empty-state p { margin: 0; font-size: 14px; }
  @media (max-width: 1240px) {
    .summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  }
  @media (max-width: 900px) {
    .page-head { grid-template-columns: 1fr; }
    .toolbar { justify-content: flex-start; }
    .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .search-box { width: 100%; }
  }
  @media (max-width: 680px) {
    .summary-grid { grid-template-columns: 1fr; }
    .table th:nth-child(3), .table td:nth-child(3),
    .table th:nth-child(4), .table td:nth-child(4),
    .table th:nth-child(6), .table td:nth-child(6) { display: none; }
    .instance-cell { grid-template-columns: 36px 1fr; }
    .icon-btn { width: 34px; height: 34px; }
    .btn-label { display: none; }
  }
</style>
