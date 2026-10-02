<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from '$lib/personal-project/shared/api';
	import CampusServices from '$lib/personal-project/student/CampusServices.svelte';
	let schools=$state<{id:number;name:string;departments:string[]}[]>([]);
	let servicesKey=$state(0);
	import '$lib/personal-project/student/student.css';
	let profile = $state({
			is_student: true,
			school: '서울대학교',
			department: '',
			admission_year: new Date().getFullYear() as number | null,
			academic_offset: 0
		}),
		loading = $state(true),
		busy = $state(false),
		error = $state(''),
		notice = $state('');
	onMount(async () => {
		try {
			const [data,list] = await Promise.all([request<typeof profile>('/student/profile'),request<typeof schools>('/student/schools')]);
			schools=list;
			if (data.school) profile = { ...data, is_student: Boolean(data.is_student) };
		} catch (e) {
			error = e instanceof Error ? e.message : '설정을 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	});
	async function save() {
		busy = true;
		error = '';
		try {
			profile = await request('/student/profile', { method: 'PUT', body: profile });
			schools=await request('/student/schools');servicesKey++;
			notice = '학교 설정을 저장했습니다.';
		} catch (e) {
			error = e instanceof Error ? e.message : '저장 실패';
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>학교 설정 · NETAQ</title></svelte:head>
<div class="student-page">
	<header>
		<span class="eyebrow">CAMPUS / SETTINGS</span>
		<h1>내 학교</h1>
		<p class="muted">학교와 학과를 등록하고 시간표·학식·수강계획을 한곳에서 확인하세요.</p>
	</header>
	{#if error}<p class="error" role="alert">{error}</p>{/if}{#if notice}<p
			class="notice"
			role="status"
		>
			{notice}
		</p>{/if}
	<form
		class="panel"
		onsubmit={(e) => {
			e.preventDefault();
			void save();
		}}
	>
		<fieldset disabled={loading || busy}>
			<legend>학생서비스 설정</legend><label
				><input type="checkbox" bind:checked={profile.is_student} />학생서비스 사용</label
			><label
				>학교<input
					bind:value={profile.school}
					list="campus-list"
					required={profile.is_student}
					maxlength="120"
					placeholder="서울대학교"
				/></label
			><label
				>학과<input
					bind:value={profile.department}
					list="department-list"
					maxlength="120"
					placeholder="예: 컴퓨터공학부"
				/></label
			><label
				>입학 연도<input
					type="number"
					min="1950"
					max="2100"
					bind:value={profile.admission_year}
				/></label
			><label
				>휴학 등 학기 보정<input
					type="number"
					min="-20"
					max="20"
					bind:value={profile.academic_offset}
				/></label
			><small>휴학한 학기 수만큼 보정합니다. 이수규정의 입학 연도는 유지됩니다.</small><button
				class="primary">설정 저장</button
			>
		</fieldset>
	</form>
	<datalist id="campus-list">{#each schools as s}<option value={s.name}></option>{/each}</datalist>
	<datalist id="department-list">{#each schools.find(s=>s.name===profile.school)?.departments || [] as d}<option value={d}></option>{/each}</datalist>
	<p class="muted">목록에 없는 학교·학과도 이름을 입력하고 저장하면 등록됩니다. KAIST·DGIST·한양대학교는 수동 시간표와 사용자 수강 규정부터 이용할 수 있습니다.</p>
	{#key servicesKey}<CampusServices />{/key}
	<div class="destinations">
		{#each [['timetable', '시간표', '강의 검색 또는 직접 입력하고 캘린더에 자동 반영'], ['meals', '학식', '지원 학교의 식단과 학교별 서비스 링크'], ['plan', '수강계획', '학교·학과별 이수규정 조회와 사용자 작성본']] as [path, title, description]}<a
				class="panel"
				href={`/personal-project/calendar/student/${path}`}
				><h2>{title} →</h2>
				<p class="muted">{description}</p></a
			>{/each}
	</div>
</div>

<style>
	form {
		max-width: 600px;
		margin-top: 24px;
	}
	fieldset {
		border: 0;
		padding: 0;
	}
	legend {
		font-weight: 600;
		margin-bottom: 18px;
	}
	label {
		margin: 16px 0;
	}
	label input:not([type='checkbox']) {
		flex: 1;
	}
	.destinations {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px;
		margin-top: 24px;
	}
	.destinations a {
		text-decoration: none;
	}
	@media (max-width: 500px) {
		.destinations {
			grid-template-columns: 1fr;
		}
	}
</style>
