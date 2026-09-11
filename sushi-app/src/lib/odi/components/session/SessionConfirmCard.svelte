<script lang="ts">
	import SurfaceCard from '$lib/odi/components/common/SurfaceCard.svelte';
	import { home as VoiceSelection } from '$lib/odi/icons';

	type SummaryItem = {
		label: string;
		value: string;
		icon?: string;
	};

	let {
		previewImage = '',
		items = []
	}: {
		previewImage?: string;
		items?: SummaryItem[];
	} = $props();
</script>

<SurfaceCard padding="0" minHeight="550px">
	<div class="confirm-card">
		{#if previewImage}
			<img class="preview-image" src={previewImage} alt="면접 세션 미리보기" decoding="async" />
		{:else}
			<div class="preview-placeholder">
				<p class="text-title-middle">AI Interview Preview</p>
			</div>
		{/if}

		<div class="summary-row">
			{#each items as item}
				<div class="summary-item">
					<img class="summary-icon" src={item.icon} alt="" />

					<p class="text-body-medium summary-label">
						{item.label}
					</p>

					<p class="summary-value">
						{item.value}
					</p>
				</div>
			{/each}
		</div>
	</div>
</SurfaceCard>

<style>
	.confirm-card {
		width: 100%;

		display: flex;
		flex-direction: column;
	}

	.preview-image {
		width: 100%;
		height: clamp(240px, 31vh, 370px);

		object-fit: cover;

		border-top-left-radius: var(--radius-md);
		border-top-right-radius: var(--radius-md);
	}

	.preview-placeholder {
		width: 100%;
		height: clamp(240px, 31vh, 370px);

		display: flex;
		align-items: center;
		justify-content: center;

		background: linear-gradient(135deg, var(--purple-light), var(--blue-light));

		color: var(--text-secondary);

		border-top-left-radius: var(--radius-md);
		border-top-right-radius: var(--radius-md);
	}

	.summary-row {
		display: grid;

		grid-template-columns: repeat(4, minmax(0, 1fr));

		background: var(--surface);
	}

	.summary-item {
		min-height: 180px;

		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;

		gap: 14px;

		padding: 11px var(--space-5);
	}

	.summary-item + .summary-item {
		border-left: 1px solid var(--cool-grey-light-active);
	}

	.summary-icon {
		width: 40px;
		height: 40px;

		object-fit: contain;
	}

	.summary-label {
		color: var(--text-primary);

		text-align: center;
	}

	.summary-value {
		color: var(--text-primary);

		font-family: var(--font-family);
		font-size: clamp(22px, 1.8vw, 32px);
		font-weight: var(--font-bold);
		line-height: 140%;

		text-align: center;
		word-break: keep-all;
	}

	@media (max-width: 900px) {
		.summary-row {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.summary-item {
			min-height: 148px;
		}

		.summary-item + .summary-item {
			border-left: 0;
		}

		.summary-item:nth-child(even) {
			border-left: 1px solid var(--cool-grey-light-active);
		}

		.summary-item:nth-child(n + 3) {
			border-top: 1px solid var(--cool-grey-light-active);
		}
	}

	@media (max-width: 420px) {
		.summary-row {
			grid-template-columns: 1fr;
		}

		.summary-item {
			min-height: 128px;
		}

		.summary-item:nth-child(even) {
			border-left: 0;
		}

		.summary-item + .summary-item {
			border-top: 1px solid var(--cool-grey-light-active);
		}
	}
</style>
