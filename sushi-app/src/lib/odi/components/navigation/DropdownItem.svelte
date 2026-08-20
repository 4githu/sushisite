<script lang="ts">
	let {
		label,
		icon,
		onclick,
		disabled = false,
		status
	}: {
		label: string;
		icon?: string;
		onclick?: (event: MouseEvent) => void;
		disabled?: boolean;
		status?: string;
	} = $props();
</script>

<button
	type="button"
	class="dropdown-item clickable"
	onclick={onclick}
	{disabled}
>
	<div class="left">
		{#if icon}
			<img
				class="icon"
				src={icon}
				alt=""
			/>
		{/if}

		<span class="text-caption-medium">
			{label}
		</span>
	</div>

	{#if status}<span class="status">{status}</span>{:else}<span class="arrow">›</span>{/if}
</button>

<style>

.dropdown-item{

	display:inline-flex;
	box-sizing:border-box;

	align-items:center;
	justify-content:space-between;

	width:100%;
	height:40px;

	padding:4px 8px;

	border-radius:var(--radius-sm);

	color:var(--surface);
}

.dropdown-item:hover{

	background:rgb(from var(--surface) r g b / 8%);
}

.dropdown-item:disabled {
	cursor: not-allowed;
	opacity: .48;
}

.dropdown-item:disabled:hover { background: transparent; }

.status {
	padding: 3px 6px;
	border: 1px solid rgb(from var(--surface) r g b / 35%);
	border-radius: 999px;
	font-size: 10px;
}

.left{

	display:flex;

	align-items:center;
	min-width:0;

	gap:10px;
}

.icon{

	width:24px;
	height:24px;

	flex-shrink:0;
}

.arrow{

	font-size:20px;

	line-height:1;
}

</style>
