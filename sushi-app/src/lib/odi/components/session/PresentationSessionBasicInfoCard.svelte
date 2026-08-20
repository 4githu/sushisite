<!-- src/lib/odi/components/session/PresentationSessionBasicInfoCard.svelte -->
<script lang="ts">
	import SurfaceCard from "$lib/odi/components/common/SurfaceCard.svelte";
	import TextInput from "$lib/odi/components/common/TextInput.svelte";
	import SessionSelect from "$lib/odi/components/session/SessionSelect.svelte";
	import SegmentedControl from "$lib/odi/components/session/SegmentedControl.svelte";
	import SessionSlider from "$lib/odi/components/session/SessionSlider.svelte";
	import {
		podium as 세미나실콘,
		school as 학회장콘,
		chair_alt as 강의실콘,
		alarm as 알람콘

	} from "$lib/odi/icons";

	//console.log(알람콘);

	let {
		title = $bindable(""),
		purpose = $bindable(""),
		language = $bindable(""),
		place = $bindable(""),
		durationMinutes = $bindable(0),
		questionCount = $bindable(0)
	}: {
		title?: string;
		purpose?: string;
		language?: string;
		place?: string;
		durationMinutes?: number;
		questionCount?: number;
	} = $props();

	const purposeItems = [
		{ label: "프로젝트 목적", value: "프로젝트 목적" },
		{ label: "연구 결과 공유", value: "연구 결과 공유" },
		{ label: "프로젝트 발표", value: "프로젝트 발표" },
		{ label: "사업 제안", value: "사업 제안" },
		{ label: "수업 발표", value: "수업 발표" },
		{ label: "성과 보고", value: "성과 보고" }
	];

	const languageItems = [
		{ label: "한국어", value: "한국어" },
		{ label: "영어", value: "영어" }
	];

	const durationItems = [
		{ label: "2분", value: "2" },
		{ label: "5분", value: "5" },
		{ label: "10분", value: "10" },
		{ label: "15분", value: "15" },
		{ label: "20분", value: "20" },
		{ label: "30분", value: "30" }
	];

	const placeItems = [
		{ label: "강의실", value: "강의실", icon: 강의실콘 },
		{ label: "세미나실", value: "세미나실", icon: 세미나실콘 },
		{ label: "학회 발표장", value: "학회 발표장", icon: 학회장콘 }
	];

	const questionTicks = [
		{ value: 0, label: "0개" },
		{ value: 1, label: "1개" },
		{ value: 2, label: "2개" },
		{ value: 3, label: "3개" },
		{ value: 4, label: "4개" },
		{ value: 5, label: "5개" }
	];
</script>

<SurfaceCard padding="36px" minHeight="609px">
	<div class="presentation-basic-card">
		<h2 class="text-title-middle">발표 기본 정보</h2>

		<section class="top-grid">
			<TextInput
				label="발표 제목"
				required
				placeholder="예) AI 시대의 커뮤니케이션 전략"
				width="100%"
				bind:value={title}
			/>

			<div class="field">
				<div class="label text-body-active">
					<span>발표 목적</span>
					<span class="required">*</span>
				</div>

				<SessionSelect
					items={purposeItems}
					width="100%"
					placeholder="발표 목적 선택"
					bind:value={purpose}
				/>
			</div>

			<div class="field">
				<div class="label text-body-active">사용 언어</div>

				<SessionSelect
					items={languageItems}
					width="100%"
					bind:value={language}
				/>
			</div>
		</section>

		<section class="environment-grid">
			<div class="left-column">
				<div class="field">
					<div class="label text-body-active">
						<span>발표 시간</span>
						<span class="required">*</span>
					</div>

					<SessionSelect
						items={durationItems}
						value={String(durationMinutes)}
						width="100%"
						icon={알람콘}
						onchange={(event) => durationMinutes = Number((event.currentTarget as HTMLSelectElement).value)}
					/>
				</div>

				<div class="field">
					<div class="label text-title-small">
						<span>질의 응답 개수</span>
						<span class="required">*</span>
					</div>

					<SessionSlider
						mode="node"
						min={0}
						max={5}
						step={1}
						majorTicks={questionTicks}
						showCurrentTick
						bind:value={questionCount}
					/>
				</div>
			</div>

			<div class="right-column">
				<div class="field">
					<div class="label text-title-small">
						<span>발표 환경</span>
						<span class="required">*</span>
					</div>

					<SegmentedControl
						items={placeItems}
						itemWidth="calc((100% - 40px) / 3)"
						bind:selected={place}
					/>
				</div>
			</div>
		</section>
	</div>
</SurfaceCard>

<style>
	.presentation-basic-card {
		container-type: inline-size;
		display: flex;
		flex-direction: column;
		gap: 40px;
	}

	.top-grid {
		display: grid;
		grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr);
		gap: 40px 38px;
		align-items: end;
	}

	.environment-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 40px;
		align-items: start;
	}

	.left-column,
	.right-column,
	.field {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.left-column {
		gap: 32px;
	}

	.label {
		display: flex;
		align-items: center;
		gap: 4px;
		color: var(--text-primary);
	}

	.required {
		color: var(--purple);
	}

	@container (max-width: 980px) {
		.top-grid,
		.environment-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
