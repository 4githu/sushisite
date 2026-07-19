<!-- src/lib/odi/components/login/RegisterVerifyStep.svelte -->
<script lang="ts">
	import {
		home as Mail,
		home as Check
	} from "$lib/odi/icons";

	import AuthField from "$lib/odi/components/login/AuthField.svelte";

	let {
		email,
		code = $bindable(""),
		remainingSeconds = 0,
		error = "",
		success = "",
		onResend
	}: {
		email: string;
		code?: string;
		remainingSeconds?: number;
		error?: string;
		success?: string;
		onResend?: () => void;
	} = $props();

	const timeText = $derived(`${String(Math.floor(remainingSeconds / 60)).padStart(2, "0")}:${String(remainingSeconds % 60).padStart(2, "0")}`);
</script>

<div class="verify-step">
	<div class="verify-card">
		<div class="verify-icon">
			<img src={Mail} alt="" />
		</div>

		<h2 class="text-title-middle">이메일 인증</h2>
		<p class="text-caption-main"><strong>{email}</strong>으로 인증번호를 보냈습니다.</p>

		<div class="verify-input">
			<AuthField
				label="인증번호"
				placeholder="인증번호 6자리를 입력해주세요"
				bind:value={code}
				error={error}
				success={success}
				required
			/>
		</div>

		<div class="verify-meta">
			<p class="timer text-body-active">{timeText}</p>

			<button type="button" class="resend-button clickable text-button" onclick={onResend}>
				<img src={Check} alt="" />
				<span>인증번호 재전송</span>
			</button>
		</div>
	</div>
</div>

<style>
	.verify-step {
		display: flex;
		justify-content: center;
	}

	.verify-card {
		width: 592px;
		padding: 48px;
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

	.verify-icon {
		width: 80px;
		height: 80px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius-full);
		background: var(--blue-light);
	}

	.verify-icon img {
		width: 40px;
		height: 40px;
		object-fit: contain;
	}

	.verify-card p {
		color: var(--text-secondary);
	}

	.verify-card strong {
		color: var(--primary);
	}

	.verify-input {
		width: 100%;
		margin-top: var(--space-4);
		text-align: left;
	}

	.verify-meta {
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-4);
	}

	.timer {
		color: var(--primary);
	}

	.resend-button {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		color: var(--primary);
	}

	.resend-button img {
		width: 18px;
		height: 18px;
		object-fit: contain;
	}
</style>