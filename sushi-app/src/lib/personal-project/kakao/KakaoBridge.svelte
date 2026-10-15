<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from '../shared/api';
	import { uploadResource } from '../resources/api';
	type Item = {
		id: string;
		room: string;
		text: string;
		metadata: string;
		photo_id: string | null;
		photo_error: string | null;
		published_post: number | null;
	};
	type Status = {
		installed: boolean;
		sources: {
			room: string;
			mention: string;
			enabled: number;
			last_scan: string | null;
			error: string | null;
		}[];
		jobs: { id: string; state: string; result: string; created_at: string }[];
		inbox: Item[];
	};
	let bridgeState = $state<Status | null>(null),
		room = $state('2026 파인애플 (졸업생)'),
		mention = $state('김지후'),
		enabled = $state(false),
		text = $state(''),
		photo = $state(''),
		error = $state(''),
		notice = $state(''),
		busy = $state(false),
		boards = $state<{ id: number; name: string }[]>([]),
		board = $state(1);
	let key = crypto.randomUUID();
	function jobLabel(value: string) {
		return (
			(
				{
					queued: '전송 대기',
					running: '전송 중',
					succeeded: '전송 확인',
					failed: '전송 실패',
					unknown: '전송 여부 확인 필요'
				} as Record<string, string>
			)[value] || value
		);
	}
	async function refresh() {
		bridgeState = await request('/kakao-bridge');
	}
	onMount(() => {
		void refresh().catch(() => {});
		const timer = setInterval(() => {
			if (bridgeState) void refresh().catch((e) => (error = String(e)));
		}, 5000);
		return () => clearInterval(timer);
	});
	async function action(fn: () => Promise<unknown>) {
		if (busy) return;
		busy = true;
		error = '';
		try {
			const result: any = await fn();
			if (result?.error) throw Error(result.error);
			await refresh();
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
	async function publish(item: Item) {
		const title = prompt('게시판 글 제목', item.text.replace(/^@\S+\s*/, '').slice(0, 100));
		if (!title) return;
		await action(async () => {
			await request(`/kakao-bridge/inbox/${item.id}/publish`, {
				method: 'POST',
				body: { board_id: board, title }
			});
			notice = '선택한 게시판에 공개했습니다.';
		});
	}
</script>

{#if bridgeState}<section class="bridge">
		<details>
			<summary>카카오톡 자료 공유</summary>
			<p>
				이 Mac의 카카오톡에서 읽은 멘션은 내 보관함에 저장됩니다. 공개할 항목을 골라 게시판으로
				보내세요.
			</p>
			<p class="hint">
				현재 불러온 대화만 확인할 수 있습니다. Mac이 잠들거나 카카오톡이 닫혀 있으면 수집이
				멈춥니다. 사진은 카카오톡의 이미지 복사본(PNG)으로 보관합니다.
			</p>
			{#if !bridgeState.installed}<p role="alert">Mac 도우미 설치가 필요합니다.</p>{/if}
			<div class="controls">
				<label>채팅방 이름<input bind:value={room} /></label><label
					>내 멘션 이름<input bind:value={mention} /></label
				><button
					disabled={busy}
					onclick={() =>
						action(() =>
							request('/kakao-bridge/search', {
								method: 'POST',
								body: { room, mention, enabled: false }
							})
						)}>방 검색 · 열기</button
				><button
					disabled={busy}
					onclick={() =>
						action(() =>
							request('/kakao-bridge/scan', {
								method: 'POST',
								body: { room, mention, enabled: false }
							})
						)}>지금 수집</button
				>
			</div>
			<label><input type="checkbox" bind:checked={enabled} />30초마다 멘션 확인</label><button
				disabled={busy}
				onclick={() =>
					action(() =>
						request('/kakao-bridge/source', { method: 'PUT', body: { room, mention, enabled } })
					)}>수집 설정 저장</button
			>
			{#each bridgeState.sources as s}<p>
					{s.room} · {s.enabled ? '수집 켜짐' : '수집 꺼짐'} · {s.last_scan || '아직 확인하지 않음'}
					{s.error || ''}
				</p>{/each}
			<h3>글·사진 보내기</h3>
			<textarea
				aria-label="카카오톡으로 보낼 글"
				bind:value={text}
				oninput={() => (key = crypto.randomUUID())}
				placeholder="지정한 채팅방으로 보낼 내용"
			></textarea><label
				>사진<input
					type="file"
					accept="image/png,image/jpeg,image/webp"
					onchange={(e) => {
						const f = e.currentTarget.files?.[0];
						if (f)
							void action(async () => {
								photo = (await uploadResource(f)).id;
								key = crypto.randomUUID();
								notice = '사진을 첨부했습니다.';
							});
					}}
				/></label
			>{#if photo}<button
					onclick={() => {
						photo = '';
						key = crypto.randomUUID();
					}}>사진 빼기</button
				>{/if}<button
				disabled={busy || (!text.trim() && !photo)}
				onclick={() =>
					action(async () => {
						await request('/kakao-bridge/send', {
							method: 'POST',
							body: { room, text, resources: photo ? [photo] : [], idempotency_key: key }
						});
						notice = '전송 대기열에 넣었습니다. 아래 결과를 확인해주세요.';
					})}>「{room}」에 보내기</button
			>
			{#each bridgeState.jobs as j}<p>
					{j.created_at} · {jobLabel(j.state)}
					{j.result ? JSON.parse(j.result).error || '' : ''}
				</p>{/each}
			<h3>내 멘션 보관함</h3>
			<button
				onclick={() =>
					action(async () => {
						boards = (await request<{ boards: { id: number; name: string }[] }>('/boards')).boards;
					})}>공개할 게시판 선택</button
			>{#if boards.length}<select aria-label="공개할 게시판" bind:value={board}
					>{#each boards as b}<option value={b.id}>{b.name}</option>{/each}</select
				>{/if}
			{#each bridgeState.inbox as item}<article>
					<small>{item.room} · {item.metadata}</small>
					<p>{item.text}</p>
					{#if item.photo_id}<img
							src={`/api/personal/resources/${item.photo_id}`}
							alt="멘션 다음 사진"
						/>{/if}{#if item.photo_error}<p role="alert">
							{item.photo_error}
						</p>{/if}{#if item.published_post}<a
							href={`/personal-project/calendar/boards?post=${item.published_post}`}
							>공개한 글 보기</a
						>{:else if boards.length}<button disabled={busy} onclick={() => publish(item)}
							>선택한 게시판에 공개</button
						>{/if}
				</article>{:else}<p>아직 수집한 멘션이 없습니다.</p>{/each}
			{#if error}<p role="alert">{error}</p>{/if}{#if notice}<p role="status">{notice}</p>{/if}
		</details>
	</section>{/if}

<style>
	.bridge {
		margin-block: 24px;
		border-block: 1px solid #8884;
		padding: 16px 0;
	}
	summary {
		font-weight: 650;
		cursor: pointer;
	}
	.hint,
	small {
		opacity: 0.65;
	}
	.controls {
		display: flex;
		gap: 12px;
		flex-wrap: wrap;
		align-items: end;
	}
	label {
		display: inline-flex;
		gap: 8px;
		align-items: center;
		margin: 8px;
	}
	textarea {
		display: block;
		width: 100%;
		min-height: 90px;
	}
	article {
		border-top: 1px solid #8884;
		padding: 16px 0;
	}
	article p {
		white-space: pre-wrap;
	}
	article img {
		max-width: 240px;
		max-height: 200px;
	}
	button {
		margin: 6px;
	}
	p[role='alert'] {
		color: #b32946;
	}
</style>
