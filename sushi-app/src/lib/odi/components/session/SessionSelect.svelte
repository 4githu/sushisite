<script lang="ts">
	import {down} from "$lib/odi/icons"
	type Option = {
		label: string;
		value: string;
	};

	let {
		items = [],
		value = $bindable(""),
		placeholder = "선택",
		width = "343px",
		disabled = false,
		icon,
		onchange
	}: {
		items?: Option[];
		value?: string;
		placeholder?: string;
		width?: string;
		disabled?: boolean;
		icon?: string;
		onchange?: (event: Event) => void;
	} = $props();
</script>

<label class="select clickable" class:disabled style:width>
	<div class="content">
		{#if icon}
			<img class="icon" src={icon} alt="" aria-hidden="true" />
		{/if}

		<select class="text-body" bind:value {disabled} onchange={onchange}>
			<option value="" disabled>{placeholder}</option>

			{#each items as item}
				<option value={item.value}>{item.label}</option>
			{/each}
		</select>
	</div>

	<img class="chevron" src={down} alt="" aria-hidden="true" />
</label>

<style>
	.select {
		height: 50px;

		display: flex;
		align-items: center;
		justify-content: space-between;

		padding: 0 var(--space-5);

		background: var(--surface);

		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
	}

	.select:hover:not(.disabled) {
		border-color: var(--primary);
	}

	.select.disabled {
		background: rgba(212, 214, 226, 0.2);
		border-color: var(--border);
	}

	.content {
		flex: 1;
		min-width: 0;

		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.icon {
		width: 24px;
		height: 24px;

		flex-shrink: 0;
	}

	select {
		width: 100%;
		min-width: 0;

		border: none;
		outline: none;
		background: transparent;

		color: var(--text-primary);

		appearance: none;
		cursor: pointer;
	}

	.select.disabled select {
		color: var(--text-disabled);
		cursor: default;
	}

	.chevron {
		width: 24px;
		height: 24px;

		flex-shrink: 0;

		pointer-events: none;
	}
</style>