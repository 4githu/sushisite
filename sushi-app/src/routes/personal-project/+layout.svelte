<script lang="ts">
	import { onMount } from 'svelte';
	import PersonalLogin from '$lib/personal-project/shared/PersonalLogin.svelte';
	import { checkPersonalAuth, type PersonalUser } from '$lib/personal-project/shared/auth';
	import { PersonalApiError } from '$lib/personal-project/shared/api';

	let { children } = $props();
	let authState = $state<'checking' | 'authenticated' | 'guest' | 'offline'>('checking');
	let user = $state<PersonalUser | null>(null);
	let message = $state('');

	async function check() {
		authState = 'checking';
		message = '';
		try {
			user = await checkPersonalAuth();
			authState = user ? 'authenticated' : 'guest';
		} catch (cause) {
			user = null;
			authState =
				cause instanceof PersonalApiError && cause.code === 'backend_unreachable'
					? 'offline'
					: 'guest';
			message =
				cause instanceof Error
					? cause.message
					: '로그인 상태 확인 중 오류가 발생했습니다. / Authentication check failed.';
		}
	}

	onMount(check);
</script>

{#if authState === 'checking'}
	<div class="auth-loading" role="status">
		<span></span>
		<strong>로그인 상태 확인 중… / Checking your session…</strong>
	</div>
{:else if authState === 'authenticated' && user}
	{@render children()}
{:else}
	<PersonalLogin
		serverMessage={authState === 'offline' ? message : ''}
		onSuccess={(loggedInUser) => {
			user = loggedInUser;
			authState = 'authenticated';
		}}
	/>
{/if}

<style>
	.auth-loading {
		min-height: 100vh;
		display: grid;
		place-content: center;
		justify-items: center;
		gap: 14px;
		background: #f7f5ef;
		color: #68736b;
		font:
			11px 'Noto Sans KR',
			sans-serif;
	}
	.auth-loading span {
		width: 26px;
		height: 26px;
		border: 3px solid #dce2dc;
		border-top-color: #536b60;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
