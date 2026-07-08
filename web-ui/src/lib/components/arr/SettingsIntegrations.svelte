<script lang="ts">
  import { onMount } from 'svelte';
  import { listArrInstances } from '$lib/api/arr';
  import type { ArrInstanceResponse } from '$lib/api/types';

  export let navigate: (page: string, data?: any) => void = () => {};

  let radarrInstances: ArrInstanceResponse[] = [];
  let sonarrInstances: ArrInstanceResponse[] = [];
  let busy = false;

  onMount(async () => {
    busy = true;
    try {
      const [radarr, sonarr] = await Promise.all([
        listArrInstances('radarr').catch(() => []),
        listArrInstances('sonarr').catch(() => []),
      ]);
      radarrInstances = radarr;
      sonarrInstances = sonarr;
    } catch { /* ignore */ }
    finally { busy = false; }
  });

  function goBack() {
    navigate('settings-integrations');
  }

  function editRadarr(inst: ArrInstanceResponse) {
    navigate('radarr-instance-form', { instance: inst });
  }

  function addRadarr() {
    navigate('radarr-instance-form', {});
  }

  function editSonarr(inst: ArrInstanceResponse) {
    navigate('sonarr-instance-form', { instance: inst });
  }

  function addSonarr() {
    navigate('sonarr-instance-form', {});
  }

  function statusClass(status: string): string {
    if (status === 'connected') return 'green';
    if (status === 'warning') return 'yellow';
    if (status === 'error') return 'red';
    return 'muted';
  }
</script>

