<script lang="ts">
  export let limit = 50;
  export let offset = 0;
  export let onChange: (limit: number, offset: number) => void = () => {};

  function updateLimit(value: string) {
    limit = Number(value);
    offset = 0;
    onChange(limit, offset);
  }
</script>

<div class="pager">
  <select class="select" style="width: 110px" bind:value={limit} on:change={(e) => updateLimit((e.currentTarget as HTMLSelectElement).value)}>
    <option value={10}>10</option>
    <option value={25}>25</option>
    <option value={50}>50</option>
    <option value={100}>100</option>
    <option value={200}>200</option>
  </select>
  <button class="btn" disabled={offset === 0} on:click={() => { offset = Math.max(0, offset - limit); onChange(limit, offset); }}>Previous</button>
  <button class="btn" on:click={() => { offset += limit; onChange(limit, offset); }}>Next</button>
</div>
