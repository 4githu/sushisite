<!-- src/lib/odi/components/login/Modal.svelte -->
<script lang="ts">
	import type { Snippet } from "svelte";

	let {
		children,
		onClose,
		labelledby,
		width = "536px",
		minHeight = "600px",
		panelClass = ""
	}: {
		children: Snippet;
		onClose?: () => void;
		labelledby?: string;
		width?: string;
		minHeight?: string;
		panelClass?: string;
	} = $props();

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === "Escape") {
			onClose?.();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="modal-root" style={`--modal-width: ${width}; --modal-min-height: ${minHeight};`}>
	<button
		type="button"
		class="modal-backdrop"
		aria-label="모달 닫기"
		onclick={onClose}
	></button>

	<dialog
		open
		class={`modal-panel ${panelClass}`}
		aria-labelledby={labelledby}
	>
		{@render children()}
	</dialog>
</div>

<style>
	.modal-root {
		position: fixed;
		inset: 0;
		z-index: 1000;

		display: flex;
		align-items: center;
		justify-content: center;

		padding: var(--space-6);
	}

	.modal-backdrop {
		position: absolute;
		inset: 0;

		width: 100%;
		height: 100%;

		background: rgba(255, 255, 255, 0.72);
		backdrop-filter: blur(1px);
	}

	.modal-panel {
		position: relative;
		z-index: 1;

		width: min(var(--modal-width), calc(100vw - 48px));
		min-height: var(--modal-min-height);

		margin: 0;
		padding: 0;

		border: none;
		border-radius: var(--radius-md);

		background: var(--surface);
		color: var(--text-primary);

		box-shadow: 0 0 16px rgba(0, 0, 0, 0.15);

		overflow: visible;
	}

	.modal-panel::backdrop {
		background: transparent;
	}

	@media (max-height: 720px) {
		.modal-root {
			align-items: flex-start;
			overflow: auto;
		}

		.modal-panel {
			margin-block: var(--space-6);
		}
	}
</style>