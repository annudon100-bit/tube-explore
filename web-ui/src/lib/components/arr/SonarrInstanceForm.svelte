<script lang="ts">
  import { onMount } from 'svelte';
  import { createArrInstance, updateArrInstance, testArrInstance, getArrRootFolders, getArrQualityProfiles } from '$lib/api/arr';
  import { showToast } from '$lib/state/toast-state';
  import type { ArrInstanceResponse, SonarrRootFolder, SonarrQualityProfile } from '$lib/api/types';

  export let navigate: (page: string, data?: any) => void = () => {};
  export let instance: ArrInstanceResponse | null = null;

  let name = '';
  let baseUrl = '';
  let apiKey = '';
  let tubeWritePath = '';
  let arrImportPath = '';
  let hostPathHint = '';
  let defaultRootFolderPath = '';
  let importMode = 'move';
  let enabled = true;
  let defaultQualityProfileId: number | undefined = undefined;

  let busy = false;
  let error: string | null = null;
  let testResult: string | null = null;
  let testing = false;
  let testOk = false;

  let rootFolders: SonarrRootFolder[] = [];
  let qualityProfiles: SonarrQualityProfile[] = [];

  const isEdit = !!instance;

  onMount(() => {
    if (instance) {
      name = instance.name;
      baseUrl = instance.baseUrl;
      tubeWritePath = instance.tubeWritePath;
      arrImportPath = instance.arrImportPath;
      hostPathHint = instance.hostPathHint || '';
      defaultRootFolderPath = instance.defaultRootFolderPath || '';
      importMode = instance.importMode;
      enabled = instance.enabled;
      defaultQualityProfileId = instance.defaultQualityProfileId ?? undefined;
    }
  });

  async function handleTest() {
    testing = true;
    testResult = null;
    testOk = false;
    try {
      if (instance) {
        const resp = await testArrInstance(instance.id, {
          baseUrl: baseUrl || undefined,
          apiKey: apiKey || undefined,
          tubeWritePath: tubeWritePath || undefined,
        });
        if (resp.ok) {
          testResult = 'Connection OK';
          testOk = true;
        } else {
          testResult = resp.errors?.join(', ') || resp.warnings?.join(', ') || 'Connection failed';
        }
      } else {
        const resp = await testArrInstance('_new_', {
          baseUrl: baseUrl || undefined,
          apiKey: apiKey || undefined,
          tubeWritePath: tubeWritePath || undefined,
        });
        if (resp.ok) {
          testResult = 'Connection OK';
          testOk = true;
        } else {
          testResult = resp.errors?.join(', ') || resp.warnings?.join(', ') || 'Connection failed';
        }
      }
    } catch (e) {
      testResult = e instanceof Error ? e.message : 'Test failed';
    } finally { testing = false; }
  }

  async function handleSave() {
    busy = true;
    error = null;
    try {
      const body: Record<string, unknown> = {
        kind: 'sonarr',
        name,
        baseUrl,
        apiKey: apiKey || undefined,
        tubeWritePath,
        arrImportPath,
        hostPathHint: hostPathHint || undefined,
        defaultRootFolderPath: defaultRootFolderPath || undefined,
        importMode,
        enabled,
      };
      if (defaultQualityProfileId !== undefined) {
        body.defaultQualityProfileId = defaultQualityProfileId;
      }
      if (isEdit && instance) {
        await updateArrInstance(instance.id, body);
        showToast(`Updated ${name}`);
      } else {
        const created = await createArrInstance(body as any);
        showToast(`Created ${created.name}`);
      }
      navigate('instances-sonarr');
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    } finally { busy = false; }
  }

  function goBack() {
    navigate('instances-sonarr');
  }
</script>

