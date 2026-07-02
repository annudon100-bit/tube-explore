<script lang="ts">
  import type { MetadataResponse } from '$lib/api/types';
  import { bytes, duration } from '$lib/utils/format';
  export let data: MetadataResponse;
  export let onDownload: (url: string) => void = () => {};
</script>

<div class="grid" style="gap:18px">
  <div class="row" style="border:1px solid var(--line); border-radius:20px;">
    {#if data.thumbnail}<img class="thumb" src={data.thumbnail} alt="" />{:else}<div class="thumb">▶</div>{/if}
    <div>
      <div class="row-title">{data.title || data.id}</div>
      <div class="row-sub">{data.channel || 'Unknown channel'} · {duration(data.duration)} · Best {data.bestHeight || '—'}p</div>
      <div class="row-sub">{data.url}</div>
    </div>
    <button class="btn red" type="button" on:click={() => onDownload(data.url)}>Download</button>
  </div>

  {#if data.description}
    <div class="panel card" style="box-shadow:none"><p>{data.description}</p></div>
  {/if}

  <h3>Available formats</h3>
  {#if data.formats.length === 0}
    <div class="empty">No format details returned.</div>
  {:else}
    <div class="simple-list">
      {#each data.formats as format}
        <div class="row">
          <div class="avatar">{format.ext || 'fmt'}</div>
          <div>
            <div class="row-title">{format.formatId}</div>
            <div class="row-sub">{format.width || '—'}×{format.height || '—'} · {format.vcodec || 'no video'} / {format.acodec || 'no audio'} · {format.fps || '—'} fps</div>
          </div>
          <button class="btn" type="button" on:click={() => navigator.clipboard?.writeText(format.formatId)}>Copy ID</button>
        </div>
      {/each}
    </div>
  {/if}
</div>