<div class="page">
  <header class="page-head">
    <div>
      <h1 class="page-title">Integrations</h1>
      <p class="page-subtitle">Configure and manage connections to Radarr and Sonarr services for automated media imports.</p>
    </div>
  </header>

  <div class="split-layout">
    <div>
      <section class="panel">
        <div class="section-head">
          <h2>Radarr <span class="muted">({radarrInstances.length})</span></h2>
          <button class="primary-btn-sm" type="button" on:click={addRadarr}>
            <svg width="16" height="16"><use href="#i-plus"/></svg>
            Add Radarr
          </button>
        </div>
        {#if radarrInstances.length === 0}
          <div class="empty-state"><strong>No Radarr instances configured</strong></div>
        {:else}
          <div class="instance-list">
            {#each radarrInstances as inst}
              <div class="instance-row">
                <div class="instance-main">
                  <div class="instance-avatar radarr">
                    <svg width="20" height="20"><use href="#i-radarr"/></svg>
                  </div>
                  <div>
                    <div class="item-title">{inst.name}</div>
                    <div class="sub">API: ••••••</div>
                  </div>
                </div>
                <div>
                  <span class="badge {statusClass(inst.status)}">{inst.status}</span>
                  <div class="sub">Last sync: {inst.lastSyncAt ? new Date(inst.lastSyncAt).toLocaleString() : 'never'}</div>
                </div>
                <div class="actions">
                  <button class="secondary-btn-sm" type="button" on:click={() => editRadarr(inst)}>Edit</button>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </section>

      <section class="panel" style="margin-top:18px">
        <div class="section-head">
          <h2>Sonarr <span class="muted">({sonarrInstances.length})</span></h2>
          <button class="primary-btn-sm" type="button" on:click={addSonarr}>
            <svg width="16" height="16"><use href="#i-plus"/></svg>
            Add Sonarr
          </button>
        </div>
        {#if sonarrInstances.length === 0}
          <div class="empty-state"><strong>No Sonarr instances configured</strong></div>
        {:else}
          <div class="instance-list">
            {#each sonarrInstances as inst}
              <div class="instance-row">
                <div class="instance-main">
                  <div class="instance-avatar sonarr">
                    <svg width="20" height="20"><use href="#i-sonarr"/></svg>
                  </div>
                  <div>
                    <div class="item-title">{inst.name}</div>
                    <div class="sub">API: ••••••</div>
                  </div>
                </div>
                <div>
                  <span class="badge {statusClass(inst.status)}">{inst.status}</span>
                  <div class="sub">Last sync: {inst.lastSyncAt ? new Date(inst.lastSyncAt).toLocaleString() : 'never'}</div>
                </div>
                <div class="actions">
                  <button class="secondary-btn-sm" type="button" on:click={() => editSonarr(inst)}>Edit</button>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    </div>

    <aside class="side-panel">
      <div class="side-card">
        <h3>Path Mapping Setup</h3>
        <p class="sub" style="line-height:1.5">Each Radarr and Sonarr instance stores a Tube Explore write path and an Arr import path pointing to the same physical directory.</p>
        <div class="notice-box" style="margin-top:12px">
          <b>Docker Setup</b><br>
          Both paths must point to the same host directory. They differ only in how the containers see the mount.
        </div>
      </div>
      <div class="side-card">
        <h3>Quick Help</h3>
        <div class="check-list">
          <div class="check-item"><span class="check-icon ok">✓</span> Use <b>Test Connection</b> before saving</div>
          <div class="check-item"><span class="check-icon ok">✓</span> API keys are encrypted at rest</div>
          <div class="check-item"><span class="check-icon fail">×</span> Path mismatches cause import failures</div>
          <div class="check-item"><span class="check-icon fail">×</span> Disabled instances won't import</div>
        </div>
      </div>
    </aside>
  </div>
</div>

<style>
  .page { min-width: 0; }
  .page-head { margin-bottom: 24px; }
  .page-title { margin: 0; font-size: clamp(30px, 3.6vw, 42px); line-height: 1; letter-spacing: -0.055em; font-weight: 950; }
  .page-subtitle { margin: 10px 0 0; color: var(--muted); font-size: 15px; }
  .split-layout { display: grid; grid-template-columns: 1fr 340px; gap: 24px; align-items: start; }
  .panel { border-radius: 22px; overflow: hidden; background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(8,13,34,.64); border: 1px solid rgba(255,255,255,.105); }
  .section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 18px; border-bottom: 1px solid rgba(255,255,255,.08); }
  .section-head h2 { margin: 0; font-size: 18px; letter-spacing: -0.03em; }
  .muted { color: var(--muted); }
  .primary-btn-sm { height: 36px; padding: 0 14px; border: 0; border-radius: 10px; display: inline-flex; align-items: center; gap: 6px; color: white; cursor: pointer; font-weight: 800; font-size: 13px; background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%); white-space: nowrap; }
  .empty-state { padding: 32px 20px; text-align: center; color: var(--muted); }
  .empty-state strong { color: white; font-size: 16px; }
  .instance-list { display: grid; gap: 2px; padding: 6px 10px 14px; }
  .instance-row { display: grid; grid-template-columns: 200px 1fr auto; gap: 18px; align-items: center; padding: 12px; border-radius: 14px; }
  .instance-row:hover { background: rgba(255,255,255,.026); }
  .instance-main { display: flex; align-items: center; gap: 12px; }
  .instance-avatar { width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center; flex: 0 0 auto; }
  .instance-avatar.radarr { background: rgba(124,60,255,.16); color: var(--purple-light); }
  .instance-avatar.sonarr { background: rgba(47,140,255,.16); color: var(--blue); }
  .item-title { font-weight: 850; font-size: 14px; }
  .sub { color: var(--muted); font-size: 12px; margin-top: 2px; }
  .badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 8px; font-size: 12px; font-weight: 850; }
  .badge.green { background: rgba(20,216,148,.16); color: var(--green); }
  .badge.yellow { background: rgba(255,200,87,.16); color: #ffc857; }
  .badge.red { background: rgba(255,77,126,.16); color: var(--red); }
  .badge.muted { background: rgba(169,175,208,.12); color: var(--muted); }
  .actions { display: flex; gap: 6px; }
  .secondary-btn-sm { height: 34px; padding: 0 12px; border-radius: 9px; border: 1px solid rgba(255,255,255,.1); background: rgba(255,255,255,.045); color: white; cursor: pointer; font-weight: 800; font-size: 13px; white-space: nowrap; transition: 180ms ease; }
  .secondary-btn-sm:hover { background: rgba(255,255,255,.075); }
  .side-panel { display: flex; flex-direction: column; gap: 16px; }
  .side-card { padding: 18px; border-radius: 18px; background: linear-gradient(180deg, rgba(255,255,255,.055), rgba(255,255,255,.025)), rgba(8,13,34,.6); border: 1px solid rgba(255,255,255,.095); }
  .side-card h3 { margin: 0 0 8px; font-size: 16px; letter-spacing: -0.03em; }
  .check-list { display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }
  .check-item { display: flex; align-items: center; gap: 10px; font-size: 13px; }
  .check-icon { width: 22px; height: 22px; border-radius: 999px; display: grid; place-items: center; font-size: 12px; font-weight: 900; flex: 0 0 auto; }
  .check-icon.ok { background: rgba(20,216,148,.15); color: var(--green); }
  .check-icon.fail { background: rgba(255,77,126,.15); color: var(--red); }
  .notice-box { padding: 14px; border-radius: 12px; background: rgba(255,200,87,.08); border: 1px solid rgba(255,200,87,.18); color: #ffc857; font-size: 13px; line-height: 1.5; }
  @media (max-width: 1240px) { .split-layout { grid-template-columns: 1fr; } .instance-row { grid-template-columns: 1fr; gap: 10px; } }
</style>
