<script lang="ts">
	import SurfaceCard from "$lib/odi/components/common/SurfaceCard.svelte";

	import SegmentedControl from "$lib/odi/components/session/SegmentedControl.svelte";
	import SessionSlider from "$lib/odi/components/session/SessionSlider.svelte";

	import {
		DocumentIcon as FileDocumentOutline,
		PersonIcon as Person,
		school as School,
		CrownIcon as CloudArrowUpOutline,
		audiance as Group
	} from "$lib/odi/icons";

	type PersonaType = "" | "general" | "student" | "judge" | "mixed";

	let {
		personaType = $bindable(""),
		audienceSize = $bindable(6),
		expertiseLevel = $bindable(2),
		interestLevel = $bindable(2)
	}: {
		personaType?: PersonaType;
		audienceSize?: number;
		expertiseLevel?: number;
		interestLevel?: number;
	} = $props();

	const personaItems = [
		{
			value: "general",
			icon: Person,
			label: "일반 청중",
			description: "비전공자 중심"
		},
		{
			value: "student",
			icon: School,
			label: "학생 중심",
			description: "관련 전공 학생"
		},
		{
			value: "judge",
			icon: CloudArrowUpOutline,
			label: "심사위원 중심",
			description: "교수 및 평가위원"
		},
		{
			value: "mixed",
			icon: Group,
			label: "혼합",
			description: "다양한 청중 구성"
		}
	];

	const audienceSizeTicks = [
		{ value: 1, label: "1" },
		{ value: 10, label: "10" },
		{ value: 20, label: "20" },
		{ value: 30, label: "30" },
		{ value: 40, label: "40" },
		{ value: 50, label: "50 +" }
	];

	const levelTicks = [
		{ value: 1, label: "낮음" },
		{ value: 2, label: "중간" },
		{ value: 3, label: "높음" }
	];
</script>

<SurfaceCard padding="43px 36px" minHeight="609px">
	<div class="interviewer-content">
		<section class="persona-section">
			<div class="section-header">
				<div class="title-row">
					<div class="title-icon">
						<img src={FileDocumentOutline} alt="" />
					</div>

					<h2 class="text-title-middle">
						청중 유형
					</h2>
				</div>

				<p class="helper text-caption-medium">
					청중 유형과 아래 항목을 하나씩 직접 선택해주세요.
				</p>
			</div>

			<SegmentedControl
				variant="card"
				itemWidth="184px"
				items={personaItems}
				bind:selected={personaType}
			/>
		</section>

		<section class="audience-section">
			<div class="section-header">
				<div class="title-row">
					<div class="title-icon">
						<img src={FileDocumentOutline} alt="" />
					</div>

					<h2 class="text-title-middle">
						청중 규모
					</h2>
				</div>

				<p class="helper size-helper text-caption-medium">
					발표에 참여하는 청중의 인원 수를 설정하세요. 발표 기본 정보 시에 설정한 청중 규모가 연동됩니다.
				</p>
			</div>

			<div class="audience-slider">
				<SessionSlider
					mode="range"
					min={1}
					max={50}
					step={1}
					majorTicks={audienceSizeTicks}
					showValue
					valueSuffix="명"
					bind:value={audienceSize}
				/>
			</div>
		</section>

		<section class="level-row">
			<div class="level-field">
				<div class="level-header">
					<h3 class="text-title-small">
						전문성 수준
					</h3>

					<p class="helper text-caption-medium">
						청중의 발표 주제에 대한 전문성을 설정하세요.
					</p>
				</div>

				<SessionSlider
					mode="node"
					min={1}
					max={3}
					step={1}
					majorTicks={levelTicks}
					bind:value={expertiseLevel}
				/>
			</div>

			<div class="level-field">
				<div class="level-header">
					<h3 class="text-title-small">
						관심도 수준
					</h3>

					<p class="helper text-caption-medium">
						청중이 발표 주제에 가지는 관심도를 설정하세요.
					</p>
				</div>

				<SessionSlider
					mode="node"
					min={1}
					max={3}
					step={1}
					majorTicks={levelTicks}
					bind:value={interestLevel}
				/>
			</div>
		</section>
	</div>
</SurfaceCard>

<style>
	.interviewer-content {
		display: flex;
		flex-direction: column;
	}

	.persona-section {
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
	}

	.section-header {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	.title-row {
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

	.helper {
		color: var(--text-disabled);
		line-height: 135%;
	}

	.audience-section {
		display: flex;
		flex-direction: column;
		gap: var(--space-5);

		margin-top: 28px;
	}

	.size-helper {
		width: min(775px, 100%);
		padding-left: 44px;
	}

	.audience-slider {
		width: min(900px, 100%);
		margin-left: 38px;
	}

	.level-row {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 38px;

		margin-top: 40px;
		margin-left: 44px;
	}

	.level-field {
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
	}

	.level-header {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	@media (max-width: 760px) {
		.size-helper,
		.audience-slider,
		.level-row {
			width: 100%;
			margin-left: 0;
			padding-left: 0;
		}

		.level-row {
			grid-template-columns: 1fr;
		}
	}
</style>
