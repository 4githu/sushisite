<script lang="ts">
	import RuleTree from './RuleTree.svelte';
	import RuleText from './RuleText.svelte';
	import CourseCompletion from './CourseCompletion.svelte';
	import { courseState, type CourseProgress } from './progress';
	let {
		value,
		progress = { planned: [], completed: [] },
		oncomplete,
		busy = false
	}: {
		value: unknown;
		progress?: CourseProgress;
		oncomplete?: (code: string) => void;
		busy?: boolean;
	} = $props();
	const labels: Record<string, string> = {
		math: '수학',
		science: '과학',
		msc: '수학·과학·컴퓨팅',
		suri: '수학·과학·컴퓨팅',
		suri_sub: '수학·과학·컴퓨팅 세부 조건',
		dept: '학과',
		colleges: '단과대학',
		label: '구분',
		note: '참고',
		area: '영역',
		code_prefixes: '과목번호 시작값',
		codes: '과목번호',
		baseline_assumed: '임시 기준',
		recog_max_courses: '최대 인정 과목 수',
		any_dept: '학과 제한 없음',
		major_select_min_courses: '전공선택 최소 과목 수',
		seq: '순서',
		combined: '합산 조건',
		select_required: '선택필수',
		min_slots: '최소 선택 수',
		slots: '선택 항목',
		english_min_courses: '외국어 강의 최소 과목 수',
		all: '모두 이수',
		any: '선택 이수',
		pool: '선택 대상 과목',
		groups: '과목군',
		required: '필수 이수 조건',
		name: '이름',
		code: '과목번호',
		credits: '학점',
		min_courses: '최소 과목 수',
		min_credits: '최소 학점',
		major_min_credits: '전공 최소 학점',
		required_credits: '전공필수 학점',
		select_min: '선택 최소 학점',
		recog_max: '타 전공 인정 상한',
		general: '교양 이수 적용',
		required_extra: '추가 필수 조건',
		notes: '참고 사항',
		min: '최소',
		courses: '과목',
		choose: '선택 수',
		min_groups: '최소 과목군',
		approval_max_credits: '승인 인정 상한',
		depts: '인정 학과',
		departments: '학과',
		classifications: '이수 구분',
		key: '구분'
	};
</script>

{#if Array.isArray(value)}<ul>
		{#each value as item}<li><RuleTree value={item} {progress} {oncomplete} {busy} /></li>{/each}
	</ul>
{:else if value !== null && typeof value === 'object' && 'name' in value && 'code' in value}<div
		class="rule-course"
		class:completed={courseState(progress, String(value.code)) === 'completed'}
		class:planned={courseState(progress, String(value.code)) === 'planned'}
	>
		<div><strong>{String(value.name)}</strong><small>{String(value.code)}</small></div>
		{#if 'credits' in value}<span>{String(value.credits)}학점</span>{/if}
		<span
			>{courseState(progress, String(value.code)) === 'completed'
				? '지난 학기 수강'
				: courseState(progress, String(value.code)) === 'planned'
					? '진행 중·예정 학기'
					: '남은 과목'}</span
		>
	</div>
{:else if value !== null && typeof value === 'object'}<dl>
		{#each Object.entries(value) as [key, item]}<div
				class:nested={item !== null && typeof item === 'object'}
			>
				<dt>{labels[key] || '추가 조건'}</dt>
				<dd><RuleTree value={item} {progress} {oncomplete} {busy} /></dd>
			</div>{/each}
	</dl>
{:else}<span
		>{#if typeof value === 'boolean'}{value
				? '적용'
				: '미적용'}{:else if value === null}미지정{:else}<RuleText
				text={String(value)}
			/>{/if}</span
	>{/if}

<style>
	ul {
		padding-left: 0;
		list-style: none;
		margin: 6px 0;
	}
	li {
		margin: 8px 0;
	}
	dl {
		margin: 0;
	}
	dl > div {
		display: flex;
		gap: 12px;
		align-items: baseline;
		margin: 5px 0;
		flex-wrap: wrap;
	}
	.nested {
		display: block;
	}
	.nested > dt {
		font-weight: 600;
		margin: 12px 0 8px;
	}
	.nested > dd {
		margin-left: 8px;
	}
	dt {
		color: #73757d;
		font-size: 12px;
		min-width: 90px;
	}
	dd {
		margin: 0;
		flex: 1;
		min-width: 0;
		overflow-wrap: anywhere;
		font-size: 13px;
	}
	span {
		white-space: pre-wrap;
		line-height: 1.6;
	}
	.rule-course {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		border: 1px solid #e5e6eb;
		border-radius: 8px;
		padding: 12px;
	}
	.rule-course.completed {
		background: #edf8f2;
		border-color: #77b69a;
	}
	.rule-course.planned {
		background: #fffae9;
		border-color: #d9bf71;
	}
	.rule-course {
		flex-wrap: wrap;
		align-items: center;
	}
	.rule-course strong {
		font-size: 13px;
		line-height: 1.5;
	}
	.rule-course small {
		display: block;
		font-size: 11px;
		color: #747680;
		margin-top: 4px;
		overflow-wrap: anywhere;
	}
	.rule-course > span {
		font-size: 11px;
		white-space: nowrap;
		color: #747680;
	}
</style>
