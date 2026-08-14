<!-- src/routes/odi/report/[session_id]/+page.svelte -->

<script lang="ts">
	import { goto } from "$app/navigation";
	import { page } from "$app/state";
	import { onMount } from "svelte";

	import { session } from "$lib/odi/stores";
	import ReportPageView from "$lib/odi/components/report/ReportPageView.svelte";

	import type { ReportSession } from "$lib/odi/components/report/reportTypes";

	let reportSession = $state(null as ReportSession | null);
	let loading = $state(true);
	let errorMessage = $state("");

	const sessionId = $derived(page.params.session_id);

	onMount(async () => {
		loading = true;
		errorMessage = "";

		try {
			const result = await session.getReport(sessionId);
			reportSession = result as unknown as ReportSession;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "리포트를 불러오지 못했습니다.";
		} finally {
			loading = false;
		}
	});

	function openPreviousReports() {
		goto("/odi/report");
	}

	function downloadReport() {
		window.print();
	}

	function openAllFeedback() {
		console.log("전체 피드백 보기");
	}

	function startTraining() {
		goto("/odi/practice");
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

			<button type="button" class="back-button clickable" onclick={() => goto("/odi")}>
				홈으로 이동하기
			</button>
		</div>
	{:else if reportSession}
		<ReportPageView
			session={reportSession}
			onOpenPrevious={openPreviousReports}
			onDownload={downloadReport}
			onOpenAllFeedback={openAllFeedback}
			onStartTraining={startTraining}
		/>
	{/if}
</main>

<style>
	.report-page {
		width: 100%;
		min-width: 0;
		min-height: 100vh;
		padding: 36px 48px 40px;
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
</style>
