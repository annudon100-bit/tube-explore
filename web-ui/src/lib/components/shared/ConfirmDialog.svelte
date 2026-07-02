<script lang="ts">
  import ModalFrame from './ModalFrame.svelte';
  export let title = 'Confirm action';
  export let message = 'Are you sure?';
  export let confirmLabel = 'Confirm';
  export let onCancel: () => void = () => {};
  export let onConfirm: () => void = () => {};
</script>

<ModalFrame {title} size="small" onClose={onCancel}>
  <p>{message}</p>
  <div class="dialog-actions">
    <button class="btn" type="button" on:click={onCancel}>Cancel</button>
    <button class="btn red" type="button" on:click={onConfirm}>{confirmLabel}</button>
  </div>
</ModalFrame>
