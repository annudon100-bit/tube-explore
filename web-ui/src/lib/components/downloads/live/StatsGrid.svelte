<script lang="ts">
  import { bytes } from '$lib/utils/format';

  export let speed: string | null | undefined = null;
  export let eta: string | null | undefined = null;
  export let totalBytes: number | null | undefined = null;
  export let downloadedBytes: number | null | undefined = null;
  export let elapsed: number | null | undefined = null;
  export let step: string | null | undefined = null;

  $: formattedElapsed = elapsed != null ? formatElapsed(elapsed) : null;

  function formatElapsed(sec: number): string {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  }
</script>

<div class="stats-grid">
  <div class="stat">
    <span class="stat-label">Speed</span>
    <span class="stat-value">{speed || (step === 'fetching_metadata' ? '…' : '—')}</span>
  </div>
  <div class="stat">
    <span class="stat-label">ETA</span>
    <span class="stat-value">{eta || (step === 'fetching_metadata' ? '…' : '—')}</span>
  </div>
  <div class="stat">
    <span class="stat-label">Size</span>
    <span class="stat-value">{totalBytes ? bytes(totalBytes) : '—'}</span>
  </div>
  <div class="stat">
    <span class="stat-label">Elapsed</span>
    <span class="stat-value">{formattedElapsed || '—'}</span>
  </div>
</div>

<style>
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
  }
  .stat {
    display: grid;
    gap: 2px;
    padding: 10px 12px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
  }
  .stat-label {
    font-size: 11px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .stat-value {
    font-size: 14px;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }
</style>
