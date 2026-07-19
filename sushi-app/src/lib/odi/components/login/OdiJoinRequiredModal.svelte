<!-- src/lib/odi/components/login/OdiJoinRequiredModal.svelte -->
<script lang="ts">
	import Modal from "$lib/odi/components/login/Modal.svelte";
	import Button from "$lib/odi/components/common/Button.svelte";
	import { account_circle as AccountCircle, home as Logout, home as Seedling } from "$lib/odi/icons";

	let {
		userName = "사용자",
		userEmail = "",
		onJoin,
		onLogout
	}: {
		userName?: string;
		userEmail?: string;
		onJoin?: () => void;
		onLogout?: () => void;
	} = $props();

	const titleId = "odi-join-required-title";
</script>

<Modal width="536px" minHeight="520px" labelledby={titleId}>
	<div class="join-required-modal">
		<div class="hero">
			<div class="hero-icon">
				<img src={Seedling} alt="" />
			</div>

			<p class="welcome text-body-active">Re:hear 서비스 시작이 필요해요</p>

			<h2 id={titleId} class="modal-title">
				현재 로그인된 계정으로<br />
				Re:hear를 시작할까요?
			</h2>
		</div>

		<div class="account-box">
			<img src={AccountCircle} alt="" />

			<div class="account-text">
				<strong>{userName}</strong>
				<p>{userEmail || "이메일 정보를 확인할 수 없습니다."}</p>
			</div>
		</div>

		<div class="guide-box">
			<p>Re:hear 계정을 만들면 발표와 면접 연습 기록, 맞춤 리포트, 훈련 목표를 저장할 수 있습니다.</p>
		</div>

		<div class="actions">
			<Button variant="primary" width="100%" onclick={onJoin}>
				Re:hear 시작하기
			</Button>

			<button type="button" class="logout-button clickable" onclick={onLogout}>
				<img src={Logout} alt="" />
				<span>다른 계정으로 로그인</span>
			</button>
		</div>
	</div>
</Modal>

<style>
	.join-required-modal {
		width: 100%;
		min-height: 520px;
		padding: 44px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-6);
		background: var(--surface);
		border-radius: var(--radius-md);
	}

	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-2);
		text-align: center;
	}

	.hero-icon {
		width: 96px;
		height: 96px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius-full);
		background: var(--blue-light);
	}

	.hero-icon img {
		width: 56px;
		height: 56px;
		object-fit: contain;
	}

	.welcome {
		color: var(--primary);
	}

	.modal-title {
		color: var(--brand-black);
		font-family: var(--font-family);
		font-size: 28px;
		font-weight: var(--font-bold);
		line-height: 135%;
	}

	.account-box {
		width: 100%;
		padding: var(--space-5);
		display: flex;
		align-items: center;
		gap: var(--space-4);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.account-box img {
		width: 44px;
		height: 44px;
		flex-shrink: 0;
	}

	.account-text {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	.account-text strong {
		color: var(--brand-black);
		font-size: 18px;
		font-weight: var(--font-bold);
	}

	.account-text p {
		color: var(--text-secondary);
		font-size: 16px;
		font-weight: var(--font-medium);
		word-break: break-all;
	}

	.guide-box {
		width: 100%;
		padding: var(--space-4);
		border-radius: var(--radius-sm);
		background: var(--blue-light);
		color: var(--text-secondary);
		font-size: 16px;
		font-weight: var(--font-medium);
		line-height: 145%;
	}

	.actions {
		width: 100%;
		margin-top: auto;
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}

	.logout-button {
		height: 50px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: var(--space-2);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text-secondary);
		font-size: 18px;
		font-weight: var(--font-medium);
	}

	.logout-button:hover {
		border-color: var(--primary);
		color: var(--primary);
		background: var(--blue-light);
	}

	.logout-button img {
		width: 20px;
		height: 20px;
	}
</style>