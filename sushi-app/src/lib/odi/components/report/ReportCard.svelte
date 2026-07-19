<!-- src/lib/odi/components/report/ReportCard.svelte -->

<script lang="ts">
	import type { Snippet } from "svelte";

	let {
		children,
		className = "",
		padding = "20px",
		minHeight = "auto"
	}: {
		children: Snippet;
		className?: string;
		padding?: string;
		minHeight?: string;
	} = $props();
</script>

<section class={`report-card ${className}`} style={`--card-padding: ${padding}; --card-min-height: ${minHeight};`}>
	{@render children()}
</section>

<style>
	.report-card {
		min-height: var(--card-min-height);
		padding: var(--card-padding);
		border-radius: var(--radius-md);
		background: var(--surface);
		box-shadow: 0 0 8px rgba(0, 0, 0, 0.15);
		overflow: hidden;
	}
</style>