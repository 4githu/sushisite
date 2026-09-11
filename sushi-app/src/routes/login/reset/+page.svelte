<script lang="ts">
	import { goto } from "$app/navigation";
	import "$lib/odi/styles/globals.css";
	import Button from "$lib/odi/components/common/Button.svelte";
	import AuthField from "$lib/odi/components/login/AuthField.svelte";
	import { API_BASE as API } from "$lib/config/api";
	import { home as Mail, home as Lock } from "$lib/odi/icons";

	let email = $state("");
	let code = $state("");
	let newPassword = $state("");
	let newPasswordConfirm = $state("");
	let codeSent = $state(false);
	let loading = $state(false);
	let message = $state("");
	let errorMessage = $state("");

	const emailValid = $derived(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()));
	const passwordValid = $derived(/^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$/.test(newPassword));
	const passwordError = $derived(newPassword && !passwordValid ? "영문, 숫자, 특수문자를 포함해 8자리 이상 입력해주세요." : "");
	const passwordConfirmError = $derived(newPasswordConfirm && newPassword !== newPasswordConfirm ? "비밀번호가 일치하지 않습니다." : "");
	const canSend = $derived(emailValid && !loading);
	const canReset = $derived(codeSent && emailValid && code.trim().length > 0 && passwordValid && newPassword === newPasswordConfirm && !loading);

	async function requestCode() {
		if (!canSend) return;
		loading = true;
		message = "";
		errorMessage = "";
		try {
			const response = await fetch(`${API}/auth/password-reset/send`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ email: email.trim() })
			});
			const data = await response.json().catch(() => null);
			if (!response.ok || !data?.success) throw new Error(data?.detail ?? data?.message ?? "인증 코드 요청에 실패했습니다.");
			codeSent = true;
			message = "가입된 이메일이라면 인증 코드를 보냈습니다. 메일함을 확인해주세요.";
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "인증 코드 요청에 실패했습니다.";
		} finally {
			loading = false;
		}
	}

	async function resetPassword() {
		if (!canReset) return;
		loading = true;
		message = "";
		errorMessage = "";
		try {
			const response = await fetch(`${API}/auth/password-reset/confirm`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ email: email.trim(), code: code.trim(), new_password: newPassword })
			});
			const data = await response.json().catch(() => null);
			if (!response.ok || !data?.success) throw new Error(data?.detail ?? data?.message ?? "비밀번호 재설정에 실패했습니다.");
			message = "비밀번호를 변경했습니다. 새 비밀번호로 로그인해주세요.";
			setTimeout(() => goto("/login"), 1000);
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "비밀번호 재설정에 실패했습니다.";
		} finally {
			loading = false;
		}
	}
</script>

<main class="reset-page">
	<section class="reset-card">
		<div class="title-group">
			<p class="page-label text-caption-main">Password Reset</p>
			<h1 class="text-title-main">비밀번호 재설정</h1>
			<p class="subtitle text-caption-main">가입한 이메일로 인증한 뒤 새 비밀번호를 설정하세요.</p>
		</div>

		<div class="form">
			<AuthField label="이메일" type="email" placeholder="가입한 이메일 주소" icon={Mail} autocomplete="email" bind:value={email} required />
			<Button variant="secondary" width="100%" disabled={!canSend} onclick={requestCode}>
				{codeSent ? "인증 코드 다시 보내기" : "인증 코드 보내기"}
			</Button>

			{#if codeSent}
				<AuthField label="인증 코드" type="text" placeholder="이메일로 받은 6자리 코드" icon={Mail} autocomplete="one-time-code" bind:value={code} required />
				<AuthField label="새 비밀번호" type="password" placeholder="영문·숫자·특수문자 포함 8자리 이상" icon={Lock} autocomplete="new-password" bind:value={newPassword} error={passwordError} required />
				<AuthField label="새 비밀번호 확인" type="password" placeholder="새 비밀번호를 다시 입력해주세요" icon={Lock} autocomplete="new-password" bind:value={newPasswordConfirm} error={passwordConfirmError} required />
			{/if}

			{#if message}<p class="success-message text-caption-medium">{message}</p>{/if}
			{#if errorMessage}<p class="error-message text-caption-medium">{errorMessage}</p>{/if}
		</div>

		<div class="actions">
			{#if codeSent}
				<Button variant="primary" width="100%" disabled={!canReset} onclick={resetPassword}>비밀번호 변경</Button>
			{/if}
			<a class="login-link text-caption-medium" href="/login">로그인으로 돌아가기</a>
		</div>
	</section>
</main>

<style>
	.reset-page { min-height: 100vh; padding: 36px 48px; display: flex; align-items: center; justify-content: center; background: var(--background); }
	.reset-card { width: 536px; padding: 48px; display: flex; flex-direction: column; gap: var(--space-8); border-radius: var(--radius-md); background: var(--surface); box-shadow: var(--shadow-md); }
	.title-group, .form, .actions { display: flex; flex-direction: column; }
	.title-group { gap: var(--space-2); text-align: center; }
	.form { gap: var(--space-5); }
	.actions { gap: var(--space-3); }
	.page-label, .login-link { color: var(--primary); }
	.subtitle { color: var(--text-secondary); }
	.login-link { align-self: center; text-decoration: underline; text-underline-offset: 3px; }
	.error-message, .success-message { padding: var(--space-3) var(--space-4); border-radius: var(--radius-sm); }
	.error-message { background: var(--accent-light); color: var(--accent); }
	.success-message { background: var(--accent-light); color: var(--primary); }
	@media (max-width: 640px) { .reset-page { padding: 20px; align-items: flex-start; } .reset-card { width: 100%; padding: 28px 20px; } }
</style>
