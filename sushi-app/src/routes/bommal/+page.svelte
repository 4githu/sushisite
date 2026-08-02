<script lang="ts">
	import BommalAnalyzer from '$lib/bommal/components/BommalAnalyzer.svelte';
	import EndpointSummary from '$lib/bommal/components/EndpointSummary.svelte';
	import logo from '$lib/bommal/assets/logo.png';

	const backendDocsUrl = `${import.meta.env.VITE_SUSHIFASTURL || 'http://localhost:8000'}/docs`;
</script>

<svelte:head>
	<title>봄말 | 시각적 발음 피드백</title>
	<meta
		name="description"
		content="봄말은 STT 문장 분석과 LPC 글자 평가를 결합한 한국어 발음 학습 서비스입니다."
	/>
</svelte:head>

<main class="bommal-page">
	<section class="hero">
		<nav aria-label="봄말 내비게이션">
			<a class="brand" href="/bommal">
				<img src={logo} alt="봄말" />
			</a>
			<div class="nav-links">
				<a href="#analyzer">평가하기</a>
				<a href="#api">API</a>
			</div>
		</nav>

		<div class="hero-grid">
			<div class="hero-copy">
				<p>보다 그리고 말하다</p>
				<h1>봄말</h1>
				<strong>한국어 발음을 눈으로 확인하고, 다시 말하며 고치는 연습 경험</strong>
				<div class="hero-actions">
					<a href="#analyzer">음성 평가 시작</a>
					<a class="ghost" href={backendDocsUrl} target="_blank" rel="noreferrer">백엔드 문서 확인</a>
				</div>
			</div>

			<div class="hero-board" aria-label="봄말 평가 흐름">
				<div class="flow-card active">
					<span>01</span>
					<strong>음성 업로드</strong>
					<p>Unity 또는 웹에서 녹음 파일을 보냅니다.</p>
				</div>
				<div class="flow-card">
					<span>02</span>
					<strong>STT·LPC 분석</strong>
					<p>문장은 Deepgram STT, 글자는 LPC 곡선으로 평가합니다.</p>
				</div>
				<div class="flow-card accent">
					<span>03</span>
					<strong>시각 피드백</strong>
					<p>오류 위치, 조음 Tip, LPC 그래프 값을 반환합니다.</p>
				</div>
			</div>
		</div>
	</section>

	<section id="analyzer">
		<BommalAnalyzer />
	</section>

	<section id="api">
		<EndpointSummary />
	</section>
</main>

<style>
	:global(body) {
		margin: 0;
		background: #eefcef;
		font-family:
			Pretendard,
			Inter,
			-apple-system,
			BlinkMacSystemFont,
			system-ui,
			sans-serif;
	}

	:global(*) {
		box-sizing: border-box;
	}

	.bommal-page {
		min-height: 100vh;
		background:
			linear-gradient(135deg, rgba(218, 255, 28, 0.58), rgba(255, 255, 255, 0.78) 42%),
			#eefcef;
		color: #070100;
	}

	.hero,
	.bommal-page > section {
		width: min(1180px, calc(100% - 40px));
		margin: 0 auto;
	}

	.hero {
		display: grid;
		gap: 52px;
		padding: 28px 0 34px;
	}

	nav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 20px;
	}

	.brand {
		display: inline-flex;
		align-items: center;
		width: 144px;
	}

	.brand img {
		width: 100%;
		height: auto;
		object-fit: contain;
	}

	.nav-links {
		display: flex;
		gap: 10px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.72);
		padding: 8px;
		box-shadow: 0 16px 48px rgba(7, 1, 0, 0.08);
	}

	.nav-links a {
		border-radius: 999px;
		color: rgba(7, 1, 0, 0.7);
		font-size: 14px;
		font-weight: 800;
		padding: 10px 14px;
		text-decoration: none;
	}

	.nav-links a:hover {
		background: #daff1c;
		color: #070100;
	}

	.hero-grid {
		display: grid;
		grid-template-columns: minmax(360px, 0.95fr) minmax(420px, 1.05fr);
		gap: 34px;
		align-items: stretch;
	}

	.hero-copy {
		display: flex;
		min-height: 460px;
		flex-direction: column;
		justify-content: center;
		border-radius: 28px;
		background: #ffffff;
		padding: 44px;
		box-shadow: 0 24px 90px rgba(7, 1, 0, 0.1);
	}

	.hero-copy p {
		margin: 0 0 10px;
		color: #59d26b;
		font-size: 16px;
		font-weight: 900;
	}

	h1 {
		margin: 0;
		color: #070100;
		font-size: 88px;
		font-weight: 900;
		letter-spacing: 0;
		line-height: 0.94;
	}

	.hero-copy strong {
		display: block;
		max-width: 520px;
		margin-top: 22px;
		color: rgba(7, 1, 0, 0.68);
		font-size: 24px;
		font-weight: 700;
		letter-spacing: 0;
		line-height: 1.35;
	}

	.hero-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 12px;
		margin-top: 34px;
	}

	.hero-actions a {
		border-radius: 999px;
		background: #070100;
		color: #fff;
		font-size: 16px;
		font-weight: 900;
		padding: 15px 20px;
		text-decoration: none;
	}

	.hero-actions .ghost {
		background: #daff1c;
		color: #070100;
	}

	.hero-board {
		display: grid;
		gap: 16px;
		border-radius: 28px;
		background: #070100;
		padding: 28px;
		box-shadow: 0 24px 90px rgba(7, 1, 0, 0.18);
	}

	.flow-card {
		display: grid;
		gap: 8px;
		border: 1px solid rgba(255, 255, 255, 0.14);
		border-radius: 22px;
		background: rgba(255, 255, 255, 0.08);
		color: #ffffff;
		padding: 24px;
	}

	.flow-card.active {
		background: #ffffff;
		color: #070100;
	}

	.flow-card.accent {
		background: linear-gradient(135deg, #daff1c, #ffffff);
		color: #070100;
	}

	.flow-card span {
		width: fit-content;
		border-radius: 999px;
		background: #4088ee;
		color: #ffffff;
		font-size: 13px;
		font-weight: 900;
		padding: 7px 11px;
	}

	.flow-card strong {
		color: inherit;
		font-size: 26px;
		font-weight: 900;
		letter-spacing: 0;
	}

	.flow-card p {
		margin: 0;
		color: currentColor;
		font-size: 16px;
		font-weight: 600;
		line-height: 1.5;
		opacity: 0.68;
	}

	.bommal-page > section {
		padding: 28px 0;
	}

	@media (max-width: 920px) {
		.hero-grid {
			grid-template-columns: 1fr;
		}

		.hero-copy {
			min-height: auto;
			padding: 32px;
		}

		h1 {
			font-size: 64px;
		}
	}

	@media (max-width: 620px) {
		.hero,
		.bommal-page > section {
			width: min(100% - 24px, 1180px);
		}

		nav {
			align-items: flex-start;
			flex-direction: column;
		}

		.nav-links {
			width: 100%;
			justify-content: space-between;
		}

		h1 {
			font-size: 52px;
		}

		.hero-copy strong {
			font-size: 20px;
		}
	}
</style>
