<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import { getHealth, getReady } from '$lib/api/health';
  import type { HealthResponse } from '$lib/api/types';

  export let health: HealthResponse | null = null;
  export let onClose: () => void = () => {};
  let ready: HealthResponse | null = null;
  let error: string | null = null;
  async function refresh() { try { health = await getHealth(); ready = await getReady(); } catch(e) { error = e instanceof Error ? e.message : 'Unable to load health'; } }
  refresh();
</script>

<ModalFrame title="System health" onClose={onClose}>
  <ErrorMessage message={error} />
  {#if !health}<div class="empty">Loading health…</div>{:else}
    <div class="grid" style="gap:8px">
      <div class="kv"><b>Status</b><span>{health.status}</span></div>
      <div class="kv"><b>Readiness</b><span>{ready?.status || '—'}</span></div>
      <div class="kv"><b>ffmpeg</b><span class={health.hasFfmpeg ? 'ok' : 'bad'}>{health.hasFfmpeg ? `OK ${health.ffmpegVersion || ''}` : 'Missing'}</span></div>
      <div class="kv"><b>yt-dlp</b><span class={health.hasYtdlp ? 'ok' : 'bad'}>{health.hasYtdlp ? `OK ${health.ytdlpVersion || ''}` : 'Missing'}</span></div>
      <div class="kv"><b>Download directory</b><span class={health.downloadDirectoryWritable ? 'ok' : 'bad'}>{health.downloadDirectoryWritable ? 'Writable' : 'Not writable'}</span></div>
      <div class="kv"><b>Temp directory</b><span class={health.tempDirectoryWritable ? 'ok' : 'bad'}>{health.tempDirectoryWritable ? 'Writable' : 'Not writable'}</span></div>
      <div class="kv"><b>Worker</b><span class={health.workerRunning ? 'ok' : 'bad'}>{health.workerRunning ? 'Running' : 'Stopped'}</span></div>
      <div class="kv"><b>SSE connections</b><span>{health.activeSseConnections}</span></div>
    </div>
    <div class="dialog-actions"><button class="btn" on:click={refresh}>Refresh</button><button class="btn primary" on:click={onClose}>Done</button></div>
  {/if}
</ModalFrame>
