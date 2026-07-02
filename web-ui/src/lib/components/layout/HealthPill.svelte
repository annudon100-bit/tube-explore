<script lang="ts">
  import type { HealthResponse } from '$lib/api/types';
  export let health: HealthResponse | null = null;
  export let onOpen: () => void = () => {};

  $: healthy = !!health && health.status === 'ok' && health.hasFfmpeg && health.hasYtdlp && health.workerRunning && health.downloadDirectoryWritable && health.tempDirectoryWritable;
</script>

<div class="health-pill">
  <strong class={healthy ? 'ok' : 'bad'}>{healthy ? 'System Healthy' : 'Needs Attention'}</strong>
  <div class="health-line"><span>ffmpeg</span><b class={health?.hasFfmpeg ? 'ok' : 'bad'}>{health?.hasFfmpeg ? 'OK' : 'Missing'}</b></div>
  <div class="health-line"><span>yt-dlp</span><b class={health?.hasYtdlp ? 'ok' : 'bad'}>{health?.hasYtdlp ? 'OK' : 'Missing'}</b></div>
  <div class="health-line"><span>Worker</span><b class={health?.workerRunning ? 'ok' : 'bad'}>{health?.workerRunning ? 'Running' : 'Stopped'}</b></div>
  <button class="btn ghost" type="button" on:click={onOpen}>View Health</button>
</div>
