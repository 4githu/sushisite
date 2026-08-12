<!-- src/routes/login/+page.svelte -->
<script lang="ts">
	import { goto } from "$app/navigation";

	import "$lib/odi/styles/globals.css";

	import Button from "$lib/odi/components/common/Button.svelte";
	import AuthField from "$lib/odi/components/login/AuthField.svelte";
	import { odiuser } from "$lib/odi/stores";

	import {
		home as Mail,
		home as Lock
	} from "$lib/odi/icons";

	const configuredApi = import.meta.env.VITE_SUSHIFASTURL || '';
	const API = /^(https?:\/\/)?(localhost|127\.0\.0\.1)(:\d+)?$/i.test(configuredApi.replace(/\/$/, '')) ? '' : configuredApi;

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

			if (access.status === "odi_authenticated") {
				goto("/odi");
				return;
			}

			goto("/odi/join");
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "로그인에 실패했습니다.";
		} finally {
			loading = false;
		}
	}
</script>

<main class="login-page">
	<section class="login-card">
		<div class="title-group">
			<p class="page-label text-caption-main">Welcome Back</p>
			<h1 class="text-title-main">로그인</h1>
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

			<Button variant="secondary" width="100%" onclick={() => goto("/register")}>
				회원가입
			</Button>
		</div>
	</section>
</main>

<style>
	.login-page {
		min-height: 100vh;
		padding: 36px 48px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--background);
	}

	.login-card {
		width: 536px;
		padding: 48px;
		display: flex;
		flex-direction: column;
		gap: var(--space-8);
		border-radius: var(--radius-md);
		background: var(--surface);
		box-shadow: var(--shadow-md);
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
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}
</style>
