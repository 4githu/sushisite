<script lang="ts">
	import hero from '$lib/odi/assets/home-202609/hero.png';
	import heroNew from '$lib/odi/assets/home-202609/hero-new.png';
	import Button from '../common/Button.svelte';
	let { first = false, onstart }: { first?: boolean; onstart: () => void } = $props();
</script>

<section
	class="hero"
	class:first
	style:background-image={`linear-gradient(90deg,rgba(3,8,28,.66),transparent 78%),url(${first ? heroNew : hero})`}
>
	<div>
		{#if first}<p class="eyebrow">START YOUR FIRST PRACTICE</p>{/if}
		<h2>
			{first ? '첫 번째 발표 연습을' : 'AI 청중과 실전처럼,'}<br />{first
				? '시작해보세요'
				: '새로운 발표를 시작해보세요.'}
		</h2>
		<p>발표 자료를 준비하고, AI 청중 앞에서 연습한 뒤<br />상세한 피드백을 받아보세요.</p>
		<Button onclick={onstart}>＋ 새 세션 시작하기 →</Button>{#if first}<small
				>발표 자료 업로드 · AI 청중과 발표 · 결과 확인</small
			>{/if}
	</div>
</section>

<style>
	.hero {
		min-height: 240px;
		border-radius: 12px;
		padding: 34px 40px;
		background-color: #050632;
		background-size: cover;
		background-position: center;
		display: flex;
		align-items: center;
		color: white;
		margin-bottom: 24px;
	}
	.hero.first {
		min-height: 380px;
	}
	.hero h2 {
		font-size: clamp(25px, 2.3vw, 38px);
		line-height: 1.35;
		letter-spacing: -0.035em;
	}
	.hero p {
		font-size: 15px;
		margin: 0 0 22px;
		color: #e5e9ff;
	}
	.hero .eyebrow {
		color: #b9c9f3;
		font-size: 12px;
	}
	.hero small {
		display: block;
		margin-top: 28px;
		color: #c5cde1;
	}
	@media (max-width: 700px) {
		.hero {
			padding: 28px 22px;
			background-position: 65%;
		}
		.hero.first {
			min-height: 320px;
		}
		.hero p {
			max-width: 260px;
		}
	}
</style>
