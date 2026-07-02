<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import EmptyState from '$lib/components/shared/EmptyState.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import PaginationControls from '$lib/components/shared/PaginationControls.svelte';
  import ConfirmDialog from '$lib/components/shared/ConfirmDialog.svelte';
  import ProfileFormDialog from './ProfileFormDialog.svelte';
  import { deleteProfile, listProfiles } from '$lib/api/profiles';
  import { showToast } from '$lib/state/toast-state';
  import type { ProfileResponse } from '$lib/api/types';

  export let onClose: () => void = () => {};
  let profiles: ProfileResponse[] = [];
  let editing: ProfileResponse | null | 'new' = null;
  let confirmDelete: ProfileResponse | null = null;
  let limit = 50; let offset = 0; let error: string | null = null; let busy = false;
  async function load() { busy = true; error = null; try { profiles = await listProfiles({ limit, offset }); } catch(e) { error = e instanceof Error ? e.message : 'Unable to load profiles'; } finally { busy = false; } }
  async function remove() { if (!confirmDelete) return; try { await deleteProfile(confirmDelete.id); showToast('Profile deleted'); confirmDelete = null; await load(); } catch(e) { error = e instanceof Error ? e.message : 'Unable to delete profile'; } }
  $: loadKey = `${limit}:${offset}`;
  $: if (loadKey) load();
</script>

<ModalFrame title="Profiles" size="large" onClose={onClose}>
  <ErrorMessage message={error} />
  <div class="card-header"><span></span><button class="btn primary" on:click={() => editing = 'new'}>Create profile</button></div>
  {#if busy}<div class="empty">Loading profiles…</div>{:else if profiles.length === 0}<EmptyState title="No profiles yet" detail="Create a reusable profile for common download settings." />{:else}
    <div class="simple-list">
      {#each profiles as profile}
        <div class="row">
          <div class="avatar">♙</div>
          <div><div class="row-title">{profile.label || profile.name}</div><div class="row-sub">{profile.downloadQualityMode} · {profile.downloadDirectory || 'default directory'} · {profile.convertPreset || 'no conversion'}</div></div>
          <div style="display:flex; gap:8px; justify-content:flex-end"><button class="btn" on:click={() => editing = profile}>Edit</button><button class="btn red" on:click={() => confirmDelete = profile}>Delete</button></div>
        </div>
      {/each}
    </div>
  {/if}
  <PaginationControls {limit} {offset} onChange={(l, o) => { limit = l; offset = o; }} />
  {#if editing}<ProfileFormDialog profile={editing === 'new' ? null : editing} onClose={() => editing = null} onSaved={load} />{/if}
  {#if confirmDelete}<ConfirmDialog title="Delete profile" message={`Delete profile “${confirmDelete.name}”?`} confirmLabel="Delete" onCancel={() => confirmDelete = null} onConfirm={remove} />{/if}
</ModalFrame>
