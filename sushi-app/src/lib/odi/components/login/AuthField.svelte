<!-- src/lib/odi/components/login/AuthField.svelte -->
<script lang="ts">
	import {
		home as Check,
		home as Visibility,
		home as VisibilityOff
	} from "$lib/odi/icons";

	let {
		label,
		type = "text",
		value = $bindable(""),
		placeholder = "",
		icon,
		message = "",
		error = "",
		success = "",
		disabled = false,
		autocomplete = "",
		required = false
	}: {
		label: string;
		type?: "text" | "email" | "password";
		value?: string;
		placeholder?: string;
		icon?: string;
		message?: string;
		error?: string;
		success?: string;
		disabled?: boolean;
		autocomplete?: string;
		required?: boolean;
	} = $props();

	let visible = $state(false);
	const inputType = $derived(type === "password" && visible ? "text" : type);
	const hasFeedback = $derived(Boolean(error || success || message));
</script>

<div class="field">
	<label class="field-label text-body-active">
		{label}
		{#if required}
			<span>*</span>
		{/if}
	</label>

	<div class="input-shell" class:error={Boolean(error)} class:success={Boolean(success)}>
		{#if icon}
			<img class="field-icon" src={icon} alt="" />
		{/if}

		<input
			class="field-input text-body"
			type={inputType}
			bind:value
			{placeholder}
			{disabled}
			{autocomplete}
		/>

		{#if type === "password"}
			<button type="button" class="visibility-button clickable" onclick={() => (visible = !visible)} aria-label={visible ? "비밀번호 숨기기" : "비밀번호 보기"}>
				<img src={visible ? VisibilityOff : Visibility} alt="" />
			</button>
		{/if}
	</div>

	{#if hasFeedback}
		<p class="feedback text-caption-medium" class:error={Boolean(error)} class:success={Boolean(success)}>
			{#if success}
				<img src={Check} alt="" />
				<span>{success}</span>
			{:else if error}
				<span>{error}</span>
			{:else}
				<span>{message}</span>
			{/if}
		</p>
	{/if}
</div>

<style>
	.field {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.field-label {
		display: flex;
		align-items: center;
		gap: var(--space-1);
		color: var(--brand-black);
	}

	.field-label span {
		color: var(--primary);
	}

	.input-shell {
		width: 100%;
		height: 50px;
		padding: 0 11px 0 20px;
		display: flex;
		align-items: center;
		gap: var(--space-3);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.input-shell:focus-within {
		border-color: var(--primary);
		box-shadow: 0 0 0 2px var(--blue-light);
	}

	.input-shell.error {
		border-color: var(--accent);
	}

	.input-shell.success {
		border-color: #44c699;
	}

	.field-icon {
		width: 24px;
		height: 24px;
		object-fit: contain;
		flex-shrink: 0;
	}

	.field-input {
		flex: 1;
		min-width: 0;
		height: 100%;
		border: 0;
		background: transparent;
		color: var(--brand-black);
	}

	.field-input::placeholder {
		color: var(--text-secondary);
	}

	.visibility-button {
		width: 24px;
		height: 24px;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.visibility-button img {
		width: 22px;
		height: 22px;
		object-fit: contain;
	}

	.feedback {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		color: var(--text-secondary);
	}

	.feedback img {
		width: 17px;
		height: 17px;
		object-fit: contain;
	}

	.feedback.error {
		color: var(--accent);
	}

	.feedback.success {
		color: #44c699;
	}
</style>