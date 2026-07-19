<script lang="ts">
	let {
		label,
		required = false,

		type = "text",

		placeholder = "",

		value = $bindable(""),

		width = "342px",

		disabled = false,
		readonly = false
	}: {
		label: string;

		required?: boolean;

		type?:
			| "text"
			| "email"
			| "password"
			| "number";

		placeholder?: string;

		value?: string;

		width?: string;

		disabled?: boolean;

		readonly?: boolean;
	} = $props();

	const inputId = `text-input-${crypto.randomUUID()}`;
</script>

<div
	class="text-input"
	style={`width:${width};`}
>

	<label
		for={inputId}
		class="label text-body-active"
	>

		<span>{label}</span>

		{#if required}
			<span class="required">*</span>
		{/if}

	</label>

	<input

		id={inputId}

		class="field text-body"

		{type}

		bind:value

		{placeholder}

		{disabled}

		{readonly}

	/>

</div>

<style>

.text-input{

	display:inline-flex;

	flex-direction:column;

	align-items:flex-start;

	gap:var(--space-4);
}

.label{

	display:flex;

	align-items:center;

	gap:2px;

	color:var(--text-primary);
}

.required{

	color:var(--purple);
}

.field{

	width:100%;
	height:50px;

	padding:
		11px
		var(--space-3)
		11px
		var(--space-5);

	border:1px solid var(--cool-grey-light-active);

	border-radius:var(--radius-sm);

	background:var(--surface);

	color:var(--text-primary);

	transition:
		border-color var(--transition-fast),
		background var(--transition-fast);
}

.field::placeholder{

	color:var(--text-secondary);
}

.field:focus{

	border-color:var(--primary);
}

.field:disabled{

	background:rgb(from var(--cool-grey-light-active) r g b / 20%);

	color:var(--text-disabled);
}

.field:read-only:not(:disabled){

	background:var(--surface);
}

</style>