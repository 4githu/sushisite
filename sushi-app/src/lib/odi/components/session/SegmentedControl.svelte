<script lang="ts">
	import SegmentItem from "$lib/odi/components/session/SegmentItem.svelte";

	type SegmentVariant = "button" | "card";

	type SegmentOption = {
		label: string;
		value: string;
		description?: string;
		icon?: string;
	};

	let {
		items = [],
		selected = $bindable(""),
		variant = "button",
		itemWidth,
		gap = "20px",
		disabled = false
	}: {
		items?: SegmentOption[];
		selected?: string;
		variant?: SegmentVariant;
		itemWidth?: string;
		gap?: string;
		disabled?: boolean;
	} = $props();

	const styleVars = $derived(`--segment-gap:${gap};`);

	function select(value: string) {
		if (disabled) return;

		selected = value;
	}
</script>

<div class={["segmented-control", variant]} style={styleVars}>
	{#each items as item}
		<SegmentItem
			label={item.label}
			description={item.description}
			icon={item.icon}
			selected={selected === item.value}
			{disabled}
			{variant}
			width={itemWidth}
			onclick={() => select(item.value)}
		/>
	{/each}
</div>

<style>
	.segmented-control {
		display: inline-flex;
		align-items: center;

		gap: var(--segment-gap);
	}

	.card {
		align-items: flex-start;
	}
</style>