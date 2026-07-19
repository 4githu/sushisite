<!-- src/lib/odi/components/login/OdiJoinOptionCard.svelte -->
<script lang="ts">
	let {
		title,
		description = "",
		icon,
		selected = false,
		wide = false,
		onclick
	}: {
		title: string;
		description?: string;
		icon?: string;
		selected?: boolean;
		wide?: boolean;
		onclick?: () => void;
	} = $props();
</script>

<button
	type="button"
	class="option-card clickable"
	class:selected
	class:wide
	onclick={onclick}
>
	{#if icon}
		<div class="icon-box">
			<img src={icon} alt="" />
		</div>
	{/if}

	<div class="text-group">
		<strong>{title}</strong>

		{#if description}
			<p>{description}</p>
		{/if}
	</div>
</button>

<style>
	.option-card {
		min-height: 80px;
		padding: 11px 20px;
		display: flex;
		align-items: center;
		gap: 28px;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
		text-align: left;
		color: var(--text-secondary);
	}

	.option-card.wide {
		min-height: 80px;
	}

	.option-card.selected {
		border: 2px solid var(--primary);
		background: rgba(0, 51, 255, 0.05);
		color: var(--brand-black);
	}

	.icon-box {
		width: 48px;
		height: 48px;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		border-radius: var(--radius-sm);
		background: var(--cool-grey-light-active);
	}

	.option-card.selected .icon-box {
		background: rgba(0, 51, 255, 0.15);
	}

	.icon-box img {
		width: 28px;
		height: 28px;
		object-fit: contain;
	}

	.text-group {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		min-width: 0;
	}

	.text-group strong {
		color: inherit;
		font-size: 18px;
		font-weight: var(--font-medium);
		line-height: 140%;
	}

	.text-group p {
		color: var(--text-secondary);
		font-size: 14px;
		font-weight: var(--font-medium);
		line-height: 140%;
	}
</style>