<script lang="ts">
  import { onMount } from 'svelte';
  import { listRadarrInstances, syncRadarrInstance } from '$lib/api/radarr';
  import { showToast } from '$lib/state/toast-state';
  import type { RadarrInstanceResponse } from '$lib/api/types';

  export let navigate: (page: string, data?: any) => void = () => {};

  let activeTab = 'instances';
  let instances: RadarrInstanceResponse[] = [];
  let busy = false;
  let autoImport = true;
  let preferLargest = true;
  let retryOnce = true;
  let defaultImportMode = 'move';

  onMount(async () => {
    try {
      instances = await listRadarrInstances();
    } catch { /* ignore */ }
  });

  function goBack() { navigate('radarr-instances'); }

  function editInstance(inst: RadarrInstanceResponse) {
    navigate('radarr-instance-form', { instance: inst });
  }

  async function handleSync(inst: RadarrInstanceResponse) {
    try {
      await syncRadarrInstance(inst.id);
      showToast(`Sync started for ${inst.name}`);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Sync failed');
    }
  }
</script>

<div class="page">
  <header class="page-head">
    <div>
      <div class="crumbs">
        <button class="crumb-btn" type="button" on:click={goBack}>← Back to Radarr</button>
      </div>
      <h1 class="page-title">Radarr Settings</h1>
      <p class="page-subtitle">Manage instances, defaults, path mappings, import rules, and sync behavior.</p>
    </div>
    <div class="toolbar">
      <button class="primary-btn" type="button" on:click={() => navigate('radarr-instance-form', {})}>
        <svg width="18" height="18"><use href="#i-plus"/></svg>
        Add Radarr Instance
      </button>
    </div>
  </header>

  <div class="split-layout">
    <div>
      <section class="panel">
        <div class="tabs-bar" role="tablist">
          <button class="tab-btn" class:active={activeTab === 'instances'} type="button" on:click={() => activeTab = 'instances'}>Instances</button>
          <button class="tab-btn" class:active={activeTab === 'defaults'} type="button" on:click={() => activeTab = 'defaults'}>Defaults</button>
          <button class="tab-btn" class:active={activeTab === 'paths'} type="button" on:click={() => activeTab = 'paths'}>Path Mappings</button>
          <button class="tab-btn" class:active={activeTab === 'rules'} type="button" on:click={() => activeTab = 'rules'}>Import Rules</button>
          <button class="tab-btn" class:active={activeTab === 'advanced'} type="button" on:click={() => activeTab = 'advanced'}>Advanced</button>
        </div>

        <div class="tab-content">
          {#if activeTab === 'instances'}
            <div class="tab-inner">
              <div class="section-row">
                <h2 class="section-title">Radarr Instances ({instances.length})</h2>
              </div>
              <div class="instance-cards">
                {#each instances as inst}
                  <div class="instance-card" class:default={inst.isDefault}>
                    <div class="instance-card-main">
                      <div class="instance-avatar">
                        <svg width="24" height="24"><use href="#i-radarr"/></svg>
                      </div>
                      <div>
                        <div class="item-title">
                          {inst.name}
                          {#if inst.isDefault}
                            <span class="badge purple">Default</span>
                          {/if}
                        </div>
                        <div class="sub">API Key: ••••••••••••••••••</div>
                      </div>
                    </div>
                    <div>
                      <span class="badge {inst.status === 'connected' ? 'green' : inst.status === 'warning' ? 'yellow' : 'muted'}">{inst.status === 'connected' ? 'Connected' : inst.status === 'warning' ? 'Warning' : 'Unknown'}</span>
                      <div class="sub">Last sync: {inst.lastSyncAt ? new Date(inst.lastSyncAt).toLocaleString() : 'never'}</div>
                    </div>
                    <div>
                      <b class="text-muted">—</b> missing
                      <div class="sub">
                        <span class="path">{inst.tubeWritePath}</span><br>
                        <span class="path">{inst.radarrImportPath}</span>
                      </div>
                    </div>
                    <div class="actions">
                      <button class="secondary-btn-sm" type="button" on:click={() => editInstance(inst)}>Edit</button>
                      <button class="secondary-btn-sm" type="button" on:click={() => handleSync(inst)}>Sync</button>
                    </div>
                  </div>
                {/each}
                {#if instances.length === 0}
                  <div class="empty-state"><strong>No instances configured</strong></div>
                {/if}
              </div>
            </div>

          {:else if activeTab === 'defaults'}
            <div class="tab-inner">
              <div class="card-inner">
                <h2 class="section-title">Default Behavior</h2>
                <div class="form-grid">
                  <div class="form-group">
                    <label>Default Import Mode</label>
                    <select class="input" bind:value={defaultImportMode}>
                      <option value="move">Move</option>
                      <option value="copy">Copy</option>
                    </select>
                  </div>
                  <div class="form-group full">
                    <label class="checkline">
                      <input class="checkbox" type="checkbox" bind:checked={autoImport} />
                      <span>Automatically import after download completes</span>
                    </label>
                  </div>
                </div>
              </div>
            </div>

          {:else if activeTab === 'paths'}
            <div class="tab-inner">
              <div class="card-inner">
                <h2 class="section-title">Path Mappings</h2>
                <p class="page-subtitle">Each Radarr instance stores a Tube Explore write path and a Radarr-visible import path.</p>
                <table class="table">
                  <thead>
                    <tr>
                      <th>Instance</th>
                      <th>Tube Write Path</th>
                      <th>Radarr Import Path</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each instances as inst}
                      <tr>
                        <td>{inst.name}</td>
                        <td><span class="path">{inst.tubeWritePath}</span></td>
                        <td><span class="path">{inst.radarrImportPath}</span></td>
                        <td>
                          <span class="badge {inst.status === 'connected' ? 'green' : 'yellow'}">
                            {inst.status === 'connected' ? 'Verified' : 'Warning'}
                          </span>
                        </td>
                      </tr>
                    {/each}
                    {#if instances.length === 0}
                      <tr><td colspan="4" class="empty-cell">No instances configured</td></tr>
                    {/if}
                  </tbody>
                </table>
              </div>
            </div>

          {:else if activeTab === 'rules'}
            <div class="tab-inner">
              <div class="card-inner">
                <h2 class="section-title">Import Rules</h2>
                <label class="checkline">
                  <input class="checkbox" type="checkbox" bind:checked={autoImport} />
                  <span>Reject playlist downloads for Radarr movie import</span>
                </label>
                <label class="checkline">
                  <input class="checkbox" type="checkbox" bind:checked={preferLargest} />
                  <span>Prefer largest video file from task result</span>
                </label>
                <label class="checkline">
                  <input class="checkbox" type="checkbox" bind:checked={retryOnce} />
                  <span>Retry failed import automatically once</span>
                </label>
              </div>
            </div>

          {:else if activeTab === 'advanced'}
            <div class="tab-inner">
              <div class="card-inner">
                <h2 class="section-title">Advanced Settings</h2>
                <p class="page-subtitle">Configure sync intervals, concurrency limits, and logging.</p>
                <div class="form-grid">
                  <div class="form-group">
                    <label>Sync Interval (minutes)</label>
                    <input class="input" type="number" value={15} />
                  </div>
                  <div class="form-group">
                    <label>Max Concurrent Imports</label>
                    <input class="input" type="number" value={3} />
                  </div>
                  <div class="form-group full">
                    <label class="checkline">
                      <input class="checkbox" type="checkbox" checked />
                      <span>Enable debug logging for imports</span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          {/if}
        </div>
      </section>
    </div>

    <aside class="side-panel">
      <div class="side-card">
        <h3>How Radarr Integration Works</h3>
        <div class="steps">
          <div class="step">
            <div class="step-num">1</div>
            <div><b>Download</b><div class="sub">Tube Explore downloads to the configured write path.</div></div>
          </div>
          <div class="step">
            <div class="step-num">2</div>
            <div><b>Import</b><div class="sub">Radarr scans the mapped import path.</div></div>
          </div>
          <div class="step">
            <div class="step-num">3</div>
            <div><b>Organize</b><div class="sub">Radarr moves/renames the file into the library.</div></div>
          </div>
        </div>
      </div>
      <div class="side-card">
        <h3>Common Issues</h3>
        <div class="check-list">
          <div class="check-item"><span class="check-icon ok">✓</span> Paths are mapped correctly</div>
          <div class="check-item"><span class="check-icon ok">✓</span> Radarr can access import path</div>
          <div class="check-item"><span class="check-icon fail">×</span> Import path not accessible</div>
          <div class="check-item"><span class="check-icon fail">×</span> Permission denied</div>
        </div>
      </div>
      <div class="notice-box">
        <b>Tip</b><br>
        If import fails, compare Tube Explore write path and Radarr import path first.
      </div>
    </aside>
  </div>
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
    margin: 8px 0 0;
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
  .crumbs { margin-bottom: 4px; }
  .crumb-btn {
    border: 0;
    background: transparent;
    color: var(--purple-light);
    cursor: pointer;
    font-weight: 800;
    font-size: 14px;
    padding: 0;
  }
  .crumb-btn:hover { text-decoration: underline; }
  .toolbar { display: flex; gap: 12px; align-items: center; }
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
  .primary-btn:hover { transform: translateY(-1px); }
  .split-layout {
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 24px;
    align-items: start;
  }
  .panel {
    border-radius: 22px;
    overflow: hidden;
    background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(8, 13, 34, 0.64);
    border: 1px solid rgba(255, 255, 255, 0.105);
    box-shadow: 0 22px 60px rgba(0,0,0,.22);
  }
  .tabs-bar {
    height: 52px;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 0 14px;
    border-bottom: 1px solid rgba(255,255,255,.08);
    overflow-x: auto;
    scrollbar-width: none;
  }
  .tab-btn {
    height: 40px;
    border: 0;
    border-radius: 10px;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    padding: 0 14px;
    white-space: nowrap;
    font-weight: 800;
    font-size: 14px;
    transition: 180ms ease;
  }
  .tab-btn.active { color: white; background: rgba(124, 60, 255, 0.18); }
  .tab-content { min-height: 300px; }
  .tab-inner { padding: 18px; }
  .section-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }
  .section-title { margin: 0; font-size: 18px; letter-spacing: -0.03em; }
  .instance-cards { display: grid; gap: 12px; }
  .instance-card {
    display: grid;
    grid-template-columns: 220px 1fr 1fr auto;
    gap: 18px;
    align-items: center;
    padding: 16px;
    border-radius: 16px;
    background: rgba(255,255,255,.035);
    border: 1px solid rgba(255,255,255,.09);
  }
  .instance-card.default { border-color: rgba(167,134,255,.45); }
  .instance-card-main { display: flex; align-items: center; gap: 12px; }
  .instance-avatar {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: rgba(124,60,255,.16);
    color: var(--purple-light);
    display: grid;
    place-items: center;
    flex: 0 0 auto;
  }
  .item-title {
    font-weight: 850;
    font-size: 15px;
  }
  .sub { color: var(--muted); font-size: 12px; margin-top: 3px; }
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
  .badge.purple { background: rgba(124,60,255,.16); color: var(--purple-light); }
  .badge.yellow { background: rgba(255,200,87,.16); color: #ffc857; }
  .badge.muted { background: rgba(169,175,208,.12); color: var(--muted); }
  .path {
    font-family: monospace;
    font-size: 12px;
    background: rgba(255,255,255,.05);
    padding: 1px 5px;
    border-radius: 4px;
  }
  .actions { display: flex; gap: 8px; }
  .secondary-btn-sm {
    height: 36px;
    padding: 0 14px;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,.1);
    background: rgba(255,255,255,.045);
    color: white;
    cursor: pointer;
    font-weight: 800;
    font-size: 13px;
    transition: 180ms ease;
  }
  .secondary-btn-sm:hover { background: rgba(255,255,255,.075); }
  .text-muted { color: var(--muted); }
  .card-inner { padding: 0; }
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 16px;
  }
  .form-group { display: flex; flex-direction: column; gap: 6px; }
  .form-group.full { grid-column: 1 / -1; }
  .form-group label { font-size: 14px; font-weight: 800; }
  .input {
    height: 44px;
    border-radius: 12px;
    padding: 0 14px;
    border: 1px solid rgba(255,255,255,.12);
    background: rgba(255,255,255,.045);
    color: white;
    font-size: 14px;
    outline: 0;
    width: 100%;
  }
  .input:focus { border-color: rgba(167,134,255,.4); }
  .checkline {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    padding: 8px 0;
  }
  .checkbox { width: 18px; height: 18px; accent-color: var(--purple); }
  .table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  .table th, .table td {
    padding: 12px 16px;
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
  .empty-cell { text-align: center; color: var(--muted); padding: 24px; }
  .empty-state { text-align: center; padding: 32px; color: var(--muted); }
  .side-panel { display: flex; flex-direction: column; gap: 16px; }
  .side-card {
    padding: 18px;
    border-radius: 18px;
    background: linear-gradient(180deg, rgba(255,255,255,.055), rgba(255,255,255,.025)), rgba(8,13,34,.6);
    border: 1px solid rgba(255,255,255,.095);
  }
  .side-card h3 { margin: 0 0 14px; font-size: 16px; letter-spacing: -0.03em; }
  .steps { display: flex; flex-direction: column; gap: 14px; }
  .step { display: flex; gap: 12px; align-items: flex-start; }
  .step-num {
    width: 28px; height: 28px; border-radius: 999px;
    background: rgba(124,60,255,.2); color: var(--purple-light);
    display: grid; place-items: center; font-weight: 900; font-size: 14px; flex: 0 0 auto;
  }
  .check-list { display: flex; flex-direction: column; gap: 10px; }
  .check-item { display: flex; align-items: center; gap: 10px; font-size: 14px; }
  .check-icon {
    width: 24px; height: 24px; border-radius: 999px;
    display: grid; place-items: center; font-size: 13px; font-weight: 900; flex: 0 0 auto;
  }
  .check-icon.ok { background: rgba(20,216,148,.15); color: var(--green); }
  .check-icon.fail { background: rgba(255,77,126,.15); color: var(--red); }
  .notice-box {
    padding: 14px;
    border-radius: 12px;
    background: rgba(255,200,87,.08);
    border: 1px solid rgba(255,200,87,.18);
    color: #ffc857;
    font-size: 13px;
    line-height: 1.5;
  }
  @media (max-width: 1240px) {
    .split-layout { grid-template-columns: 1fr; }
    .instance-card { grid-template-columns: 1fr; gap: 12px; }
  }
  @media (max-width: 900px) {
    .page-head { grid-template-columns: 1fr; }
    .form-grid { grid-template-columns: 1fr; }
  }
</style>
