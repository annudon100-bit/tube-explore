<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import EmptyState from '$lib/components/shared/EmptyState.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import PaginationControls from '$lib/components/shared/PaginationControls.svelte';
  import { fileDownloadUrl, listFiles } from '$lib/api/files';
  import { bytes, dateTime } from '$lib/utils/format';
  import type { FileInfo } from '$lib/api/types';

  export let onClose: () => void = () => {};
  let files: FileInfo[] = [];
  let limit = 50;
  let offset = 0;
  let error: string | null = null;
  let busy = false;
  async function load() {
    busy = true; error = null;
    try { files = await listFiles({ limit, offset }); } catch (e) { error = e instanceof Error ? e.message : 'Unable to load files'; } finally { busy = false; }
  }
  $: loadKey = `${limit}:${offset}`;
  $: if (loadKey) load();
</script>

<ModalFrame title="Downloaded files" size="large" onClose={onClose}>
  <ErrorMessage message={error} />
  {#if busy}<div class="empty">Loading files…</div>{:else if files.length === 0}<EmptyState title="No downloaded files" detail="Completed task files will appear here." />{:else}
    <div class="simple-list">
      {#each files as file}
        <div class="row">
          <div class="avatar">▣</div>
          <div>
            <div class="row-title">{file.name}</div>
            <div class="row-sub">{bytes(file.size)} · {dateTime(file.createdAt)}</div>
            <div class="row-sub">{file.path}</div>
          </div>
          <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end">
            {#if file.id}<a class="btn blue" href={fileDownloadUrl(file.id)}>Download</a>{/if}
            <button class="btn" on:click={() => navigator.clipboard?.writeText(file.path)}>Copy path</button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
  <PaginationControls {limit} {offset} onChange={(l, o) => { limit = l; offset = o; }} />
</ModalFrame>
