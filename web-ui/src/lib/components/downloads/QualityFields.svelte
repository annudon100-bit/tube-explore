<script lang="ts">
  import type { QualityMode } from '$lib/api/types';
  export let mode: QualityMode | '' = '';
  export let value: number | null = null;
  export let onChange: (mode: QualityMode | '', value: number | null) => void = () => {};

  $: needsValue = mode === 'at_most' || mode === 'at_least';
</script>

<div class="field">
  <label>Quality mode</label>
  <select class="select" bind:value={mode} on:change={() => onChange(mode, value)}>
    <option value="">Use default/profile</option>
    <option value="best">Best</option>
    <option value="least">Least</option>
    <option value="at_most">At most</option>
    <option value="at_least">At least</option>
  </select>
</div>
<div class="field">
  <label>Quality value</label>
  <input class="input" type="number" min="1" placeholder={needsValue ? 'Pixel height, e.g. 1080' : 'Optional'} bind:value={value} on:input={() => onChange(mode, value)} />
</div>
