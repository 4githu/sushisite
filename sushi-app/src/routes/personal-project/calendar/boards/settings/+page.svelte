<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { request } from '$lib/personal-project/shared/api';
	import '$lib/personal-project/student/student.css';
	type Board = {
		id: number;
		name: string;
		parent_id: number | null;
		permissions: Record<string, boolean>;
		post_count?: number;
		archived?: number;
		system_key?: string | null;
	};
	let boards = $state<Board[]>([]);
	let canAdmin = $state(false);
	let selectedId = $state(0);
	let channelName = $state('');
	let busy = $state(false);
	let loading = $state(true);
	let error = $state('');
	let notice = $state('');
	let management = $state<{ archived: { id: number; name: string }[] }>({ archived: [] });
	const selected = $derived(boards.find((board) => board.id === selectedId));
	const channels = $derived(boards.filter((board) => board.parent_id === selectedId));

	async function load() {
		const result = await request<{ boards: Board[]; canAdmin: boolean }>('/boards');
		boards = result.boards;
		canAdmin = result.canAdmin;
		if (!selectedId || !boards.some((board) => board.id === selectedId)) {
			const requested = Number(page.url.searchParams.get('board'));
			selectedId =
				requested && boards.some((board) => board.id === requested)
					? requested
					: boards.find((board) => !board.parent_id)?.id || boards[0]?.id || 0;
		}
		if (selectedId) management = await request(`/boards/${selectedId}/management`);
	}
	async function run(action: () => Promise<void>) {
		busy = true;
		error = '';
		notice = '';
		try {
			await action();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			busy = false;
			loading = false;
		}
	}
	onMount(() => {
		void run(load);
	});
	async function saveName(board: Board, value: string) {
		await request(`/boards/${board.id}/settings`, { method: 'PUT', body: { name: value } });
		await load();
		notice = '게시판 이름을 저장했습니다.';
	}
</script>

