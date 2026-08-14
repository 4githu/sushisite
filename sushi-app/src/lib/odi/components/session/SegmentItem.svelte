<script lang="ts">
	type SegmentVariant = "button" | "card";

	let {
		label = "text",
		description,
		icon,
		selected = false,
		disabled = false,
		variant = "button",
		width,
		onclick
	}: {
		label?: string;
		description?: string;
		icon?: string;
		selected?: boolean;
		disabled?: boolean;
		variant?: SegmentVariant;
		width?: string;
		onclick?: (event: MouseEvent) => void;
	} = $props();

	const styleVars = $derived(
		`--segment-width:${width ?? (variant === "card" ? "184px" : "228.33px")};`
	);
</script>

<button
	type="button"
	class={["segment-item", "clickable", variant, selected && "selected"]}
	style={styleVars}
	disabled={disabled}
	onclick={onclick}
>
	{#if icon}
		<img class="icon" src={icon} alt="" />
	{/if}

	<div class="text-group">
		<span class={variant === "card" ? "text-body-active" : "text-body"}>
			{label}
		</span>

		{#if description}
			<span class="description text-caption-medium">
				{description}
			</span>
		{/if}
	</div>
</button>

<style>
	.segment-item {
		width: var(--segment-width);

		display: inline-flex;
		align-items: center;
		justify-content: center;

		overflow: hidden;

		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);

		background: var(--surface);

		color: var(--text-secondary);
	}

	.segment-item:hover:not(:disabled) {
		border-color: var(--primary);
	}

	.segment-item.selected {
		border-color: var(--primary);

		color: var(--primary);
	}

	.segment-item:disabled {
		background: rgba(212, 214, 226, 0.2);

		color: var(--text-disabled);
	}

	.button {
		height: 50px;

		padding: 11px;
	}

	.card {
		height: 148px;

		flex-direction: column;

		gap: 14px;

		padding: 11px;
	}

	.card.selected {
		background: var(--blue-light);
	}

	.icon {
		width: 36px;
		height: 36px;

		flex-shrink: 0;

		object-fit: contain;
		/* Source SVGs have different baked-in colours. Keep every option neutral
		 * until it is selected, then use the same blue as the control. */
		filter: grayscale(1) saturate(0) brightness(0.62);
	}

	.selected .icon {
		filter: brightness(0) saturate(100%) invert(17%) sepia(97%) saturate(5138%) hue-rotate(233deg) brightness(103%) contrast(102%);
	}

	.text-group {
		display: flex;
		flex-direction: column;
		align-items: center;

		gap: var(--space-1);

		text-align: center;
	}

	.description {
		color: var(--text-disabled);
	}

	.selected .description {
		color: var(--text-secondary);
	}
</style>
