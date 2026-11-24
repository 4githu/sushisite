<script lang="ts">
	import { resolve } from '$app/paths';
	import { onDestroy, untrack } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import {
		extractPdfSegments,
		translateSegments,
		type ReaderSegment
	} from '$lib/personal-project/reader/reader';

	import { PersonalApiError } from '$lib/personal-project/shared/api';
	import { privateCacheUser } from '$lib/personal-project/shared/auth';
	import PersonalTextEditor from '$lib/personal-project/editor/PersonalTextEditor.svelte';
	import ReaderPdf from '$lib/personal-project/reader/ReaderPdf.svelte';
	import { createDocument, createTextBlock } from '$lib/textediter/model';
	import type { ReaderAnnotation } from '$lib/personal-project/reader/annotations';
	import type { EditorDocument } from '$lib/textediter/types';
	import example from '$lib/personal-project/reader/example-park-2024.json';
	let segments = $state<ReaderSegment[]>([]);
	let translations = $state<Record<string, string>>({});
	let fileName = $state('');
	let progress = $state(0);
	let totalPages = $state(0);
	let busy = $state(false);
	let translating = $state(false);
	let consent = $state(false);
	let translationPath = $state<'shared' | 'local'>('shared');
	let error = $state('');
	let notice = $state('');
	let view = $state<'parallel' | 'stacked' | 'source'>('parallel');
	let translationProgress = $state(0);
	let failedSegment = $state('');
	let notes = $state<Record<string, string>>({});
	let annotations = $state<ReaderAnnotation[]>([]);
	let fileInput: HTMLInputElement;
	let openNotes = $state<Record<string, boolean>>({});
	let showNotes = $state(true);
	let selectedSegment = $state('');
	let pageNumbers = $derived([
		...new Set(
			segments.map((segment) => Number(segment.id.match(/^p(\d+)/)?.[1])).filter(Number.isFinite)
		)
	]);
	let documentKey = '';
	let translationKey = '';
	let saveStatus = $state('');
	let richNote = $state<EditorDocument>(createDocument());
	let initialEditor = $state<EditorDocument>(createDocument());
	let storageReadable = true;
	let editorKey = $state(0);
	let storedSnapshot: string | null = null;
	let conflict = $state(false);
	let translationController: AbortController | null = null;
	let exampleController: AbortController | null = null;
	beforeNavigate((navigation) => {
		if (
			saveStatus.startsWith('저장 안 됨') &&
			!navigation.willUnload &&
			!confirm('저장되지 않은 메모가 사라집니다. JSON으로 내보낼 수 있습니다. 이동하시겠습니까?')
		) {
			navigation.cancel();
			return;
		}
		translationController?.abort();
		exampleController?.abort();
		operationId += 1;
	});
	async function saveNotes() {
		if (!documentKey || !storageReadable) return;
		const key = documentKey;
		saveStatus = '저장 안 됨 · 저장 중';
		if (!navigator.locks) {
			saveStatus =
				'저장 안 됨 · 이 브라우저는 안전한 동시 저장을 지원하지 않습니다. JSON으로 내보내 주세요';
			return;
		}
		await navigator.locks
			.request(`paiper-reader:${key}`, () => {
				if (documentKey !== key) return;
				try {
					if (localStorage.getItem(documentKey) !== storedSnapshot) {
						conflict = true;
						saveStatus =
							'저장 안 됨 · 다른 탭에서 변경됨. 현재 메모를 JSON으로 내보내거나 저장본을 복구하세요';
						return;
					}
					const next = JSON.stringify({ notes, richNote, annotations });
					localStorage.setItem(documentKey, next);
					storedSnapshot = next;
					saveStatus = '이 기기에 저장됨';
				} catch {
					saveStatus = '저장 안 됨 · JSON으로 내보내 주세요';
				}
			})
			.catch(() => {
				if (documentKey === key) saveStatus = '저장 안 됨 · JSON으로 내보내 주세요';
			});
	}
	function updateNote(id: string, value: string) {
		notes = { ...notes, [id]: value };
		saveNotes();
	}
	function updateRichNote(value: EditorDocument) {
		untrack(() => {
			richNote = value;
			saveNotes();
		});
	}
	let operationId = 0;
	let pdfUrl = $state('');
	let showPdf = $state(false);
	let isExample = $state(false);
	onDestroy(() => {
		translationController?.abort();
		exampleController?.abort();
		operationId += 1;
		if (pdfUrl) URL.revokeObjectURL(pdfUrl);
	});

	async function chooseFile(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		input.value = '';
		await openFile(file);
	}
	async function openExample() {
		if (busy) return;
		const operation = ++operationId;
		const controller = new AbortController();
		exampleController = controller;
		busy = true;
		try {
			const response = await fetch('/personal-project/reader/example-park-2024.pdf', { signal: controller.signal });
			if (!response.ok) throw new Error('예시 PDF를 불러오지 못했습니다.');
			const blob = await response.blob();
			if (operation !== operationId || controller.signal.aborted) return;
			await openFile(new File([blob], 'Park-2024.pdf', { type: 'application/pdf' }), true);
		} catch (cause) {
			if (operation !== operationId || controller.signal.aborted) return;
			error = cause instanceof Error ? cause.message : '예시 논문을 열지 못했습니다.';
		} finally {
			if (exampleController === controller) exampleController = null;
			if (operation === operationId) busy = false;
		}
	}
	async function openFile(file: File, exampleRequested = false) {
		if (
			saveStatus.startsWith('저장 안 됨') &&
			!confirm('저장하지 못한 메모가 사라집니다. 다른 PDF를 여시겠습니까?')
		) {
			return;
		}
		translationController?.abort();
		exampleController?.abort();
		documentKey = '';
		translationKey = '';
		storedSnapshot = null;
		conflict = false;
		storageReadable = true;
		saveStatus = '';
		richNote = createDocument();
		notes = {};
		annotations = [];
		openNotes = {};
		const operation = ++operationId;
		if (pdfUrl) URL.revokeObjectURL(pdfUrl);
		pdfUrl = '';
		showPdf = false;
		segments = [];
		isExample = false;
		translations = {};
		failedSegment = '';
		fileName = '';
		consent = false;
		translating = false;
		error = '';
		notice = '';
		progress = 0;
		totalPages = 0;
		busy = false;
		if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
			error = 'PDF 파일을 선택해주세요. / Please choose a PDF file.';
			return;
		}
		busy = true;
		fileName = file.name;
		pdfUrl = URL.createObjectURL(file);
		try {
			const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
			const user = privateCacheUser();
			const userDigest = user
				? await crypto.subtle.digest('SHA-256', new TextEncoder().encode(user))
				: null;
			if (operation !== operationId) return;
			documentKey = userDigest
				? 'paiper.reader.notes.v2.' +
					Array.from(new Uint8Array(userDigest), (b) => b.toString(16).padStart(2, '0')).join('') +
					'.' +
					Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('')
				: '';
			try {
				if (!documentKey) throw new Error('No verified user');
				const stored = localStorage.getItem(documentKey);
				storedSnapshot = stored;
				if (stored) {
					const restored = JSON.parse(stored);
					if (restored.notes && typeof restored.notes === 'object') notes = restored.notes;
					if (restored.richNote?.version === 1) richNote = restored.richNote;
					if (Array.isArray(restored.annotations)) annotations = restored.annotations;
					saveStatus = '이 기기에 저장된 메모 복구됨';
				} else saveStatus = '메모를 작성하면 이 기기에 저장됩니다';
			} catch {
				storageReadable = false;
				saveStatus = '저장 안 됨 · 저장된 메모를 읽지 못했습니다';
			}
			initialEditor = richNote;
			editorKey += 1;
			const extracted = await extractPdfSegments(file, (current, total) => {
				if (operation !== operationId) return;
				progress = current;
				totalPages = total;
			});
			if (operation !== operationId) return;
			segments = extracted;
			if (exampleRequested) {
				if (JSON.stringify(extracted) !== JSON.stringify(example.segments)) {
					throw new Error('예시 논문 원문이 저장된 번역과 일치하지 않습니다.');
				}
				segments = extracted.map((segment) => {
					if (segment.id === 'p9-s3') return { ...segment, text: segment.text.replace(' qRT-PCR analysis confirmed that ROS scav -', '') };
					if (segment.id === 'p9-s4') return { ...segment, text: segment.text.replace(/^enging by NAC/, 'qRT-PCR analysis confirmed that ROS scavenging by NAC') };
					return segment;
				});
				translations = {
					...example.translations,
					'p9-s3': example.translations['p9-s3'].replace(' qRT-PCR 분석을 통해 ROS 제거제가', ''),
					'p9-s4': example.translations['p9-s4'].replace('NAC에 의한 enging은 3R4F로 처리한 hMSC에서 NLRP3 인플라마좀 관련 유전자의 발현을 감소시켰다', 'qRT-PCR 분석을 통해 NAC에 의한 ROS 제거가 3R4F로 처리한 hMSC에서 NLRP3 인플라마좀 관련 유전자의 발현을 감소시켰음이 확인되었다')
				};
				isExample = true;
			}
			if (documentKey && segments.length) {
				translationKey = documentKey.replace('paiper.reader.notes.v2.', 'paiper.reader.translations.v1.');
				try {
					const saved = JSON.parse(localStorage.getItem(translationKey) || 'null');
					if (saved?.segments && JSON.stringify(saved.segments) === JSON.stringify(segments)) {
						translations = saved.translations || {};
						const firstMissing = segments.findIndex((segment) => !translations[segment.id]?.trim());
						translationProgress = firstMissing < 0 ? segments.length : firstMissing;
						failedSegment = firstMissing < 0 ? '' : segments[firstMissing].id;
					}
				} catch {
					translationKey = '';
				}
			}
			if (!segments.length) {
				error =
					'선택한 PDF에서 텍스트를 찾지 못했습니다. 스캔 이미지 PDF는 지원되지 않을 수 있습니다. / No selectable text was found. Scanned PDFs may not be supported.';
			} else {
				notice = `${segments.length}개 구간을 기기에서 추출했습니다. 원본 PDF는 전송되지 않았습니다. / ${segments.length} segments extracted in your browser. The PDF itself was not uploaded.`;
			}
		} catch (cause) {
			if (operation !== operationId) return;
			segments = [];
			fileName = '';
			error =
				cause instanceof Error ? cause.message : 'PDF를 읽지 못했습니다. / Could not read the PDF.';
		} finally {
			if (operation === operationId) busy = false;
		}
	}

	function warnAboutNotes(event: BeforeUnloadEvent) {
		if (saveStatus.startsWith('저장 안 됨')) {
			event.preventDefault();
		}
	}

	function restoreStoredNotes() {
		if (
			!confirm(
				'현재 저장되지 않은 메모가 사라집니다. 필요하면 먼저 JSON으로 내보내세요. 저장본을 복구하시겠습니까?'
			)
		)
			return;
		try {
			const stored = localStorage.getItem(documentKey);
			const restored = stored ? JSON.parse(stored) : {};
			notes = restored.notes && typeof restored.notes === 'object' ? restored.notes : {};
			richNote = restored.richNote?.version === 1 ? restored.richNote : createDocument();
			annotations = Array.isArray(restored.annotations) ? restored.annotations : [];
			storedSnapshot = stored;
			initialEditor = richNote;
			editorKey += 1;
			conflict = false;
			storageReadable = true;
			saveStatus = '이 기기에 저장된 메모 복구됨';
		} catch {
			saveStatus = '저장 안 됨 · 저장된 메모를 읽지 못했습니다';
		}
	}

	function downloadNotes() {
		const entries = segments
			.filter((segment) => notes[segment.id]?.trim())
			.map((segment) => ({ id: segment.id, source: segment.text, note: notes[segment.id] }));
		const url = URL.createObjectURL(
			new Blob(
				[
					JSON.stringify(
						{ document: fileName, notes: entries, editor: richNote, annotations },
						null,
						2
					)
				],
				{
					type: 'application/json'
				}
			)
		);
		const link = document.createElement('a');
		link.href = url;
		link.download = `${fileName.replace(/\.pdf$/i, '')}-notes.json`;
		link.click();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}

	async function startTranslation(resume = false) {
		if (!consent || translating || !segments.length) return;
		const startIndex = resume ? Math.max(0, segments.findIndex((item) => item.id === failedSegment)) : 0;
		const previous = startIndex > 0 ? translations[segments[startIndex - 1].id] ?? '' : '';
		if (!resume) translations = {};
		failedSegment = '';
		const operation = ++operationId;
		const controller = new AbortController();
		translationController = controller;
		translating = true;
		translationProgress = startIndex;
		error = '';
		notice = '';
		let storageFailed = false;
		try {
			const result = await translateSegments(
				segments,
				(completed) => {
					if (operation === operationId) translationProgress = completed;
				},
				translationPath,
				controller.signal,
				(items) => {
					if (operation === operationId) {
						translations = { ...translations, ...Object.fromEntries(items.map(({ id, text }) => [id, text])) };
						if (translationKey) {
							try {
								localStorage.setItem(translationKey, JSON.stringify({ segments, translations }));
							} catch {
								storageFailed = true;
								notice = '번역을 이 기기에 저장하지 못했습니다. 페이지를 닫기 전에 확인해 주세요.';
							}
						}
					}
				},
				startIndex,
				previous
			);
			if (operation !== operationId) return;
			translations = { ...translations, ...Object.fromEntries(result.map(({ id, text }) => [id, text])) };
			if (!storageFailed) notice = '번역을 받았습니다. / Translation received.';
		} catch (cause) {
			if (operation !== operationId) return;
			failedSegment = segments[translationProgress]?.id ?? '';
			error =
				cause instanceof PersonalApiError &&
				cause.status === 503 &&
				cause.code === 'translation_provider_unavailable'
					? '번역 연결이 필요합니다. 현재 이 계정에서 번역 서비스를 사용할 수 없습니다. / Translation is not connected for this account.'
					: cause instanceof Error
						? cause.message
						: '번역 요청에 실패했습니다. / Translation request failed.';
		} finally {
			if (operation === operationId) translating = false;
		}
	}
