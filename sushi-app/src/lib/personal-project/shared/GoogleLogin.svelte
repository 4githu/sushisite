<script lang="ts">
	import { onMount } from 'svelte';
	let { returnTo = '/personal-project/calendar' }: { returnTo?: string } = $props();
	let error = $state('');
	onMount(() => {
		const code = new URL(location.href).searchParams.get('google_error');
		if (code)
			error =
				code === 'cancelled'
					? '구글 로그인을 취소했습니다.'
					: code === 'account_link_required'
						? '기존 계정 연결을 확인해주세요. 이메일 로그인을 이용할 수 있습니다.'
						: '구글 연결을 완료하지 못했습니다. 다시 시도해주세요.';
	});
</script>

<a class="google-signin" href={`/auth/google/start?return_to=${encodeURIComponent(returnTo)}`}>
	<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"
		><path
			fill="#4285F4"
			d="M21.6 12.2c0-.7-.1-1.5-.2-2.2H12v4.2h5.4a4.6 4.6 0 0 1-2 3v2.5h3.3c1.9-1.8 2.9-4.4 2.9-7.5Z"
		/><path
			fill="#34A853"
			d="M12 22c2.7 0 5-.9 6.7-2.3l-3.3-2.6c-.9.6-2 .9-3.4.9-2.6 0-4.8-1.8-5.6-4.2H3v2.7A10 10 0 0 0 12 22Z"
		/><path fill="#FBBC05" d="M6.4 13.8a6 6 0 0 1 0-3.6V7.5H3a10 10 0 0 0 0 9l3.4-2.7Z" /><path
			fill="#EA4335"
			d="M12 6c1.5 0 2.8.5 3.8 1.5l2.9-2.9A9.6 9.6 0 0 0 12 2a10 10 0 0 0-9 5.5l3.4 2.7C7.2 7.8 9.4 6 12 6Z"
		/></svg
	>
	Google로 계속하기
</a>
{#if error}<p role="alert">{error}</p>{/if}

<style>
	.google-signin {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 12px;
		min-height: 46px;
		padding: 10px 18px;
		border: 1px solid #d7dce3;
		border-radius: 8px;
		background: white;
		color: #263140;
		font:
			500 14px system-ui,
			sans-serif;
		text-decoration: none;
	}
	.google-signin:hover {
		background: #f5f7fa;
	}
	.google-signin:focus-visible {
		outline: 3px solid #8fb5fa;
	}
	p {
		color: #a33535;
		font-size: 13px;
	}
</style>
