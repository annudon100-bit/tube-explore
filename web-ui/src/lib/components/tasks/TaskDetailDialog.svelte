<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import StatusBadge from '$lib/components/shared/StatusBadge.svelte';
  import ProgressBar from '$lib/components/shared/ProgressBar.svelte';
  import FileProgressRow from '$lib/components/shared/FileProgressRow.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import StatsGrid from '$lib/components/downloads/live/StatsGrid.svelte';
  import { cancelTask, deleteTask, getTask, getTaskResult, retryTask } from '$lib/api/tasks';
  import { fileDownloadUrl } from '$lib/api/files';
  import { tasks } from '$lib/state/event-stream';
  import { showToast } from '$lib/state/toast-state';
  import { bytes, dateTime, duration } from '$lib/utils/format';
  import { API_BASE_URL } from '$lib/config/env';
  import type { TaskResponse, TaskResultResponse } from '$lib/api/types';

  export let task: TaskResponse;
  export let onClose: () => void = () => {};
  export let onChanged: () => void = () => {};
  let current = task;
  let result: TaskResultResponse | null = null;
  let error: string | null = null;

  $: {
    const updated = $tasks.find(t => t.id === current.id);
    if (updated) current = updated;
  }
  $: thumbnailUrl = current.thumbnailPath ? `${API_BASE_URL}${current.thumbnailPath}` : null;
  $: isPartiallyFailed = current.status === 'completed' && !!current.error;
  $: fileList = current.fileProgress ?? [];
  $: activeIdx = fileList.findIndex(f => f.status === 'downloading');

  async function refresh() {
    try { current = await getTask(current.id); } catch (e) { error = e instanceof Error ? e.message : 'Unable to refresh task'; }
  }
  async function loadResult() {
    try { result = await getTaskResult(current.id); } catch (e) { error = e instanceof Error ? e.message : 'Unable to load result'; }
  }
  async function doCancel() {
    try { await cancelTask(current.id); showToast('Task cancelled'); await refresh(); onChanged(); } catch (e) { error = e instanceof Error ? e.message : 'Unable to cancel'; }
  }
  async function doRetry() {
    try { const next = await retryTask(current.id); showToast(`Retry queued: ${next.taskId}`); onChanged(); onClose(); } catch (e) { error = e instanceof Error ? e.message : 'Unable to retry'; }
  }
  async function doDelete() {
    try { await deleteTask(current.id); showToast('Task deleted'); onChanged(); onClose(); } catch (e) { error = e instanceof Error ? e.message : 'Unable to delete'; }
  }
</script>

<ModalFrame title="Task details" onClose={onClose}>
  <ErrorMessage message={error} />
  <div class="grid" style="gap:16px">
    {#if thumbnailUrl}
      <div class="thumb-row">
        <img class="thumb" src={thumbnailUrl} alt="" />
        <div class="thumb-meta">
          <h3>{current.title || (current.type === 'playlist' ? 'Playlist' : 'Video')}</h3>
          {#if current.channel}<span class="row-sub">{current.channel}</span>{/if}
          {#if current.duration}<span class="row-sub">{duration(current.duration)}</span>{/if}
        </div>
      </div>
    {/if}
    <div class="panel card" style="box-shadow:none">
      <div class="card-header">
        <div>
          <h3>{current.type} task</h3>
          <div class="row-sub">{current.id}</div>
        </div>
        <StatusBadge status={current.status} />
      </div>
      <ProgressBar value={current.progressPercent} />
    </div>

    {#if current.status === 'running' || current.status === 'completed'}
      <div class="panel card" style="box-shadow:none">
        <StatsGrid
          speed={current.speed}
          eta={current.eta}
          totalBytes={current.totalBytes}
          downloadedBytes={current.downloadedBytes}
          elapsed={current.elapsed}
          step={current.progressStep}
        />
      </div>
    {/if}

    {#if fileList.length > 1}
      <div class="panel card" style="box-shadow:none">
        <div class="card-header"><h3>Files ({fileList.length})</h3></div>
        <div class="file-tree">
          {#each fileList as file, i}
            <FileProgressRow {file} isActive={i === activeIdx} />
          {/each}
        </div>
      </div>
    {:else if fileList.length === 1 && fileList[0].title}
      <div class="file-tree">
        <FileProgressRow file={fileList[0]} isActive={fileList[0].status === 'downloading'} />
      </div>
    {/if}

    <div class="kv"><b>URL</b><span>{current.url}</span></div>
    <div class="kv"><b>Created</b><span>{dateTime(current.createdAt)}</span></div>
    <div class="kv"><b>Updated</b><span>{dateTime(current.updatedAt)}</span></div>
    <div class="kv"><b>Completed</b><span>{dateTime(current.completedAt)}</span></div>
    {#if current.error}<div class="kv"><b>Error</b><span class="bad">{current.error}</span></div>{/if}

    <div class="action-row">
      <button class="btn" on:click={refresh}>Refresh</button>
      <button class="btn orange" disabled={!['pending','running'].includes(current.status)} on:click={doCancel}>Cancel</button>
      <button class="btn green" disabled={!(current.status === 'failed' || isPartiallyFailed)} on:click={doRetry}>Retry</button>
      <button class="btn red" disabled={['pending','running'].includes(current.status)} on:click={doDelete}>Delete</button>
      {#if current.status === 'completed'}
        <button class="btn" on:click={loadResult}>View result</button>
      {/if}
    </div>

    {#if result || current.result}
      <h3>Result files</h3>
      <div class="simple-list">
        {#each (result?.files || current.result || []) as file}
          <div class="row">
            <div class="avatar">▣</div>
            <div><div class="row-title">{file.name}</div><div class="row-sub">{bytes(file.size)} · {file.path}</div></div>
            {#if file.id}<a class="btn blue" href={fileDownloadUrl(file.id)}>Download</a>{/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</ModalFrame>

<style>
  .file-tree {
    display: grid;
    gap: 4px;
    margin-top: 6px;
  }
  .thumb-row {
    display: flex;
    gap: 14px;
    align-items: flex-start;
  }
  .thumb {
    width: 160px;
    height: 90px;
    border-radius: 12px;
    object-fit: cover;
    flex-shrink: 0;
    background: rgba(255,255,255,0.06);
  }
  .thumb-meta {
    min-width: 0;
    overflow: hidden;
  }
  .thumb-meta h3 {
    margin: 0 0 6px;
    font-size: 18px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .thumb-meta .row-sub {
    margin-top: 0;
  }
</style>