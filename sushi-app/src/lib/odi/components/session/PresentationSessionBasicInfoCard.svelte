<!-- src/lib/odi/components/session/PresentationSessionBasicInfoCard.svelte -->
<script lang="ts">
	import { locale, copy } from "$lib/odi/i18n";
	import SurfaceCard from "$lib/odi/components/common/SurfaceCard.svelte";
	import TextInput from "$lib/odi/components/common/TextInput.svelte";
	import SessionSelect from "$lib/odi/components/session/SessionSelect.svelte";
	import SegmentedControl from "$lib/odi/components/session/SegmentedControl.svelte";
	import SessionSlider from "$lib/odi/components/session/SessionSlider.svelte";
	import {
		formatDurationInput,
		minutesToSeconds,
		roundDuration,
		secondsToMinutes,
		type DurationUnit
	} from "$lib/odi/utils/duration";
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

	const purposeItems = $derived([
		{ label: copy($locale, "프로젝트 목적"), value: "프로젝트 목적" },
		{ label: copy($locale, "연구 결과 공유"), value: "연구 결과 공유" },
		{ label: copy($locale, "프로젝트 발표"), value: "프로젝트 발표" },
		{ label: copy($locale, "사업 제안"), value: "사업 제안" },
		{ label: copy($locale, "수업 발표"), value: "수업 발표" },
		{ label: copy($locale, "성과 보고"), value: "성과 보고" }
	]);

	const languageItems = $derived([
		{ label: copy($locale, "한국어"), value: "한국어" },
		{ label: copy($locale, "영어"), value: "영어" }
	]);

	const durationItems = $derived([
		{ label: copy($locale, "2분"), value: "2" },
		{ label: copy($locale, "5분"), value: "5" },
		{ label: copy($locale, "10분"), value: "10" },
		{ label: copy($locale, "15분"), value: "15" },
		{ label: copy($locale, "20분"), value: "20" },
		{ label: copy($locale, "30분"), value: "30" },
		{ label: copy($locale, "직접 입력"), value: "custom" }
	]);
	const presetDurations = new Set([2, 5, 10, 15, 20, 30]);
	let customDuration = $state(false);
	let customUnit = $state<DurationUnit>('minutes');
	let customValue = $state('2');
	let customSeconds = $state(120);

	const durationSelectValue = $derived(
		customDuration || !presetDurations.has(durationMinutes) ? 'custom' : String(durationMinutes)
	);

	$effect(() => {
		if (!customDuration && durationMinutes > 0 && !presetDurations.has(durationMinutes)) {
			customSeconds = durationMinutes * 60;
			customValue = formatDurationInput(durationMinutes);
		}
	});

	function selectDuration(event: Event) {
		const value = (event.currentTarget as HTMLSelectElement).value;
		if (value === 'custom') {
			customDuration = true;
			customUnit = 'minutes';
			customSeconds = durationMinutes > 0 ? durationMinutes * 60 : 120;
			customValue = formatDurationInput(customSeconds / 60);
			applyCustomDuration();
			return;
		}

		customDuration = false;
		durationMinutes = Number(value);
	}

	function applyCustomDuration() {
		const numericValue = Number(customValue);
		if (!Number.isFinite(numericValue) || numericValue <= 0) {
			durationMinutes = 0;
			return;
		}

		const roundedValue = roundDuration(numericValue);
		customValue = formatDurationInput(roundedValue);
		customSeconds = customUnit === 'minutes' ? roundedValue * 60 : roundedValue;
		// 기존 JSON의 duration_minutes 필드를 그대로 사용해 이전 코드와 호환합니다.
		durationMinutes = customSeconds / 60;
	}

	function changeCustomUnit(event: Event) {
		const nextUnit = (event.currentTarget as HTMLSelectElement).value as DurationUnit;
		customUnit = nextUnit;
		customValue = formatDurationInput(
			nextUnit === 'minutes' ? secondsToMinutes(customSeconds) : minutesToSeconds(customSeconds / 60)
		);
	}

	const placeItems = $derived([
		{ label: copy($locale, "강의실"), value: "강의실", icon: 강의실콘 },
		{ label: copy($locale, "세미나실"), value: "세미나실", icon: 세미나실콘 },
		{ label: copy($locale, "학회 발표장"), value: "학회 발표장", icon: 학회장콘 }
	]);

	const questionTicks = $derived([
		{ value: 0, label: copy($locale, "0개") },
		{ value: 1, label: copy($locale, "1개") },
		{ value: 2, label: copy($locale, "2개") },
		{ value: 3, label: copy($locale, "3개") },
		{ value: 4, label: copy($locale, "4개") },
		{ value: 5, label: copy($locale, "5개") }
	]);
</script>

<SurfaceCard padding="36px" minHeight="609px">
	<div class="presentation-basic-card">
		<h2 class="text-title-middle">{copy($locale, "발표 기본 정보")}</h2>

		<section class="top-grid">
			<TextInput
				label={copy($locale, "발표 제목")}
				required
				placeholder={copy($locale, "예) AI 시대의 커뮤니케이션 전략")}
				width="100%"
				bind:value={title}
			/>

			<div class="field">
				<div class="label text-body-active">
					<span>{copy($locale, "발표 목적")}</span>
					<span class="required">*</span>
				</div>

				<SessionSelect
					items={purposeItems}
					width="100%"
					placeholder={copy($locale, "발표 목적 선택")}
					bind:value={purpose}
				/>
			</div>

			<div class="field">
				<div class="label text-body-active">{copy($locale, "사용 언어")}</div>

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
						<span>{copy($locale, "발표 시간")}</span>
						<span class="required">*</span>
					</div>

					<SessionSelect
						items={durationItems}
						value={durationSelectValue}
						width="100%"
						icon={알람콘}
						onchange={selectDuration}
					/>

					{#if durationSelectValue === 'custom'}
						<div class="custom-duration-row">
							<input
								class="custom-duration-input text-body-medium"
								type="number"
								inputmode="decimal"
								min="0.01"
								step="0.01"
								aria-label={copy($locale, "직접 입력 발표 시간")}
								bind:value={customValue}
								oninput={applyCustomDuration}
							/>
							<select
								class="custom-duration-unit text-body-medium"
								aria-label={copy($locale, "발표 시간 단위")}
								value={customUnit}
								onchange={changeCustomUnit}
							>
								<option value="minutes">{copy($locale, "분")}</option>
								<option value="seconds">{copy($locale, "초")}</option>
							</select>
						</div>
						<p class="duration-help text-caption-medium">{copy($locale, "소수점 둘째 자리까지 입력할 수 있어요.")}</p>
					{/if}
				</div>

				<div class="field">
					<div class="label text-title-small">
						<span>{copy($locale, "질의 응답 개수")}</span>
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
						<span>{copy($locale, "발표 환경")}</span>
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

	.custom-duration-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 112px;
		gap: var(--space-3);
	}

	.custom-duration-input,
	.custom-duration-unit {
		width: 100%;
		height: 52px;
		padding: 0 var(--space-4);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text-primary);
	}

	.duration-help {
		margin-top: calc(var(--space-2) * -1);
		color: var(--text-secondary);
	}

	@container (max-width: 980px) {
		.top-grid,
		.environment-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
