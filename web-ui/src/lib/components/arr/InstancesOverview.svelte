<script lang="ts">
  import { onMount } from 'svelte';
  import { getArrSummary } from '$lib/api/arr';
  import { listArrInstances } from '$lib/api/arr';
  import type { ArrSummaryResponse, ArrInstanceResponse } from '$lib/api/types';

  export let navigate: (page: string, data?: any) => void = () => {};

  let summary: ArrSummaryResponse | null = null;
  let radarrCount = 0;
  let sonarrCount = 0;
  let busy = false;
  let error: string | null = null;

  onMount(async () => {
    busy = true;
    try {
      const [summ, instances] = await Promise.all([
        getArrSummary().catch(() => null),
        listArrInstances().catch(() => [] as ArrInstanceResponse[]),
      ]);
      summary = summ;
      radarrCount = instances.filter(i => i.kind === 'radarr').length;
      sonarrCount = instances.filter(i => i.kind === 'sonarr').length;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    } finally { busy = false; }
  });
</script>

<div class="page">
  <header class="page-head">
    <div>
      <h1 class="page-title">Instances</h1>
      <p class="page-subtitle">Manage your Radarr and Sonarr connections for automated media imports.</p>
    </div>
  </header>

  {#if error}
    <div class="error-box">{error}</div>
  {/if}

  {#if summary}
    <section class="summary-grid">
      <article class="summary-card">
        <div class="summary-icon purple"><svg width="26" height="26"><use href="#i-box"/></svg></div>
        <div>
          <div class="summary-label">Total Instances</div>
          <div class="summary-number">{summary.totalInstances}</div>
          <div class="summary-sub">Across all integrations</div>
        </div>
      </article>
      <article class="summary-card">
        <div class="summary-icon green"><svg width="26" height="26"><use href="#i-check"/></svg></div>
        <div>
          <div class="summary-label">Connected</div>
          <div class="summary-number">{summary.activeConnections}</div>
          <div class="summary-sub">Healthy instances</div>
        </div>
      </article>
      <article class="summary-card">
        <div class="summary-icon red"><svg width="26" height="26"><use href="#i-video"/></svg></div>
        <div>
          <div class="summary-label">Missing</div>
          <div class="summary-number">{summary.missingItems}</div>
          <div class="summary-sub">Across all instances</div>
        </div>
      </article>
      <article class="summary-card">
        <div class="summary-icon blue"><svg width="26" height="26"><use href="#i-refresh"/></svg></div>
        <div>
          <div class="summary-label">Last Sync</div>
          <div class="summary-number">{summary.lastSyncAt ? new Date(summary.lastSyncAt).toLocaleString() : '—'}</div>
          <div class="summary-sub">All instances</div>
        </div>
      </article>
      <article class="summary-card">
        <div class="summary-icon purple"><svg width="26" height="26"><use href="#i-download"/></svg></div>
        <div>
          <div class="summary-label">Imports (24h)</div>
          <div class="summary-number">{summary.imports24h}</div>
          <div class="summary-sub">Successful imports</div>
        </div>
      </article>
    </section>
  {/if}

  <div class="integration-grid">
    <article class="integration-card">
      <div class="integration-head">
        <div class="integration-icon radarr"><svg width="28" height="28"><use href="#i-radarr"/></svg></div>
        <div>
          <h2>Radarr</h2>
          <p class="sub">{radarrCount} instance{radarrCount !== 1 ? 's' : ''} configured</p>
        </div>
      </div>
      <p class="integration-desc">Manage movie downloads and import completed files into your Radarr library.</p>
      <div class="integration-actions">
        <button class="primary-btn" type="button" on:click={() => navigate('instances-radarr')}>
          <svg width="18" height="18"><use href="#i-radarr"/></svg>
          Open Radarr
        </button>
        {#if radarrCount === 0}
          <button class="secondary-btn" type="button" on:click={() => navigate('radarr-instance-form', {})}>
            <svg width="18" height="18"><use href="#i-plus"/></svg>
            Add Instance
          </button>
        {:else}
          <button class="secondary-btn" type="button" on:click={() => navigate('radarr-instance-form', {})}>
            <svg width="18" height="18"><use href="#i-plus"/></svg>
            Add Another
          </button>
        {/if}
      </div>
    </article>

    <article class="integration-card">
      <div class="integration-head">
        <div class="integration-icon sonarr"><svg width="28" height="28"><use href="#i-sonarr"/></svg></div>
        <div>
          <h2>Sonarr</h2>
          <p class="sub">{sonarrCount} instance{sonarrCount !== 1 ? 's' : ''} configured</p>
        </div>
      </div>
      <p class="integration-desc">Manage TV series episode downloads and import completed files into your Sonarr library.</p>
      <div class="integration-actions">
        <button class="primary-btn" type="button" on:click={() => navigate('instances-sonarr')}>
          <svg width="18" height="18"><use href="#i-sonarr"/></svg>
          Open Sonarr
        </button>
        {#if sonarrCount === 0}
          <button class="secondary-btn" type="button" on:click={() => navigate('sonarr-instance-form', {})}>
            <svg width="18" height="18"><use href="#i-plus"/></svg>
            Add Instance
          </button>
        {:else}
          <button class="secondary-btn" type="button" on:click={() => navigate('sonarr-instance-form', {})}>
            <svg width="18" height="18"><use href="#i-plus"/></svg>
            Add Another
          </button>
        {/if}
      </div>
    </article>
  </div>
</div>

<style>
  .page { min-width: 0; }
  .page-head { margin-bottom: 24px; }
  .page-title { margin: 0; font-size: clamp(30px, 3.6vw, 42px); line-height: 1; letter-spacing: -0.055em; font-weight: 950; }
  .page-subtitle { margin: 10px 0 0; color: var(--muted); font-size: 15px; }
  .error-box { margin-bottom: 16px; padding: 12px 18px; border-radius: 14px; background: rgba(255,77,126,.12); border: 1px solid rgba(255,77,126,.2); color: var(--red); font-size: 14px; font-weight: 750; }
  .summary-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin-bottom: 24px; }
  .summary-card { min-height: 100px; padding: 18px; border-radius: 18px; background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(255,255,255,.035); border: 1px solid rgba(255,255,255,.095); display: flex; align-items: center; gap: 15px; }
  .summary-icon { width: 50px; height: 50px; border-radius: 16px; display: grid; place-items: center; flex: 0 0 auto; box-shadow: inset 0 1px 0 rgba(255,255,255,.28); }
  .summary-icon.purple { background: rgba(124, 60, 255, 0.2); color: var(--purple-light); }
  .summary-icon.red { background: rgba(255, 77, 126, 0.14); color: var(--red); }
  .summary-icon.green { background: rgba(20, 216, 148, 0.14); color: var(--green); }
  .summary-icon.blue { background: rgba(47, 140, 255, 0.14); color: var(--blue); }
  .summary-number { font-size: 26px; line-height: 1; font-weight: 950; letter-spacing: -0.05em; }
  .summary-label { margin-top: 4px; color: var(--muted); font-size: 14px; font-weight: 700; }
  .summary-sub { margin-top: 4px; color: #737b9f; font-size: 13px; }
  .integration-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  .integration-card { padding: 24px; border-radius: 22px; background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(8,13,34,.64); border: 1px solid rgba(255,255,255,.105); }
  .integration-head { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
  .integration-head h2 { margin: 0; font-size: 22px; letter-spacing: -0.04em; }
  .integration-icon { width: 54px; height: 54px; border-radius: 16px; display: grid; place-items: center; flex: 0 0 auto; box-shadow: inset 0 1px 0 rgba(255,255,255,.28); }
  .integration-icon.radarr { background: rgba(124, 60, 255, 0.2); color: var(--purple-light); }
  .integration-icon.sonarr { background: rgba(47, 140, 255, 0.2); color: var(--blue); }
  .sub { color: var(--muted); font-size: 13px; margin-top: 3px; }
  .integration-desc { color: var(--muted); font-size: 14px; line-height: 1.5; margin-bottom: 18px; }
  .integration-actions { display: flex; gap: 10px; }
  .primary-btn { height: 44px; border: 0; border-radius: 14px; padding: 0 18px; display: inline-flex; align-items: center; gap: 8px; color: white; cursor: pointer; font-weight: 850; font-size: 14px; background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%); box-shadow: 0 12px 24px rgba(99, 49, 255, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.38), inset 0 -8px 14px rgba(39, 8, 143, 0.44); transition: 180ms ease; white-space: nowrap; }
  .primary-btn:hover { transform: translateY(-1px); }
  .secondary-btn { height: 44px; border-radius: 14px; padding: 0 18px; display: inline-flex; align-items: center; gap: 8px; color: white; background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.1); cursor: pointer; font-weight: 800; font-size: 14px; white-space: nowrap; transition: 180ms ease; }
  .secondary-btn:hover { background: rgba(255,255,255,.075); }
  @media (max-width: 1240px) { .summary-grid { grid-template-columns: repeat(3, 1fr); } .integration-grid { grid-template-columns: 1fr; } }
  @media (max-width: 900px) { .summary-grid { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 680px) { .summary-grid { grid-template-columns: 1fr; } }
</style>
