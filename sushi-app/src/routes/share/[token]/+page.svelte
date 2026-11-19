<script lang="ts">
	import { page } from '$app/state';
	import { API_BASE } from '$lib/personal-project/shared/api';
	let item = $state<{ name: string; byteSize: number } | null>(null),
		error = $state('');
	const url = $derived(
		`${API_BASE}/api/personal/drive/shared/${encodeURIComponent(page.params.token || '')}`
	);
	$effect(() => {
		let current = true;
		item = null;
		error = '';
		void fetch(url, { credentials: 'omit', referrerPolicy: 'no-referrer' })
			.then(async (response) => {
				if (!response.ok) {
					const data = await response.json().catch(() => null);
					throw new Error(
						typeof data?.detail === 'string' ? data.detail : '이 공유 링크를 열 수 없어요.'
					);
				}
				return response.json();
			})
			.then((value) => {
				if (current) item = value;
			})
			.catch((e) => {
				if (current) error = e.message;
			});
		return () => {
			current = false;
		};
	});
</script>

<svelte:head
	><title>공유 파일 · NETAQ</title><meta name="referrer" content="no-referrer" /><meta
		name="robots"
		content="noindex,nofollow"
	/></svelte:head
>
<main>
	<a class="brand" href="https://netaq.chobab.app">NETAQ</a>{#if item}<h1>{item.name}</h1>
		<p>{(item.byteSize / 1024 / 1024).toFixed(2)} MB</p>
		<a class="download" href={`${url}/content`} download={item.name} referrerpolicy="no-referrer"
			>파일 다운로드</a
		>{:else if error}<h1>파일을 열 수 없어요</h1>
		<p role="alert">{error}</p>{:else}<p role="status">파일을 확인하는 중…</p>{/if}
</main>

<style>
	main {
		max-width: 600px;
		margin: 12vh auto;
		padding: 24px;
		color: #242529;
		font-family: inherit;
	}
	.brand {
		color: #c4412c;
		font-weight: 700;
		text-decoration: none;
		font-size: 22px;
	}
	h1 {
		font-size: 26px;
		margin: 32px 0 12px;
		overflow-wrap: anywhere;
	}
	p {
		color: #696b73;
		font-size: 14px;
		line-height: 1.7;
	}
	.download {
		display: inline-flex;
		align-items: center;
		min-height: 48px;
		padding: 8px 20px;
		border-radius: 8px;
		background: #c4412c;
		color: white;
		text-decoration: none;
		margin-top: 16px;
		box-sizing: border-box;
	}
</style>
