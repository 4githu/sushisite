<script lang="ts">
	import Icon from '../_components/Icon.svelte';
	import PageHeader from '../_components/PageHeader.svelte';
	import PresentationScene from '../_components/PresentationScene.svelte';

	const stats = [
		{ label: '발표 시간', value: '15분' },
		{ label: '발표 환경', value: '세미나실' },
		{ label: '청중 페르소나', value: '일반 청중' },
		{ label: '청중 규모', value: '일반적' }
	];
</script>

<div class="rehear-page">
	<PageHeader
		title="Ready for Re:hear 🌟"
		description="모든 설정이 완료되었어요. 대기 중인 AI 면접관과 함께 실전 같은 면접 연습을 시작해보세요!"
	/>

	<p class="rehear-confirm-summary">
		발표 정보<br />
		AI 시대의 커뮤니케이션 전략 / 발표 목적 - 연구 결과 공유
	</p>

	<section class="rehear-confirm-card" aria-label="세션 확인">
		<div class="rehear-confirm-scene-wrap">
			<PresentationScene />
		</div>

		<div class="rehear-stats">
			{#each stats as stat}
				<div class="rehear-stat">
					<Icon name="upload" size={32} strokeWidth={2.2} />
					<span>{stat.label}</span>
					<strong>{stat.value}</strong>
				</div>
			{/each}
		</div>
	</section>

	<p class="rehear-start-note">클릭하면 가상 발표 환경으로 이동하여 세션을 시작합니다.</p>

	<div class="rehear-start-button">
		<a class="rehear-primary-button" href="/playground">
			<Icon name="goggles" size={30} strokeWidth={2.4} />
			<span>시작하기</span>
		</a>
	</div>
</div>
