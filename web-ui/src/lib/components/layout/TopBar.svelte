<script lang="ts">
  export let onNewDownload: () => void = () => {};
  let light = true;
</script>

<div class="topbar">
  <div class="page-title">
    <h1>What would you like to do today?</h1>
    <p>Search, inspect, and download media without clutter.</p>
  </div>
  <div class="top-actions">
    <button class="btn" type="button" on:click={() => light = !light}>{light ? '☀ Light' : '◐ Dark'}</button>
    <button class="btn primary" type="button" on:click={onNewDownload}>＋ New Download</button>
  </div>
</div>
