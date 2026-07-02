<script lang="ts">
  import type { SearchResponse, SearchResult } from '$lib/api/types';
  import { duration } from '$lib/utils/format';
  export let data: SearchResponse;
  export let onInspect: (url: string) => void = () => {};
  export let onDownload: (url: string) => void = () => {};
</script>

{#if data.results.length === 0}
  <div class="empty">No results for “{data.query}”.</div>
{:else}
  <div class="simple-list">
    {#each data.results as item}
      <div class="row">
        {#if item.thumbnail}
          <img class="thumb" src={item.thumbnail} alt="" />
        {:else}
          <div class="thumb">▶</div>
        {/if}
        <div>
          <div class="row-title">{item.title || item.id}</div>
          <div class="row-sub">{item.channel || 'Unknown channel'} · {duration(item.duration)}</div>
          <div class="row-sub">{item.url}</div>
        </div>
        <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end">
          <button class="btn blue" on:click={() => onInspect(item.url)}>Inspect</button>
          <button class="btn red" on:click={() => onDownload(item.url)}>Download</button>
        </div>
      </div>
    {/each}
  </div>
{/if}
