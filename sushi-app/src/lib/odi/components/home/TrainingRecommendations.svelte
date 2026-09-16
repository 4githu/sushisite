<script lang="ts">
	import { trainingNames } from '$lib/odi/domain/sessionSummary';
	import { practiceIcon } from '$lib/odi/icons/practice';
	let { ids }: { ids: string[] } = $props();
</script>

<section class="surface">
	<div class="section-head">
		<div>
			<h2>추천 훈련</h2>
			<p class="muted">최근 세션을 바탕으로 필요한 역량을 연습해요.</p>
		</div>
		<a href="/odi/practice">훈련하러 가기 ›</a>
	</div>
	<div class="training-grid">
		{#each ids as id, rowIndex0 (rowIndex0)}<a
				href={`/odi/practice?training=${id}`}
				class="training"
				><img src={practiceIcon(id)} alt="" />
				<div>
					<h3>{trainingNames[id]}</h3>
					<p>짧은 음성 연습으로 한 가지 역량에 집중해 보세요.</p>
					<span>훈련 시작 →</span>
				</div></a
			>{/each}
	</div>
</section>

<style>
	.section-head p {
		font-size: 13px;
		margin-top: -8px;
	}
	.training-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 14px;
	}
	.training {
		display: flex;
		gap: 14px;
		padding: 18px;
		border: 1px solid #dce0ea;
		border-radius: 8px;
	}
	.training img {
		width: 28px;
		height: 28px;
		object-fit: contain;
	}
	.training h3 {
		color: #030812;
		font-size: 15px !important;
	}
	.training p {
		font-size: 12px;
		color: #687185;
	}
	.training span {
		font-size: 13px;
	}
	@media (max-width: 850px) {
		.training-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
