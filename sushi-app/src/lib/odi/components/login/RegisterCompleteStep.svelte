<!-- src/lib/odi/components/login/RegisterCompleteStep.svelte -->
<script lang="ts">
	import {
		home as Check,
		home as Lock
	} from "$lib/odi/icons";

	let {
		email
	}: {
		email: string;
	} = $props();
</script>

<div class="complete-step">
	<div class="complete-card">
		<div class="complete-icon">
			<img src={Check} alt="" />
		</div>

		<h2 class="text-title-middle">계정 생성이 완료되었습니다</h2>
		<p class="text-caption-main">{email} 계정으로 Re:hear를 시작할 수 있어요.</p>

		<div class="guide-box">
			<img src={Lock} alt="" />
			<p>다음 단계에서 Re:hear 서비스 이용을 위한 약관 동의와 기본 설정을 완료합니다.</p>
		</div>
	</div>
</div>

<style>
	.complete-step {
		display: flex;
		justify-content: center;
	}

	.complete-card {
		width: 592px;
		padding: 56px 48px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-5);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		background: var(--surface);
		box-shadow: var(--shadow-sm);
		text-align: center;
	}

	.complete-icon {
		width: 88px;
		height: 88px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius-full);
		background: rgba(68, 198, 153, 0.15);
	}

	.complete-icon img {
		width: 42px;
		height: 42px;
		object-fit: contain;
	}

	.complete-card p {
		color: var(--text-secondary);
	}

	.guide-box {
		width: 100%;
		margin-top: var(--space-4);
		padding: var(--space-5);
		display: flex;
		align-items: center;
		gap: var(--space-4);
		border-radius: var(--radius-sm);
		background: var(--blue-light);
		color: var(--text-secondary);
		text-align: left;
	}

	.guide-box img {
		width: 28px;
		height: 28px;
		object-fit: contain;
		flex-shrink: 0;
	}
</style>