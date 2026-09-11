<script lang="ts">
	import ReportCard from './ReportCard.svelte';
	import { resolveReportMedia } from './reportMedia';
	import { formatSeconds } from './reportUtils';
	import { session as sessionStore } from '$lib/odi/stores';
	import { figmaChevronDown, reportAudience, reportPlay } from '$lib/odi/icons';
	import type { ReportFeedback, ReportMedia, ReportTimelineItem } from './reportTypes';

	let {
		feedback,
		sessionId,
		showMedia = true,
		maxItems = 4,
		variant = 'default'
	}: {
		feedback: ReportFeedback;
		sessionId: string;
		showMedia?: boolean;
		maxItems?: number;
		variant?: 'default' | 'figma';
	} = $props();

	let expanded = $state(false);
	let selectedIndex = $state<number | null>(null);
	let videoElement = $state<HTMLVideoElement>();
	let fileInput = $state<HTMLInputElement>();
	let isPlaying = $state(false);
	let uploading = $state(false);
	let uploadError = $state('');
	let uploadedMedia = $state<ReportMedia>();

	const allItems = $derived(feedback.timeline ?? []);
	const problemItems = $derived.by(() => {
		const filtered = allItems.filter((item) => item.type === 'warning' || item.type === 'negative');
		return filtered.length > 0 ? filtered : allItems;
	});
	const selectableItems = $derived(variant === 'figma' ? allItems : problemItems);
	const visibleItems = $derived(expanded ? selectableItems : selectableItems.slice(0, maxItems));
	const resolvedMedia = $derived(resolveReportMedia(uploadedMedia ?? feedback.media, sessionId));
	const videoUrl = $derived(resolvedMedia.videoUrl);
	const videoTitle = $derived(resolvedMedia.title);
	const hasMediaPane = $derived(showMedia);
	const selectedItem = $derived(selectedIndex === null ? null : selectableItems[selectedIndex]);
	const selectedEvidence = $derived(
		selectedItem
			? (feedback.evidence ?? []).find((item) =>
					(selectedItem?.evidence_ids ?? [`segment-${selectedItem?.source_step}`]).includes(
						item.evidence_id
					)
				)
			: undefined
	);
	const selectedReactions = $derived(
		selectedItem
			? (feedback.reaction_trace ?? []).filter((item) =>
					(selectedItem?.reaction_ids ?? []).includes(item.reaction_id)
				)
			: []
	);
	const playbackLabel = $derived(
		!videoUrl ? '영상 미연결' : isPlaying ? '재생 중' : selectedItem ? '일시정지' : '선택 전'
	);

	$effect(() => {
		feedback;
		sessionId;
		expanded = false;
		selectedIndex = variant === 'figma' && selectableItems.length > 0 ? 0 : null;
		isPlaying = false;
		uploadedMedia = undefined;
		uploadError = '';
	});

	function itemType(type: string) {
		if (type === 'positive') return 'positive';
		if (type === 'warning') return 'warning';
		return 'negative';
	}

	function segmentEnd(item: ReportTimelineItem) {
		return item.end_sec && item.end_sec > item.time_sec ? item.end_sec : item.time_sec + 8;
	}

	function impact(value: number | undefined) {
		if (!Number.isFinite(value)) return '—';
		const points = Math.round((value ?? 0) * 100);
		return `${points > 0 ? '+' : ''}${points}`;
	}

	async function selectItem(item: ReportTimelineItem, index: number) {
		selectedIndex = index;
		if (!videoUrl || !videoElement) return;

		videoElement.currentTime = Math.max(0, item.time_sec);

		try {
			await videoElement.play();
		} catch {
			isPlaying = false;
		}
	}

	function handleTimeUpdate() {
		if (!videoElement || !selectedItem) return;
		if (videoElement.currentTime >= segmentEnd(selectedItem)) videoElement.pause();
	}

	async function uploadVideo(file: File | undefined) {
		if (!file || uploading) return;
		if (file.size > 300 * 1024 * 1024) {
			uploadError = '영상은 300MB 이하만 업로드할 수 있습니다.';
			return;
		}

		uploading = true;
		uploadError = '';
		try {
			const updated = await sessionStore.uploadSessionVideo(sessionId, file);
			uploadedMedia = (updated.feedback?.media ?? undefined) as ReportMedia | undefined;
		} catch (error) {
			uploadError = error instanceof Error ? error.message : '영상을 업로드하지 못했습니다.';
		} finally {
			uploading = false;
			if (fileInput) fileInput.value = '';
		}
	}