<svelte:head><title>게시판 설정 · NETAQ</title></svelte:head>
<main class="student-page board-settings-page">
	<header class="page-heading">
		<div>
			<p class="eyebrow">NETAQ</p>
			<h1>게시판 설정</h1>
		</div>
		<a href="/personal-project/calendar/boards">게시판으로 돌아가기</a>
	</header>
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	{#if notice}<p role="status">{notice}</p>{/if}
	{#if loading}<p role="status">게시판 설정을 불러오는 중…</p>
	{:else if !canAdmin}<p role="alert">게시판 설정은 관리자만 사용할 수 있습니다.</p>
	{:else}
		<section class="settings-card">
			<label
				>게시판 선택<select
					bind:value={selectedId}
					onchange={() => {
						void run(load);
					}}
				>
					{#each boards.filter((board) => !board.parent_id) as board}<option value={board.id}
							>{board.name}</option
						>{/each}
				</select></label
			>
			{#if selected}<div class="root-settings">
					<form
						onsubmit={(event) => {
							event.preventDefault();
							void run(() =>
								saveName(
									selected!,
									(event.currentTarget.elements.namedItem('board-name') as HTMLInputElement).value
								)
							);
						}}
					>
						<label
							>게시판 이름<input
								name="board-name"
								value={selected.name}
								required
								maxlength="80"
							/></label
						><button disabled={busy}>이름 저장</button>
					</form>
					<button
						class="danger"
						disabled={busy || !!selected.system_key}
						title={selected.system_key
							? '시스템 게시판은 삭제할 수 없습니다.'
							: '게시판과 하위 채널을 영구 삭제'}
						onclick={() =>
							void run(async () => {
								if (
									!confirm(
										`‘${selected!.name}’과 하위 채널, 게시글, 첨부 파일을 모두 영구 삭제할까요? 되돌릴 수 없습니다.`
									)
								)
									return;
								await request(`/admin/boards/${selected!.id}`, { method: 'DELETE' });
								selectedId = 0;
								await load();
								notice = '게시판을 삭제했습니다.';
							})}>게시판 삭제</button
					>
				</div>{/if}
		</section>
		<section class="settings-card">
			<div class="section-heading">
				<div>
					<h2>세부 채널</h2>
					<p>{selected?.name} 아래에서 사용하는 채널입니다.</p>
				</div>
			</div>
			<form
				class="create-channel"
				onsubmit={(event) => {
					event.preventDefault();
					void run(async () => {
						await request('/boards', {
							method: 'POST',
							body: { name: channelName, parent_id: selectedId }
						});
						channelName = '';
						await load();
						notice = '채널을 만들었습니다.';
					});
				}}
			>
				<label
					>새 채널 이름<input
						bind:value={channelName}
						required
						maxlength="80"
						placeholder="예: 생명과학"
					/></label
				><button class="primary" disabled={busy || !channelName.trim()}>채널 추가</button>
			</form>
			<div class="table-scroll">
				<table>
					<thead><tr><th>채널</th><th>게시글</th><th>작업</th></tr></thead><tbody>
						{#each channels as channel}<tr
								><td><strong>{channel.name}</strong></td><td>{channel.post_count ?? 0}</td><td
									class="actions"
								>
									<button
										disabled={busy}
										onclick={() =>
											void run(async () => {
												const name = prompt('새 채널 이름', channel.name);
												if (name === null || !name.trim()) return;
												await saveName(channel, name.trim());
											})}>이름 변경</button
									>
									<button
										disabled={busy}
										onclick={() =>
											void run(async () => {
												if (!confirm(`‘${channel.name}’ 채널을 보관할까요? 게시글은 보존됩니다.`))
													return;
												await request(`/boards/${channel.id}/settings`, {
													method: 'PUT',
													body: { name: channel.name, archived: true }
												});
												await load();
												notice = '채널을 보관했습니다.';
											})}>보관</button
									>
									<button
										class="danger"
										disabled={busy || !!channel.system_key}
										title={channel.system_key
											? '시스템 채널은 삭제할 수 없습니다.'
											: '채널과 하위 자료를 영구 삭제'}
										onclick={() =>
											void run(async () => {
												if (
													!confirm(
														`‘${channel.name}’과 게시글, 첨부 파일을 모두 영구 삭제할까요? 이 작업은 되돌릴 수 없습니다.`
													)
												)
													return;
												await request(`/boards/${selectedId}/channels/${channel.id}`, {
													method: 'DELETE'
												});
												await load();
												notice = '채널을 삭제했습니다.';
											})}>삭제</button
									>
								</td></tr
							>{:else}<tr><td colspan="3">아직 채널이 없습니다.</td></tr>{/each}
					</tbody>
				</table>
			</div>
			{#if management.archived.length}<h3>보관한 채널</h3>
				<div class="archived-list">
					{#each management.archived as channel}<div>
							<span>{channel.name}</span><button
								disabled={busy}
								onclick={() =>
									void run(async () => {
										await request(`/boards/${selectedId}/channels/${channel.id}/restore`, {
											method: 'POST'
										});
										await load();
										notice = '채널을 복구했습니다.';
									})}>복구</button
							>
						</div>{/each}
				</div>{/if}
		</section>
		<p class="settings-footnote">
			보관하면 게시글을 보존하고 목록에서 숨깁니다. 삭제하면 게시글, 댓글, 첨부 파일과 하위 채널이
			영구 삭제됩니다.
		</p>
	{/if}
</main>

<style>
	.board-settings-page {
		max-width: 1080px;
	}
	.page-heading,
	.section-heading,
	.create-channel,
	form {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 12px;
		flex-wrap: wrap;
	}
	.root-settings {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 12px;
		flex-wrap: wrap;
	}
	.page-heading a {
		color: inherit;
	}
	.settings-card {
		margin: 22px 0;
		padding: 20px;
		border: 1px solid var(--border, #ddd);
		border-radius: 14px;
		background: var(--surface, #fff);
	}
	.settings-card label {
		display: grid;
		gap: 6px;
		min-width: min(100%, 260px);
	}
	.settings-card input,
	.settings-card select,
	.settings-card button {
		min-height: 40px;
		padding: 8px 12px;
		border: 1px solid #8885;
		border-radius: 8px;
		background: var(--surface, #fff);
		color: inherit;
	}
	.settings-card button {
		cursor: pointer;
	}
	.settings-card .primary {
		background: #6d28d9;
		color: #fff;
	}
	table {
		width: 100%;
		border-collapse: collapse;
	}
	th,
	td {
		padding: 12px 8px;
		text-align: left;
		border-bottom: 1px solid #8883;
	}
	.actions {
		white-space: nowrap;
		text-align: right;
	}
	.danger {
		color: #b42318 !important;
	}
	.archived-list > div {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 0;
		border-bottom: 1px solid #8883;
	}
	.settings-footnote {
		color: var(--muted, #777);
		font-size: 13px;
	}
</style>
