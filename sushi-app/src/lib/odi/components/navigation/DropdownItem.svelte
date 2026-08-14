<script lang="ts">
	let {
		label,
		icon,
		onclick
	}: {
		label: string;
		icon?: string;
		onclick?: (event: MouseEvent) => void;
	} = $props();
</script>

<button
	type="button"
	class="dropdown-item clickable"
	onclick={onclick}
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

	<span class="arrow">›</span>
</button>

<style>

.dropdown-item{

	display:inline-flex;

	align-items:center;
	justify-content:space-between;

	width:212px;
	height:40px;

	padding:4px 8px;

	border-radius:var(--radius-sm);

	color:var(--surface);
}

.dropdown-item:hover{

	background:rgb(from var(--surface) r g b / 8%);
}

.left{

	display:flex;

	align-items:center;

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
