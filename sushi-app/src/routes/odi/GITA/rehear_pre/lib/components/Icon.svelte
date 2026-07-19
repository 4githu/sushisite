<script lang="ts">
  const { name = 'Property 1=chevron_down, Size=20', size = 20, alt = 'icon' } = $props();
  const iconPath = `../Icons/${encodeURIComponent(name)}`;
  const src = new URL(iconPath, import.meta.url).href;
</script>

<img class="rehear-icon" src={src} alt={alt} width={size} height={size} />
