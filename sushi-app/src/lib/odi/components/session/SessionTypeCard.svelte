<script lang="ts">
	import { grayright } from "$lib/odi/icons";

	let {
		title,
		description,
		image,
		badge,
		meta,
		selected = false,
		onselect
	}: {
		title: string;
		description: string;
		image: string;
		badge?: string;
		meta?: string;
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
	{#if badge}
		<span class="badge">{badge}</span>
	{/if}
	<div class="content">
		<div class="image-wrap">
			<img
				class="type-image"
				src={image}
				alt=""
				decoding="async"
			/>
		</div>

		<div class="text-group">
			<p class="text-title-small">
				{title}
			</p>

			<p class="description text-caption-medium">
				{description}
			</p>

			{#if meta}
				<p class="meta">{meta}</p>
			{/if}
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
		position: relative;
		box-sizing: border-box;
		width: 280px;
		height: 304px;

		padding: 16px 20px 14px;

		background: var(--surface);

		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);

		box-shadow: none;

		transition:
			background var(--transition-fast),
			border-color var(--transition-fast),
			box-shadow var(--transition-fast);
	}

	.badge {
		position: absolute;
		top: 12px;
		right: 12px;
		z-index: 1;
		padding: 5px 9px;
		border-radius: var(--radius-full);
		background: var(--primary);
		color: var(--text-on-primary);
		font-size: 11px;
		font-weight: var(--font-bold);
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
		width: 100%;
		height: 100%;

		display: flex;
		flex-direction: column;
		align-items: center;

		gap: 10px;
	}

	.image-wrap {
		flex: 0 0 96px;
		width: 100%;
		height: 96px;

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
		max-width: 100%;
		width: 96px;
		height: 96px;

		object-fit: contain;
	}

	.text-group {
		width: 100%;
		min-height: 104px;

		display: flex;
		flex-direction: column;
		align-items: center;

		gap: 6px;

		text-align: center;
	}

	.text-title-small {
		margin: 0;
		color: var(--text-primary);

		transition: var(--transition-fast);
	}

	.description {
		margin: 0;
		color: var(--text-secondary);

		line-height: 145%;

		white-space: pre-line;

		transition: var(--transition-fast);
	}

	.meta {
		margin: 0;
		color: var(--primary);
		font-size: 12px;
		font-weight: var(--font-medium);
	}

	.arrow-button {
		flex: 0 0 28px;
		width: 28px;
		height: 28px;

		display: flex;
		align-items: center;
		justify-content: center;

		margin-top: 0;

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
		width: 14px;
		height: 14px;

		object-fit: contain;
	}

	.session-type-card:active {
		transform: scale(.98);
	}
</style>
