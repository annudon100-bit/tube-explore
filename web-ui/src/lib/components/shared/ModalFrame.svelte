<script lang="ts">
  export let title = '';
  export let size: 'small' | 'normal' | 'large' = 'normal';
  export let onClose: () => void = () => {};
</script>

<div class="modal-backdrop" role="presentation" on:click={onClose}>
  <section class="modal {size === 'small' ? 'small' : size === 'large' ? 'large' : ''}" role="dialog" aria-modal="true" aria-label={title} on:click|stopPropagation>
    <header class="modal-head">
      <h2>{title}</h2>
      <button class="close-btn" type="button" aria-label="Close" on:click={onClose}>×</button>
    </header>
    <div class="modal-body">
      <slot />
    </div>
  </section>
</div>
