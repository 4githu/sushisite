<script lang="ts">
	import SurfaceCard from "$lib/odi/components/common/SurfaceCard.svelte";
	import SegmentedControl from "$lib/odi/components/session/SegmentedControl.svelte";

	import {
		ArOnYouIcon as ArOnYou,
		PermContactCalendarIcon as PermContactCalendar,
		PersonIcon as Person
	} from "$lib/odi/icons";

	type InterviewerPersona =
		| "hr"
		| "practical"
		| "executive"
		| "mixed";

	type InterviewStyle =
		| "friendly"
		| "neutral"
		| "critical"
		| "pressure";

	let {
		interviewerPersona = $bindable("hr"),
		interviewStyle = $bindable("friendly")
	}: {
		interviewerPersona?: InterviewerPersona;
		interviewStyle?: InterviewStyle;
	} = $props();

	const personaItems = [
		{
			value: "hr",
			icon: Person,
			label: "인사담당자(HR)",
			description: "조직 적합성과 성장 가능성\n중심으로 평가합니다."
		},
		{
			value: "practical",
			icon: Person,
			label: "실무자(Practical)",
			description: "직무 역량과 실무 적합성을\n중심으로 평가합니다."
		},
		{
			value: "executive",
			icon: Person,
			label: "임원(Executive)",
			description: "전략적 사고와 리더십 역량을\n중심으로 평가합니다."
		},
		{
			value: "mixed",
			icon: Person,
			label: "혼합(Mixed)",
			description: "다양한 관점에서 다각도로\n평가받을 수 있습니다."
		}
	];

	const styleItems = [
		{
			value: "friendly",
			icon: Person,
			label: "우호적(Friendly)",
			description: "편안하고 긍정적인 분위기에서\n대화를 이끌어갑니다."
		},
		{
			value: "neutral",
			icon: Person,
			label: "일반적(Neutral)",
			description: "균형 잡힌 태도로 공정하고\n객관적인 질문을 합니다."
		},
		{
			value: "critical",
			icon: Person,
			label: "비판적(Critical)",
			description: "날카로운 질문으로 깊이 있는\n답변을 요구합니다."
		},
		{
			value: "pressure",
			icon: Person,
			label: "압박형(Pressure)",
			description: "빠른 판단과 강한 압박 속에서\n역량을 테스트합니다."
		}
	];
</script>

<SurfaceCard padding="43px 36px" minHeight="609px">
	<div class="interviewer-setting-content">
		<section class="setting-section">
			<div class="section-title">
				<div class="title-icon">
					<img src={PermContactCalendar} alt="" />
				</div>

				<h2 class="text-title-middle">
					면접관 페르소나
				</h2>
			</div>

			<SegmentedControl
				variant="card"
				itemWidth="246px"
				items={personaItems}
				bind:selected={interviewerPersona}
			/>
		</section>

		<section class="setting-section">
			<div class="section-title">
				<div class="title-icon">
					<img src={ArOnYou} alt="" />
				</div>

				<h2 class="text-title-middle">
					면접 스타일
				</h2>
			</div>

			<SegmentedControl
				variant="card"
				itemWidth="246px"
				items={styleItems}
				bind:selected={interviewStyle}
			/>
		</section>
	</div>
</SurfaceCard>

<style>
	.interviewer-setting-content {
		display: flex;
		flex-direction: column;

		gap: 46px;
	}

	.setting-section {
		display: flex;
		flex-direction: column;

		gap: var(--space-6);
	}

	.section-title {
		display: flex;
		align-items: center;

		gap: var(--space-2);
	}

	.title-icon {
		width: 36px;
		height: 36px;

		display: flex;
		align-items: center;
		justify-content: center;

		border-radius: var(--radius-full);

		background: rgba(0, 80, 255, 0.15);
	}

	.title-icon img {
		width: 24px;
		height: 24px;
	}
</style>
