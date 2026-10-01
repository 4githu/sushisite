<script lang="ts">
	import { privateCacheUser } from '$lib/personal-project/shared/auth';
	import KakaoBridge from '$lib/personal-project/kakao/KakaoBridge.svelte';
	import { onMount } from 'svelte';
	import { request, PersonalApiError } from '$lib/personal-project/shared/api';
	import { uploadResource, type Resource } from '$lib/personal-project/resources/api';
	import PdfEditor from '$lib/personal-project/pdf/PdfEditor.svelte';
	import PersonalTextEditor from '$lib/personal-project/editor/PersonalTextEditor.svelte';
	import { createDocument } from '$lib/textediter/model';
	import type { EditorDocument } from '$lib/textediter/types';
	import '$lib/personal-project/student/student.css';
	let copies = $state<{ document_key: string; updated_at: string }[]>([]),
		conflict = $state(false);
	let firstDirtyAt = 0;
	const recoveryKey = () => `ondo-private:${privateCacheUser()}:material-notes`;
	let resources = $state<Resource[]>([]),
		selected = $state<Resource | null>(null),
		error = $state(''),
		progress = $state<number | null>(null),
		loading = $state(true),
		initial = $state<EditorDocument>(createDocument()),
		document = $state<EditorDocument>(createDocument()),
		revision = 0,
		dirty = $state(false),
		saving = $state(false);
	let input: HTMLInputElement;
	onMount(() => {
		void (async () => {
			try {
				const [files, doc] = await Promise.all([
					request<Resource[]>('/resources'),
					request<{ data: EditorDocument | null; revision: number }>('/documents/material-notes')
				]);
				resources = files;
				if (doc.data) initial = document = doc.data;
				revision = doc.revision;
				copies = await request('/documents');
				const local = privateCacheUser() && localStorage.getItem(recoveryKey());
				if (local) {
					const r = JSON.parse(local);
					initial = document = r.data;
					dirty = true;
					if (r.revision !== revision) {
						conflict = true;
						error =
							'다른 화면에서 자료 메모를 변경했습니다. 복구본과 최신 내용을 함께 보존해주세요.';
					}
				}
			} catch (e) {
				error = String(e);
			} finally {
				loading = false;
			}
		})();
	});
	async function upload(files: File[]) {
		for (const file of files) {
			try {
				progress = 0;
				const r = await uploadResource(file, undefined, (v) => (progress = v));
				resources = [r, ...resources];
				if (r.mimeType === 'application/pdf') selected = r;
			} catch (e) {
				error = String(e);
			} finally {
				progress = null;
			}
		}
	}
	async function save() {
		if (saving || conflict) return;
		saving = true;
		const snapshot = JSON.stringify(document);
		try {
			const r = await request<{ revision: number }>('/documents/material-notes', {
				method: 'PUT',
				body: { revision, data: JSON.parse(snapshot) }
			});
			revision = r.revision;
			if (snapshot === JSON.stringify(document)) {
				dirty = false;
				firstDirtyAt = 0;
				localStorage.removeItem(recoveryKey());
			}
		} catch (e) {
			if (e instanceof PersonalApiError && e.status === 409) conflict = true;
			error = String(e);
		} finally {
			saving = false;
		}
	}
	$effect(() => {
		document;
		if (dirty && !loading) {
			try {
				if (privateCacheUser())
					localStorage.setItem(recoveryKey(), JSON.stringify({ data: document, revision }));
			} catch {}
		}
		if (dirty && !saving && !error) {
			if (!firstDirtyAt) firstDirtyAt = Date.now();
			const t = setTimeout(
				() => void save(),
				Math.max(0, Math.min(500, 2000 - (Date.now() - firstDirtyAt)))
			);
			return () => clearTimeout(t);
		}
	});
	async function preserve() {
		try {
			await request(`/documents/material-conflict:${crypto.randomUUID()}`, {
				method: 'PUT',
				body: { revision: 0, data: document }
			});
			localStorage.removeItem(recoveryKey());
			location.reload();
		} catch (e) {
			error = String(e);
		}
	}
</script>

<svelte:head><title>자료 · PDF · NETAQ</title></svelte:head>
<div class="student-page">
	<header>
		<h1>자료</h1>
		<button class="primary" onclick={() => input.click()}>사진·파일 올리기</button><input
			hidden
			type="file"
			multiple
			bind:this={input}
			onchange={(e) => {
				void upload(Array.from(e.currentTarget.files || []));
				e.currentTarget.value = '';
			}}
		/>
	</header>
	{#if error}<p class="error" role="alert">{error}</p>{/if}{#if progress !== null}<p role="status">
			업로드 {progress}%
		</p>{/if}{#if loading}<p role="status">자료 불러오는 중…</p>{/if}
	{#if selected}<button onclick={() => (selected = null)}>← 자료 목록</button
		>{#key selected.id}<PdfEditor
				resourceId={selected.id}
				url={selected.url}
				name={selected.name}
			/>{/key}{:else}<KakaoBridge />{#if copies.length}<details>
				<summary>별도로 보존한 복구본</summary>{#each copies as c}<p>
						<a href={`/api/personal/documents/${encodeURIComponent(c.document_key)}`} download
							>{c.updated_at} · {c.document_key}</a
						>
					</p>{/each}
			</details>{/if}
		<div class="library">
			{#each resources as r}<article>
					{#if r.mimeType.startsWith('image/')}<img
							src={r.url}
							alt={r.name}
							loading="lazy"
						/>{/if}<strong>{r.name}</strong><small>{(r.byteSize / 1024).toFixed(0)}KB</small
					>{#if r.mimeType === 'application/pdf'}<button onclick={() => (selected = r)}
							>PDF 열기 · 필기</button
						>{/if}<a href={r.url} download={r.name}>원본 다운로드</a>
				</article>{:else}{#if !loading}<p>아직 올린 자료가 없습니다.</p>{/if}{/each}
		</div>
		<section>
			<h2>자료 메모</h2>
			{#if !loading}<PersonalTextEditor
					initialValue={initial}
					onchange={(v) => {
						document = v;
						dirty = true;
					}}
				/>{/if}
			<p role="status">{saving ? '저장 중…' : dirty ? '저장 대기' : '저장됨'}</p>
			{#if conflict}<button onclick={preserve}>복구본 별도 보존 후 최신 메모 불러오기</button
				>{:else if dirty && error}<button onclick={save}>저장 다시 시도</button>{/if}
		</section>{/if}
</div>

<style>
	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.library {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: 16px;
		margin: 24px 0;
	}
	.library article {
		display: flex;
		flex-direction: column;
		gap: 10px;
		border-bottom: 1px solid #8884;
		padding: 16px 0;
		overflow-wrap: anywhere;
	}
	.library img {
		height: 150px;
		object-fit: contain;
	}
	.library small {
		opacity: 0.6;
	}
	section {
		margin-top: 32px;
	}
</style>
