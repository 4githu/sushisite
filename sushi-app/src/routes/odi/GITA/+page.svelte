<script lang="ts">
	import StepIndicator from "$lib/odi/components/session/StepIndicator.svelte";
	import ProgressStepper from "$lib/odi/components/session/ProgressStepper.svelte";
	const steps = [
		{ label: "면접 기본 정보" },
		{ label: "자료 업로드" },
		{ label: "AI 면접관 설정" },
		{ label: "세션 확인" }
	];


	import SegmentItem from "$lib/odi/components/session/SegmentItem.svelte";
    import SegmentedControl from "$lib/odi/components/session/SegmentedControl.svelte";
	let interviewType = $state("one");
	const interviewTypes = [
		{
			label: "일대일",
			value: "one"
		},
		{
			label: "일대다",
			value: "many"
		},
		{
			label: "다대다",
			value: "group"
		}
	];

	import SessionSelect from "$lib/odi/components/session/SessionSelect.svelte";
	import { alarm as Alarm, lock as Lock } from "$lib/odi/icons";
	let duration = $state("");
	let people = $state("");
	const durationItems = [
		{ label: "0분", value: "0" },
		{ label: "5분", value: "5" },
		{ label: "10분", value: "10" }
	];

	import SessionSlider from "$lib/odi/components/session/SessionSlider.svelte";
	let difficulty = $state(2);
	let timeduration = $state(25);

	import Button from "$lib/odi/components/common/Button.svelte";
	import TextInput from "$lib/odi/components/common/TextInput.svelte";
	let company = $state("");

	import ProfileDropdown from "$lib/odi/components/navigation/ProfileDropdown.svelte";

	function logout() {
		// Firebase logout
	}

</script>

<div class="page">
	<h1>ODI Component Showcase</h1>

	<section>
		<h2>StepIndicator</h2>

		<div class="row">
			<StepIndicator step={1} label="Inactive" status="inactive" />
			<StepIndicator step={2} label="Active" status="active" />
			<StepIndicator step={3} label="Done" status="done" />
		</div>
	</section>

	<section>
		<h2>ProgressStepper</h2>

		<ProgressStepper
			steps={steps}
			currentStep={1}
		/>
	</section>

	<section>
		<h2>SegmentItem</h2>

		<div class="row">
			<SegmentItem label="기본" />
			<SegmentItem label="선택됨" selected />
			<SegmentItem label="비활성" disabled />
		</div>
	</section>

	<SegmentedControl
	items={interviewTypes}
	bind:selected={interviewType}
	/>

	<SessionSelect
		items={durationItems}
		bind:value={people}
		icon={Lock}
		disabled
	/>

	<SessionSlider
	label = "난이도"
	mode="node"
	min={1}
	max={3}
	step={1}
	bind:value={difficulty}
	majorTicks={[
		{ value: 1, label: "쉬움" },
		{ value: 2, label: "보통" },
		{ value: 3, label: "어려움" }
	]}
	/>


	<SessionSlider
		label="발표 시간"
		mode="range"
		min={10}
		max={60}
		step={1}
		bind:value={timeduration}
		majorTicks={[
			{ value: 10, label: "10분" },
			{ value: 20, label: "20분" },
			{ value: 30, label: "30분" },
			{ value: 40, label: "40분" },
			{ value: 50, label: "50분" },
			{ value: 60, label: "60분" }
		]}
		showValue = {true}
		valueSuffix = "분"
	/>


	<Button href="/odi/icons"> 다음 단계 </Button>
	<Button variant="secondary"	href="/odi">이전 단계</Button>
	<Button variant="soft"	href="/odi">팝업 단계</Button>
	<Button variant="outline"	href="/odi">그냥 단계</Button>


	<TextInput
		label="기업명"
		placeholder="입력해주세요"
		bind:value={company}
	/>


	<ProfileDropdown
		userName="리히어"
		planName="Plus"
		onLogout={logout}
	/>

</div>



<style>
	.page {
		padding: var(--space-8);
		display: flex;
		flex-direction: column;
		gap: var(--space-12);
	}

	section {
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
	}

	.row {
		display: flex;
		gap: var(--space-6);
		align-items: center;
		flex-wrap: wrap;
	}
</style>
