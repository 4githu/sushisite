<script lang="ts">
	import SurfaceCard from "$lib/odi/components/common/SurfaceCard.svelte";

	type Tip = {
		title?: string;
		description: string;
		icon: string;
	};

	let {
		title,
		description,
		tips = []
	}: {
		title: string;
		description: string;
		tips?: Tip[];
	} = $props();
</script>

<SurfaceCard padding="43px 36px" minHeight="609px">
	<aside class="tip-content">
		<div class="background-shape"></div>

		<div class="content">
			<h2 class="text-title-middle">
				{title}
			</h2>

			<p class="main-description text-body-medium">
				{description}
			</p>

			<div class="tip-list">
				{#each tips as tip}
					<div class="tip-item">
						<div class="tip-icon">
							<img src={tip.icon} alt="" />
						</div>

						<div class="tip-text">
							{#if tip.title}
								<h3 class="tip-title text-caption-medium">
									{tip.title}
								</h3>
							{/if}

							<p class="tip-description text-caption-medium">
								{tip.description}
							</p>
						</div>
					</div>
				{/each}
			</div>
		</div>
	</aside>
</SurfaceCard>

<style>
	.tip-content {
		position: relative;

		width: 100%;
		height: 100%;

		overflow: hidden;
	}

	.content {
		position: relative;
		z-index: 1;

		display: flex;
		flex-direction: column;
	}

	.main-description {
		width: 100%;

		margin-top: 36px;

		color: #4522c4;

		line-height: 135%;
	}

	.tip-list {
		display: flex;
		flex-direction: column;
		gap: 36px;

		margin-top: 92px;
	}

	.tip-item {
		display: flex;
		align-items: flex-start;
		gap: var(--space-5);
	}

	.tip-icon {
		width: 36px;
		height: 36px;

		display: flex;
		align-items: center;
		justify-content: center;

		flex-shrink: 0;

		border-radius: var(--radius-full);

		background: rgba(128, 125, 254, 0.15);
	}

	.tip-icon img {
		width: 22px;
		height: 22px;
	}

	.tip-text {
		flex: 1;
		min-width: 0;

		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	.tip-title {
		color: var(--text-primary);
		font-weight: var(--font-bold);
		line-height: 135%;
	}

	.tip-description {
		color: var(--text-secondary);
		line-height: 135%;
	}

	.background-shape {
		position: absolute;
		right: -40px;
		bottom: -90px;

		width: 390px;
		height: 260px;

		border-radius: 50% 50% 0 0;

		background:
			radial-gradient(circle at 20% 48%, rgba(128, 125, 254, 0.2) 0 12%, transparent 13%),
			radial-gradient(circle at 42% 55%, rgba(128, 125, 254, 0.16) 0 9%, transparent 10%),
			radial-gradient(circle at 67% 62%, rgba(128, 125, 254, 0.14) 0 7%, transparent 8%),
			linear-gradient(180deg, rgba(255, 255, 255, 0) 0%, rgba(128, 125, 254, 0.16) 100%);
	}
</style>