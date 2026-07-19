<script lang="ts">
  const { title = 'Card title', highlight = false, children } = $props();
</script>

<div class="rehear-card {highlight ? 'highlight' : ''}">
  <div class="card-header">
    <div>
      <div class="card-title">{title}</div>
    </div>
  </div>
  <div class="card-body">
    {@render children()}
  </div>
</div>
