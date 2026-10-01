<script lang="ts">
	import ApiKeys from '$lib/personal-project/boards/ApiKeys.svelte';
	import { onMount, untrack } from 'svelte';
	import { page } from '$app/state';
	import { goto, beforeNavigate } from '$app/navigation';
	import { request } from '$lib/personal-project/shared/api';
	import PersonalTextEditor from '$lib/personal-project/editor/PersonalTextEditor.svelte';
	import { createDocument } from '$lib/textediter/model';
	import type { EditorDocument } from '$lib/textediter/types';
	import '$lib/personal-project/student/student.css';
	type Board = { id: number; name: string; realm: string; permissions: Record<string, boolean> };
	type Post = {
		id: number;
		title: string;
		author_id: number;
		author_name: string;
		pinned: number;
		revision: number;
		created_at: string;
		comments: number;
	};
	type Detail = Omit<Post, 'comments'> & {
		board_id: number;
		document: EditorDocument;
		canEdit: boolean;
		canManage: boolean;
		canComment: boolean;
		comments: {
			id: number;
			content: string;
			parent_id: number | null;
			author_id: number;
			author_name: string;
			created_at: string;
			deleted: number;
			canDelete: boolean;
		}[];
	};
	let boards = $state<Board[]>([]),
		canAdmin = $state(false),
		canCreate = $state(false),
		posts = $state<Post[]>([]),
		total = $state(0),
		detail = $state<Detail | null>(null),
		loading = $state(true),
		busy = $state(false),
		error = $state(''),
		q = $state(''),
		trash = $state(false);
	let composing = $state(false),
		editId = $state<number | null>(null),
		title = $state(''),
		initial = $state<EditorDocument>(createDocument()),
		document = $state<EditorDocument>(createDocument()),
		changed = $state(false),
		comment = $state(''),
		reply = $state<number | null>(null),
		ready = $state(false);
	let account = $state<number | undefined>(),
		scope = $state('main'),
		action = $state('read'),
		permission = $state('allow'),
		acl = $state<{ user_id: number; scope: string; action: string; allowed: number }[]>([]);
	const bid = $derived(Number(page.url.searchParams.get('board') || 1));
	const pid = $derived(Number(page.url.searchParams.get('post') || 0));
	const currentPage = $derived(Number(page.url.searchParams.get('page') || 1));
	const board = $derived(boards.find((b) => b.id === bid));
	let generation = 0;
	beforeNavigate(({ cancel }) => {
		if (changed && !confirm('작성 중인 글을 두고 이동할까요?')) cancel();
	});
	async function run(fn: () => Promise<void>) {
		if (busy) return;
		busy = true;
		error = '';
		try {
			await fn();
		} catch (e) {
			error = e instanceof Error ? e.message : '처리하지 못했습니다.';
		} finally {
			busy = false;
			if (!ready) loading = false;
		}
	}
	onMount(() => {
		void run(async () => {
			const data = await request<{ boards: Board[]; canAdmin: boolean; canCreate: boolean }>(
				'/boards'
			);
			boards = data.boards;
			canAdmin = data.canAdmin;
			canCreate = data.canCreate;
			ready = true;
		});
	});
	$effect(() => {
		bid;
		pid;
		currentPage;
		if (ready) void untrack(load);
	});
	async function load() {
		const version = ++generation;
		loading = true;
		error = '';
		composing = false;
		changed = false;
		detail = null;
		try {
			if (pid) {
				const data = await request<Detail>(`/boards/posts/${pid}`);
				if (version === generation) detail = data;
			} else {
				const data = await request<{ posts: Post[]; total: number }>(
					`/boards/${bid}/posts?${new URLSearchParams({ page: String(currentPage), q, deleted: String(trash) })}`
				);
				if (version === generation) {
					posts = data.posts;
					total = data.total;
				}
			}
		} catch (e) {
			if (version === generation) error = String(e);
		} finally {
			if (version === generation) loading = false;
		}
	}
	function navigate(b: number, p = 0, n = 1) {
		return goto(`?board=${b}${p ? `&post=${p}` : ''}${n > 1 ? `&page=${n}` : ''}`, {
			keepFocus: true,
			noScroll: false
		});
	}
	function compose(edit = false) {
		editId = edit && detail ? detail.id : null;
		title = edit && detail ? detail.title : '';
		initial = edit && detail ? detail.document : createDocument();
		document = initial;
		composing = true;
		changed = false;
	}
	async function save() {
		const result = await request<{ id: number }>(
			editId ? `/boards/posts/${editId}` : `/boards/${bid}/posts`,
			{
				method: editId ? 'PUT' : 'POST',
				body: { title, document, revision: editId ? detail?.revision : 0 }
			}
		);
		changed = false;
		composing = false;
		if (result.id === pid) await load();
		else await navigate(bid, result.id);
	}
