<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import { getSettings, patchSettings } from '$lib/api/settings';
  import { showToast } from '$lib/state/toast-state';
  import type { SettingsResponse } from '$lib/api/types';

  export let onClose: () => void = () => {};
  let settings: SettingsResponse | null = null;
  let error: string | null = null;
  let busy = false;
  async function load() { try { settings = await getSettings(); } catch(e) { error = e instanceof Error ? e.message : 'Unable to load settings'; } }
  async function save() { if (!settings) return; busy = true; error = null; try { settings = await patchSettings(settings); showToast('Settings saved'); } catch(e) { error = e instanceof Error ? e.message : 'Unable to save settings'; } finally { busy = false; } }
  load();
</script>

<ModalFrame title="Settings" onClose={onClose}>
  <ErrorMessage message={error} />
  {#if !settings}<div class="empty">Loading settings…</div>{:else}
    <div class="form-grid">
      <div class="field"><label>Rate limit</label><input class="input" bind:value={settings.rateLimit} placeholder="100K or 1M" /></div>
      <div class="field"><label>Temporary directory</label><input class="input" bind:value={settings.tempDirectory} /></div>
      <div class="field"><label>Max parallel downloads</label><input class="input" type="number" min="1" bind:value={settings.maxParallelDownloads} /></div>
      <div class="field"><label>Retry count</label><input class="input" type="number" bind:value={settings.retryCount} /></div>
      <div class="field"><label>Socket timeout</label><input class="input" type="number" bind:value={settings.socketTimeout} /></div>
    </div>
    <div class="dialog-actions"><button class="btn" on:click={onClose}>Close</button><button class="btn primary" disabled={busy} on:click={save}>{busy ? 'Saving…' : 'Save settings'}</button></div>
  {/if}
</ModalFrame>
