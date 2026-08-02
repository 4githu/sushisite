<script lang="ts">
	import { loginPersonal, type PersonalUser } from './auth';

	let {
		onSuccess,
		serverMessage = ''
	}: {
		onSuccess: (user: PersonalUser) => void;
		serverMessage?: string;
	} = $props();

	let email = $state('');
	let password = $state('');
	let loading = $state(false);
	let error = $state('');
	let showPassword = $state(false);

	const canSubmit = $derived(Boolean(email.trim() && password && !loading));

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!canSubmit) return;
		loading = true;
		error = '';
		try {
			onSuccess(await loginPersonal(email.trim(), password));
		} catch (cause) {
			error =
				cause instanceof Error
					? cause.message
					: '로그인 중 알 수 없는 오류가 발생했습니다. / An unknown login error occurred.';
		} finally {
			loading = false;
		}
	}
</script>

<main class="auth-page">
	<section class="auth-card">
		<div class="brand-mark">P</div>
		<p class="eyebrow">Personal workspace</p>
		<h1>개인 프로젝트 로그인</h1>
		<p class="subtitle">
			캘린더와 아우라가 같은 계정 쿠키를 사용합니다.<br />Calendar and Aura share one account.
		</p>

		{#if serverMessage}
			<div class="server-message">{serverMessage}</div>
		{/if}

		<form onsubmit={submit}>
			<label for="personal-email">이메일 / Email</label>
			<input
				id="personal-email"
				type="email"
				autocomplete="email"
				bind:value={email}
				placeholder="name@example.com"
				required
			/>

			<label for="personal-password">비밀번호 / Password</label>
			<div class="password-field">
				<input
					id="personal-password"
					type={showPassword ? 'text' : 'password'}
					autocomplete="current-password"
					bind:value={password}
					required
				/>
				<button
					type="button"
					onclick={() => (showPassword = !showPassword)}
					aria-label={showPassword
						? '비밀번호 숨기기 / Hide password'
						: '비밀번호 보기 / Show password'}>{showPassword ? '숨김' : '보기'}</button
				>
			</div>

			{#if error}<p class="error-message" role="alert">{error}</p>{/if}

			<button class="submit-button" disabled={!canSubmit}>
				{loading ? '로그인 중… / Signing in…' : '로그인 / Sign in'}
			</button>
		</form>
		<a href="/register">계정 만들기 / Create account</a>
	</section>
</main>

<style>
	.auth-page {
		min-height: 100vh;
		padding: 32px 18px;
		display: grid;
		place-items: center;
		background:
			radial-gradient(circle at 15% 15%, #e5ece5 0, transparent 30%),
			radial-gradient(circle at 85% 80%, #f3e4db 0, transparent 28%), #f7f5ef;
		color: #282b27;
		font-family: 'Noto Sans KR', sans-serif;
	}
	.auth-card {
		width: min(100%, 440px);
		padding: 42px;
		border: 1px solid #deddd5;
		border-radius: 18px;
		background: rgba(255, 255, 252, 0.95);
		box-shadow: 0 18px 50px rgba(67, 72, 64, 0.1);
	}
	.brand-mark {
		width: 42px;
		height: 42px;
		display: grid;
		place-items: center;
		border-radius: 50%;
		background: #536b60;
		color: white;
		font:
			600 20px Georgia,
			serif;
	}
	.eyebrow {
		margin: 22px 0 5px;
		color: #718277;
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.18em;
		text-transform: uppercase;
	}
	h1 {
		margin: 0;
		font:
			500 27px Georgia,
			'Noto Sans KR',
			serif;
	}
	.subtitle {
		margin: 10px 0 25px;
		color: #777b74;
		font-size: 11px;
		line-height: 1.7;
	}
	form {
		display: grid;
		gap: 9px;
	}
	label {
		margin-top: 8px;
		font-size: 11px;
		font-weight: 700;
	}
	input {
		width: 100%;
		height: 45px;
		padding: 0 13px;
		border: 1px solid #d5d6cf;
		border-radius: 9px;
		background: white;
		color: inherit;
		font: inherit;
		font-size: 12px;
		box-sizing: border-box;
	}
	input:focus {
		border-color: #708a7c;
		outline: 3px solid #e5ede8;
	}
	.password-field {
		position: relative;
	}
	.password-field input {
		padding-right: 58px;
	}
	.password-field button {
		position: absolute;
		top: 7px;
		right: 7px;
		height: 31px;
		border: 0;
		background: transparent;
		color: #62766b;
		font-size: 10px;
		font-weight: 700;
		cursor: pointer;
	}
	.submit-button {
		height: 46px;
		margin-top: 14px;
		border: 0;
		border-radius: 9px;
		background: #536b60;
		color: white;
		font-size: 11px;
		font-weight: 800;
		cursor: pointer;
	}
	.submit-button:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.error-message,
	.server-message {
		padding: 11px 13px;
		border-radius: 8px;
		font-size: 10px;
		line-height: 1.5;
	}
	.error-message {
		margin: 4px 0 0;
		background: #fff0eb;
		color: #9b4f3d;
	}
	.server-message {
		margin-bottom: 13px;
		background: #fff6dd;
		color: #80622e;
	}
	.auth-card > a {
		margin-top: 18px;
		display: block;
		color: #536b60;
		font-size: 10px;
		font-weight: 700;
		text-align: center;
		text-decoration: none;
	}
	@media (max-width: 500px) {
		.auth-card {
			padding: 30px 23px;
		}
	}
</style>
