<!-- src/lib/odi/components/login/OdiGuestModal.svelte -->
<script lang="ts">
	import Modal from "$lib/odi/components/login/Modal.svelte";

    import Lock from "$lib/odi/icons/lock.png";
	import {
		Close,
		star as KidStar,
		paper as ListAlt,
		voice as VoiceSelection
	} from "$lib/odi/icons";

	let {
		onClose,
		onRegister,
		onLogin
	}: {
		onClose?: () => void;
		onRegister?: () => void;
		onLogin?: () => void;
	} = $props();

	const titleId = "odi-guest-modal-title";
</script>

<Modal
	width="536px"
	minHeight="600px"
	labelledby={titleId}
	{onClose}
	panelClass="guest-modal-panel"
>
	<div class="guest-modal">
		<button
			type="button"
			class="close-button clickable"
			aria-label="닫기"
			onclick={onClose}
		>
			<img src={Close} alt="" />
		</button>

		<div class="hero">
			<div class="lock-frame">
				<img src={Lock} alt="" />
			</div>

			<p class="welcome text-body-active">만나서 반가워요!</p>

			<h2 id={titleId} class="modal-title">
				계정을 만들고 맞춤 리포트와<br />
				훈련 기능을 이용해보세요
			</h2>
		</div>

		<div class="benefits">
			<div class="benefit-item">
				<div class="benefit-icon">
					<img src={KidStar} alt="" />
				</div>

				<div class="benefit-text">
					<strong>개인 맞춤 분석 리포트</strong>
					<p>나의 스타일을 분석하고 개선 지점을 코칭받아요</p>
				</div>
			</div>

			<div class="benefit-item">
				<div class="benefit-icon">
					<img src={ListAlt} alt="" />
				</div>

				<div class="benefit-text">
					<strong>기록 및 성과 관리</strong>
					<p>성장 추이를 확인하고 꾸준히 실력을 향상시켜요</p>
				</div>
			</div>

			<div class="benefit-item">
				<div class="benefit-icon">
					<img src={VoiceSelection} alt="" />
				</div>

				<div class="benefit-text">
					<strong>체계적인 훈련 미션</strong>
					<p>목표 설정부터 피드백까지 한 번에 관리해요</p>
				</div>
			</div>
		</div>

		<div class="actions">
			<button
				type="button"
				class="register-button clickable text-button"
				onclick={onRegister}
			>
				회원가입
			</button>

			<button
				type="button"
				class="login-button clickable text-button"
				onclick={onLogin}
			>
				로그인
			</button>
		</div>
	</div>
</Modal>

<style>
	.guest-modal {
		box-sizing: border-box;
		position: relative;

		width: 100%;
		min-height: 600px;

		padding: 38px 18px 18px;

		display: flex;
		flex-direction: column;
		align-items: center;

		background: var(--surface);
		border-radius: var(--radius-md);
		overflow-y: auto;
	}

	.close-button {
		position: absolute;

		top: 20px;
		right: 20px;

		width: 24px;
		height: 24px;

		display: flex;
		align-items: center;
		justify-content: center;
	}

	.close-button img {
		width: 14px;
		height: 14px;
		object-fit: contain;
	}

	.hero {
		width: 100%;
		max-width: 420px;

		display: flex;
		flex-direction: column;
		align-items: center;

		gap: var(--space-1);

		text-align: center;
	}

	.lock-frame {
		width: 143px;
		height: 143px;

		display: flex;
		align-items: center;
		justify-content: center;
	}

	.lock-frame img {
		width: 104px;
		height: 104px;
		object-fit: contain;
	}

	.welcome {
		color: var(--primary);
		line-height: 135%;
	}

	.modal-title {
		margin-top: var(--space-1);

		color: var(--brand-black);

		font-family: var(--font-family);
		font-size: 24px;
		font-weight: var(--font-bold);
		line-height: 135%;

		text-align: center;
		white-space: normal;
	}

	.benefits {
		width: 349px;

		margin-top: 46px;

        margin-bottom : 30px;

		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.benefit-item {
		width: 100%;

		display: flex;
		align-items: center;

		gap: var(--space-5);
	}

	.benefit-icon {
		width: 36px;
		height: 36px;

		display: flex;
		align-items: center;
		justify-content: center;

		flex-shrink: 0;

		border-radius: var(--radius-full);
		background: rgba(0, 51, 255, 0.15);
	}

	.benefit-icon img {
		width: 20px;
		height: 20px;
		object-fit: contain;
	}

	.benefit-text {
		flex: 1;
		min-width: 0;

		display: flex;
		flex-direction: column;

		gap: var(--space-1);
	}

	.benefit-text strong {
		color: var(--brand-black);

		font-family: var(--font-family);
		font-size: 16px;
		font-weight: var(--font-bold);
		line-height: 135%;
	}

	.benefit-text p {
		color: var(--text-secondary);

		font-family: var(--font-family);
		font-size: 16px;
		font-weight: var(--font-medium);
		line-height: 135%;
	}

	.actions {
		width: 100%;
		max-width: 500px;

		margin-top: auto;
		padding-top: var(--space-4);
		padding-bottom: 2px;

		display: flex;
		gap: var(--space-3);
		background: var(--surface);
	}

	.actions button {
		flex: 1;

		height: 50px;

		display: flex;
		align-items: center;
		justify-content: center;

		border-radius: var(--radius-sm);
	}

	.register-button {
		background: var(--primary);
		color: var(--text-on-primary);
	}

	.register-button:hover {
		background: var(--primary-hover);
	}

	.login-button {
		border: 1px solid var(--cool-grey-light-active);

		background: var(--surface);
		color: var(--text-secondary);
	}

	.login-button:hover {
		border-color: var(--primary);

		background: var(--blue-light);
		color: var(--primary);
	}

	@media (max-width: 640px) {
		.guest-modal {
			min-height: auto;
			padding: var(--space-8) var(--space-5) var(--space-5);
		}

		.benefits,
		.actions {
			width: 100%;
		}

		.actions {
			margin-top: var(--space-8);
		}
	}
</style>
