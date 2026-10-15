<script lang="ts">
	import RuleFields from './RuleFields.svelte';
	let {
		value,
		onchange,
		label = '조건'
	}: { value: any; onchange: (value: any) => void; label?: string } = $props();
	const names: Record<string, string> = {
		total_credits: '졸업 총학점',
		major_min_credits: '전공 최소 학점',
		required_credits: '필수 학점',
		select_min: '선택 최소 학점',
		required: '필수 이수',
		all: '모두 이수',
		pool: '선택 대상',
		min_courses: '최소 과목 수',
		min_credits: '최소 학점',
		any: '선택 이수',
		groups: '과목군',
		name: '이름',
		code: '과목코드',
		credits: '학점',
		general: '교양 적용',
		recog_max: '타 전공 인정 상한',
		select_required: '선택필수',
		required_extra: '추가 필수 조건'
	};
</script>

{#if Array.isArray(value)}<fieldset>
		<legend>{label}</legend>{#each value as item, i}<div class="item">
				<RuleFields
					value={item}
					label={`${i + 1}`}
					onchange={(v) => onchange(value.map((x: any, j: number) => (i === j ? v : x)))}
				/><button
					type="button"
					onclick={() => onchange(value.filter((_: any, j: number) => i !== j))}>항목 삭제</button
				>
			</div>{/each}<button
			type="button"
			onclick={() =>
				onchange([
					...value,
					typeof value[0] === 'string' ? '' : { name: '', code: '', credits: 3 }
				])}>항목 추가</button
		>
	</fieldset>
{:else if value && typeof value === 'object'}<fieldset>
		<legend>{label}</legend
		>{#each Object.entries(value).filter(([k]) => !['key', 'id'].includes(k)) as [key, item]}<RuleFields
				value={item}
				label={names[key] || key}
				onchange={(v) => onchange({ ...value, [key]: v })}
			/>{/each}
	</fieldset>
{:else if typeof value === 'number'}<label
		>{label}<input
			type="number"
			min="0"
			max="500"
			step="0.5"
			{value}
			oninput={(e) => onchange(Number(e.currentTarget.value))}
		/></label
	>
{:else if typeof value === 'boolean'}<label
		><input
			type="checkbox"
			checked={value}
			onchange={(e) => onchange(e.currentTarget.checked)}
		/>{label}</label
	>
{:else}<label
		>{label}<input value={value ?? ''} oninput={(e) => onchange(e.currentTarget.value)} /></label
	>{/if}

<style>
	fieldset {
		border: 1px solid #8884;
		border-radius: 8px;
		margin: 10px 0;
		padding: 12px;
	}
	legend {
		font-weight: 600;
	}
	label {
		display: flex;
		gap: 12px;
		align-items: center;
		margin: 8px 0;
		font-size: 14px;
	}
	input:not([type='checkbox']) {
		min-width: 80px;
		flex: 1;
		width: 100%;
	}
	input[type='number'] {
		max-width: 120px;
	}
	.item {
		border-bottom: 1px solid #8883;
		padding-bottom: 10px;
	}
	button {
		font-size: 13px;
	}
</style>
