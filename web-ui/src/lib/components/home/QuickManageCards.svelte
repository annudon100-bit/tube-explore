<script lang="ts">
  export let onOpen: (key: string) => void = () => {};
  const cards = [
    ['profiles', '♙', 'Profiles', 'Create and manage download profiles.', 'tint-blue'],
    ['presets', '⚙', 'Presets', 'Configure conversion presets.', 'tint-green'],
    ['outbox', '▱', 'Outbox', 'Review and retry failed conversions.', 'tint-purple'],
    ['settings', '◌', 'Settings', 'Adjust global preferences.', 'tint-orange']
  ];
</script>

<div class="grid manage-grid">
  {#each cards as [key, icon, title, detail, tint]}
    <button class="manage-card" type="button" on:click={() => onOpen(key)}>
      <div>
        <div class="manage-icon {tint}">{icon}</div>
        <h3>{title}</h3>
        <p class="row-sub" style="white-space: normal">{detail}</p>
      </div>
      <strong>Open →</strong>
    </button>
  {/each}
</div>
