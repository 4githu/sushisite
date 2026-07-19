<!-- src/lib/odi/components/login/OdiJoinCompleteStep.svelte -->
<script lang="ts">
	import Button from "$lib/odi/components/common/Button.svelte";
	import { Seedling } from "$lib/odi/icons";

	let {
		nickname,
		level = "새싹 보이스",
		onStartSession,
		onGoHome
	}: {
		nickname: string;
		level?: string;
		onStartSession?: () => void;
		onGoHome?: () => void;
	} = $props();
</script>

<div class="complete-page">
	<div class="glow" aria-hidden="true"></div>

	<section class="complete-content">
		<div class="title-group">
			<h1>계정 설정이 완료되었어요<br />Re:hear에 오신 걸 환영해요</h1>
			<p>첫 세션을 시작하고 나만의 리포트와 훈련 기록을 쌓아보세요</p>
		</div>

		<div class="profile-card">
			<div class="profile-inner">
				<div class="profile-image">
					<img src={Seedling} alt="" />
				</div>

				<div class="level-badge">{level}</div>

				<strong>{nickname}</strong>

				<p>첫 칭호를 획득했어요!<br />앞으로의 성장을 응원해요</p>
			</div>
		</div>

		<div class="complete-actions">
			<Button variant="primary" size="lg" width="464px" onclick={onStartSession}>
				첫 세션 만들기
			</Button>

			<Button variant="outline" size="lg" width="464px" onclick={onGoHome}>
				홈으로 이동하기
			</Button>
		</div>
	</section>
</div>

<style>
	.complete-page {
		position: relative;
		min-height: calc(100vh - 72px);
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
		background: var(--surface);
	}

	.glow {
		position: absolute;
		width: 1800px;
		height: 1100px;
		left: 50%;
		top: 0;
		transform: translateX(-50%);
		border-radius: var(--radius-full);
		background: radial-gradient(ellipse at center, rgba(0, 51, 255, 0.58) 0%, rgba(0, 51, 255, 0) 70%);
		pointer-events: none;
	}

	.complete-content {
		position: relative;
		z-index: 1;
		width: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 40px;
		text-align: center;
	}

	.title-group {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-4);
	}

	.title-group h1 {
		color: var(--brand-black);
		font-size: 42px;
		font-weight: var(--font-bold);
		line-height: 125%;
	}

	.title-group p {
		color: var(--primary);
		font-size: 26px;
		font-weight: var(--font-medium);
	}

	.profile-card {
		width: 370px;
		height: 500px;
		padding: 45px 84px;
		border: 1px solid var(--surface);
		border-radius: var(--radius-md);
		background: rgba(255, 255, 255, 0.5);
		box-shadow: 0 0 40px rgba(255, 255, 255, 0.4);
	}

	.profile-inner {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-4);
	}

	.profile-image {
		width: 203px;
		height: 203px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius-full);
		background: rgba(255, 255, 255, 0.4);
		overflow: hidden;
	}

	.profile-image img {
		width: 128px;
		height: 128px;
		object-fit: contain;
	}

	.level-badge {
		padding: 4px 16px;
		border-radius: var(--radius-full);
		background: rgba(255, 255, 255, 0.15);
		color: var(--primary);
		font-size: 20px;
		font-weight: var(--font-bold);
		line-height: 130%;
	}

	.profile-inner strong {
		color: var(--brand-black);
		font-size: 42px;
		font-weight: var(--font-bold);
		line-height: 130%;
	}

	.profile-inner p {
		color: var(--text-primary);
		font-size: 20px;
		font-weight: var(--font-medium);
		line-height: 130%;
	}

	.complete-actions {
		width: 464px;
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}
</style>