<div class="page">
  <header class="page-head">
    <div>
      <div class="crumbs">
        <button class="crumb-btn" type="button" on:click={goBack}>← Back to Sonarr Instances</button>
      </div>
      <h1 class="page-title">{isEdit ? 'Edit Sonarr Instance' : 'Add Sonarr Instance'}</h1>
      <p class="page-subtitle">Connect a Sonarr server and configure Docker-safe path mapping.</p>
    </div>
    <div class="toolbar">
      <button class="secondary-btn" type="button" on:click={handleTest} disabled={testing}>
        <svg width="18" height="18"><use href={testing ? '#i-refresh' : testOk ? '#i-check' : '#i-refresh'}/></svg>
        {testing ? 'Testing…' : testResult && testOk ? 'Connection OK' : 'Test Connection'}
      </button>
    </div>
  </header>

  {#if error}
    <div class="error-box">{error}</div>
  {/if}
  {#if testResult && !testOk}
    <div class="error-box">{testResult}</div>
  {:else if testResult && testOk}
    <div class="success-box">{testResult}</div>
  {/if}

  <div class="two-col">
    <form class="card" on:submit|preventDefault={handleSave}>
      <h2 class="card-title">Connection Details</h2>
      <div class="form-grid">
        <div class="form-group">
          <label>Instance Name <span class="required">*</span></label>
          <input class="input" bind:value={name} placeholder="Main Sonarr" required />
          <div class="hint">Friendly name shown in selectors and missing episode pages.</div>
        </div>
        <div class="form-group">
          <label>Base URL <span class="required">*</span></label>
          <input class="input" bind:value={baseUrl} placeholder="http://sonarr-main:8989" required />
          <div class="hint">Include protocol and port. Example: http://sonarr:8989</div>
        </div>
        <div class="form-group full">
          <label>API Key <span class="required">*</span></label>
          <input class="input" type="password" bind:value={apiKey} placeholder={isEdit ? 'Leave blank to keep existing' : 'Enter API key'} />
          <div class="hint">Stored encrypted. Never returned by the API.</div>
        </div>
      </div>

      <hr class="divider" />
      <h2 class="card-title">Path Mapping</h2>
      <div class="form-grid">
        <div class="form-group">
          <label>Tube Explore Write Path <span class="required">*</span></label>
          <input class="input" bind:value={tubeWritePath} placeholder="/downloads/sonarr-main" required />
          <div class="hint">Path inside the Tube Explore container where files are downloaded.</div>
        </div>
        <div class="form-group">
          <label>Sonarr Import Path <span class="required">*</span></label>
          <input class="input" bind:value={arrImportPath} placeholder="/data/imports/tube-explore/sonarr-main" required />
          <div class="hint">Path inside the Sonarr container pointing to the same physical directory.</div>
        </div>
        <div class="form-group full">
          <label>Host Path Hint</label>
          <input class="input" bind:value={hostPathHint} placeholder="/mnt/media/sonarr" />
          <div class="hint">Optional host-level path for debugging.</div>
        </div>
      </div>

      <div class="notice-box">
        <b>Important: Docker path mapping</b><br>
        Both paths must point to the same physical host directory. They may be different because Tube Explore and Sonarr run in different containers.
      </div>

      <hr class="divider" />
      <h2 class="card-title">Defaults</h2>
      <div class="form-grid">
        <div class="form-group">
          <label>Default Quality Profile</label>
          <select class="input" bind:value={defaultQualityProfileId}>
            <option value={undefined}>— Use Sonarr default —</option>
            {#each qualityProfiles as qp}
              <option value={qp.id}>{qp.name}</option>
            {/each}
          </select>
        </div>
        <div class="form-group">
          <label>Default Root Folder</label>
          <select class="input" bind:value={defaultRootFolderPath}>
            <option value="">— Use Sonarr default —</option>
            {#each rootFolders as rf}
              <option value={rf.path}>{rf.path}</option>
            {/each}
          </select>
        </div>
        <div class="form-group">
          <label>Import Mode</label>
          <select class="input" bind:value={importMode}>
            <option value="move">Move</option>
            <option value="copy">Copy</option>
          </select>
          <div class="hint">Move deletes from staging after import; Copy leaves a copy.</div>
        </div>
        <div class="form-group">
          <label class="checkline">
            <input class="checkbox" type="checkbox" bind:checked={enabled} />
            <span>Enabled</span>
          </label>
          <div class="hint">When disabled, this instance won't be used for imports.</div>
        </div>
      </div>

      <div class="dialog-actions">
        <button class="secondary-btn" type="button" on:click={goBack}>Cancel</button>
        <button class="primary-btn" type="submit" disabled={busy}>
          {busy ? 'Saving…' : isEdit ? 'Update Instance' : 'Save Instance'}
        </button>
      </div>
    </form>

    <aside class="side-panel">
      <div class="side-card">
        <h3>How Sonarr Integration Works</h3>
        <div class="steps">
          <div class="step">
            <div class="step-num">1</div>
            <div>
              <b>Download</b>
              <div class="sub">Tube Explore downloads to the configured write path.</div>
            </div>
          </div>
          <div class="step">
            <div class="step-num">2</div>
            <div>
              <b>Import</b>
              <div class="sub">Sonarr scans the mapped import path.</div>
            </div>
          </div>
          <div class="step">
            <div class="step-num">3</div>
            <div>
              <b>Organize</b>
              <div class="sub">Sonarr moves/renames the file into the library.</div>
            </div>
          </div>
        </div>
      </div>
      <div class="side-card">
        <h3>Common Issues</h3>
        <div class="check-list">
          <div class="check-item"><span class="check-icon ok">✓</span> Paths are mapped correctly</div>
          <div class="check-item"><span class="check-icon ok">✓</span> Sonarr can access import path</div>
          <div class="check-item"><span class="check-icon fail">×</span> Import path not accessible</div>
          <div class="check-item"><span class="check-icon fail">×</span> Permission denied</div>
        </div>
      </div>
    </aside>
  </div>
</div>

<style>
  .page { min-width: 0; }
  .page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
  .page-title { margin: 8px 0 0; font-size: clamp(30px, 3.6vw, 42px); line-height: 1; letter-spacing: -0.055em; font-weight: 950; }
  .page-subtitle { margin: 10px 0 0; color: var(--muted); font-size: 15px; }
  .crumbs { margin-bottom: 4px; }
  .crumb-btn { border: 0; background: transparent; color: var(--purple-light); cursor: pointer; font-weight: 800; font-size: 14px; padding: 0; }
  .crumb-btn:hover { text-decoration: underline; }
  .toolbar { display: flex; gap: 12px; align-items: center; }
  .secondary-btn { height: 48px; border-radius: 14px; padding: 0 18px; display: inline-flex; align-items: center; gap: 10px; color: white; background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.1); cursor: pointer; font-weight: 800; white-space: nowrap; transition: 180ms ease; }
  .secondary-btn:hover { background: rgba(255,255,255,.075); }
  .primary-btn { height: 48px; border: 0; border-radius: 15px; padding: 0 22px; display: inline-flex; align-items: center; gap: 10px; color: white; cursor: pointer; font-weight: 850; letter-spacing: -0.02em; font-size: 15px; background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%); box-shadow: 0 16px 30px rgba(99,49,255,.34), inset 0 1px 0 rgba(255,255,255,.38), inset 0 -8px 14px rgba(39,8,143,.44); transition: 180ms ease; white-space: nowrap; }
  .primary-btn:hover { transform: translateY(-1px); }
  .primary-btn:disabled { opacity: 0.5; cursor: default; }
  .error-box, .success-box { margin-bottom: 16px; padding: 12px 18px; border-radius: 14px; font-size: 14px; font-weight: 750; }
  .error-box { background: rgba(255,77,126,.12); border: 1px solid rgba(255,77,126,.2); color: var(--red); }
  .success-box { background: rgba(20,216,148,.12); border: 1px solid rgba(20,216,148,.2); color: var(--green); }
  .two-col { display: grid; grid-template-columns: 1fr 340px; gap: 24px; align-items: start; }
  .card { padding: 24px; border-radius: 22px; background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(8,13,34,.64); border: 1px solid rgba(255,255,255,.105); }
  .card-title { margin: 0 0 18px; font-size: 20px; letter-spacing: -0.035em; }
  .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .form-group { display: flex; flex-direction: column; gap: 6px; }
  .form-group.full { grid-column: 1 / -1; }
  .form-group label { font-size: 14px; font-weight: 800; color: var(--text); }
  .required { color: var(--red); }
  .input { height: 44px; border-radius: 12px; padding: 0 14px; border: 1px solid rgba(255,255,255,.12); background: rgba(255,255,255,.045); color: white; font-size: 14px; outline: 0; transition: 180ms ease; width: 100%; }
  .input:focus { border-color: rgba(167,134,255,.4); background: rgba(124,60,255,.08); }
  .input::placeholder { color: rgba(210,212,238,.4); }
  select.input { appearance: auto; }
  .hint { color: #737b9f; font-size: 12px; line-height: 1.4; }
  .divider { border: 0; border-top: 1px solid rgba(255,255,255,.08); margin: 20px 0; }
  .notice-box { margin-top: 16px; padding: 14px; border-radius: 12px; background: rgba(255,200,87,.08); border: 1px solid rgba(255,200,87,.18); color: #ffc857; font-size: 13px; line-height: 1.5; }
  .checkline { display: flex; align-items: center; gap: 10px; cursor: pointer; font-size: 14px; }
  .checkbox { width: 18px; height: 18px; accent-color: var(--purple); }
  .dialog-actions { margin-top: 24px; display: flex; justify-content: flex-end; gap: 12px; }
  .side-panel { display: flex; flex-direction: column; gap: 16px; }
  .side-card { padding: 18px; border-radius: 18px; background: linear-gradient(180deg, rgba(255,255,255,.055), rgba(255,255,255,.025)), rgba(8,13,34,.6); border: 1px solid rgba(255,255,255,.095); }
  .side-card h3 { margin: 0 0 14px; font-size: 16px; letter-spacing: -0.03em; }
  .steps { display: flex; flex-direction: column; gap: 14px; }
  .step { display: flex; gap: 12px; align-items: flex-start; }
  .step-num { width: 28px; height: 28px; border-radius: 999px; background: rgba(124,60,255,.2); color: var(--purple-light); display: grid; place-items: center; font-weight: 900; font-size: 14px; flex: 0 0 auto; }
  .sub { color: var(--muted); font-size: 13px; margin-top: 3px; }
  .check-list { display: flex; flex-direction: column; gap: 10px; }
  .check-item { display: flex; align-items: center; gap: 10px; font-size: 14px; }
  .check-icon { width: 24px; height: 24px; border-radius: 999px; display: grid; place-items: center; font-size: 13px; font-weight: 900; flex: 0 0 auto; }
  .check-icon.ok { background: rgba(20,216,148,.15); color: var(--green); }
  .check-icon.fail { background: rgba(255,77,126,.15); color: var(--red); }
  @media (max-width: 1240px) { .two-col { grid-template-columns: 1fr; } }
  @media (max-width: 900px) { .page-head { grid-template-columns: 1fr; } .form-grid { grid-template-columns: 1fr; } }
</style>
