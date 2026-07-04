<script lang="ts">
  import { clampPercent } from '$lib/utils/format';
  import type { FileProgress } from '$lib/api/types';

  export let file: FileProgress;
  export let isActive: boolean = false;

  $: pct = clampPercent(file.percent);
  $: label = file.title || (file.status === 'pending' ? `Video ${file.index + 1}` : `Video ${file.index + 1}`);
  $: statusIcon = file.status === 'downloading' ? '▸' : file.status === 'completed' ? '✓' : file.status === 'failed' ? '✗' : '○';
</script>

<div class="file-row" class:active={isActive}>
  {#if file.thumbnailUrl}
    <img src={file.thumbnailUrl} alt="" class="file-thumb" />
  {/if}
  <div class="row-main">
    <span class="status-icon" class:spin={file.status === 'downloading'}>{statusIcon}</span>
    <span class="file-title">{label}</span>
  </div>
  <div class="row-meta">
    {#if file.percent > 0 && file.status !== 'completed'}
      <span class="file-pct">{pct}%</span>
    {/if}
    {#if file.speed && file.status === 'downloading'}
      <span class="file-speed">{file.speed}</span>
    {/if}
    {#if file.eta && file.status === 'downloading'}
      <span class="file-eta">{file.eta}</span>
    {/if}
  </div>
  <div class="progress-mini-track">
    <div class="progress-mini-bar" style={`width: ${pct}%`} class:completed={file.status === 'completed'} class:failed={file.status === 'failed'}></div>
  </div>
</div>

<style>
  .file-row {
    display: grid;
    grid-template-columns: auto 1fr auto;
    grid-template-rows: auto auto;
    gap: 2px 10px;
    padding: 6px 8px;
    border-radius: 6px;
    background: rgba(255,255,255,0.03);
    transition: background 0.15s;
    align-items: center;
  }
  .file-row.active {
    background: rgba(139, 92, 246, 0.08);
  }
  .file-thumb {
    width: 40px;
    height: 24px;
    border-radius: 4px;
    object-fit: cover;
    grid-row: 1 / 2;
  }
  .row-main {
    display: flex;
    align-items: center;
    gap: 6px;
    overflow: hidden;
    grid-row: 1 / 2;
  }
  .status-icon {
    flex-shrink: 0;
    width: 14px;
    font-size: 11px;
    color: var(--text-muted);
  }
  .status-icon.spin {
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 1; }
  }
  .file-title {
    font-size: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .row-meta {
    display: flex;
    gap: 8px;
    align-items: center;
    justify-self: end;
    font-size: 11px;
    color: var(--text-muted);
    grid-row: 1 / 2;
  }
  .file-pct { font-variant-numeric: tabular-nums; }
  .file-speed { color: var(--accent); }
  .file-eta { color: var(--text-muted); }
  .progress-mini-track {
    grid-column: 1 / -1;
    height: 3px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
    overflow: hidden;
  }
  .progress-mini-bar {
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    transition: width 0.5s ease;
  }
  .progress-mini-bar.completed {
    background: var(--green, #22c55e);
  }
  .progress-mini-bar.failed {
    background: var(--red, #ef4444);
  }
</style>
