<script lang="ts">
	import { onMount } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import DriveNotebooks from '$lib/personal-project/notes/DriveNotebooks.svelte';
	import DriveItemOptions from '$lib/personal-project/shared/DriveItemOptions.svelte';
	import { API_BASE, request } from '$lib/personal-project/shared/api';
	import PdfEditor from '$lib/personal-project/pdf/PdfWorkspace.svelte';
	import './drive.css';

	type Bucket = 'transfer' | 'archive';
	type DriveItem = {
		id: string;
		bucket: Bucket;
		provider: 'local' | 'google';
		accountId: number | null;
		name: string;
		mimeType: string;
		byteSize: number;
		createdAt: string;
		expiresAt: string | null;
		googleEmail?: string | null;
	};
	type DriveStatus = {
		quotaBytes: number;
		usedBytes: number;
 fileBytes?:number;noteBytes?:number;noteHistoryBytes?:number;attachmentBytes?:number;
		transferDays: number;
		googleAccounts: { id: number; email: string }[];
	};

	type Folder={id:string;name:string;parent_id:string|null;created_at:string};
	let bucket = $state<Bucket>('archive');
	let folderId=$state<string|null>(null),search=$state(''),folderName=$state(''),expanded=$state(false);
	let folderDialog:HTMLDialogElement;
	let library=$state<{folders:Folder[];allFolders:Folder[];trail:Folder[];placements:Record<string,string>;shared:string[]}>({folders:[],allFolders:[],trail:[],placements:{},shared:[]});
	let refreshVersion=0;
	beforeNavigate(({cancel})=>{if((textDirty || noteText.trim()) && !confirm('저장하지 않은 내용을 두고 이동할까요?'))cancel();});
	async function openFolder(id:string|null){if(textDirty && !(await saveText()))return;folderId=id;selected=null;search='';loading=true;await refresh();}
	async function createFolder(){if(busy || !folderName.trim())return;busy=true;try{await request('/drive/folders',{method:'POST',body:{name:folderName,bucket,parent_id:folderId}});folderDialog.close();folderName='';await refresh();message='폴더를 만들었어요';}catch(e){message=errorMessage(e);}finally{busy=false;}}
	async function removeFolder(){if(!folderId || busy)return;busy=true;try{await request(`/drive/folders/${folderId}`,{method:'DELETE'});folderId=library.trail.at(-1)?.parent_id||null;await refresh();message='빈 폴더를 삭제했어요';}catch(e){message=errorMessage(e);}finally{busy=false;}}
	async function organizeUpload(item:{id:string;name?:string},name:string){if(folderId)try{await request(`/drive/items/${item.id}/organization`,{method:'PUT',body:{name:item.name||name,folder_id:folderId}});}catch{throw new Error('파일은 전체 파일에 저장했지만 폴더로 옮기지 못했어요. 전체 파일에서 확인해주세요.');}}
	let items = $state<DriveItem[]>([]);
	const visibleItems=$derived(items.filter(item=>(library.placements[item.id]||null)===folderId && item.name.toLowerCase().includes(search.toLowerCase())));

	let driveStatus = $state<DriveStatus | null>(null);
	let selected = $state<DriveItem | null>(null);
	let previewText = $state('');
	let editingText = $state('');
	let loading = $state(true);
	let busy = $state(false);
	let textSaving = $state(false);
	let textDirty = $state(false);
	let textStatus = $state('');
	let message = $state('');
	let noteText = $state('');
	let provider = $state('local');
	let dropActive = $state(false);
	let uploadProgress = $state<{ name: string; percent: number; phase: string } | null>(null);
	let fileInput: HTMLInputElement;
	let pdfEditorVersion = $state(0);
	let textSaveTimer: ReturnType<typeof setTimeout> | undefined;
	let previewRequest = 0;

	const selectedAccount = $derived(provider.startsWith('google:') ? Number(provider.slice(7)) : null);
	const usedPercent = $derived(
		driveStatus ? Math.min(100, Math.round((driveStatus.usedBytes / driveStatus.quotaBytes) * 100)) : 0
	);
	const previewKind = $derived(
		selected?.name.toLowerCase().endsWith('.pdf')
			? 'pdf'
			: /\.(png|jpe?g|webp|gif)$/i.test(selected?.name ?? '')
				? 'image'
				: /\.(md|markdown|txt|csv|json|log|docx)$/i.test(selected?.name ?? '')
					? 'text'
					: 'download'
	);
	const editableText = $derived(!!selected && /\.(md|markdown|txt|csv|json|log)$/i.test(selected.name));

	function size(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}
	function errorMessage(error: unknown): string {
		return error instanceof Error ? error.message : '요청을 처리하지 못했습니다.';
	}
	function contentUrl(item: DriveItem, inline = false): string {
		return `${API_BASE}/api/personal/drive/items/${item.id}/content${inline ? '?inline=true' : ''}`;
	}
	async function refresh(keepSelection = false) {
		try {
			const serial=++refreshVersion;
			const [nextStatus, nextItems, nextLibrary] = await Promise.all([
				request<DriveStatus>('/drive/status'),
				request<DriveItem[]>(`/drive/items?bucket=${bucket}`),
				request<typeof library>(`/drive/library?bucket=${bucket}${folderId?`&folder_id=${folderId}`:''}`)
			]);
			if(serial!==refreshVersion)return;
			library=nextLibrary;
			driveStatus = nextStatus;
			items = nextItems;
			if (keepSelection && selected) selected = nextItems.find((item) => item.id === selected?.id) ?? null;
			else selected = null;
			if (provider !== 'local' && !nextStatus.googleAccounts.some((account) => account.id === selectedAccount)) {
				provider = 'local';
			}
		} catch (error) {
			message = errorMessage(error);
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		const query = new URLSearchParams(window.location.search);
		if (query.get('google_error')) message = 'Google Drive 연결에 실패했습니다.';
		void refresh();
	});

	async function saveText(): Promise<boolean> {
		if (!selected || !editableText || !textDirty) return true;
		if (textSaving) return false;
		const item = selected;
		const value = editingText;
		if (textSaveTimer) clearTimeout(textSaveTimer);
		textSaveTimer = undefined;
		textSaving = true;
		textStatus = '저장 중';
		try {
			await request(`/drive/items/${item.id}/text`, { method: 'PUT', body: { text: value } });
			if (selected?.id === item.id && editingText === value) {
				textDirty = false;
				textStatus = '저장됨';
			}
			await refresh(true);
			return true;
		} catch (error) {
			textStatus = '저장 실패';
			message = errorMessage(error);
			return false;
		} finally {
			textSaving = false;
		}
	}
	function queueTextSave(value: string) {
		editingText = value;
		textDirty = true;
		textStatus = '저장 대기';
		if (textSaveTimer) clearTimeout(textSaveTimer);
		textSaveTimer = setTimeout(() => void saveText(), 900);
	}
	async function selectItem(item: DriveItem) {
		if (selected?.id !== item.id && textDirty && !(await saveText())) return;
		selected = item;
		previewText = '';
		editingText = '';
		textDirty = false;
		textStatus = '';
		const token = ++previewRequest;
		if (!/\.(md|markdown|txt|csv|json|log|docx)$/i.test(item.name)) return;
		try {
			const preview = await request<{ kind: string; text: string }>(`/drive/items/${item.id}/preview`);
			if (token === previewRequest) {
				previewText = preview.text;
				editingText = preview.text;
			}
		} catch (error) {
			if (token === previewRequest) message = errorMessage(error);
		}
	}
	async function changeBucket(next: Bucket) {
		if (bucket === next) return;
		if (textDirty && !(await saveText())) return;
		bucket = next;
		folderId=null;search='';
		selected = null;
		loading = true;
		await refresh();
	}
	async function uploadFiles(files: File[] | null, replacing?: DriveItem) {
		if (!files?.length || busy) return;
		busy = true;
		message = '';
		const list = files;
		try {
			for (let index = 0; index < list.length; index++) {
				const file = list[index];
				uploadProgress = { name: file.name, percent: 0, phase: '전송 중' };
				let session: { id: string; chunkBytes: number } | null = null;
				try {
					const targetBucket = replacing?.bucket ?? bucket;
					const targetProvider = replacing?.provider ?? (selectedAccount ? 'google' : 'local');
					const targetAccount = replacing ? replacing.accountId : selectedAccount;
					session = await request<{ id: string; chunkBytes: number }>('/drive/upload/sessions', {
						method: 'POST',
						body: {
							name: replacing?.name ?? file.name,
							bucket: targetBucket,
							provider: targetProvider,
							account_id: targetAccount,
							total_bytes: file.size,
							replace_item_id: replacing?.id ?? null
						}
					});
					for (let offset = 0; offset < file.size; offset += session.chunkBytes) {
						const end = Math.min(file.size, offset + session.chunkBytes);
						const response = await fetch(`${API_BASE}/api/personal/drive/upload/sessions/${session.id}/chunk?offset=${offset}`, {
							method: 'PUT', credentials: 'include', body: file.slice(offset, end),
							headers: { 'Content-Type': 'application/octet-stream' }
						});
						if (response.status === 401) {
							window.dispatchEvent(new Event('personal-auth-invalid'));
							throw new Error('로그인이 만료되었습니다. 다시 로그인해주세요.');
						}
						if (!response.ok) {
							const result = await response.json().catch(() => null);
							throw new Error(result?.detail?.message || result?.detail || `${file.name} 업로드에 실패했습니다.`);
						}
						uploadProgress = { name: file.name, percent: Math.round((end / file.size) * 100), phase: '전송 중' };
					}
					uploadProgress = { name: file.name, percent: 100, phase: '서버에 저장 중' };
					const stored=await request<{id:string;name:string}>(`/drive/upload/sessions/${session.id}/finish`, { method: 'POST' });
					if(!replacing)await organizeUpload(stored,file.name);
				} catch (error) {
					if (session) void request(`/drive/upload/sessions/${session.id}`, { method: 'DELETE' }).catch(() => {});
					throw error;
				}
			}
			await refresh(!!replacing);
			if (replacing?.name.toLowerCase().endsWith('.pdf')) pdfEditorVersion += 1;
			message = replacing ? '수정본을 저장했습니다.' : '파일을 저장했습니다.';
		} catch (error) {
			await refresh(true);
			message = errorMessage(error);
		} finally {
			busy = false;
			uploadProgress = null;
			if (fileInput) fileInput.value = '';
		}
	}
	async function createBlankPdf() {
		if (busy) return;
		try {
			const { PDFDocument } = await import('pdf-lib');
			const document = await PDFDocument.create();
			document.addPage([595, 842]);
			const bytes = await document.save();
			const blobBytes = new ArrayBuffer(bytes.byteLength);
			new Uint8Array(blobBytes).set(bytes);
			const file = new File([blobBytes], `빈 문서-${new Date().toLocaleDateString('sv-SE')}.pdf`, { type: 'application/pdf' });
			await uploadFiles([file]);
		} catch (error) {
			message = errorMessage(error);
		}
	}
	async function saveNote() {
		if (!noteText.trim() || busy) return;
		busy = true;
		message = '';
		try {
			const stored=await request<{id:string;name:string}>('/drive/notes', {
				method: 'POST',
				body: {
					text: noteText, bucket,
					provider: selectedAccount ? 'google' : 'local', account_id: selectedAccount
				}
			});
			noteText = '';
			await organizeUpload(stored,'메모.txt');
			await refresh();
		} catch (error) {
			message = errorMessage(error);
		} finally {
			busy = false;
		}
	}
	async function moveSelected() {
		if (!selected || busy) return;
		if (textDirty && !(await saveText())) return;
		busy = true;
		try {
			await request(`/drive/items/${selected.id}`, { method: 'PATCH', body: { bucket: bucket === 'transfer' ? 'archive' : 'transfer' } });
			await refresh();
		} catch (error) {
			message = errorMessage(error);
		} finally {
			busy = false;
		}
	}
	async function deleteSelected() {
		if (!selected || busy || !window.confirm(`「${selected.name}」 파일을 삭제할까요?`)) return;
		busy = true;
		try {
			await request(`/drive/items/${selected.id}`, { method: 'DELETE' });
			await refresh();
		} catch (error) {
			message = errorMessage(error);
		} finally {
			busy = false;
		}
	}
	function handleDrop(event: DragEvent) {
		event.preventDefault();
		dropActive = false;
		if (event.dataTransfer?.files.length) void uploadFiles(Array.from(event.dataTransfer.files));
	}
