<script lang="ts">
	let {
		label,
		icon,

		selected = false,

		onclick
	}: {
		label: string;

		icon?: string;

		selected?: boolean;

		onclick?: (event: MouseEvent) => void;
	} = $props();
</script>

<button
	type="button"
	class={[
		"navigation-item",
		"clickable",
		selected && "selected"
	]}
	onclick={onclick}
>
	
	{#if icon}
		<img
			class="icon"
			src={icon}
			alt=""
		/>
	{/if}

	<span class="text-body-medium">
		{label}
	</span>

</button>

<style>

.navigation-item{

	display:inline-flex;

	align-items:center;

	justify-content:flex-start;

	width:212px;
	height:50px;

	padding:
		12px
		11px
		11px
		12px;

	gap:10px;

	border-radius:var(--radius-sm);

	background:transparent;

	color:var(--surface);

	transition:
		background var(--transition-fast),
		color var(--transition-fast);
}

.navigation-item:hover{

	background:rgb(from var(--purple) r g b / 20%);
}

.navigation-item.selected{

	background:rgb(from var(--purple) r g b / 40%);
}

.icon{

	width:24px;
	height:24px;

	flex-shrink:0;
}

</style>