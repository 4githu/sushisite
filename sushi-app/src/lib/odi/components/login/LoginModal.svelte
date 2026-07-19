<!-- src/lib/odi/components/login/LoginModal.svelte -->
<script lang="ts">
	import { goto } from "$app/navigation";
	import Modal from "$lib/odi/components/login/Modal.svelte";
	import AuthField from "$lib/odi/components/login/AuthField.svelte";
	import Button from "$lib/odi/components/common/Button.svelte";
	import { odiuser } from "$lib/odi/stores";
	import { home as Mail, home as Lock } from "$lib/odi/icons";

	const API = import.meta.env.VITE_SUSHIFASTURL;
	const titleId = "login-modal-title";

	let {
		onClose,
		onLoginSuccess
	}: {
		onClose?: () => void;
		onLoginSuccess?: () => void;
	} = $props();

	let email = $state("");
	let password = $state("");
	let loading = $state(false);
	let errorMessage = $state("");

	const canLogin = $derived(email.trim().length > 0 && password.trim().length > 0 && !loading);

	async function fetchJson(res: Response) {
		const data = await res.json().catch(() => null);

		if (!res.ok) {
			throw new Error(data?.detail ?? data?.message ?? "요청 실패");
		}

		return data;
	}

	async function login() {
		if (!canLogin) return;

		loading = true;
		errorMessage = "";

		try {
			const res = await fetch(`${API}/auth/login`, {
				method: "POST",
				credentials: "include",
				headers: {
					"Content-Type": "application/json"
				},
				body: JSON.stringify({
					email,
					password
				})
			});

			const data = await fetchJson(res);

			if (!data.success) {
				throw new Error("이메일 또는 비밀번호가 올바르지 않습니다.");
			}

			const access = await odiuser.checkAccess();

			onLoginSuccess?.();
			onClose?.();

			if (access.status === "main_authenticated_needs_odi_join") {
				goto("/odi/join");
			}
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "로그인에 실패했습니다.";
		} finally {
			loading = false;
		}
	}

	function goRegister() {
		onClose?.();
		goto("/register");
	}
</script>

<Modal width="536px" minHeight="520px" labelledby={titleId} {onClose}>
	<div class="login-modal">
		<div class="title-group">
			<p class="page-label text-caption-main">Welcome Back</p>
			<h2 id={titleId} class="text-title-main">로그인</h2>
			<p class="subtitle text-caption-main">이메일과 비밀번호로 Re:hear에 접속하세요</p>
		</div>

		<div class="form">
			<AuthField
				label="이메일"
				type="email"
				placeholder="이메일 주소를 입력해주세요"
				icon={Mail}
				autocomplete="email"
				bind:value={email}
				required
			/>

			<AuthField
				label="비밀번호"
				type="password"
				placeholder="비밀번호를 입력해주세요"
				icon={Lock}
				autocomplete="current-password"
				bind:value={password}
				required
			/>

			{#if errorMessage}
				<p class="error-message text-caption-medium">{errorMessage}</p>
			{/if}
		</div>

		<div class="actions">
			<Button variant="primary" width="100%" disabled={!canLogin} onclick={login}>
				로그인
			</Button>

			<Button variant="secondary" width="100%" onclick={goRegister}>
				회원가입
			</Button>
		</div>
	</div>
</Modal>

<style>
	.login-modal {
		width: 100%;
		min-height: 520px;
		padding: 48px;
		display: flex;
		flex-direction: column;
		gap: var(--space-8);
		background: var(--surface);
		border-radius: var(--radius-md);
	}

	.title-group {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
		text-align: center;
	}

	.page-label {
		color: var(--primary);
	}

	.subtitle {
		color: var(--text-secondary);
	}

	.form {
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
	}

	.error-message {
		padding: var(--space-3) var(--space-4);
		border-radius: var(--radius-sm);
		background: var(--accent-light);
		color: var(--accent);
	}

	.actions {
		margin-top: auto;
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}
</style>