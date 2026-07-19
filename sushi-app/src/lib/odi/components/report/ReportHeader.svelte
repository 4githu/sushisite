<!-- src/lib/odi/components/report/ReportHeader.svelte -->

<script lang="ts">
	import type { ReportFeedback, ReportSession, ReportTemplate } from "./reportTypes";
	import { formatDateTime, formatKoreanDuration } from "./reportUtils";

	let {
		session,
		feedback,
		onOpenPrevious,
		onDownload
	}: {
		session: ReportSession;
		feedback: ReportFeedback;
		onOpenPrevious?: () => void;
		onDownload?: () => void;
	} = $props();

	const template = $derived((session.template ?? {}) as ReportTemplate);
	const environment = $derived(template.environment ?? {});
	const files = $derived(template.files ?? {});

	const title = $derived(environment.title ?? environment.company_name ?? "세션 리포트");
	const audienceCount = $derived(template.audience?.audience_count ?? environment.interviewer_count ?? "-");
	const plannedSeconds = $derived(feedback.duration?.planned_seconds ?? environment.duration_minutes * 60 ?? 0);
	const qaSeconds = $derived(feedback.duration?.qa_seconds ?? 0);
	const totalSeconds = $derived((feedback.duration?.actual_seconds ?? plannedSeconds) + qaSeconds);

	const fileNames = $derived([
		files.slide?.original_name,
		files.script?.original_name ?? (files.script_content ? "발표 스크립트.txt" : null),
		files.paper?.original_name
	].filter(Boolean) as string[]);
</script>

<header class="report-header">
	<div class="header-main">
		<p class="eyebrow">이번 세션 결과</p>

		<h1>{title}</h1>

		<div class="meta-row">
			<span>{formatDateTime(session.started_at ?? session.created_at)}</span>
			<span>{audienceCount}인</span>
			<span>발표 {formatKoreanDuration(plannedSeconds)} · Q&A {formatKoreanDuration(qaSeconds)} · 총 {formatKoreanDuration(totalSeconds)}</span>
		</div>

		{#if fileNames.length > 0}
			<div class="file-row">
				<span class="file-label">첨부 자료</span>

				<div class="file-list">
					{#each fileNames as fileName, index}
						<span class="file-name">{fileName}</span>

						{#if index < fileNames.length - 1}
							<span>·</span>
						{/if}
					{/each}
				</div>
			</div>
		{/if}
	</div>

	<div class="header-actions">
		<button type="button" class="action-button clickable" onclick={onOpenPrevious}>
			이전 리포트 보기
		</button>

		<button type="button" class="action-button clickable" onclick={onDownload}>
			리포트 다운로드
		</button>
	</div>
</header>

<style>
	.report-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: var(--space-8);
	}

	.header-main {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}

	.eyebrow {
		color: var(--primary);
		font-size: 20px;
		font-weight: var(--font-medium);
		line-height: 135%;
	}

	h1 {
		color: var(--brand-black);
		font-size: 42px;
		font-weight: var(--font-bold);
		line-height: 130%;
	}

	.meta-row,
	.file-row,
	.file-list {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: var(--space-4);
		color: var(--text-secondary);
		font-size: 20px;
		font-weight: var(--font-medium);
	}

	.file-row {
		gap: var(--space-10);
		color: var(--text-primary);
	}

	.file-label {
		color: var(--text-primary);
		font-size: 18px;
	}

	.file-list {
		gap: var(--space-2);
		color: var(--text-primary);
		font-size: 18px;
	}

	.file-name {
		text-decoration: underline;
		text-underline-offset: 3px;
	}

	.header-actions {
		display: flex;
		align-items: center;
		gap: var(--space-4);
		flex-shrink: 0;
		padding-top: 48px;
	}

	.action-button {
		width: 212px;
		height: 50px;
		padding: 11px 16px;
		display: flex;
		align-items: center;
		justify-content: center;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text-secondary);
		font-size: 18px;
		font-weight: var(--font-medium);
	}

	.action-button:hover {
		border-color: var(--primary);
		color: var(--primary);
		background: var(--blue-light);
	}

	@media (max-width: 1200px) {
		.report-header {
			flex-direction: column;
		}

		.header-actions {
			padding-top: 0;
		}
	}
</style>