</script>

<svelte:head><title>게시판 · NETAQ</title></svelte:head>
<div class="student-page board-page">
	<header class="board-heading">
		<h1>게시판</h1>
		{#if canCreate}<button
				onclick={() =>
					run(async () => {
						const name = prompt('새 게시판 이름');
						if (!name?.trim()) return;
						const b = await request<{ id: number }>('/boards', { method: 'POST', body: { name } });
						const result = await request<{ boards: Board[] }>('/boards');
						boards = result.boards;
						await navigate(b.id);
					})}>게시판 만들기</button
			>{/if}
	</header>
	{#if board}<ApiKeys boardId={bid} boardName={board.name} />{/if}
	<nav class="board-tabs" aria-label="게시판 목록">
		{#each boards as b}<a class:active={bid === b.id} href={`?board=${b.id}`}>{b.name}</a>{/each}
	</nav>
	{#if error}<p class="error" role="alert">
			{error}<button onclick={load}>다시 불러오기</button>
		</p>{/if}
	{#if composing}<section class="composer">
			<div class="heading">
				<h2>{editId ? '글 수정' : '새 글'}</h2>
				<button
					onclick={() => {
						if (!changed || confirm('작성 중인 글을 닫을까요?')) {
							composing = false;
							changed = false;
						}
					}}>닫기</button
				>
			</div>
			<label
				>제목<input
					aria-label="글 제목"
					bind:value={title}
					maxlength="160"
					oninput={() => (changed = true)}
				/></label
			><PersonalTextEditor
				initialValue={initial}
				boardId={bid}
				onchange={(value) => {
					document = value;
					changed = true;
				}}
			/>
			<div class="actions">
				<button class="primary" disabled={busy || !title.trim()} onclick={() => run(save)}
					>{busy ? '저장 중…' : editId ? '수정 저장' : '게시하기'}</button
				>
			</div>
		</section>
	{:else if loading}<p role="status" class="list-status">불러오는 중…</p>
	{:else if detail}<article class="post-detail">
			<a href={`?board=${detail.board_id}`}>← 목록</a>
			<header>
				<h2>{detail.title}</h2>
				<p class="muted">
					{detail.author_name} · {new Date(detail.created_at + 'Z').toLocaleString('ko-KR')}
				</p>
			</header>
			<PersonalTextEditor initialValue={detail.document} readonly />
			<div class="actions">
				{#if detail.canEdit}<button onclick={() => compose(true)}>수정</button><button
						onclick={() =>
							run(async () => {
								await request(`/boards/posts/${pid}`, { method: 'PATCH', body: { deleted: true } });
								await navigate(detail!.board_id);
							})}>삭제</button
					>{/if}{#if detail.canManage}<button
						onclick={() =>
							run(async () => {
								await request(`/boards/posts/${pid}`, {
									method: 'PATCH',
									body: { pinned: !detail!.pinned }
								});
								await load();
							})}>{detail.pinned ? '공지 해제' : '공지로 고정'}</button
					>{/if}
			</div>
			<section class="comments">
				<h3>댓글 {detail.comments.filter((c) => !c.deleted).length}</h3>
				{#each detail.comments as c}<article class:reply={!!c.parent_id}>
						<small>{c.author_name}{c.parent_id ? ` · 댓글 #${c.parent_id}에 답글` : ''}</small>
						<p>{c.content}</p>
						{#if !c.deleted}<button onclick={() => (reply = c.id)}>답글</button
							>{#if c.canDelete}<button
									onclick={() =>
										run(async () => {
											await request(`/boards/comments/${c.id}`, { method: 'DELETE' });
											await load();
										})}>삭제</button
								>{/if}{/if}
					</article>{/each}
				{#if detail.canComment}<form
						onsubmit={(e) => {
							e.preventDefault();
							void run(async () => {
								detail = await request(`/boards/posts/${pid}/comments`, {
									method: 'POST',
									body: { content: comment, parent_id: reply }
								});
								comment = '';
								reply = null;
							});
						}}
					>
						{#if reply}<p>
								댓글 #{reply}에 답글
								<button type="button" onclick={() => (reply = null)}>취소</button>
							</p>{/if}<textarea
							aria-label="댓글 내용"
							placeholder="댓글을 남겨보세요"
							bind:value={comment}
							required
							maxlength="10000"
							rows="3"
						></textarea><button class="primary" disabled={busy || !comment.trim()}>댓글 등록</button
						>
					</form>{/if}
			</section>
		</article>
	{:else}<section>
			<div class="list-toolbar">
				<h2>{board?.name || '게시판'}</h2>
				<form
					onsubmit={(e) => {
						e.preventDefault();
						void load();
					}}
				>
					<input aria-label="게시글 검색" placeholder="제목·본문 검색" bind:value={q} /><button
						>검색</button
					>
				</form>
				{#if board?.permissions.post}<button class="primary" onclick={() => compose()}
						>글쓰기</button
					>{/if}{#if board?.permissions.manage}<label
						><input type="checkbox" bind:checked={trash} onchange={load} />휴지통</label
					>{/if}
			</div>
			<div class="post-list">
				{#each posts as p}<div class="post-row">
						<a href={`?board=${bid}&post=${p.id}`}
							><span>{p.pinned ? '공지 · ' : ''}{p.title}</span><small
								>{p.author_name} · {p.created_at.slice(0, 10)} · 댓글 {p.comments}</small
							></a
						>{#if trash}<button
								onclick={() =>
									run(async () => {
										await request(`/boards/posts/${p.id}`, {
											method: 'PATCH',
											body: { deleted: false }
										});
										await load();
									})}>복구</button
							>{/if}
					</div>{:else}<p class="list-status">
						{q ? '검색 결과가 없습니다.' : '아직 게시글이 없습니다.'}
					</p>{/each}
			</div>
			<nav class="pagination" aria-label="게시글 페이지">
				<button disabled={currentPage <= 1} onclick={() => navigate(bid, 0, currentPage - 1)}
					>이전</button
				><span>{currentPage} / {Math.max(1, Math.ceil(total / 30))}</span><button
					disabled={currentPage * 30 >= total}
					onclick={() => navigate(bid, 0, currentPage + 1)}>다음</button
				>
			</nav>
		</section>{/if}
	{#if canAdmin}<details class="permissions">
			<summary>계정별 게시판 권한</summary>
			<form
				class="fields"
				onsubmit={(e) => {
					e.preventDefault();
					void run(async () => {
						await request('/boards/permissions', {
							method: 'PUT',
							body: {
								user_id: account,
								scope,
								action,
								allowed: permission === 'default' ? null : permission === 'allow'
							}
						});
						acl = await request('/boards/permissions');
					});
				}}
			>
				<input
					aria-label="회원 ID"
					type="number"
					min="1"
					placeholder="회원 ID"
					bind:value={account}
					required
				/><select aria-label="권한 범위" bind:value={scope}
					><option value="main">메인 게시판</option><option value="other">기타 게시판 전체</option
					>{#each boards as b}<option value={`board:${b.id}`}>{b.name}</option>{/each}</select
				><select aria-label="동작" bind:value={action}
					>{#each [['read', '읽기'], ['post', '글쓰기'], ['comment', '댓글'], ['create', '게시판 생성'], ['manage', '관리']] as [a, label]}<option
							value={a}>{label}</option
						>{/each}</select
				><select aria-label="허용 여부" bind:value={permission}
					><option value="allow">허용</option><option value="deny">거부</option><option
						value="default">기본값</option
					></select
				><button disabled={busy}>권한 저장</button>
			</form>
			<button
				onclick={() =>
					run(async () => {
						acl = await request('/boards/permissions');
					})}>현재 권한 조회</button
			>{#each acl as a}<p>
					회원 {a.user_id} · {a.scope} · {a.action} · {a.allowed ? '허용' : '거부'}
				</p>{/each}
		</details>{/if}
</div>

<style>
	.board-page {
		max-width: 1100px;
	}
	.board-heading,
	.heading,
	.list-toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		flex-wrap: wrap;
	}
	.board-heading h1 {
		font-size: 28px;
	}
	.board-tabs {
		display: flex;
		gap: 24px;
		border-bottom: 1px solid var(--border, #ddd);
		margin: 20px 0 28px;
		overflow: auto;
	}
	.board-tabs a {
		padding: 12px 0;
		text-decoration: none;
		white-space: nowrap;
	}
	.board-tabs a.active {
		border-bottom: 3px solid currentColor;
		font-weight: 700;
	}
	.list-toolbar form {
		display: flex;
		gap: 6px;
		margin-left: auto;
	}
	.list-toolbar h2 {
		font-size: 20px;
	}
	.post-list {
		margin-top: 20px;
		border-top: 2px solid currentColor;
	}
	.post-row {
		border-bottom: 1px solid var(--border, #ddd);
		display: flex;
		align-items: center;
		gap: 12px;
	}
	.post-row > a {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 20px 4px;
		text-decoration: none;
		font-size: 16px;
	}
	.post-row small {
		font-size: 13px;
		opacity: 0.65;
	}
	.post-row:hover {
		background: #8888880b;
	}
	.pagination,
	.actions {
		display: flex;
		gap: 12px;
		justify-content: flex-end;
		align-items: center;
		margin: 18px 0;
	}
	.pagination {
		justify-content: center;
	}
	.list-status {
		padding: 48px 12px;
		text-align: center;
	}
	.composer > label {
		display: block;
		margin-bottom: 16px;
	}
	.composer > label input {
		width: 100%;
		margin-top: 8px;
		font-size: 20px;
	}
	.post-detail header {
		padding: 24px 0;
	}
	.post-detail h2 {
		font-size: 28px;
	}
	.comments {
		border-top: 1px solid var(--border, #ddd);
		margin-top: 32px;
		padding-top: 24px;
	}
	.comments article {
		padding: 16px 0;
		border-bottom: 1px solid var(--border, #ddd);
	}
	.comments article.reply {
		margin-left: 24px;
	}
	.comments p {
		white-space: pre-wrap;
	}
	.comments article button {
		font-size: 13px;
		margin-right: 12px;
	}
	.comments textarea {
		display: block;
		width: 100%;
		margin: 16px 0 8px;
	}
	.permissions {
		margin-top: 48px;
		padding: 20px 0;
		border-top: 1px solid var(--border, #ddd);
	}
	@media (max-width: 600px) {
		.list-toolbar form {
			order: 3;
			width: 100%;
		}
		.list-toolbar input {
			flex: 1;
			min-width: 0;
		}
		.post-detail h2 {
			font-size: 23px;
		}
	}
</style>
