<script lang="ts">
	import Icon from '../../_components/Icon.svelte';
	import PageHeader from '../../_components/PageHeader.svelte';
	import RangeScale from '../../_components/RangeScale.svelte';
	import StepIndicator from '../../_components/StepIndicator.svelte';

	let title = $state('');
	let purpose = $state('연구 결과 공유');
	let language = $state('한국어');
	let duration = $state('10분');
	let environment = $state('세미나실');
	let questions = $state('3개');
</script>

<div class="rehear-page">
	<PageHeader
		title="발표 기본 정보"
		description="실전과 같은 환경을 설정하고, AI 면접관과 함께 연습을 시작해요."
	/>

	<StepIndicator currentStep={1} />

	<section class="rehear-card" aria-labelledby="basic-info-title">
		<h2 id="basic-info-title" class="rehear-section-title">발표 기본 정보</h2>

		<div class="rehear-form-grid">
			<div class="rehear-field">
				<label for="presentation-title">발표 제목 <span class="rehear-required">*</span></label>
				<input
					id="presentation-title"
					class="rehear-input"
					bind:value={title}
					placeholder="예) AI 시대의 커뮤니케이션 전략"
				/>
			</div>

			<div class="rehear-field">
				<label for="presentation-purpose">발표 목적 <span class="rehear-required">*</span></label>
				<select id="presentation-purpose" class="rehear-select" bind:value={purpose}>
					<option>연구 결과 공유</option>
					<option>수업 발표</option>
					<option>아이디어 제안</option>
					<option>프로젝트 보고</option>
				</select>
			</div>

			<div class="rehear-field">
				<label for="presentation-language">발표 언어</label>
				<select id="presentation-language" class="rehear-select" bind:value={language}>
					<option>한국어</option>
					<option>English</option>
				</select>
			</div>

			<div class="rehear-field">
				<label for="presentation-duration">발표 시간 <span class="rehear-required">*</span></label>
				<select id="presentation-duration" class="rehear-select" bind:value={duration}>
					<option>10분</option>
					<option>15분</option>
					<option>20분</option>
					<option>30분</option>
				</select>
			</div>

			<div class="rehear-field rehear-span-2">
				<span class="rehear-label">발표 환경 <span class="rehear-required">*</span></span>
				<div class="rehear-segmented" role="radiogroup" aria-label="발표 환경">
					{#each ['강의실', '세미나실', '학회 발표장'] as option}
						<button
							type="button"
							class="rehear-choice"
							class:active={environment === option}
							aria-pressed={environment === option}
							onclick={() => (environment = option)}
						>
							<span>ㅇ</span>
							{option}
						</button>
					{/each}
				</div>
			</div>

			<div class="rehear-field">
				<span class="rehear-label">질의 응답 개수 <span class="rehear-required">*</span></span>
				<div class="rehear-segmented" role="radiogroup" aria-label="질의 응답 개수">
					{#each ['1개', '2개', '3개'] as option}
						<button
							type="button"
							class="rehear-choice"
							class:active={questions === option}
							aria-pressed={questions === option}
							onclick={() => (questions = option)}
						>
							{option}
						</button>
					{/each}
				</div>
			</div>

			<div class="rehear-field rehear-span-2">
				<span class="rehear-scale-label">청중 규모</span>
				<RangeScale value={20} name="청중 규모" />
			</div>
		</div>
	</section>

	<div class="rehear-actions">
		<a class="rehear-secondary-button" href="/rehear">이전 단계</a>
		<a class="rehear-primary-button" href="/rehear/presentation/setup/upload">
			<span>다음 단계</span>
			<Icon name="arrow-right" size={22} />
		</a>
	</div>
</div>
