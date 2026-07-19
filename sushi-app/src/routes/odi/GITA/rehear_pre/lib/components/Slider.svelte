<script lang="ts">
  const { values = [], activeIndex = 0 } = $props();
  const progress = () => Math.max(0, Math.min(100, values.length > 1 ? (activeIndex / (values.length - 1)) * 100 : 0));
</script>

<div class="rehear-slider">
  <div class="rehear-slider-track"></div>
  <div class="rehear-slider-progress" style="width: {progress()}%"></div>
  <div class="rehear-slider-points">
    {#each values as value, index}
      <div class="rehear-slider-point {index === activeIndex ? 'active' : ''}">
        <span>{value}</span>
      </div>
    {/each}
  </div>
</div>
