<script lang="ts">
	import { goto } from "$app/navigation";

	import Button from "$lib/odi/components/common/Button.svelte";
	import SurfaceCard from "$lib/odi/components/common/SurfaceCard.svelte";
	import SessionConfirmCard from "$lib/odi/components/session/SessionConfirmCard.svelte";

	// 실제 이미지 파일 생기면 주석 해제
	// import InterviewPreview from "$lib/odi/assets/interview-preview.png";

	const applicationInfo = {
		company: "주식회사 Re:hear",
		department: "Product Design 부서",
		position: "UX Designer"
	};

	const sessionSummary = [
		{
			label: "면접 시간",
			value: "30분"
		},
		{
			label: "면접 형식",
			value: "일대다, 3명"
		},
		{
			label: "면접관 페르소나",
			value: "인사담당자 + 실무자"
		},
		{
			label: "면접 스타일",
			value: "일반적"
		}
	];

	function startSession() {
		const sessionConfig = {
			applicationInfo,
			sessionSummary
		};

		console.log(sessionConfig);

		goto("/odi/practice");
	}
</script>

<section class="session-page">
	<header class="page-header">
		<p class="text-caption-main eyebrow">
			Session Setup
		</p>

		<div class="title-group">
			<h1 class="text-title-main">
				Ready for Re:hear 🌟
			</h1>

			<p class="text-caption-main description">
				모든 설정이 완료되었어요. 대기 중인 AI 면접관과 함께 실전 같은 면접 연습을 시작해보세요!
			</p>
		</div>
	</header>

	<SurfaceCard padding="11px" minHeight="111px">
		<div class="application-card">
			<p class="text-body-medium label">
				지원 정보
			</p>

			<div class="application-values">
				<p>{applicationInfo.company}</p>
				<span>·</span>
				<p>{applicationInfo.department}</p>
				<span>·</span>
				<p>{applicationInfo.position}</p>
			</div>
		</div>
	</SurfaceCard>

	<SessionConfirmCard
		items={sessionSummary}
	/>

	<div class="start-area">
		<Button
			width="462px"
			onclick={startSession}
		>
			시작하기
		</Button>

		<p class="text-body-medium start-helper">
			클릭하면 가상 면접 환경으로 이동하여 세션을 시작합니다.
		</p>
	</div>
</section>

<style>
	.session-page {
		width: 100%;

		display: flex;
		flex-direction: column;

		gap: var(--space-5);
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
	}

	.start-area {
		display: flex;
		flex-direction: column;
		align-items: center;

		gap: var(--space-4);

		margin-top: var(--space-5);
	}

	.start-helper {
		color: var(--text-secondary);
	}
</style>