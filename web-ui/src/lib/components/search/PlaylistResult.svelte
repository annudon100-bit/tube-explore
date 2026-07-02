<script lang="ts">
  import type { PlaylistResponse } from '$lib/api/types';
  import { duration } from '$lib/utils/format';
  export let data: PlaylistResponse;
  export let onDownloadPlaylist: (url: string) => void = () => {};
  export let onDownloadVideo: (url: string) => void = () => {};
</script>

<div class="grid" style="gap:18px">
  <div class="panel card" style="box-shadow:none">
    <div class="card-header">
      <div>
        <h3>{data.count} entries</h3>
        <div class="row-sub">Total duration: {duration(data.totalDuration)}</div>
      </div>
      <button class="btn green" on:click={() => onDownloadPlaylist(data.url)}>Download playlist</button>
    </div>
    <div class="row-sub">{data.url}</div>
  </div>

  <div class="simple-list">
    {#each data.entries as entry, i}
      <div class="row">
        <div class="avatar">{i + 1}</div>
        <div>
          <div class="row-title">{entry.title || entry.id}</div>
          <div class="row-sub">{entry.channel || 'Unknown channel'} · {duration(entry.duration)}</div>
          <div class="row-sub">{entry.url}</div>
        </div>
        <button class="btn red" on:click={() => onDownloadVideo(entry.url)}>Download</button>
      </div>
    {/each}
  </div>
</div>
