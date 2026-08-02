<script lang="ts">
	const endpoints = [
		{
			method: 'GET',
			path: '/pronunciation/health',
			label: '서버 상태 확인',
			body: '입력 없음'
		},
		{
			method: 'POST',
			path: '/pronunciation/analyze',
			label: '문장·발표 분석',
			body: 'audio, mode, session_id, attempt_id, target_text'
		},
		{
			method: 'POST',
			path: '/pronunciation/word',
			label: '글자 LPC 평가',
			body: 'audio, vowel'
		}
	];
</script>

<section class="endpoints" aria-label="봄말 백엔드 API">
	<div>
		<p>Backend Contract</p>
		<h2>봄말이 사용하는 API</h2>
	</div>

	<div class="endpoint-grid">
		{#each endpoints as endpoint}
			<article>
				<span>{endpoint.method}</span>
				<strong>{endpoint.path}</strong>
				<p>{endpoint.label}</p>
				<small>{endpoint.body}</small>
			</article>
		{/each}
	</div>
</section>

<style>
	.endpoints {
		display: grid;
		gap: 18px;
		border-radius: 24px;
		background: #070100;
		padding: 24px;
		color: #fff;
	}

	.endpoints > div:first-child p {
		margin: 0 0 6px;
		color: #daff1c;
		font-size: 13px;
		font-weight: 800;
	}

	h2 {
		margin: 0;
		font-size: 28px;
		font-weight: 800;
		letter-spacing: 0;
	}

	.endpoint-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 12px;
	}

	article {
		display: grid;
		gap: 8px;
		border: 1px solid rgba(255, 255, 255, 0.14);
		border-radius: 18px;
		background: rgba(255, 255, 255, 0.08);
		padding: 16px;
	}

	span {
		width: fit-content;
		border-radius: 999px;
		background: #daff1c;
		color: #070100;
		font-size: 12px;
		font-weight: 900;
		padding: 6px 10px;
	}

	strong {
		color: #fff;
		font-size: 16px;
		font-weight: 800;
		word-break: break-word;
	}

	p,
	small {
		margin: 0;
		color: rgba(255, 255, 255, 0.72);
		line-height: 1.45;
	}

	small {
		color: rgba(255, 255, 255, 0.52);
		font-size: 12px;
	}

	@media (max-width: 840px) {
		.endpoint-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
