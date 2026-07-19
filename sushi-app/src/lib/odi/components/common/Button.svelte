<script lang="ts">
	import { goto } from "$app/navigation";
	import type { Snippet } from "svelte";

	type Variant =
		| "primary"
		| "secondary"
		| "soft"
		| "outline"
		| "ghost";

	type Size =
		| "sm"
		| "md"
		| "lg";

	let {
		variant = "primary",
		size = "md",

		width,
		block = false,

		href,

		leadingIcon,
		trailingIcon,

		iconSize = 24,

		disabled = false,

		children,

		onclick
	}: {
		variant?: Variant;
		size?: Size;

		width?: string;
		block?: boolean;

		href?: string;

		leadingIcon?: string;
		trailingIcon?: string;

		iconSize?: number;

		disabled?: boolean;

		children?: Snippet;

		onclick?: (event: MouseEvent) => void;
	} = $props();

	async function handleClick(event: MouseEvent) {
		if (disabled) return;

		if (href) {
			await goto(href);
			return;
		}

		onclick?.(event);
	}
</script>

<button
	type="button"
	class={[
		"button",
		"clickable",
		variant,
		size,
		block && "block"
	]}
	style:width
	disabled={disabled}
	onclick={handleClick}
>
	{#if leadingIcon}
		<img
			class="icon"
			src={leadingIcon}
			alt=""
			style={`width:${iconSize}px;height:${iconSize}px;`}
		/>
	{/if}

	<span
		class={[
			size === "lg"
				? "text-button-start"
				: "text-button"
		]}
	>
		{@render children?.()}
	</span>

	{#if trailingIcon}
		<img
			class="icon"
			src={trailingIcon}
			alt=""
			style={`width:${iconSize}px;height:${iconSize}px;`}
		/>
	{/if}
</button>

<style>

.button{

	display:inline-flex;
	align-items:center;
	justify-content:center;

	width:fit-content;

	flex-shrink:0;

	gap:var(--space-2);

	padding-inline:var(--space-4);

	border-radius:var(--radius-sm);

	white-space:nowrap;
}

.block{

	width:100%;
}

.sm{

	height:42px;
}

.md{

	height:50px;
}

.lg{

	height:63px;

	padding-inline:var(--space-5);
}

.primary{

	background:var(--primary);

	color:var(--text-on-primary);
}

.primary:hover:not(:disabled){

	background:var(--primary-hover);
}

.secondary{

	background:var(--surface);

	color:var(--primary);

	border:1px solid var(--cool-grey-light-active);
}

.secondary:hover:not(:disabled){

	border-color:var(--primary);
}

.soft{

	background:rgb(from var(--primary) r g b / 10%);

	color:var(--primary);
}

.soft:hover:not(:disabled){

	background:rgb(from var(--primary) r g b / 15%);
}

.outline{

	background:transparent;

	color:var(--primary);

	border:1px solid var(--primary);
}

.outline:hover:not(:disabled){

	background:var(--blue-light);
}

.ghost{

	background:transparent;

	color:var(--text-primary);
}

.button:disabled{

	background:var(--cool-grey-light-active);

	color:var(--text-disabled);

	border:none;
}

.icon{

	display:block;

	flex-shrink:0;
}

</style>