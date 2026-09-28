<script lang="ts">
	import { onMount } from 'svelte';
	let { signup = false }: { signup?: boolean } = $props();
	let returnTo = $state('/personal-project/calendar');
	let failure = $state('');
	onMount(() => {
		const url = new URL(location.href);
		returnTo =
			url.pathname.startsWith('/personal-project/') || url.pathname.startsWith('/odi')
				? url.pathname + url.search
				: location.hostname === 'rehear.chobab.app'
					? '/odi'
					: '/personal-project/calendar/student';
		if (url.searchParams.has('google_error'))
			failure =
				url.searchParams.get('google_error') === 'account_link_required'
					? '기존 계정과 연결이 필요합니다. 이메일·비밀번호로 로그인해주세요.'
					: 'Google 로그인을 완료하지 못했습니다. 다시 시도해주세요.';
	});
</script>

<a
	class="google-auth"
	href={`/auth/google/start?purpose=login&return_to=${encodeURIComponent(returnTo)}`}
	>Google로 {signup ? '가입 / 로그인' : '로그인'}</a
>
{#if failure}<p role="alert">{failure}</p>{/if}

<style>
	.google-auth {
		display: block;
		text-align: center;
		padding: 12px;
		margin: 16px 0;
		border: 1px solid #d5d8de;
		border-radius: 9px;
		background: white;
		color: #252930;
		text-decoration: none;
		font-size: 14px;
		font-weight: 600;
	}
	p {
		font-size: 13px;
		color: #b33939;
	}
</style>
