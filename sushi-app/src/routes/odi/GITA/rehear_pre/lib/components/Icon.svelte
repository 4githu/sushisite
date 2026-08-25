<script lang="ts">
	const { name = 'Property 1=chevron_down, Size=20', size = 20, alt = 'icon' } = $props();
	const src = $derived(new URL(`../Icons/${encodeURIComponent(name)}`, import.meta.url).href);
</script>

<img class="rehear-icon" {src} {alt} width={size} height={size} />
