<script lang="ts">
 import { locale as siteLocale, copy as tr } from "$lib/odi/i18n";
 import { locale, copy } from "$lib/odi/i18n";
	import TemplateSaveBar from '$lib/odi/components/session/TemplateSaveBar.svelte';
	import { goto } from '$app/navigation';

	import Button from '$lib/odi/components/common/Button.svelte';
	import SurfaceCard from '$lib/odi/components/common/SurfaceCard.svelte';
	import SessionConfirmCard from '$lib/odi/components/session/SessionConfirmCard.svelte';

	import { template, session } from '$lib/odi/stores';
	const draft = $derived($template?.type === 'interview' ? $template : null);
	const applicationInfo = $derived({
		company: draft?.environment.company_name ?? '',
		department: draft?.environment.department ?? '',
		position: draft?.environment.position ?? ''
	});
	const sessionSummary = $derived([
		{ label: '면접 시간', value: `${draft?.environment.duration_minutes ?? 0}분` },
		{
			label: '면접 형식',
			value: `${draft?.environment.interview_context ?? ''}, ${draft?.environment.interviewer_count ?? 0}명`
		},
		{
			label: '면접관 페르소나',
			value:
				(
					{ hr: '인사담당자', practical: '실무자', executive: '임원', mixed: '혼합' } as Record<
						string,
						string
					>
				)[draft?.audience.interviewer_persona ?? ''] ??
				draft?.audience.interviewer_persona ??
				''
		},
		{
			label: '면접 스타일',
			value:
				(
					{ friendly: '친근한', neutral: '일반적', critical: '비판적', pressure: '압박' } as Record<
						string,
						string
					>
				)[draft?.audience.interview_style ?? ''] ??
				draft?.audience.interview_style ??
				''
		}
	]);
	let busy = $state(false),
		error = $state('');
	async function startSession() {
		if (busy || !draft) return;
		busy = true;
		error = '';
		try {
			await session.startFromCurrentTemplate();
			await goto('/odi/waitvr?mode=regular');
		} catch (e) {
			error = e instanceof Error ? e.message : '세션을 시작하지 못했습니다.';
		} finally {
			busy = false;
		}
	}
</script>

<section class="session-page">
	<header class="page-header">
		<p class="text-caption-main eyebrow">Session Setup</p>

		<div class="title-group">
			<h1 class="text-title-main">Ready for Re:hear 🌟</h1>

			<p class="text-caption-main description">
				{tr($siteLocale, "모든 설정이 완료되었어요. 대기 중인 AI 면접관과 함께 실전 같은 면접 연습을 시작해보세요!")}
			</p>
		</div>
	</header>

	<SurfaceCard padding="11px" minHeight="111px">
		<div class="application-card">
			<p class="text-body-medium label">{tr($siteLocale, "지원 정보")}</p>

			<div class="application-values">
				<p>{applicationInfo.company}</p>
				<span>·</span>
				<p>{applicationInfo.department}</p>
				<span>·</span>
				<p>{applicationInfo.position}</p>
			</div>
		</div>
	</SurfaceCard>

	<SessionConfirmCard items={sessionSummary} />

	<div class="start-area">
		<a class="edit-environment" href="/odi/session/interview">{copy($locale, "환경 수정하기")}</a>
		<Button width="462px" onclick={startSession} disabled={busy || !draft}
			>{busy ? tr($siteLocale, "세션 준비 중…") : tr($siteLocale, "이 환경으로 세션 시작")}</Button
		>
		{#if error}<p role="alert">{error}</p>{/if}

		<p class="text-body-medium start-helper">
			{tr($siteLocale, "클릭하면 가상 면접 환경으로 이동하여 세션을 시작합니다.")}
		</p>
	</div>
	<TemplateSaveBar />
</section>

<style>
	.edit-environment {
		padding: 12px 24px;
		border: 1px solid var(--primary);
		border-radius: var(--radius-sm);
		color: var(--primary);
		text-decoration: none;
		text-align: center;
	}
	.session-page {
		width: 100%;
		min-height: 100vh;
		padding: var(--odi-page-padding-top) var(--odi-page-padding-inline)
			var(--odi-page-padding-bottom);

		display: flex;
		flex-direction: column;

		gap: var(--space-5);
		background: var(--surface);
	}

	.page-header {
		display: flex;
		flex-direction: column;

		gap: var(--space-6);
	}

	.eyebrow {
		color: var(--primary);
	}

	.title-group {
		display: flex;
		flex-direction: column;

		gap: var(--space-2);
	}

	.description {
		color: var(--text-secondary);
	}

	.application-card {
		width: 100%;
		min-height: 89px;

		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;

		gap: 14px;
	}

	.label {
		color: var(--text-primary);
	}

	.application-values {
		display: flex;
		align-items: center;
		justify-content: center;

		gap: 14px;

		color: var(--text-primary);

		font-family: var(--font-family);
		font-size: 22px;
		font-weight: var(--font-bold);
		line-height: 140%;

		text-align: center;
		flex-wrap: wrap;
		word-break: keep-all;
	}

	.start-area {
		display: flex;
		flex-direction: column;
		align-items: center;

		gap: var(--space-4);

		margin-top: var(--space-5);
	}

	.start-area :global(.button) {
		max-width: 100%;
	}

	.start-helper {
		color: var(--text-secondary);
		text-align: center;
		line-height: 1.45;
	}

	@media (max-width: 640px) {
		.session-page {
			padding: 24px 16px 32px;
		}

		.application-card {
			align-items: flex-start;
			padding: 16px;
		}

		.application-values {
			align-items: flex-start;
			justify-content: flex-start;
			font-size: 18px;
			text-align: left;
		}
	}
</style>
