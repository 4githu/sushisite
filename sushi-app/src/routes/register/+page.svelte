<!-- src/routes/register/+page.svelte -->
<script lang="ts">
	import { goto } from "$app/navigation";
	import { onDestroy } from "svelte";

	import "$lib/odi/styles/globals.css";

	import Button from "$lib/odi/components/common/Button.svelte";
	import AuthStepper from "$lib/odi/components/login/AuthStepper.svelte";
	import RegisterBasicStep from "$lib/odi/components/login/RegisterBasicStep.svelte";
	import RegisterVerifyStep from "$lib/odi/components/login/RegisterVerifyStep.svelte";
	import RegisterCompleteStep from "$lib/odi/components/login/RegisterCompleteStep.svelte";
	import { odiuser } from "$lib/odi/stores";
	import { API_BASE as API } from '$lib/config/api';

	const steps = ["기본 정보 입력", "이메일 인증", "계정 생성 완료"];

	let currentStep = $state(0);
	let loading = $state(false);
	let errorMessage = $state("");

	let name = $state("");
	let email = $state("");
	let password = $state("");
	let passwordConfirm = $state("");

	let allAgreed = $state(false);
	let serviceAgreed = $state(false);
	let privacyAgreed = $state(false);
	let marketingAgreed = $state(false);

	let code = $state("");
	let remainingSeconds = $state(180);
	let timer: ReturnType<typeof setInterval> | null = null;

	const nameSuccess = $derived(name.trim().length >= 2 ? "사용할 수 있는 이름입니다" : "");
	const emailValid = $derived(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email));
	const passwordValid = $derived(/^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,}$/.test(password));
	const passwordError = $derived(password.length > 0 && !passwordValid ? "영문, 숫자, 특수문자 포함 8자리 이상 입력해주세요" : "");
	const passwordConfirmError = $derived(passwordConfirm.length > 0 && password !== passwordConfirm ? "비밀번호가 일치하지 않습니다" : "");
	const requiredAgreementOk = $derived(serviceAgreed && privacyAgreed);
	const canSendCode = $derived(name.trim().length >= 2 && emailValid && passwordValid && password === passwordConfirm && requiredAgreementOk && !loading);
	const canVerify = $derived(code.trim().length > 0 && !loading);

	onDestroy(() => {
		if (timer) clearInterval(timer);
	});

	function startTimer() {
		if (timer) clearInterval(timer);

		remainingSeconds = 180;

		timer = setInterval(() => {
			if (remainingSeconds <= 0) {
				if (timer) clearInterval(timer);
				timer = null;
				return;
			}

			remainingSeconds -= 1;
		}, 1000);
	}

	async function fetchJson(res: Response) {
		const data = await res.json().catch(() => null);

		if (!res.ok) {
			throw new Error(data?.detail ?? data?.message ?? "요청 실패");
		}

		return data;
	}

	async function sendRegisterCode() {
		if (!canSendCode) return;

		loading = true;
		errorMessage = "";

		try {
			const res = await fetch(`${API}/auth/register/send`, {
				method: "POST",
				credentials: "include",
				headers: {
					"Content-Type": "application/json"
				},
				body: JSON.stringify({
					email,
					password,
					name
				})
			});

			const data = await fetchJson(res);

			if (!data.success) {
				throw new Error(data.message ?? "인증 메일 발송에 실패했습니다.");
			}

			currentStep = 1;
			startTimer();
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "인증 메일 발송에 실패했습니다.";
		} finally {
			loading = false;
		}
	}

	async function verifyRegisterCode() {
		if (!canVerify) return;

		loading = true;
		errorMessage = "";

		try {
			const res = await fetch(`${API}/auth/register/verify`, {
				method: "POST",
				credentials: "include",
				headers: {
					"Content-Type": "application/json"
				},
				body: JSON.stringify({
					email,
					code
				})
			});

			const data = await fetchJson(res);

			if (!data.success) {
				throw new Error(data.message ?? "인증번호가 올바르지 않습니다.");
			}

			await loginAfterRegister();
			currentStep = 2;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "회원가입 인증에 실패했습니다.";
		} finally {
			loading = false;
		}
	}

	async function loginAfterRegister() {
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
			throw new Error("회원가입은 완료되었지만 자동 로그인에 실패했습니다.");
		}
	}

	async function finishRegister() {
		const result = await odiuser.checkAccess();

		if (result.status === "odi_authenticated") {
			goto("/odi");
			return;
		}

		goto("/odi/join");
	}

	function openTerm(type: "all" | "service" | "privacy" | "marketing") {
		console.log("open term", type);
	}
</script>

<main class="register-page">
	<header class="page-header">
		<p class="page-label text-caption-main">Account Setup</p>

		<div class="title-group">
			<h1 class="text-title-main">계정 생성하기</h1>
			<p class="subtitle text-caption-main">계정을 생성하고 Re:hear를 시작해보세요</p>
		</div>
	</header>

	<AuthStepper steps={steps} currentStep={currentStep} />

	{#if errorMessage}
		<p class="error-message text-caption-main">{errorMessage}</p>
	{/if}

	<section class="register-content">
		{#if currentStep === 0}
			<RegisterBasicStep
				bind:name
				bind:email
				bind:password
				bind:passwordConfirm
				bind:allAgreed
				bind:serviceAgreed
				bind:privacyAgreed
				bind:marketingAgreed
				{nameSuccess}
				{passwordError}
				{passwordConfirmError}
				onOpenTerm={openTerm}
			/>
		{:else if currentStep === 1}
			<RegisterVerifyStep
				{email}
				bind:code
				remainingSeconds={remainingSeconds}
				error={errorMessage}
				onResend={sendRegisterCode}
			/>
		{:else}
			<RegisterCompleteStep {email} />
		{/if}
	</section>

	<footer class="page-actions">
		{#if currentStep === 0}
			<Button variant="secondary" width="360px" onclick={() => goto("/login")}>
				이미 계정이 있어요
			</Button>

			<Button variant="primary" width="360px" disabled={!canSendCode} onclick={sendRegisterCode}>
				다음 단계
			</Button>
		{:else if currentStep === 1}
			<Button variant="secondary" width="360px" onclick={() => (currentStep = 0)}>
				이전 단계
			</Button>

			<Button variant="primary" width="360px" disabled={!canVerify} onclick={verifyRegisterCode}>
				인증 완료
			</Button>
		{:else}
			<Button variant="primary" width="360px" onclick={finishRegister}>
				Re:hear 시작하기
			</Button>
		{/if}
	</footer>
</main>

<style>
	.register-page {
		min-height: 100vh;
		padding: 36px 48px 40px;
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
		background: var(--surface);
	}

	.page-header {
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
	}

	.page-label {
		color: var(--primary);
	}

	.title-group {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.subtitle {
		color: var(--text-secondary);
	}

	.register-content {
		width: 100%;
	}

	.error-message {
		padding: var(--space-4) var(--space-5);
		border: 1px solid var(--accent-light-active);
		border-radius: var(--radius-sm);
		background: var(--accent-light);
		color: var(--accent);
	}

	.page-actions {
		margin-top: auto;
		display: flex;
		justify-content: flex-end;
		gap: var(--space-4);
	}
</style>