</script>

<svelte:head><title>내 드라이브 · NETAQ</title></svelte:head>
<svelte:window onbeforeunload={(event) => { if (textDirty || noteText.trim()) event.preventDefault(); }} />

<div class="drive-page" role="region" aria-label="내 드라이브 파일 영역" class:drop-active={dropActive}
	 ondragenter={(event) => { if (event.dataTransfer?.types.includes('Files')) dropActive = true; }}
	 ondragover={(event) => { if (event.dataTransfer?.types.includes('Files')) event.preventDefault(); }}
	 ondragleave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) dropActive = false; }}
	 ondrop={handleDrop}>
	<header class="drive-header">
		<div><h1>내 드라이브</h1></div>
		<div class="drive-header-actions">
			<input bind:this={fileInput} type="file" multiple hidden onchange={(event) => void uploadFiles(Array.from(event.currentTarget.files ?? []))} />
			<button class="drive-button" type="button" disabled={busy} onclick={() => void createBlankPdf()}>빈 PDF</button>
			<button class="drive-button" type="button" disabled={busy} onclick={() => fileInput?.click()}>＋ 파일</button>
		</div>
	</header>

	<section class="drive-storage" aria-label="저장 공간">
		<div class="drive-storage-main">
			<div class="drive-storage-line"><strong>개인 저장 공간</strong><span>{size(driveStatus?.usedBytes ?? 0)} / {size(driveStatus?.quotaBytes ?? 500 * 1024 * 1024)}</span></div>
			<div class="drive-meter"><span style={`width: ${usedPercent}%`}></span></div>
 <div class="drive-storage-breakdown">파일 {size(driveStatus?.fileBytes??driveStatus?.usedBytes??0)} · 노트·저장기록 {size(driveStatus?.noteBytes??0)} · 첨부 {size(driveStatus?.attachmentBytes??0)}</div>
		</div>
		<div class="drive-storage-side">
			<label class="drive-destination">
				<select bind:value={provider} aria-label="저장 위치">
					<option value="local">기본 저장소 · 500MB</option>
					{#each driveStatus?.googleAccounts ?? [] as account}<option value={`google:${account.id}`}>Google · {account.email}</option>{/each}
				</select>
			</label>
			<a href="/auth/google/start?purpose=drive&return_to=%2Fpersonal-project%2Fcalendar%2Fdrive">{driveStatus?.googleAccounts.length ? '계정 추가' : 'Google Drive 연결'}</a>
		</div>
	</section>

	<div class="drive-toolbar">
		<div class="drive-tabs" role="tablist" aria-label="드라이브 위치">
			<button type="button" role="tab" aria-selected={bucket === 'transfer'} class:active={bucket === 'transfer'} onclick={() => void changeBucket('transfer')}>전송함 · 15일</button>
			<button type="button" role="tab" aria-selected={bucket === 'archive'} class:active={bucket === 'archive'} onclick={() => void changeBucket('archive')}>보관함</button>
		</div>
	</div>
	<div class="drive-folder-tools"><button class="drive-button" onclick={()=>{folderName='';message='';folderDialog.showModal();}}>＋ 새 폴더</button><input aria-label="파일·폴더 검색" placeholder="파일·폴더 검색" bind:value={search} /></div>
	<nav class="drive-breadcrumb" aria-label="폴더 경로"><button onclick={()=>openFolder(null)}>전체 파일</button>{#each library.trail as entry}<span>›</span><button aria-current={entry.id===folderId?'page':undefined} onclick={()=>openFolder(entry.id)}>{entry.name}</button>{/each}{#if folderId}<button class="folder-delete" onclick={removeFolder} disabled={busy}>빈 폴더 삭제</button>{/if}</nav>
	{#if uploadProgress}<div class="drive-upload-progress" role="status" aria-live="polite">
		<div><strong>{uploadProgress.name}</strong><span>{uploadProgress.phase} · {uploadProgress.percent}%</span></div>
		<progress max="100" value={uploadProgress.percent}></progress>
	</div>{/if}
	<p class="drive-message" role="status">{message}</p>

	<div class="drive-workspace" class:has-selection={selected !== null} class:expanded>
		<section class="drive-list" aria-label={bucket === 'transfer' ? '전송함 파일' : '보관함 파일'}>
			{#if loading}<div class="drive-empty">불러오는 중</div>
			{:else}
			<div class="drive-column-head"><span>이름</span><span>공유 상태</span><span>날짜</span><span>크기</span></div>
			{#if bucket==='archive' && !folderId}<DriveNotebooks {search}/>{/if}
			{#each library.folders.filter(f=>f.name.toLowerCase().includes(search.toLowerCase())) as folder}<button class="drive-row folder-row" onclick={()=>openFolder(folder.id)}><span class="drive-file-name"><img src="/netaq-design/fa24f.svg" alt="" /><strong>{folder.name}</strong></span><span class="file-sharing">나만 보기</span><span class="file-date">{new Date(folder.created_at).toLocaleDateString('ko-KR')}</span><span class="file-size">폴더</span></button>{/each}
			{#if visibleItems.length===0 && library.folders.filter(f=>f.name.toLowerCase().includes(search.toLowerCase())).length===0}<div class="drive-empty">{search?'검색 결과가 없어요.':'이 폴더에 파일을 올려보세요.'}</div>{/if}
				{#each visibleItems as item (item.id)}
				<button class="drive-row" class:selected={selected?.id === item.id} type="button" onclick={() => void selectItem(item)}>
						<span class="drive-file-name"><img src="/netaq-design/bff7c.svg" alt="" /><span class="drive-file-text"><strong>{item.name}</strong><small>{size(item.byteSize)} · {new Date(item.expiresAt ?? item.createdAt).toLocaleDateString('ko-KR')}{item.provider === 'google' ? ' · Google' : ''}</small></span></span>
						<span class="file-sharing">{library.shared.includes(item.id)?'링크로 보기':'나만 보기'}</span><span class="file-date">{new Date(item.createdAt).toLocaleDateString('ko-KR')}</span><span class="file-size">{size(item.byteSize)}</span>
					</button>
				{/each}
			{/if}
		</section>

		{#if selected}
			<aside class="drive-preview" aria-label="파일 미리보기">
				<div class="drive-preview-top"><div><strong>{selected.name}</strong><span>{size(selected.byteSize)}</span></div><button class="drive-expand" onclick={()=>expanded=!expanded}>{expanded?'목록과 함께':'크게 보기'}</button><a class="drive-download" href={contentUrl(selected)} download={selected.name}>다운로드</a><button type="button" aria-label="미리보기 닫기" onclick={async () => { if (textDirty && !(await saveText())) return; selected = null; }}>×</button></div>
				{#if previewKind === 'pdf'}
					{#key pdfEditorVersion}<PdfEditor resourceId={`drive-${selected.id}`} url={contentUrl(selected, true)} name={selected.name} onclose={()=>selected=null} />{/key}
				{:else}<div class="drive-preview-body">
					{#if previewKind === 'image'}<img src={contentUrl(selected, true)} alt={selected.name} />
					{:else if previewKind === 'text' && editableText}<div class="drive-text-editor"><textarea aria-label={`${selected.name} 편집`} bind:value={editingText} oninput={(event) => queueTextSave(event.currentTarget.value)}></textarea><span role="status">{textStatus}</span></div>
					{:else if previewKind === 'text'}<pre>{previewText}</pre>
					{:else}<p>미리보기를 지원하지 않는 파일입니다.</p>{/if}
				</div>{/if}
				<div class="drive-preview-actions">{#key selected.id}<DriveItemOptions item={selected} folders={library.allFolders} currentFolder={library.placements[selected.id]||null} onchanged={()=>refresh(true)} />{/key}<button class="drive-button" type="button" disabled={busy} onclick={() => void moveSelected()}>{bucket === 'transfer' ? '보관함으로 이동' : '전송함으로 이동'}</button><button class="drive-button danger" type="button" disabled={busy} onclick={() => void deleteSelected()}>삭제</button></div>
			</aside>
		{/if}
	</div>

	<form class="drive-composer" onsubmit={(event) => { event.preventDefault(); void saveNote(); }}>
		<textarea aria-label="텍스트 입력" placeholder="텍스트를 입력하고 Enter로 전송" maxlength="200000" bind:value={noteText} onkeydown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); void saveNote(); } }}></textarea>
		<button class="drive-button primary" type="submit" disabled={busy || !noteText.trim()}>보내기</button>
	</form>
</div>

<dialog class="drive-folder-dialog" bind:this={folderDialog} aria-labelledby="folder-title"><form onsubmit={(e)=>{e.preventDefault();void createFolder();}}><h2 id="folder-title">새 폴더</h2><p role="status">{message}</p><label>폴더 이름<input aria-label="폴더 이름" bind:value={folderName} maxlength="120" required /></label><div><button type="button" disabled={busy} onclick={()=>folderDialog.close()}>취소</button><button class="primary" disabled={busy || !folderName.trim()}>만들기</button></div></form></dialog>