</script>

<svelte:head>
	<title>Paiper Reader · 논문 읽기</title>
	<meta
		name="description"
		content="브라우저에서 PDF 텍스트를 읽고, 원하는 경우 한국어 번역을 요청하는 이중언어 논문 리더."
	/>
</svelte:head>

<svelte:window onbeforeunload={warnAboutNotes} />

<div class="reader-shell">
	<header class="topbar">
		<a class="wordmark" href={resolve('/personal-project/reader')} aria-label="Paiper 홈"
			><span>paiper</span></a
		>
		<button class="back-link" type="button" disabled={busy} onclick={() => fileInput?.click()}
			>PDF 열기</button
		>
		<strong class="document-title">{fileName || '논문 읽기'}</strong>
	</header>

	<main>
		<section class="workspace" aria-label="PDF reader workspace">
			<div class="toolbar">
				<div class="file-state">
					<span class="file-icon" aria-hidden="true">PDF</span>
					<div>
						<strong>{fileName || '아직 문서를 열지 않았어요'}</strong>
						<small
							>{#if busy}텍스트 추출 중 · Extracting text…{:else if fileName}브라우저에서만 처리 ·
								Processed in browser{:else}로컬 PDF를 선택해 시작하세요 · Choose a local PDF to
								begin{/if}</small
						>
					</div>
				</div>
				<label class="choose-button">
					<span>{fileName ? '다른 PDF 열기' : 'PDF 열기'} <span aria-hidden="true">↗</span></span>
					<input
						bind:this={fileInput}
						id="open-pdf"
						type="file"
						accept="application/pdf,.pdf"
						onchange={chooseFile}
						disabled={busy}
					/>
				</label>
				<button type="button" class="choose-button" disabled={busy} onclick={openExample}>예시 논문 열기</button>
			</div>
			{#if isExample}
				<p>Park 외 (2024), <a href="https://doi.org/10.1186/s13287-024-03731-2">원문 및 출처</a> · <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. 원문 추출 및 한국어 번역은 수정되었으며 전체 정확성은 검증되지 않았습니다.</p>
			{/if}

			{#if busy}
				<div class="progress-wrap" role="status" aria-live="polite">
					<div class="progress-copy">
						<span>페이지 텍스트를 읽고 있어요 · Reading pages locally</span><span
							>{progress}{totalPages ? ` / ${totalPages}` : ''}</span
						>
					</div>
					<div class="progress-track">
						<div
							class="progress-fill"
							style={`width: ${totalPages ? (progress / totalPages) * 100 : 8}%`}
						></div>
					</div>
				</div>
			{/if}

			{#if error}<div class="feedback error" role="alert">{error}</div>{/if}
			{#if notice}<div class="feedback notice" role="status">{notice}</div>{/if}

			{#if pdfUrl}
				<button
					type="button"
					class="pdf-toggle"
					aria-expanded={showPdf}
					onclick={() => (showPdf = !showPdf)}>{showPdf ? 'PDF 지면 닫기' : 'PDF 지면 보기'}</button
				>
				{#if showPdf}{#key pdfUrl}<ReaderPdf
							url={pdfUrl}
							{annotations}
							onchange={(value) => {
								annotations = value;
								saveNotes();
							}}
							onnote={(value) => {
								richNote = {
									...richNote,
									blocks: [...richNote.blocks, createTextBlock('paragraph', value)]
								};
								initialEditor = richNote;
								editorKey += 1;
								showNotes = true;
								saveNotes();
							}}
						/>{/key}{/if}
			{/if}

			{#if segments.length}
				<div class="consent-panel">
					<section class="consent-copy" aria-labelledby="transfer-disclosure-title">
						<strong id="transfer-disclosure-title">번역 전 데이터 처리 안내</strong>
						<p>번역 시 추출한 텍스트가 Sushi 서버와 번역 제공자에 전송될 수 있습니다. PDF 파일 자체는 전송하지 않습니다.</p>
						<details><summary>자세히 보기</summary><p>텍스트는 브라우저에서 추출합니다. 진행 중인 번역과 원문 텍스트는 이어 읽기를 위해 이 기기에 저장될 수 있습니다. 제공자별 보관 및 사용 조건이 적용되며, 서비스가 설정되지 않았거나 이용 권한이 없으면 번역할 수 없습니다. 선택한 그림 설명을 요청하면 해당 영역이 전송됩니다.</p></details>
					</section>
					<label class="consent-check">
						<input type="checkbox" bind:checked={consent} />
						<span>텍스트 전송에 동의합니다</span>
					</label>
					<button class="translate-button" onclick={() => startTranslation(!!failedSegment)} disabled={!consent || translating}>
						{translating ? `번역 요청 중 ${translationProgress} / ${segments.length}` : failedSegment ? '번역 이어서 받기' : '한국어 번역 시작'}
					</button>
				</div>
				<div class="reader-controls">
					<span>읽기 도구</span>
					<button
						type="button"
						aria-pressed={showNotes}
						onclick={() => {
							if (showNotes) initialEditor = richNote;
							showNotes = !showNotes;
						}}>메모 패널</button
					>
					<div role="group" aria-label="읽기 레이아웃">
						<button
							class:active={view === 'source'}
							aria-pressed={view === 'source'}
							onclick={() => (view = 'source')}>원문만</button
						>
						<button
							class:active={view === 'parallel'}
							aria-pressed={view === 'parallel'}
							onclick={() => (view = 'parallel')}>나란히</button
						>
						<button
							class:active={view === 'stacked'}
							aria-pressed={view === 'stacked'}
							onclick={() => (view = 'stacked')}>위아래</button
						>
					</div>
				</div>
				<div class="reading-workspace" class:with-notes={showNotes}>
					<nav class="page-nav" aria-label="페이지 목록">
						<strong>페이지</strong>{#each pageNumbers as number (number)}<a href={`#p${number}-s1`}
								>{number}</a
							>{/each}
					</nav>
					<div class="reading-content">
						<div
							class="column-headings"
							class:stacked={view === 'stacked' || view === 'source'}
							aria-hidden="true"
						>
							<span>원문</span>{#if view !== 'source'}<span>한국어</span>{/if}
						</div>
						<div class="segment-list" class:stacked={view === 'stacked' || view === 'source'}>

							{#each segments as segment (segment.id)}
								<article
									id={segment.id}
									class="segment-row"
									class:selected={selectedSegment === segment.id}
									class:stacked={view === 'stacked' || view === 'source'}
								>
									<div class="source-cell">
										<span class="segment-id">{segment.id.replace('-', ' · ')}</span>
										<p>{segment.text}</p>
										<button
											type="button"
											aria-label={`${segment.id} 메모`}
											aria-expanded={!!openNotes[segment.id]}
											onclick={() => {
												selectedSegment = segment.id;
												openNotes[segment.id] = !openNotes[segment.id];
											}}>{notes[segment.id] ? '메모 보기' : '새 메모'}</button
										>
										{#if openNotes[segment.id]}
											<label>
												<span>문단 메모 · 이 기기에 저장</span>
												<textarea
													aria-label={`${segment.id} 메모 내용`}
													value={notes[segment.id] || ''}
													oninput={(event) => updateNote(segment.id, event.currentTarget.value)}
												></textarea>
											</label>
										{/if}
									</div>
									{#if view !== 'source'}<div class="translation-cell">
											<span class="segment-id">{segment.id.replace('-', ' · ')} · 번역</span>
											<p>{translations[segment.id] ?? (failedSegment === segment.id ? '이 구간의 번역에 실패했습니다.' : translating ? '번역 대기 중' : '번역 전')}</p>
											{#if failedSegment === segment.id}<button type="button" disabled={translating || !consent} onclick={() => startTranslation(true)}>이 구간부터 다시 시도</button>{/if}
										</div>{/if}
								</article>
							{/each}
						</div>
					</div>
					{#if showNotes}
						<aside class="notes-panel" aria-label="메모 패널">
							<div class="notes-heading">
								<h2>메모</h2>
								<button type="button" onclick={downloadNotes}>JSON 내려받기</button>
								<span role="status">{saveStatus}</span>
								{#if conflict}<button type="button" onclick={restoreStoredNotes}
										>저장된 메모 복구</button
									>{/if}
							</div>
							{#key editorKey}<PersonalTextEditor
									initialValue={initialEditor}
									onchange={updateRichNote}
								/>{/key}
						</aside>
					{/if}
				</div>
			{/if}

			{#if !segments.length && !busy && !error}
				<div class="empty-state">
					<div class="paper-art" aria-hidden="true">
						<div></div>
						<div></div>
						<div></div>
						<i></i>
					</div>
					<strong>읽을 문서를 불러와 보세요</strong>
					<p>
						텍스트가 포함된 PDF를 선택하면 원문과 번역을 나란히 볼 수 있습니다.<br />Choose a
						text-based PDF to read source and translation side by side.
					</p>
				</div>
			{/if}
		</section>

		<footer>
			<span
				>원본 PDF는 브라우저에 남습니다. 선택한 그림 설명을 요청하면 해당 영역은 전송됩니다.</span
			>
			<span
				>The source file stays in this browser; a selected image region is sent when requested.</span
			>
		</footer>
	</main>
</div>

<style>
	:global(body) {
		background: #fff;
	}
	.reader-shell {
		background: #fff;
	}
	.topbar {
		height: 64px;
		padding: 0 24px;
		justify-content: flex-start;
		gap: 32px;
	}
	.wordmark {
		color: #315e52;
		font-size: 24px;
	}
	.back-link {
		border: 0;
		background: transparent;
		cursor: pointer;
		color: #202827;
		text-decoration: none;
		font-size: 14px;
	}
	.document-title {
		font-size: 14px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	main {
		max-width: none;
		padding: 0;
	}
	.workspace {
		max-width: none;
		border: 0;
		border-radius: 0;
		box-shadow: none;
	}
	.notes-panel {
		border-top: 1px solid #dfe5e3;
		padding: 24px;
		min-width: 0;
	}
	.notes-heading {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}
	.notes-heading h2 {
		font-size: 18px;
	}
	.notes-heading span {
		font-size: 12px;
		color: #526c63;
	}
	.pdf-toggle {
		border: 1px solid #8e9994;
		background: white;
		color: #253a34;
		border-radius: 6px;
	}
	@media (max-width: 600px) {
		.topbar {
			gap: 16px;
			padding: 0 16px;
		}
		.notes-panel {
			padding: 16px;
		}
	}

	.pdf-toggle {
		margin: 1rem;
		padding: 0.6rem 1rem;
		cursor: pointer;
	}
	:global(body) {
		margin: 0;
		background: #f4f2ed;
		color: #242a28;
		font-family: Inter, 'Noto Sans KR', sans-serif;
	}
	:global(*) {
		box-sizing: border-box;
	}
	.reader-shell {
		min-height: 100vh;
		background: radial-gradient(ellipse at 50% 0%, #fbfaf7 0, #f4f2ed 58%);
	}
	.topbar {
		height: 72px;
		padding: 0 clamp(22px, 6vw, 96px);
		display: flex;
		align-items: center;
		justify-content: space-between;
		border-bottom: 1px solid #e7e5df;
	}
	.wordmark {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		color: #24322e;
		text-decoration: none;
		font-size: 16px;
		font-weight: 750;
		letter-spacing: -0.05em;
	}

	main {
		max-width: 1120px;
		margin: 0 auto;
		padding: 58px 28px 32px;
	}

	.workspace {
		max-width: 1000px;
		margin: 0 auto;
		overflow: hidden;
		border: 1px solid #e5e3dd;
		border-radius: 15px;
		background: #fff;
		box-shadow: 0 16px 45px #263b3210;
	}
	.toolbar {
		min-height: 82px;
		padding: 15px 21px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		border-bottom: 1px solid #eeede8;
	}
	.file-state {
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 12px;
	}
	.file-icon {
		display: grid;
		flex: 0 0 38px;
		place-items: center;
		height: 42px;
		border: 1px solid #eee5df;
		border-radius: 9px;
		background: #fbf7f3;
		color: #a76751;
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.05em;
	}
	.file-state strong {
		display: block;
		overflow: hidden;
		color: #39433e;
		font-size: 12px;
		font-weight: 650;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.file-state small {
		display: block;
		margin-top: 5px;
		color: #9a9f9b;
		font-size: 10px;
	}
	.choose-button {
		position: relative;
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		min-height: 38px;
		padding: 0 14px;
		border: 1px solid #d8e2dc;
		border-radius: 8px;
		color: #315e52;
		background: #f8fbf8;
		cursor: pointer;
		font-size: 11px;
		font-weight: 700;
	}
	.choose-button:hover {
		background: #edf5ef;
	}
	.choose-button input {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		opacity: 0;
		cursor: pointer;
	}
	.choose-button:focus-within {
		outline: 3px solid #9bc5aa;
		outline-offset: 2px;
	}
	.progress-wrap {
		padding: 14px 22px 16px;
		border-bottom: 1px solid #eeede8;
	}
	.progress-copy {
		display: flex;
		justify-content: space-between;
		color: #68736d;
		font-size: 10px;
	}
	.progress-track {
		height: 4px;
		margin-top: 9px;
		overflow: hidden;
		border-radius: 4px;
		background: #e8eee9;
	}
	.progress-fill {
		height: 100%;
		border-radius: inherit;
		background: #54806f;
		transition: width 0.2s ease;
	}
	.reader-controls {
		min-height: 48px;
		padding: 7px 17px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		border-bottom: 1px solid #e9e8e2;
		background: #fff;
		color: #89928c;
		font-size: 9px;
		font-weight: 700;
		letter-spacing: 0.08em;
	}
	.reader-controls [role='group'] {
		padding: 2px;
		display: flex;
		gap: 2px;
		border: 1px solid #e6e8e2;
		border-radius: 7px;
		background: #f6f7f4;
	}
	.reader-controls button {
		min-height: 27px;
		padding: 0 10px;
		border: 0;
		border-radius: 5px;
		background: transparent;
		color: #858d87;
		font: inherit;
		letter-spacing: 0;
		cursor: pointer;
	}
	.reader-controls button.active {
		background: #fff;
		color: #315e52;
		box-shadow: 0 1px 3px #263b3214;
	}
	.feedback {
		margin: 16px 20px;
		padding: 12px 14px;
		border-radius: 8px;
		font-size: 12px;
		line-height: 1.7;
	}
	.error {
		color: #8b453c;
		background: #fff3ef;
		border: 1px solid #f0d5cb;
	}
	.notice {
		color: #426b58;
		background: #f1f7f2;
		border: 1px solid #dceadd;
	}
	.column-headings {
		display: grid;
		grid-template-columns: 1fr 1fr;
		background: #fafaf8;
		border-bottom: 1px solid #e9e8e2;
	}
	.column-headings span {
		padding: 12px 22px;
		color: #89928c;
		font-size: 9px;
		font-weight: 750;
		letter-spacing: 0.12em;
	}
	.column-headings span + span {
		border-left: 1px solid #e9e8e2;
	}
	.column-headings.stacked {
		grid-template-columns: 1fr;
	}
	.column-headings.stacked span + span {
		display: none;
	}
	.segment-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		border-bottom: 1px solid #edede8;
	}
	.segment-row.stacked {
		grid-template-columns: 1fr;
	}
	.segment-row:last-child {
		border-bottom: 0;
	}
	.source-cell,
	.translation-cell {
		min-width: 0;
		padding: 19px 22px 21px;
	}
	.translation-cell {
		border-left: 1px solid #edede8;
		background: #fdfdfb;
	}
	.segment-row.stacked .translation-cell {
		border-top: 1px dashed #e2e6e0;
		border-left: 0;
		background: #fafbf9;
	}
	.segment-id {
		color: #9aa29c;
		font-size: 9px;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	.source-cell p,
	.translation-cell p {
		margin: 9px 0 0;
		color: #38423d;
		font-family: Georgia, 'Noto Serif KR', serif;
		font-size: 14px;
		line-height: 1.85;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}
	.translation-cell p {
		color: #63736a;
	}
	.consent-panel {
		padding: 20px 22px;
		border-top: 1px solid #e9e8e2;
		background: #fafbf9;
	}
	.consent-copy strong {
		color: #38443e;
		font-size: 12px;
	}
	.consent-copy p {
		max-width: 800px;
		margin: 7px 0 3px;
		color: #65716a;
		font-size: 11px;
		line-height: 1.7;
	}
	.consent-copy small {
		display: block;
		max-width: 800px;
		color: #959d97;
		font-size: 10px;
		line-height: 1.6;
	}
	.consent-check {
		display: flex;
		align-items: flex-start;
		gap: 9px;
		margin-top: 16px;
		color: #45554b;
		cursor: pointer;
		font-size: 11px;
		line-height: 1.6;
	}
	.consent-check input {
		margin: 2px 0 0;
		accent-color: #477764;
	}
	.consent-check small {
		color: #8b948e;
		font-size: 10px;
	}
	.translate-button {
		display: flex;
		justify-content: space-between;
		align-items: center;
		width: 100%;
		min-height: 43px;
		margin-top: 15px;
		padding: 0 15px;
		border: 0;
		border-radius: 8px;
		color: #fff;
		background: #315e52;
		cursor: pointer;
		font-size: 11px;
		font-weight: 700;
	}
	.translate-button:hover:not(:disabled) {
		background: #244c42;
	}
	.translate-button:disabled {
		background: #aab9b0;
		cursor: not-allowed;
	}
	.empty-state {
		min-height: 267px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 28px 20px;
		text-align: center;
	}
	.empty-state strong {
		margin-top: 20px;
		color: #56635b;
		font-size: 13px;
	}
	.empty-state p {
		color: #919992;
		font-size: 11px;
		line-height: 1.8;
	}
	.paper-art {
		position: relative;
		width: 47px;
		height: 57px;
		padding: 14px 9px;
		display: grid;
		align-content: start;
		gap: 5px;
		border: 1px solid #dce3dc;
		border-radius: 4px;
		background: #fbfcfa;
		transform: rotate(-4deg);
		box-shadow: 6px 5px 0 #edf1ec;
	}
	.paper-art div {
		height: 2px;
		border-radius: 3px;
		background: #dce4dc;
	}
	.paper-art div:nth-child(2) {
		width: 75%;
	}
	.paper-art div:nth-child(3) {
		width: 85%;
	}
	.paper-art i {
		position: absolute;
		width: 17px;
		height: 17px;
		right: -10px;
		bottom: 7px;
		border: 2px solid #7b9d88;
		border-radius: 50%;
		background: #fff;
	}
	footer {
		display: flex;
		justify-content: center;
		gap: 9px;
		padding: 20px 0 0;
		color: #9ba19c;
		font-size: 10px;
	}
	footer span + span::before {
		content: '·';
		margin-right: 9px;
	}
	@media (max-width: 640px) {
		.topbar {
			height: 62px;
			padding: 0 20px;
		}
		main {
			padding: 39px 14px 24px;
		}

		.workspace {
			border-radius: 12px;
		}
		.toolbar {
			min-height: 74px;
			padding: 12px;
			gap: 8px;
		}
		.file-state {
			gap: 8px;
		}
		.file-icon {
			flex-basis: 33px;
			height: 37px;
			font-size: 9px;
		}
		.file-state strong {
			max-width: 42vw;
			font-size: 10px;
		}
		.file-state small {
			font-size: 9px;
		}
		.choose-button {
			min-height: 35px;
			padding: 0 9px;
			font-size: 10px;
		}
		.column-headings {
			display: none;
		}
		.segment-row {
			display: block;
		}
		.source-cell,
		.translation-cell {
			padding: 16px 15px 17px;
		}
		.translation-cell {
			border-left: 0;
			border-top: 1px dashed #e2e6e0;
			background: #fafbf9;
		}
		.source-cell p,
		.translation-cell p {
			font-size: 13px;
		}
		.consent-panel {
			padding: 17px 15px;
		}
		.empty-state {
			min-height: 235px;
		}
		footer {
			flex-direction: column;
			align-items: center;
			gap: 3px;
			font-size: 9px;
		}
		footer span + span::before {
			content: '';
			margin: 0;
		}
	}
	:global(body),
	.reader-shell {
		background: #fff;
	}
	.topbar {
		height: 64px;
		padding: 0 24px;
		justify-content: flex-start;
		gap: 32px;
	}
	.wordmark {
		color: #315e52;
		font-size: 24px;
	}
	main {
		max-width: none;
		padding: 0;
	}
	.workspace {
		max-width: none;
		border: 0;
		border-radius: 0;
		box-shadow: none;
	}
	@media (max-width: 600px) {
		.topbar {
			gap: 16px;
			padding: 0 16px;
		}
	}

	.reading-workspace {
		display: grid;
		grid-template-columns: 100px minmax(0, 1fr);
		align-items: start;
	}
	.reading-workspace.with-notes {
		grid-template-columns: 100px minmax(0, 1fr) minmax(290px, 360px);
	}
	.page-nav {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 20px 16px;
		border-right: 1px solid #e4e8e6;
		font-size: 13px;
	}
	.page-nav a {
		color: #315e52;
		padding: 8px;
		border-radius: 4px;
		text-decoration: none;
	}
	.segment-row.selected {
		background: #fff9e4;
	}
	.segment-row button,
	.segment-list > button {
		border: 1px solid #b5c5bf;
		border-radius: 6px;
		background: white;
		padding: 7px 12px;
		color: #315e52;
	}
	.reading-content {
		min-width: 0;
	}
	.notes-panel {
		border-top: 0;
		border-left: 1px solid #dfe5e3;
		min-height: 400px;
	}
	.source-cell p,
	.translation-cell p {
		font-family: Inter, 'Noto Sans KR', sans-serif;
		font-size: 16px;
		line-height: 1.7;
	}
	@media (max-width: 800px) {
		.reading-workspace {
			display: block;
		}
		.notes-panel {
			border-left: 0;
			border-top: 1px solid #dfe5e3;
		}
	}
</style>
