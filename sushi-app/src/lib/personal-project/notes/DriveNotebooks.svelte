<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from '../shared/api';
	import { icon } from '../../notebook/icons';
	import type { NoteLibrary } from './library';
	let { search = '' }: { search?: string } = $props();
	let catalog = $state<NoteLibrary | null>(null),
		error = $state(''),
		opened = $state(false);
	async function load() {
		try {
			const result = await request<{ data: NoteLibrary | null }>('/documents/notes%3Alibrary%3Av1');
			catalog = result.data;
			error = '';
		} catch (e) {
			error = e instanceof Error ? e.message : '노트 목록을 불러오지 못했습니다';
		}
	}
	onMount(() => {
		void load();
		window.addEventListener('focus', load);
		return () => window.removeEventListener('focus', load);
	});
	function link(notebook: string, section?: string, note?: string) {
		const q = new URLSearchParams({ notebook });
		if (section) q.set('section', section);
		if (note) q.set('note', note);
		return '/personal-project/notes?' + q;
	}
	const books = $derived(
		catalog?.notebooks.filter(
			(b) =>
				!search ||
				b.title.toLowerCase().includes(search.toLowerCase()) ||
				b.sections.some(
					(s) =>
						s.title.toLowerCase().includes(search.toLowerCase()) ||
						s.notes.some((n) => !n.deleted && n.title.toLowerCase().includes(search.toLowerCase()))
				)
		) || []
	);
</script>

{#if !search || books.length}
	<details class="drive-notebooks" bind:open={opened}>
		<summary class="drive-row"
			><span class="drive-file-name">{@html icon('open')}<strong>노트북</strong></span><span
				class="file-sharing">나만 보기</span
			><span class="file-date">NETAQ Notes</span><span class="file-size">폴더</span></summary
		>
		{#if opened}<div class="notebooks-tree" aria-label="드라이브 노트북">
				{#if error}<p role="alert">
						{error}<button onclick={load}>다시 불러오기</button>
					</p>{:else if !catalog || !books.length}<div class="notes-folder-empty">
						<span>노트북을 만들고 페이지를 정리해 보세요.</span><a href="/personal-project/notes"
							>Notes 열기</a
						>
					</div>{/if}
				{#each books as book (book.id)}<details class="notebook-branch">
						<summary
							>{@html icon('pages')}<span>{book.title}</span><a
								href={link(book.id)}
								aria-label={book.title + ' 노트북 열기'}
								onclick={(e) => e.stopPropagation()}>열기 ↗</a
							></summary
						>
						{#each book.sections as section (section.id)}<details class="section-branch">
								<summary><span class="section-line"></span>{section.title}</summary>
								<div class="notes-leaves">
									{#each section.notes.filter((n) => !n.deleted) as note (note.id)}<a
											href={link(book.id, section.id, note.id)}
											>{@html icon('text')}<span>{note.title}</span><span aria-hidden="true">↗</span
											></a
										>{:else}<span class="no-pages">빈 섹션</span>{/each}
								</div>
							</details>{/each}
					</details>{/each}
			</div>{/if}
	</details>{/if}

<style>
	.drive-notebooks {
		border-bottom: 1px solid #e8eaf0;
	}
	.drive-notebooks > summary {
		list-style: none;
		cursor: pointer;
	}
	.drive-notebooks > summary::-webkit-details-marker {
		display: none;
	}
	.drive-notebooks :global(svg) {
		width: 18px;
		height: 18px;
		flex: none;
		color: #7d8797;
	}
	.drive-notebooks > summary :global(svg) {
		width: 24px;
		height: 24px;
		color: #bd7545;
	}
	.notebooks-tree {
		padding: 10px 20px 16px 42px;
		background: #fafafb;
		border-top: 1px solid #edeef2;
		font:
			12px 'Noto Sans KR',
			sans-serif;
		color: #3b404a;
	}
	.notebook-branch > summary,
	.section-branch > summary {
		display: flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
		min-height: 34px;
		list-style: none;
	}
	.notebook-branch > summary a {
		margin-left: auto;
		color: #8a8f99;
		text-decoration: none;
		font-size: 10px;
	}
	.section-branch {
		margin-left: 26px;
	}
	.section-line {
		width: 3px;
		height: 15px;
		background: #ac705c;
		border-radius: 1px;
	}
	.notes-leaves {
		display: grid;
		gap: 3px;
		margin-left: 16px;
	}
	.notes-leaves > a {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px;
		color: #4b515d;
		text-decoration: none;
		border-radius: 4px;
	}
	.notes-leaves > a:hover {
		background: #edeef2;
	}
	.notes-leaves > a :global(svg) {
		width: 14px;
		height: 14px;
	}
	.notes-leaves > a > span:nth-child(2) {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.notes-leaves > a > span:last-child {
		margin-left: auto;
		color: #9a9faa;
	}
	.no-pages {
		color: #9398a3;
		padding: 8px;
		font-size: 11px;
	}
	.notes-folder-empty {
		display: flex;
		gap: 16px;
		align-items: center;
		font-size: 11px;
		color: #8a8f99;
		padding: 10px 0;
	}
	.notes-folder-empty a {
		color: #a25943;
		text-decoration: none;
	}
	.notebooks-tree p {
		font-size: 11px;
	}
	.notebooks-tree button {
		margin-left: 10px;
		background: white;
		border: 1px solid #dddfe6;
		border-radius: 3px;
		padding: 4px 6px;
		font: inherit;
	}
</style>
