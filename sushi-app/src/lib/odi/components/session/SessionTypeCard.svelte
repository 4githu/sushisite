<script lang="ts">
	import { grayright } from "$lib/odi/icons";

	let {
		title,
		description,
		image,
		selected = false,
		onselect
	}: {
		title: string;
		description: string;
		image: string;
		selected?: boolean;
		onselect?: () => void;
	} = $props();
</script>

<button
	type="button"
	class="session-type-card clickable"
	class:selected
	onclick={onselect}
>
	<div class="content">
		<div class="image-wrap">
			<img
				class="type-image"
				src={image}
				alt=""
			/>
		</div>

		<div class="text-group">
			<p class="text-title-small">
				{title}
			</p>

			<p class="description text-caption-medium">
				{description}
			</p>
		</div>

		<div class="arrow-button">
			<img
				src={grayright}
				alt=""
			/>
		</div>
	</div>
</button>

<style>
	.session-type-card {
		width: 240px;
		height: 301px;

		padding: 11px 16px 12px 17px;

		background: var(--surface);

		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);

		box-shadow: none;

		transition:
			background var(--transition-fast),
			border-color var(--transition-fast),
			box-shadow var(--transition-fast);
	}

	.session-type-card:hover {
		border-color: var(--primary);
		background: var(--blue-light);
	}

	.session-type-card.selected {
		background: var(--blue-light);

		border-color: var(--primary);

		box-shadow: 7px 7px 14px rgba(0, 51, 255, .11);
	}

	.content {
		width: 204px;
		height: 100%;

		display: flex;
		flex-direction: column;
		align-items: center;

		gap: var(--space-4);
	}

	.image-wrap {
		width: 143px;
		height: 143px;

		display: flex;
		align-items: center;
		justify-content: center;

		background: var(--surface);

		transition: var(--transition-fast);
	}

	.session-type-card:hover .image-wrap,
	.session-type-card.selected .image-wrap {
		background: var(--blue-light);
	}

	.type-image {
		width: 143px;
		height: 143px;

		object-fit: contain;
	}

	.text-group {
		width: 100%;

		display: flex;
		flex-direction: column;
		align-items: center;

		gap: var(--space-2);

		text-align: center;
	}

	.text-title-small {
		color: var(--text-primary);

		transition: var(--transition-fast);
	}

	.description {
		color: var(--text-secondary);

		line-height: 135%;

		white-space: pre-line;

		transition: var(--transition-fast);
	}

	.arrow-button {
		width: 36px;
		height: 36px;

		display: flex;
		align-items: center;
		justify-content: center;

		margin-top: auto;

		border: 1px solid var(--cool-grey);
		border-radius: var(--radius-full);

		background: var(--surface);

		transition:
			border-color var(--transition-fast),
			background var(--transition-fast),
			transform var(--transition-fast);
	}

	.session-type-card:hover .arrow-button,
	.session-type-card.selected .arrow-button {
		border-color: var(--primary);
	}

	.arrow-button img {
		width: 16px;
		height: 16px;

		object-fit: contain;
	}

	.session-type-card:active {
		transform: scale(.98);
	}
</style>