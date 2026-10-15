<script lang="ts">
	import { request } from '$lib/personal-project/shared/api';
	let { boardId, boardName }: { boardId: number; boardName: string } = $props();
	type Key = { id: string; name: string; expires_at: number; revoked: number };
	let keys = $state<Key[]>([]),
		name = $state('게시글 자동 등록'),
		days = $state(30),
		secret = $state(''),
		error = $state(''),
		busy = $state(false),
		opened = $state(false);
	let scopes = $state(['read', 'post', 'upload']);
	async function load() {
		try {
			keys = await request<Key[]>('/board-api/tokens', { cache: 'no-store' });
		} catch (e) {
			error = String(e);
		}
	}
	async function create() {
		if (busy) return;
		busy = true;
		error = '';
		secret = '';
		try {
			const r = await request<{ token: string }>('/board-api/tokens', {
				method: 'POST',
				body: { name, board_ids: [boardId], scopes, expires_days: days }
			});
			secret = r.token;
			await load();
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
	async function revoke(id: string) {
		try {
			await request(`/board-api/tokens/${id}`, { method: 'DELETE' });
			secret = '';
			await load();
		} catch (e) {
			error = String(e);
		}
	}
</script>

<details
	ontoggle={(e) => {
		opened = e.currentTarget.open;
		if (opened) void load();
		else secret = '';
	}}
>
	<summary>게시글 자동 등록 · API 키</summary>
	{#if opened}
		<p>
			현재 게시판 ‘{boardName}’에만 사용할 키를 만듭니다. 키는 발급 직후 한 번 표시되며
			선택한 게시판과 허용한 작업에만 사용할 수 있습니다.
		</p>
		<div class="fields">
			<label>키 이름 <input bind:value={name} maxlength="80" /></label><label
				>만료 <select bind:value={days}
					><option value={7}>7일</option><option value={30}>30일</option><option value={90}
						>90일</option
					></select
				></label
			>
		</div>
		<fieldset>
			<legend>허용 작업</legend
			>{#each [['read', '읽기'], ['post', '글 작성·수정'], ['comment', '댓글'], ['upload', '파일 업로드']] as [value, label]}<label
					><input type="checkbox" {value} bind:group={scopes} />{label}</label
				>{/each}
		</fieldset>
		<button onclick={create} disabled={busy || !scopes.length || !name.trim()}
			>현재 게시판용 키 발급</button
		>
		{#if secret}<label class="secret"
				>API 키 — 안전한 곳에 보관한 뒤 닫으세요<textarea
					readonly
					value={secret}
					aria-label="발급된 API 키"
				></textarea></label
			>{/if}
		{#if error}<p role="alert">{error}</p>{/if}
		<ul>
			{#each keys as key}<li>
					{key.name} · {new Date(key.expires_at * 1000).toLocaleDateString()} 만료 {#if key.revoked}·
						폐기됨{:else}<button onclick={() => revoke(key.id)}>폐기</button>{/if}
				</li>{/each}
		</ul>
		<a href="/docs/board-api.md" target="_blank" rel="noreferrer">API 문서와 Python 예제</a>
	{/if}
</details>

<style>
	details {
		margin: 1rem 0;
		padding: 0.8rem;
		border: 1px solid var(--border-color, #8884);
		border-radius: 0.6rem;
	}
	summary {
		cursor: pointer;
	}
	p {
		font-size: 0.85rem;
		line-height: 1.6;
	}
	.fields,
	fieldset {
		display: flex;
		gap: 0.8rem;
		flex-wrap: wrap;
		margin: 0.7rem 0;
	}
	label {
		display: flex;
		gap: 0.4rem;
		align-items: center;
	}
	input,
	select,
	textarea {
		max-width: 100%;
		padding: 0.4rem;
		background: transparent;
		color: inherit;
		border: 1px solid #8886;
		border-radius: 0.3rem;
	}
	.secret {
		display: block;
		margin: 1rem 0;
	}
	textarea {
		width: 100%;
		min-height: 5rem;
		overflow-wrap: anywhere;
	}
	li {
		margin: 0.5rem 0;
	}
	button {
		padding: 0.35rem 0.7rem;
		border: 1px solid #8886;
		border-radius: 0.3rem;
	}
</style>
