<!-- src/lib/odi/components/report/TimelineFeedbackCard.svelte -->

<script lang="ts">
	import ReportCard from './ReportCard.svelte';
	import { formatSeconds } from './reportUtils';
	import type { ReportFeedback } from './reportTypes';

	let {
		feedback,
		maxItems = 4
	}: {
		feedback: ReportFeedback;
		maxItems?: number;
	} = $props();

	let expanded = $state(false);
	let selectedIndex = $state<number | null>(null);
	let videoElement = $state<HTMLVideoElement>();
	let isPlaying = $state(false);
	const items = $derived(feedback.timeline ?? []);
	const visibleItems = $derived(expanded ? items : items.slice(0, maxItems));
	const videoUrl = $derived(feedback.media?.video_url ?? '');
	const selectedItem = $derived(selectedIndex === null ? null : items[selectedIndex]);

	$effect(() => {
		feedback;
		selectedIndex = null;
		isPlaying = false;
	});

	function itemType(type: string) {
		if (type === 'positive') return 'positive';
		if (type === 'warning') return 'warning';
		return 'negative';
	}

	async function selectItem(item: (typeof items)[number], index: number) {
		if (!videoUrl || !videoElement) return;
		selectedIndex = index;
		videoElement.currentTime = Math.max(0, item.time_sec);

		try {
			await videoElement.play();
		} catch {
			isPlaying = false;
		}
	}

	function handleTimeUpdate() {
		if (!videoElement || !selectedItem?.end_sec) return;
		if (videoElement.currentTime >= selectedItem.end_sec) videoElement.pause();
	}
</script>

<ReportCard padding="22px 16px" minHeight="524px">
	<div class="timeline-card">
		<h2>실시간 피드백</h2>

		{#if videoUrl}
			<div class="video-area">
				<video
					bind:this={videoElement}
					src={videoUrl}
					controls
					preload="metadata"
					onplay={() => (isPlaying = true)}
					onpause={() => (isPlaying = false)}
					onended={() => (isPlaying = false)}
					ontimeupdate={handleTimeUpdate}
				>
					<track kind="captions" />
				</video>
				<p class="playback-status" aria-live="polite">
					{selectedItem
						? `${formatSeconds(selectedItem.time_sec)} · ${selectedItem.title}`
						: '확인할 피드백 구간을 선택하세요'}
					<span>{isPlaying ? '재생 중' : '일시정지'}</span>
				</p>
			</div>
		{/if}

		<div class="timeline-list">
			{#each visibleItems as item, index}
				<button
					type="button"
					class="timeline-item"
					class:selected={selectedItem === item}
					class:interactive={Boolean(videoUrl)}
					disabled={!videoUrl}
					onclick={() => selectItem(item, index)}
				>
					<div class={`timeline-icon ${itemType(item.type)}`}></div>

					<div class="timeline-text">
						<time>{formatSeconds(item.time_sec)}</time>
						<strong>{item.title}</strong>
						<p>{item.description}</p>
					</div>
				</button>
			{/each}
		</div>

		{#if items.length > maxItems}
			<button
				type="button"
				class="all-button clickable"
				aria-expanded={expanded}
				onclick={() => (expanded = !expanded)}
			>
				<span>{expanded ? '피드백 접기' : `전체 피드백 보기 (${items.length})`}</span>
				<span>{expanded ? '⌃' : '›'}</span>
			</button>
		{/if}
	</div>
</ReportCard>

<style>
	.timeline-card {
		position: relative;
		min-height: 480px;
		display: flex;
		flex-direction: column;
	}

	h2 {
		color: var(--brand-black);
		font-size: 20px;
		font-weight: var(--font-bold);
	}

	.timeline-list {
		position: relative;
		margin-top: var(--space-8);
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
	}

	.video-area {
		margin-top: var(--space-5);
		display: grid;
		gap: var(--space-2);
	}
	.video-area video {
		width: 100%;
		max-height: 220px;
		border-radius: var(--radius-sm);
		background: #10131a;
	}
	.playback-status {
		display: flex;
		justify-content: space-between;
		gap: var(--space-3);
		color: var(--text-secondary);
		font-size: 12px;
	}
	.playback-status span {
		color: var(--primary);
		white-space: nowrap;
	}

	.timeline-list::before {
		content: '';
		position: absolute;
		left: 10px;
		top: 8px;
		bottom: 8px;
		width: 1px;
		background: #d8dce8;
	}

	.timeline-item {
		position: relative;
		display: flex;
		align-items: flex-start;
		gap: var(--space-5);
		width: 100%;
		padding: 4px;
		border-radius: var(--radius-sm);
		background: transparent;
		text-align: left;
	}

	.timeline-item.interactive {
		cursor: pointer;
	}
	.timeline-item.interactive:hover,
	.timeline-item.selected {
		background: rgba(0, 51, 255, 0.05);
	}
	.timeline-item:disabled {
		color: inherit;
	}

	.timeline-icon {
		position: relative;
		z-index: 1;
		width: 20px;
		height: 20px;
		margin-top: 4px;
		border-radius: var(--radius-full);
		background: var(--cool-grey-light-active);
		flex-shrink: 0;
	}

	.timeline-icon.positive {
		background: #44c699;
	}

	.timeline-icon.warning {
		background: #ffd736;
	}

	.timeline-icon.negative {
		background: #ff4343;
	}

	.timeline-text {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	time {
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: var(--font-medium);
	}

	.timeline-text strong {
		color: var(--brand-black);
		font-size: 16px;
		font-weight: var(--font-bold);
	}

	.timeline-text p {
		display: -webkit-box;
		color: var(--text-secondary);
		font-size: 14px;
		font-weight: var(--font-medium);
		line-height: 135%;
		overflow: hidden;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
	}

	.all-button {
		height: 50px;
		margin-top: auto;
		padding: 11px 16px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		border: 1px solid var(--primary);
		border-radius: var(--radius-sm);
		background: rgba(0, 51, 255, 0.05);
		color: var(--primary);
		font-size: 18px;
		font-weight: var(--font-medium);
	}
</style>
