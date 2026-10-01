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
	type Board = {
		id: number;
		name: string;
		realm: string;
		post_count?: number;
		last_title?: string;
		permissions: Record<string, boolean>;
	};
	type Post = {
		thumbnail?: string;
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
	const bid = $derived(Number(page.url.searchParams.get('board') || 0));
	const pid = $derived(Number(page.url.searchParams.get('post') || 0));
	const currentPage = $derived(Number(page.url.searchParams.get('page') || 1));
	const board = $derived(boards.find((b) => b.id === bid));
	let composer = $state<PersonalTextEditor>();
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
			} else if (bid) {
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
		<h1>{board?.name || '게시판'}</h1>
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
	{#if board}<a href="/personal-project/calendar/boards">← 전체 게시판</a>{/if}
	{#if bid}<nav class="board-tabs" aria-label="게시판 목록">
			{#each boards as b}<a class:active={bid === b.id} href={`?board=${b.id}`}>{b.name}</a>{/each}
		</nav>{/if}
	{#if !bid}<section class="board-directory">
			<h2>전체 게시판</h2>
			{#if !ready}<p>게시판을 불러오는 중…</p>{/if}{#each boards as b}<a href={`?board=${b.id}`}
					><div>
						<strong>{b.name}</strong>
						<p>{b.last_title || '첫 글을 남겨보세요.'}</p>
					</div>
					<span>{b.post_count || 0}개 글 · 목록 보기 →</span></a
				>{/each}
		</section>{/if}
	{#if error}<p class="error" role="alert">
			{error}<button onclick={load}>다시 불러오기</button>
		</p>{/if}
	{#if bid}{#if composing}<section class="composer">
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
				>
				<p class="attachment-help">
					‘그림 메모’로 그려서 첨부하세요. 사진·그림을 선택하면 위치와 크기를 바꿀 수 있습니다.
				</p>
				<PersonalTextEditor
					bind:this={composer}
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
									await request(`/boards/posts/${pid}`, {
										method: 'PATCH',
										body: { deleted: true }
									});
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
							></textarea><button class="primary" disabled={busy || !comment.trim()}
								>댓글 등록</button
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
								>{#if p.thumbnail}<img
										class="post-thumb"
										src={p.thumbnail}
										alt="첨부 이미지"
										loading="lazy"
									/>{/if}<span>{p.pinned ? '공지 · ' : ''}{p.title}</span><small
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
	{/if}
	{#if board}<ApiKeys boardId={bid} boardName={board.name} />{/if}
	{#if canAdmin}<a href="/personal-project/calendar/admin">관리자 화면 →</a>{/if}
</div>

<style>
	.post-thumb {
		float: right;
		width: 76px;
		height: 64px;
		object-fit: cover;
		border-radius: 6px;
		margin-left: 12px;
	}
	.attachment-help {
		font-size: 13px;
		color: #666;
	}
	.board-directory {
		display: grid;
		gap: 0;
	}
	.board-directory > a {
		display: flex;
		justify-content: space-between;
		gap: 16px;
		padding: 22px 4px;
		border-bottom: 1px solid #8884;
		text-decoration: none;
		color: inherit;
	}
	.board-directory p {
		font-size: 13px;
		color: #666;
		margin: 8px 0 0;
	}
	.board-directory span {
		font-size: 13px;
		color: #777;
	}
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
		min-width: 0;
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 8px;
		padding: 20px 4px;
		text-decoration: none;
		font-size: 16px;
	}
	.post-row > a > span,
	.post-row > a > small {
		grid-column: 1;
		overflow-wrap: anywhere;
	}
	.post-row > a > .post-thumb {
		grid-column: 2;
		grid-row: 1 / 3;
		align-self: center;
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
