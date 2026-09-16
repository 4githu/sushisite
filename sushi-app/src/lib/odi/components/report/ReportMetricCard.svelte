<script lang="ts">
	import { scoreGrade, scoreCardLabel } from './reportUtils';
	import { metricEnglish } from './reportViewModel';
	let {
		metric,
		score,
		description
	}: {
		metric: { key: 'engagement' | 'clarity' | 'credibility'; meaning: string; icon: string };
		score?: number;
		description?: string;
	} = $props();
</script>

<article class="metric-card">
	<div class="metric-copy">
		<div class="metric-title">
			<div>
				<h3>{metricEnglish(metric.key)}</h3>
				<small>{scoreCardLabel(metric.key)}</small>
			</div>
		</div>
		<p class="metric-number">
			<strong>{score ?? '--'}</strong><small>/100</small><span
				>{score == null ? '미측정' : scoreGrade(score)}</span
			>
		</p>
		<p>{description ?? metric.meaning}</p>
	</div>
	<div class={`metric-icon ${metric.key}`}>
		<img src={metric.icon} alt="" aria-hidden="true" />
	</div>
</article>

<style>
	.metric-card {
		min-width: 0;
		border: 1px solid #eceef3;
		border-radius: 16px;
		background: #fff;
		box-shadow: 0 2px 10px rgba(5, 6, 50, 0.08);
	}

	.metric-card {
		min-height: 307px;
		padding: 33px 38px 44px 44px;
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 28px;
	}

	.metric-icon {
		width: 167px;
		height: 167px;
		flex: 0 0 167px;
		display: grid;
		place-items: center;
		background: transparent;
	}

	.metric-icon img {
		width: 167px;
		height: 167px;
		object-fit: contain;
	}

	.metric-copy {
		min-width: 0;
		display: grid;
		gap: 8px;
		width: 210px;
	}

	.metric-title {
		display: flex;
		align-items: flex-start;
		gap: 6px;
	}

	.metric-title h3 {
		font-size: 32px;
		font-weight: 600;
	}

	.metric-title small {
		display: block;
		margin-top: 2px;
		color: #030812;
		font-size: 20px;
		font-weight: 400;
	}

	.metric-number {
		display: flex;
		align-items: flex-end;
		gap: 4px;
		color: #636363;
		font-size: 20px;
	}

	.metric-number strong {
		margin-right: 2px;
		color: #111325;
		font-size: 64px;
		font-weight: 600;
	}

	.metric-number small {
		padding-bottom: 12px;
		font-size: 20px;
	}

	.metric-number span {
		align-self: center;
		margin-left: 8px;
		padding: 6px 15px;
		border-radius: 14px;
		background: #d9e0ff;
		color: #03f;
		font-size: 20px;
		white-space: nowrap;
	}

	.metric-copy > p:last-child {
		color: var(--text-secondary);
		font-size: 20px;
		line-height: 1.5;
		word-break: keep-all;
	}

	@container (max-width: 480px) {
		.metric-card {
			flex-direction: column;
		}
	}
</style>
