<script lang="ts">
	import { request } from '../shared/api';
	import type { Course } from './catalog';
	let {
		code,
		initial,
		onchange,
		preferredMajor = ''
	}: { code: string; initial?: NonNullable<Course['personalTags']>; onchange?: () => void; preferredMajor?: string } =
		$props();
	let tags = $state<NonNullable<Course['personalTags']>>([]),
		majors = $state<string[]>([]),
		kind = $state<'major_select' | 'major_required' | 'general'>('major_select'),
		major = $state(''),
		targetMajor = $state(''),
		area = $state('수학'),
		busy = $state(false),
		error = $state(''),
		editing = $state(false);
	let loaded = $state(false);
	$effect(() => {
		if (initial) {
			tags = initial;
		}
	});
	$effect(() => {
		if (preferredMajor && !targetMajor) targetMajor = preferredMajor;
	});
	async function load() {
		if (loaded) return;
		try {
			if (initial) tags = initial;
			else {
				const all =
					await request<Record<string, NonNullable<Course['personalTags']>>>(
						'/student/course-tags'
					);
				tags = all[code.toUpperCase()] || [];
			}
		} catch (e) {
			error = String(e);
		}
		let department = '';
		let school = '';
		try {
			const profile = await request<{ department?: string; school?: string }>('/student/profile');
			department = profile.department?.trim() || '';
			school = profile.school || '';
		} catch {}
		if (!school || school === '서울대학교') {
			try {
				const index = await request<{ index: { major: string }[] }>('/student/rules');
				majors = [...new Set(index.index.map((item) => item.major).filter(Boolean))].sort();
			} catch {}
		}
		if (department && !majors.includes(department)) majors = [...majors, department].sort();
		const savedGeneralMajor = tags.find((tag) => tag.kind === 'general' && tag.major)?.major;
		targetMajor =
			savedGeneralMajor ||
			preferredMajor ||
			(majors.includes(department) ? department : majors.length === 1 ? majors[0] : '');
		if (preferredMajor) {
			if (!majors.includes(preferredMajor)) majors = [...majors, preferredMajor].sort();
			if (!major) major = preferredMajor;
		}
		loaded = true;
	}
	async function save(next: NonNullable<Course['personalTags']>) {
		busy = true;
		error = '';
		try {
			await request(`/student/course-tags/${encodeURIComponent(code)}`, {
				method: 'PUT',
				body: { tags: next }
			});
			tags = next;
			editing = false;
			onchange?.();
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
</script>

<div class="course-tags">
	{#each tags as tag, i}<span class="tag"
			>{tag.kind === 'general'
				? `${tag.major === '*' ? '모든 전공' : tag.major || '전공 선택 필요'} · 교양 · ${tag.area}`
				: `${tag.major} · ${tag.kind === 'major_required' ? '전공필수' : '전공선택'}`}<button
				disabled={busy}
				aria-label="과목 분류 삭제"
				onclick={() => save(tags.filter((_, n) => n !== i))}>×</button
			></span
		>{/each}
	<button
		class="edit-trigger"
		aria-expanded={editing}
		onclick={async () => {
			editing = !editing;
			if (editing) await load();
		}}>과목 분류 편집</button
	>
	{#if editing}<div class="editor" aria-label="과목 분류 편집">
			<select aria-label="과목 분류 종류" bind:value={kind}
				><option value="major_select">전공선택</option><option value="major_required">전공필수</option
				><option value="general">교양</option></select
			>
			{#if kind === 'general'}
				<select aria-label="적용 전공" bind:value={targetMajor}>
					<option value="">전공 선택</option>
					<option value="*">모든 전공</option>
					{#each majors as value}<option>{value}</option>{/each}
				</select>
				<select aria-label="교양 영역" bind:value={area}
					>{#each ['수학', '과학', '외국어', '글쓰기', '베리타스', '지성의 열쇠'] as value}<option
							>{value}</option
						>{/each}</select
				>{:else}<input
					aria-label="인정 전공"
					placeholder="전공 선택"
					list="course-major-options"
					bind:value={major}
				/><datalist id="course-major-options"
					>{#each majors as name}<option value={name}></option>{/each}</datalist
				>{/if}
			<button
				disabled={busy || !loaded || (kind === 'general' ? !targetMajor : !major.trim())}
				onclick={() =>
					save([
						...tags,
						{
							kind,
							major: kind === 'general' ? targetMajor : major.trim(),
							area: kind === 'general' ? area : ''
						}
					])}>분류 추가</button
			>
		</div>{/if}
	{#if error}<p role="alert">{error}</p>{/if}
</div>

<style>
	.course-tags {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: 4px;
		flex-wrap: wrap;
		max-width: 100%;
	}
	.edit-trigger {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 30px;
		padding: 0 10px;
		border: 1px solid #d6d8dd;
		border-radius: 999px;
		background: #fff;
		color: #424650;
		font-size: 11px;
		font-weight: 650;
		cursor: pointer;
		white-space: nowrap;
	}
	.editor {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 6px;
		flex-basis: 100%;
		width: min(100%, 560px);
		padding: 10px;
		border: 1px solid #e0e2e7;
		border-radius: 12px;
		background: #fafafa;
		box-sizing: border-box;
	}
	.tag {
		font-size: 11px;
		background: #edf2f5;
		padding: 5px 8px;
		margin: 3px;
	}
	.tag {
		display: inline-flex;
		gap: 6px;
		border-radius: 16px;
		background: #8b5cf618;
		padding: 4px 8px;
		margin: 4px;
	}
	button,
	select,
	input {
		border: 1px solid #8885;
		border-radius: 6px;
		min-height: 32px;
		padding: 4px 8px;
		color: inherit;
		background: var(--surface, #fff);
	}
	.tag button {
		min-height: 18px;
		padding: 0 2px;
		border: 0;
		background: transparent;
		font-size: 14px;
	}
</style>
