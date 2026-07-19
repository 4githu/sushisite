<script lang="ts">
  const { options = [], selectedIndex = 0 } = $props();
</script>

<div class="rehear-segmented-control">
  {#each options as option, index}
    <button class="rehear-segmented-tab {selectedIndex === index ? 'selected' : ''}">
      {option}
    </button>
  {/each}
</div>
