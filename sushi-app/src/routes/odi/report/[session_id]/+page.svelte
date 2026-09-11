<!-- src/routes/odi/report/[session_id]/+page.svelte -->

<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { odiuser, session } from '$lib/odi/stores';
	import ReportPageView from '$lib/odi/components/report/ReportPageView.svelte';
	import ReportPageViewV1 from '$lib/odi/components/report/ReportPageViewV1.svelte';
	import ReportPageViewV3 from '$lib/odi/components/report/ReportPageViewV3.svelte';
	import {
		resolveReportViewVersion,
		resolveTimelineVideoPreference
	} from '$lib/odi/components/report/reportPreferences';

	import type { ReportSession } from '$lib/odi/components/report/reportTypes';

	let reportSession = $state(null as ReportSession | null);
	let loading = $state(true);
	let errorMessage = $state('');

	const sessionId = $derived(page.params.session_id ?? '');
	const reportViewVersion = $derived(
		resolveReportViewVersion($odiuser?.config?.preferences?.report_view_version)
	);
	const showTimelineVideo = $derived(
		resolveTimelineVideoPreference($odiuser?.config?.preferences?.show_timeline_video)
	);
	let requestVersion = 0;
	const sessionIdPattern = /^[A-Za-z0-9_-]{1,128}$/;

	async function loadReport(targetSessionId = sessionId) {
		const version = ++requestVersion;
		reportSession = null;
		loading = true;
		errorMessage = '';

		try {
			if (!targetSessionId) throw new Error('세션 ID가 없습니다.');
			if (!sessionIdPattern.test(targetSessionId)) {
				throw new Error('올바르지 않은 세션 주소입니다. 이전 리포트 목록에서 다시 선택해 주세요.');
			}
			const result = await session.getReport(targetSessionId);
			if (version !== requestVersion) return;
			reportSession = result as unknown as ReportSession;
		} catch (error) {
			if (version !== requestVersion) return;
			errorMessage = error instanceof Error ? error.message : '리포트를 불러오지 못했습니다.';
		} finally {
			if (version === requestVersion) loading = false;
		}
	}

	$effect(() => {
		const targetSessionId = sessionId;
		void loadReport(targetSessionId);

		return () => {
			requestVersion += 1;
		};
	});

	function openPreviousReports() {
		goto('/odi/report');
	}

	function downloadReport() {
		window.print();
	}

	function startTraining() {
		goto('/odi/practice');
	}
</script>

<main class="report-page">
	{#if loading}
		<div class="state-card">
			<p class="text-caption-main">리포트를 불러오는 중입니다.</p>
		</div>
	{:else if errorMessage}
		<div class="state-card error">
			<p class="text-caption-main">{errorMessage}</p>

			<div class="state-actions">
				<button type="button" class="retry-button clickable" onclick={() => void loadReport()}
					>다시 시도</button
				>
				<button type="button" class="back-button clickable" onclick={() => goto('/odi')}
					>홈으로 이동하기</button
				>
			</div>
		</div>
	{:else if reportSession}
		{#if reportViewVersion === 'v1'}
			<ReportPageViewV1
				session={reportSession}
				{showTimelineVideo}
				onOpenPrevious={openPreviousReports}
				onDownload={downloadReport}
				onStartTraining={startTraining}
			/>
		{:else if reportViewVersion === 'v2'}
			<ReportPageView
				session={reportSession}
				{showTimelineVideo}
				onOpenPrevious={openPreviousReports}
				onDownload={downloadReport}
				onStartTraining={startTraining}
			/>
		{:else}
			<ReportPageViewV3
				session={reportSession}
				{showTimelineVideo}
				onOpenPrevious={openPreviousReports}
				onDownload={downloadReport}
				onStartTraining={startTraining}
			/>
		{/if}
	{/if}
</main>

<style>
	.report-page {
		width: 100%;
		min-width: 0;
		min-height: 100vh;
		padding: var(--odi-page-padding-top) var(--odi-page-padding-inline)
			var(--odi-page-padding-bottom);
		background: var(--surface);
	}

	.state-card {
		min-height: 300px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-5);
		border-radius: var(--radius-md);
		background: var(--surface);
		box-shadow: var(--shadow-sm);
		color: var(--text-secondary);
	}

	.state-card.error {
		color: var(--accent);
	}

	.back-button {
		height: 50px;
		padding: 0 var(--space-6);
		border-radius: var(--radius-sm);
		background: var(--primary);
		color: var(--text-on-primary);
		font-size: 18px;
		font-weight: var(--font-medium);
	}

	.state-actions {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: var(--space-3);
	}
	.retry-button {
		height: 50px;
		padding: 0 var(--space-6);
		border: 1px solid var(--primary);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--primary);
		font-size: 18px;
		font-weight: var(--font-medium);
	}

	@media (max-width: 640px) {
		.report-page {
			padding: 20px 12px 32px;
		}
	}
</style>