</script>

<ReportCard padding="24px" minHeight="0">
	<div class:figma={variant === 'figma'} class="timeline-card">
		<div class="timeline-heading">
			<div>
				<h2>{variant === 'figma' ? '주요 장면 재생' : '대표 문제 구간'}</h2>
				<p>
					{videoUrl
						? '개선 구간을 선택하면 영상이 해당 시점부터 재생되고, 구간 끝에서 멈춰요.'
						: hasMediaPane
							? '현재 세션의 동영상을 업로드하면 문제 구간과 연결해 볼 수 있어요.'
							: '발표 흐름에서 우선 확인할 개선 구간을 시간순으로 정리했어요.'}
				</p>
			</div>
			<span class="count-chip">{selectableItems.length}개 구간</span>
		</div>

		<div class="timeline-layout" class:timeline-only={!hasMediaPane}>
			{#if hasMediaPane}
				<section class="video-pane" aria-label="선택 구간 영상">
					<input
						bind:this={fileInput}
						class="video-file-input"
						type="file"
						accept=".mp4,.webm,.mov,video/mp4,video/webm,video/quicktime"
						onchange={(event) => void uploadVideo(event.currentTarget.files?.[0])}
					/>
					{#if videoUrl}
						<video
							bind:this={videoElement}
							src={videoUrl}
							controls
							preload="metadata"
							onplay={() => (isPlaying = true)}
							onpause={() => (isPlaying = false)}
							onended={() => (isPlaying = false)}
							ontimeupdate={handleTimeUpdate}
							crossorigin="use-credentials"
						>
							<track kind="captions" />
						</video>
					{:else if resolvedMedia.hasSessionMismatch}
						<div class="video-empty media-mismatch" role="alert">
							<strong>이 세션의 영상이 아닙니다</strong>
							<p>
								다른 세션에 연결된 주소라 재생하지 않았어요. 현재 세션에 영상을 다시 연결해 주세요.
							</p>
							<button
								type="button"
								class="upload-button clickable"
								onclick={() => fileInput?.click()}
							>
								현재 세션 영상 업로드
							</button>
						</div>
					{:else}
						<div class="video-empty">
							<strong>동영상이 없습니다</strong>
							<p>이 세션에 연결된 영상을 업로드하면 문제 구간과 함께 재생할 수 있어요.</p>
							<button
								type="button"
								class="upload-button clickable"
								disabled={uploading}
								onclick={() => fileInput?.click()}
							>
								{uploading ? '업로드 중…' : '동영상 업로드'}
							</button>
						</div>
					{/if}

					{#if videoUrl}
						<div class="media-action-row">
							<span>{videoTitle}</span>
							<button
								type="button"
								class="replace-button clickable"
								disabled={uploading}
								onclick={() => fileInput?.click()}
							>
								{uploading ? '업로드 중…' : '영상 교체'}
							</button>
						</div>

						<div class="current-segment" class:active={Boolean(selectedItem)} aria-live="polite">
							<div>
								<span>현재 선택</span>
								{#if selectedItem}
									<strong>{selectedItem.title}</strong>
									<small
										>{formatSeconds(selectedItem.time_sec)}–{formatSeconds(
											segmentEnd(selectedItem)
										)}</small
									>
								{:else}
									<strong>구간을 선택해 주세요</strong>
									<small>{videoTitle}</small>
								{/if}
							</div>
							<span class="playback-state" class:playing={isPlaying}>{playbackLabel}</span>
						</div>
					{/if}

					{#if uploadError}<p class="upload-error" role="alert">{uploadError}</p>{/if}
				</section>
			{/if}

			<section class="feedback-pane" aria-label="개선 구간 목록">
				{#if visibleItems.length === 0}
					<div class="timeline-empty">분석된 개선 구간이 아직 없습니다.</div>
				{:else}
					<div class="timeline-list">
						{#each visibleItems as item, index}
							<button
								type="button"
								class="timeline-item clickable"
								class:selected={selectedItem === item}
								aria-pressed={selectedItem === item}
								onclick={() => selectItem(item, index)}
							>
								<span class={`timeline-icon ${itemType(item.type)}`}></span>

								<span class="timeline-text">
									<span class="timeline-meta">
										<time>{formatSeconds(item.time_sec)}–{formatSeconds(segmentEnd(item))}</time>
										<span>{item.type === 'positive' ? '강점 구간' : '개선 구간'}</span>
									</span>
									<strong>{item.title}</strong>
									<span class="description">{item.description}</span>
								</span>
							</button>
						{/each}
					</div>
				{/if}

				{#if selectableItems.length > maxItems}
					<button
						type="button"
						class="all-button clickable"
						aria-expanded={expanded}
						onclick={() => (expanded = !expanded)}
					>
						<span>{expanded ? '피드백 접기' : `전체 피드백 보기 (${selectableItems.length})`}</span>
						<span class="toggle-icon" class:expanded aria-hidden="true"
							><img src={figmaChevronDown} alt="" /></span
						>
					</button>
				{/if}

				{#if selectedItem}
					<article class="evidence-panel" aria-live="polite">
						<header>
							<div><img src={reportPlay} alt="" /><strong>선택 구간의 평가 근거</strong></div>
							<time
								>{formatSeconds(selectedItem.time_sec)}–{formatSeconds(
									segmentEnd(selectedItem)
								)}</time
							>
						</header>
						<div class="impact-grid">
							<span>몰입도 <b>{impact(selectedItem.metric_impacts?.engagement)}</b></span>
							<span>명확도 <b>{impact(selectedItem.metric_impacts?.clarity)}</b></span>
							<span>신뢰도 <b>{impact(selectedItem.metric_impacts?.credibility)}</b></span>
						</div>
						{#if selectedEvidence}
							<p class="transcript">
								<strong>발표 내용</strong>“{selectedEvidence.transcript_excerpt}”
							</p>
						{/if}
						{#if selectedReactions.length > 0}
							<p class="reaction-link">
								<img src={reportAudience} alt="" /><span
									>이 평가로 청중 {selectedReactions.flatMap((item) => item.audiences ?? [])
										.length}명의 반응과 Unity 명령 {selectedReactions.flatMap(
										(item) => item.commands ?? []
									).length}개가 기록되었습니다.</span
								>
							</p>
						{/if}
					</article>
				{/if}
			</section>
		</div>
	</div>
</ReportCard>

<style>
	.timeline-card {
		container-type: inline-size;
		display: grid;
		gap: var(--space-5);
	}

	.timeline-card.figma {
		gap: 24px;
	}

	.timeline-card.figma .timeline-heading p,
	.timeline-card.figma .count-chip {
		display: none;
	}

	.timeline-card.figma .timeline-heading h2 {
		font-size: 28px;
	}

	.timeline-card.figma .timeline-layout {
		grid-template-columns: minmax(360px, 1.08fr) minmax(340px, 0.92fr);
		gap: 28px;
	}

	.timeline-card.figma .feedback-pane {
		display: contents;
	}

	.timeline-card.figma .timeline-list {
		grid-column: 1 / -1;
		grid-row: 1;
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 16px;
	}

	.timeline-card.figma .timeline-item {
		min-height: 148px;
		align-items: flex-start;
		padding: 20px;
		border: 1px solid #dfe2ea;
		border-radius: 12px;
		box-shadow: 0 3px 12px rgba(5, 6, 50, 0.08);
	}

	.timeline-card.figma .timeline-item.selected {
		border: 2px solid var(--primary);
		background: #f7f8ff;
	}

	.timeline-card.figma .video-pane {
		grid-column: 1;
		grid-row: 2;
	}

	.timeline-card.figma .evidence-panel {
		grid-column: 2;
		grid-row: 2;
		align-self: stretch;
		margin: 0;
	}

	.timeline-card.figma .all-button,
	.timeline-card.figma .timeline-empty {
		grid-column: 1 / -1;
	}

	.timeline-card.figma .timeline-layout.timeline-only {
		grid-template-columns: minmax(0, 1fr);
	}

	.timeline-card.figma .timeline-layout.timeline-only .evidence-panel {
		grid-column: 1;
		grid-row: 2;
	}

	.timeline-heading {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: var(--space-5);
	}

	h2 {
		color: var(--brand-black);
		font-size: 20px;
		font-weight: var(--font-bold);
	}

	.timeline-heading p {
		margin-top: 6px;
		color: var(--text-secondary);
		font-size: 14px;
		line-height: 1.45;
	}

	.count-chip {
		padding: 7px 10px;
		border-radius: var(--radius-full);
		background: var(--blue-light);
		color: var(--primary);
		font-size: 13px;
		font-weight: var(--font-bold);
		white-space: nowrap;
	}

	.timeline-layout {
		display: grid;
		grid-template-columns: minmax(360px, 1.05fr) minmax(360px, 0.95fr);
		gap: var(--space-6);
		align-items: start;
	}

	.timeline-layout.timeline-only {
		grid-template-columns: minmax(0, 1fr);
	}

	.video-pane,
	.feedback-pane {
		min-width: 0;
		display: grid;
		gap: var(--space-3);
	}

	.video-file-input {
		display: none;
	}

	.video-pane video,
	.video-empty {
		width: 100%;
		aspect-ratio: 16 / 9;
		border-radius: 12px;
		background: #10131a;
	}

	.video-pane video {
		object-fit: contain;
	}

	.video-empty {
		padding: 28px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-2);
		color: #fff;
		text-align: center;
	}

	.video-empty p {
		max-width: 440px;
		color: #caced9;
		font-size: 14px;
		line-height: 1.45;
	}

	.upload-button {
		min-height: 40px;
		margin-top: 8px;
		padding: 0 18px;
		border-radius: 8px;
		background: var(--primary);
		color: #fff;
		font-size: 14px;
		font-weight: var(--font-bold);
	}

	.upload-button:disabled,
	.replace-button:disabled {
		cursor: wait;
		opacity: 0.65;
	}

	.media-action-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		color: var(--text-secondary);
		font-size: 13px;
	}

	.media-action-row > span {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.replace-button {
		flex: 0 0 auto;
		padding: 6px 10px;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: 7px;
		color: var(--primary);
		font-size: 12px;
		font-weight: var(--font-bold);
	}

	.upload-error {
		padding: 10px 12px;
		border-radius: 8px;
		background: #fff0f2;
		color: #c9364d;
		font-size: 13px;
		line-height: 1.45;
	}

	.evidence-panel {
		padding: 18px;
		display: grid;
		gap: 14px;
		border: 1px solid #dfe3ff;
		border-radius: 12px;
		background: #f8f9ff;
	}

	.evidence-panel header,
	.evidence-panel header > div,
	.reaction-link {
		display: flex;
		align-items: center;
	}

	.evidence-panel header {
		justify-content: space-between;
		gap: 12px;
	}

	.evidence-panel header > div,
	.reaction-link {
		gap: 8px;
	}

	.evidence-panel img {
		width: 20px;
		height: 20px;
	}

	.evidence-panel time {
		color: var(--primary);
		font-size: 13px;
		font-weight: var(--font-bold);
	}

	.impact-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 8px;
	}

	.impact-grid span {
		padding: 9px 10px;
		border-radius: 8px;
		background: #fff;
		color: var(--text-secondary);
		font-size: 12px;
	}

	.impact-grid b {
		display: block;
		margin-top: 3px;
		color: var(--brand-black);
		font-size: 17px;
	}

	.transcript,
	.reaction-link {
		color: var(--text-secondary);
		font-size: 13px;
		line-height: 1.55;
	}

	.transcript strong {
		display: grid;
		gap: 4px;
	}

	.transcript strong {
		color: var(--brand-black);
	}

	.current-segment {
		min-height: 68px;
		padding: 12px 14px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-4);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.current-segment.active {
		border-color: var(--primary);
		background: rgba(0, 51, 255, 0.03);
	}

	.current-segment > div {
		min-width: 0;
		display: grid;
		gap: 2px;
	}

	.current-segment div > span,
	.current-segment small {
		color: var(--text-secondary);
		font-size: 12px;
	}

	.current-segment strong {
		overflow: hidden;
		color: var(--brand-black);
		font-size: 15px;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.playback-state {
		padding: 6px 9px;
		border-radius: var(--radius-full);
		background: var(--cool-grey-light);
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: var(--font-bold);
		white-space: nowrap;
	}

	.playback-state.playing {
		background: rgba(68, 198, 153, 0.15);
		color: #238b66;
	}

	.timeline-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.timeline-item {
		position: relative;
		width: 100%;
		min-width: 0;
		padding: 13px 14px;
		display: flex;
		align-items: flex-start;
		gap: var(--space-3);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
		text-align: left;
	}

	.timeline-item:hover,
	.timeline-item.selected {
		border-color: var(--primary);
		background: rgba(0, 51, 255, 0.04);
	}

	.timeline-icon {
		width: 12px;
		height: 12px;
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
		flex: 1;
		flex-direction: column;
		gap: 4px;
	}

	.timeline-meta {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-3);
		color: var(--text-secondary);
		font-size: 12px;
	}

	.timeline-meta > span {
		color: #b48a00;
		font-weight: var(--font-bold);
	}

	.timeline-text strong {
		color: var(--brand-black);
		font-size: 16px;
		font-weight: var(--font-bold);
	}

	.description {
		display: -webkit-box;
		overflow: hidden;
		color: var(--text-secondary);
		font-size: 14px;
		line-height: 1.4;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
	}

	.timeline-empty {
		min-height: 180px;
		display: grid;
		place-items: center;
		border: 1px dashed var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		color: var(--text-secondary);
	}

	.all-button {
		min-height: 46px;
		padding: 10px 14px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		border: 1px solid var(--primary);
		border-radius: var(--radius-sm);
		background: rgba(0, 51, 255, 0.05);
		color: var(--primary);
		font-size: 15px;
		font-weight: var(--font-medium);
	}
	.toggle-icon {
		display: grid;
		width: 24px;
		height: 24px;
		place-items: center;
	}
	.toggle-icon img {
		display: block;
		width: 24px;
		height: 24px;
		object-fit: contain;
		transition: transform 0.2s ease;
		transform-origin: center;
	}
	.toggle-icon.expanded img {
		transform: rotate(180deg);
	}

	@container (max-width: 860px) {
		.timeline-layout {
			grid-template-columns: 1fr;
		}
	}

	@container (max-width: 480px) {
		.timeline-heading,
		.current-segment {
			align-items: flex-start;
			flex-direction: column;
		}

		.video-empty {
			padding: 20px;
		}
	}
</style>
