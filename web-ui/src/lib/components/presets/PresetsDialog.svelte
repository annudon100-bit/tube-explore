<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import EmptyState from '$lib/components/shared/EmptyState.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import PaginationControls from '$lib/components/shared/PaginationControls.svelte';
  import ConfirmDialog from '$lib/components/shared/ConfirmDialog.svelte';
  import PresetFormDialog from './PresetFormDialog.svelte';
  import { deletePreset, listPresets } from '$lib/api/presets';
  import { showToast } from '$lib/state/toast-state';
  import type { ConversionPresetResponse } from '$lib/api/types';

  export let onClose: () => void = () => {};
  let presets: ConversionPresetResponse[] = [];
  let editing: ConversionPresetResponse | null | 'new' = null;
  let confirmDelete: ConversionPresetResponse | null = null;
  let limit = 50; let offset = 0; let error: string | null = null; let busy = false;
  async function load() { busy = true; error = null; try { presets = await listPresets({ limit, offset }); } catch(e) { error = e instanceof Error ? e.message : 'Unable to load presets'; } finally { busy = false; } }
  async function remove() { if (!confirmDelete) return; try { await deletePreset(confirmDelete.name); showToast('Preset deleted'); confirmDelete = null; await load(); } catch(e) { error = e instanceof Error ? e.message : 'Unable to delete preset'; } }
  $: loadKey = `${limit}:${offset}`;
  $: if (loadKey) load();
</script>

<ModalFrame title="Conversion presets" size="large" onClose={onClose}>
  <ErrorMessage message={error} />
  <div class="card-header"><span></span><button class="btn primary" on:click={() => editing = 'new'}>Create preset</button></div>
  {#if busy}<div class="empty">Loading presets…</div>{:else if presets.length === 0}<EmptyState title="No presets yet" detail="Create a conversion preset for repeated encoding settings." />{:else}
    <div class="simple-list">
      {#each presets as preset}
        <div class="row">
          <div class="avatar">⚙</div>
          <div><div class="row-title">{preset.label || preset.name}</div><div class="row-sub">{preset.container} → .{preset.outputExt} · {preset.videoCodec || 'no video'} / {preset.audioCodec || 'no audio'}</div></div>
          <div style="display:flex; gap:8px; justify-content:flex-end"><button class="btn" on:click={() => editing = preset}>Edit</button><button class="btn red" on:click={() => confirmDelete = preset}>Delete</button></div>
        </div>
      {/each}
    </div>
  {/if}
  <PaginationControls {limit} {offset} onChange={(l, o) => { limit = l; offset = o; }} />
  {#if editing}<PresetFormDialog preset={editing === 'new' ? null : editing} onClose={() => editing = null} onSaved={load} />{/if}
  {#if confirmDelete}<ConfirmDialog title="Delete preset" message={`Delete preset “${confirmDelete.name}”?`} confirmLabel="Delete" onCancel={() => confirmDelete = null} onConfirm={remove} />{/if}
</ModalFrame>
