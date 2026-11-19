<script lang="ts">
	import { onMount, tick } from 'svelte';
	import NotebookWorkspace from '../../notebook/NotebookWorkspace.svelte';
	import AnchoredPopover from '../../notebook/AnchoredPopover.svelte';
	import PaperOptions from '../../notebook/PaperOptions.svelte';
	import { type PaperTemplate, savePaperDefault } from '../../notebook/paper';
	import { icon } from '../../notebook/icons';
	import { openLibrary, type NoteLibrary, type NoteEntry } from './library';
	import './notes-library.css';
	let library = $state<NoteLibrary | null>(null),
		service = $state.raw<Awaited<ReturnType<typeof openLibrary>>>(null!),
		workspace = $state<NotebookWorkspace>(null!);
	let importDone = $state(false);
	let loading = $state(true),
		error = $state(''),
		notice = $state(''),
		busy = $state(false),
		navigation = $state(false),
		search = $state(''),
		trash = $state(false);
	let form = $state(''),
		draft = $state(''),
		formInput = $state<HTMLInputElement>(null!);
	let paperOpen = $state(false),
		paperAnchor = $state<HTMLButtonElement | null>(null),
		defaultOnly = $state(false);
	const notebook = $derived(
		library?.notebooks.find((n) => n.id === library?.active.notebook) || library?.notebooks[0]
	);
	const section = $derived(
		notebook?.sections.find((s) => s.id === library?.active.section) || notebook?.sections[0]
	);
	const notes = $derived(
		(section?.notes || []).filter(
			(n) =>
				Boolean(n.deleted) === trash &&
				n.title.toLocaleLowerCase().includes(search.toLocaleLowerCase())
		)
	);
	const active = $derived(section?.notes.find((n) => n.id === library?.active.note && !n.deleted));
	let adapter = $derived(service && active ? service.document(active.id) : undefined);
	async function leave(e: MouseEvent, url: string) {
		if (e.metaKey || e.ctrlKey || e.shiftKey) return;
		e.preventDefault();
		if ((await flush()) && (await saveCatalog())) window.location.assign(url);
	}
	async function load() {
		loading = true;
		error = '';
		try {
			service = await openLibrary();
			library = service.data;
            const requested = new URL(window.location.href).searchParams.get('note');
            if(requested){
                for(const book of library.notebooks){
                    for(const group of book.sections){
                        if(group.notes.some(note=>note.id===requested&&!note.deleted)){
                            library.active={notebook:book.id,section:group.id,note:requested};
                            break;
                        }
                    }
                }
            }
		} catch (e) {
			error = e instanceof Error ? e.message : '노트 목록을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}
	onMount(load);
	async function saveCatalog() {
		if (!library) return false;
		try {
			await service.save($state.snapshot(library));
			notice = '';
			return true;
		} catch (e) {
			notice = e instanceof Error ? e.message : '목록 저장 실패 · 다시 시도해 주세요';
			return false;
		}
	}
	async function flush() {
		return !workspace || !!(await workspace.flush());
	}
	async function pick(note: NoteEntry) {
		if (busy || !(await flush())) return;
		library!.active.note = note.id;
		navigation = false;
		trash = false;
		void saveCatalog();
	}
	async function chooseSection(id: string) {
		if (busy || !(await flush())) return;
		library!.active.section = id;
		const next = notebook?.sections.find((s) => s.id === id);
		library!.active.note = next?.notes.find((n) => !n.deleted)?.id || '';
		search = '';
		trash = false;
		void saveCatalog();
	}
	async function chooseBook(id: string) {
		if (busy || !(await flush())) return;
		const book = library!.notebooks.find((n) => n.id === id)!;
		library!.active = {
			notebook: id,
			section: book.sections[0]?.id || '',
			note: book.sections[0]?.notes.find((n) => !n.deleted)?.id || ''
		};
		search = '';
		trash = false;
		void saveCatalog();
	}
	async function startForm(kind: string) {
		form = kind;
		draft =
			kind === 'renameBook'
				? notebook?.title || ''
				: kind === 'renameSection'
					? section?.title || ''
					: '';
		await tick();
		formInput?.focus();
		formInput?.select();
	}
	async function submitForm() {
		if (!draft.trim() || !library || !(await flush())) return;
		const title = draft.trim().slice(0, 120);
		if (form === 'book') {
			const id = crypto.randomUUID(),
				sid = crypto.randomUUID();
			library.notebooks.push({ id, title, sections: [{ id: sid, title: '빠른 메모', notes: [] }] });
			library.active = { notebook: id, section: sid, note: '' };
		} else if (form === 'section') {
			const id = crypto.randomUUID();
			notebook!.sections.push({ id, title, notes: [] });
			library.active.section = id;
			library.active.note = '';
		} else if (form === 'renameBook') notebook!.title = title;
		else if (form === 'renameSection') section!.title = title;
		form = '';
		await saveCatalog();
	}
	async function addPage(paper = library!.defaults, remember = false) {
		if (busy || !library || !section || !(await flush())) return;
		busy = true;
		if (remember) {
			library.defaults = paper;
			savePaperDefault(paper);
		}
		const entry = {
			id: crypto.randomUUID(),
			title: '제목 없는 페이지',
			paper: { ...paper },
			updatedAt: Date.now()
		};
		section.notes.push(entry);
		library.active.note = entry.id;
		trash = false;
		search = '';
		paperOpen = false;
		await saveCatalog();
		navigation = false;
		busy = false;
	}
	async function applyPaper(paper: PaperTemplate, remember: boolean) {
		if (defaultOnly) {
			library!.defaults = paper;
			savePaperDefault(paper);
			paperOpen = false;
			await saveCatalog();
		} else await addPage(paper, remember);
	}
	function titleHandler(id: string) {
		return (title: string) => {
			const entry = library?.notebooks
				.flatMap((b) => b.sections.flatMap((s) => s.notes))
				.find((n) => n.id === id);
			if (entry && entry.title !== title) {
				entry.title = title;
				entry.updatedAt = Date.now();
				void saveCatalog();
			}
		};
	}

	async function removePage(note: NoteEntry) {
		if (!(await flush())) return;
		note.deleted = true;
		if (library!.active.note === note.id)
			library!.active.note = section!.notes.find((n) => !n.deleted)?.id || '';
		await saveCatalog();
	}
	async function copyLocalToAccount() {
		if (busy || !library || !(await flush())) return;
		busy = true;
		notice = '선택한 기기 노트를 NETAQ 계정으로 복사하는 중…';
		try {
			const updated = $state.snapshot(library);
			await service.copyLocalToAccount(updated);
			library = updated;
			importDone = true;
			notice = '';
		} catch (e) {
			notice = e instanceof Error ? e.message : '복사 실패 · 기기 원본은 보존했습니다';
		} finally {
			busy = false;
		}
	}
	async function restorePage(note: NoteEntry) {
		note.deleted = false;
		await saveCatalog();
	}
</script>

<svelte:head
	><title>NETAQ Notes</title><meta
		name="description"
		content="노트북, 섹션, 페이지로 정리하는 나의 필기 공간"
	/></svelte:head
>
{#if loading}<div class="library-loading" role="status">
		노트를 불러오는 중…
	</div>{:else if error}<div class="library-loading">
		<p role="alert">{error}</p>
		<button onclick={load}>다시 연결</button><a href="/personal-project/calendar">NETAQ 홈</a>
	</div>{:else if library}
	<div class="note-library" class:nav-open={navigation} data-notes-library="1">
		<button class="library-shade" aria-label="노트 탐색 닫기" onclick={() => (navigation = false)}
		></button>
		<aside class="notebook-navigation" aria-label="노트북과 섹션">
			<a
				class="notes-brand"
				href="/personal-project/notes"
				onclick={(e) => leave(e, '/personal-project/notes')}><i></i>NETAQ <span>Notes</span></a
			>
			<label class="book-select"
				><span>노트북</span><select
					aria-label="노트북 선택"
					value={notebook?.id}
					onchange={(e) => chooseBook(e.currentTarget.value)}
					>{#each library.notebooks as book (book.id)}<option value={book.id}>{book.title}</option
						>{/each}</select
				></label
			>
			<div class="section-heading">
				<span>섹션</span><button
					aria-label="노트북 이름 바꾸기"
					title="노트북 이름 바꾸기"
					onclick={() => startForm('renameBook')}>{@html icon('pen')}</button
				>
			</div>
			<nav>
				{#each notebook?.sections || [] as item (item.id)}<button
						class:current={section?.id === item.id}
						onclick={() => chooseSection(item.id)}
						><span class="section-mark"></span><span>{item.title}</span></button
					>{/each}
			</nav>
			<button class="add-section" onclick={() => startForm('section')}>＋ 섹션 만들기</button
			><button class="add-notebook" onclick={() => startForm('book')}>＋ 노트북 만들기</button>
			{#if form}<form
					class="library-name-form"
					onsubmit={(e) => {
						e.preventDefault();
						submitForm();
					}}
				>
					<label
						>{form === 'book' ? '새 노트북' : form === 'section' ? '새 섹션' : '이름 바꾸기'}<input
							bind:this={formInput}
							aria-label="이름"
							bind:value={draft}
							maxlength="120"
							required
						/></label
					>
					<div>
						<button type="submit">{form.startsWith('rename') ? '변경' : '만들기'}</button><button
							type="button"
							onclick={() => (form = '')}>취소</button
						>
					</div>
				</form>{/if}
			<div class="library-bottom">
				{#if service.importSummary && !importDone}<div class="local-copy">
						<small>이 기기 노트: {service.importSummary.title}</small><button
							disabled={busy}
							onclick={copyLocalToAccount}>NETAQ 계정으로 복사</button
						>
					</div>{/if}
				<button
					onclick={(e) => {
						paperAnchor = e.currentTarget;
						defaultOnly = true;
						paperOpen = true;
					}}>페이지 기본값</button
				><button class:current={trash} onclick={() => (trash = !trash)}>휴지통</button><a
					href="/personal-project/calendar"
					onclick={(e) => leave(e, '/personal-project/calendar')}>NETAQ 홈으로</a
				><small
					>{service.remote ? 'NETAQ 계정에 저장' : '이 브라우저에 저장'}{#if !service.remote}<a
							href="/personal-project/notes">로그인하여 기기 간 동기화</a
						>{/if}</small
				>
			</div>
		</aside>
		<aside class="note-page-navigation" aria-label="섹션 페이지">
			<div class="note-section-title">
				<strong>{trash ? '휴지통' : section?.title}</strong><button
					aria-label="섹션 이름 바꾸기"
					onclick={() => startForm('renameSection')}>{@html icon('pen')}</button
				>
			</div>
			<input
				class="note-search"
				aria-label="페이지 검색"
				placeholder="페이지 검색"
				bind:value={search}
			/>
			<div class="library-add-page">
				<button disabled={busy} onclick={() => addPage()}>＋ 페이지 추가</button><button
					bind:this={paperAnchor}
					aria-label="새 페이지 용지 선택"
					onclick={(e) => {
						paperAnchor = e.currentTarget;
						defaultOnly = false;
						paperOpen = !paperOpen;
					}}>▾</button
				>
			</div>
			<div class="library-page-list">
				{#each notes as note (note.id)}<div
						class="library-page-entry"
						class:current={active?.id === note.id && !trash}
					>
						<button class="page-name" onclick={() => (trash ? restorePage(note) : pick(note))}
							><span>{note.title}</span><small
								>{trash
									? '클릭하여 복원'
									: new Date(note.updatedAt).toLocaleDateString('ko-KR', {
											month: 'short',
											day: 'numeric'
										})}</small
							></button
						>{#if !trash}<button
								class="delete-page"
								aria-label={note.title + ' 페이지 삭제'}
								title="휴지통으로 이동"
								onclick={() => removePage(note)}>{@html icon('trash')}</button
							>{/if}
					</div>{:else}<p class="empty-pages">
						{search
							? '검색한 페이지가 없습니다'
							: trash
								? '휴지통이 비어 있습니다'
								: '첫 페이지를 추가해 보세요'}
					</p>{/each}
			</div>
			<button class="close-library-mobile" onclick={() => (navigation = false)}
				>필기로 돌아가기</button
			>
		</aside>
		<main class="library-workspace-host">
			{#if active && adapter}{#key active.id}<NotebookWorkspace
						bind:this={workspace}
						documentStorage={adapter}
						remoteStorage={service.remote}
						name={active.title}
						initialPaper={active.paper}
						defaultPaper={library.defaults}
						onpaperdefaultchange={(p) => {
							library!.defaults = p;
							void saveCatalog();
						}}
						libraryMode
						onhome={() => (navigation = !navigation)}
						ontitlechange={titleHandler(active.id)}
					/>{/key}{:else}<div class="library-empty">
					<button class="library-mobile-menu" onclick={() => (navigation = true)}
						>☰ 노트 목록</button
					>
					<h1>{section?.title}</h1>
					<p>필기를 시작할 페이지를 추가하세요.</p>
					<button onclick={() => addPage()}>＋ 페이지 추가</button>
				</div>{/if}
		</main>
		{#if notice}<div class="library-notice" role="alert">
				{notice}<button onclick={saveCatalog}>저장 다시 시도</button>
			</div>{/if}
		<AnchoredPopover
			anchor={paperAnchor}
			open={paperOpen}
			onclose={() => (paperOpen = false)}
			width={310}
			><PaperOptions
				initial={library.defaults}
				label={defaultOnly ? '기본값 저장' : '페이지 추가'}
				onapply={applyPaper}
			/></AnchoredPopover
		>
	</div>{/if}
