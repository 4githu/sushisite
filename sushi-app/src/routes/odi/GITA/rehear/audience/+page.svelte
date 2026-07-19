<script lang="ts">
	import Icon from '../_components/Icon.svelte';
	import PageHeader from '../_components/PageHeader.svelte';
	import RangeScale from '../_components/RangeScale.svelte';
	import StepIndicator from '../_components/StepIndicator.svelte';

	const personas = [
		{ title: '일반 청중', detail: '비전공자 중심' },
		{ title: '학생 중심', detail: '관련 전공 학생' },
		{ title: '심사위원 중심', detail: '교수 및 평가위원' },
		{ title: '혼합', detail: '다양한 청중 구성' }
	];

	let selectedPersona = $state('일반 청중');
</script>

<div class="rehear-page">
	<PageHeader
		title="AI 청중 설정"
		description="청중 페르소나를 설정하여 원하는 발표 분위기를 구성할 수 있어요."
	/>

	<StepIndicator currentStep={3} />

	<div class="rehear-grid">
		<section class="rehear-card" aria-label="AI 청중 설정 입력">
			<h2 class="rehear-section-title compact">
				<span class="rehear-title-icon"><Icon name="document" size={21} /></span>
				청중 유형
			</h2>
			<p class="rehear-section-help">청중 유형을 선택하면 추천 설정이 자동 적용됩니다.</p>

			<div class="rehear-audience-types" role="radiogroup" aria-label="청중 유형">
				{#each personas as persona}
					<button
						type="button"
						class="rehear-audience-option"
						class:active={selectedPersona === persona.title}
						aria-pressed={selectedPersona === persona.title}
						onclick={() => (selectedPersona = persona.title)}
					>
						<Icon name="upload" size={34} />
						<span>
							<strong>{persona.title}</strong>
							<span>{persona.detail}</span>
						</span>
					</button>
				{/each}
			</div>

			<h2 class="rehear-section-title compact">
				<span class="rehear-title-icon"><Icon name="document" size={21} /></span>
				청중 규모
			</h2>
			<p class="rehear-section-help">
				발표에 참여하는 청중의 인원 수를 설정하세요. 발표 기본 정보 시에 설정한 청중 규모가
				연동됩니다.
			</p>
			<RangeScale value={20} name="청중 규모" />

			<div class="rehear-dual-scale">
				<div class="rehear-level-scale">
					<h3>전문성 수준</h3>
					<p>청중의 발표 주제에 대한 전문성을 설정하세요.</p>
					<div class="rehear-level-line" aria-hidden="true"></div>
					<div class="rehear-level-labels">
						<span>낮음</span>
						<span>중간</span>
						<span>높음</span>
					</div>
				</div>

				<div class="rehear-level-scale">
					<h3>관심도 수준</h3>
					<p>청중이 발표 주제에 가지는 관심도를 설정하세요.</p>
					<div class="rehear-level-line" aria-hidden="true"></div>
					<div class="rehear-level-labels">
						<span>낮음</span>
						<span>중간</span>
						<span>높음</span>
					</div>
				</div>
			</div>
		</section>

		<aside class="rehear-tip-card" aria-label="청중 페르소나 선택 팁">
			<h2>청중 페르소나 선택 TIP</h2>
			<div class="rehear-tip-list">
				<div class="rehear-tip-row">
					<span class="rehear-tip-icon"><Icon name="wand" size={28} /></span>
					<p>
						<strong>AI 추천 설정</strong>
						<span>청중 유형을 선택하면 전문성과 관심도가 추천값으로 자동 설정됩니다.</span>
					</p>
				</div>
				<div class="rehear-tip-row">
					<span class="rehear-tip-icon"><Icon name="sliders" size={28} /></span>
					<p>
						<strong>언제든 수정 가능</strong>
						<span>추천값은 언제든 자유롭게 변경할 수 있어 나만의 맞춤 청중을 만들 수 있어요.</span>
					</p>
				</div>
				<div class="rehear-tip-row">
					<span class="rehear-tip-icon"><Icon name="users" size={28} /></span>
					<p>
						<strong>청중 규모의 중요성</strong>
						<span>청중 규모가 클수록 다양한 반응과 질문을 경험할 수 있습니다.</span>
					</p>
				</div>
				<div class="rehear-tip-row">
					<span class="rehear-tip-icon"><Icon name="target" size={28} /></span>
					<p>
						<strong>발표 목적에 맞게 선택</strong>
						<span
							>발표 목적과 강의/학회 상황에 맞는 청중 구성을 선택하면 더욱 현실적인 발표 연습이
							가능합니다.</span
						>
					</p>
				</div>
			</div>
		</aside>
	</div>

	<div class="rehear-actions">
		<a class="rehear-secondary-button" href="/rehear/presentation/setup/upload">이전 단계</a>
		<a class="rehear-primary-button" href="/rehear/presentation/setup/confirm">
			<span>다음 단계</span>
			<Icon name="arrow-right" size={22} />
		</a>
	</div>
</div>
