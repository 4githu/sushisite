<script lang="ts">
	let {
		score,
		label = '종합 점수',
		tone = 'lime'
	}: {
		score?: number | null;
		label?: string;
		tone?: 'lime' | 'green' | 'blue' | 'red';
	} = $props();

	const normalized = $derived(Math.max(0, Math.min(100, score ?? 0)));
	const dash = $derived(`${normalized}, 100`);
</script>

<div class={`score-dial ${tone}`}>
	<svg viewBox="0 0 42 42" aria-hidden="true">
		<circle class="track" cx="21" cy="21" r="15.9" />
		<circle class="value" cx="21" cy="21" r="15.9" stroke-dasharray={dash} />
	</svg>
	<div class="score-content">
		<strong>{score == null ? '-' : score.toFixed(1)}</strong>
		<span>{label}</span>
	</div>
</div>

<style>
	.score-dial {
		position: relative;
		display: grid;
		width: 168px;
		aspect-ratio: 1;
		place-items: center;
		border-radius: 50%;
		background: #ffffff;
		box-shadow: 0 20px 60px rgba(7, 1, 0, 0.1);
	}

	svg {
		position: absolute;
		inset: 10px;
		width: calc(100% - 20px);
		height: calc(100% - 20px);
		transform: rotate(-90deg);
	}

	circle {
		fill: none;
		stroke-width: 3.8;
	}

	.track {
		stroke: #e5e4e4;
	}

	.value {
		stroke: #daff1c;
		stroke-linecap: round;
	}

	.green .value {
		stroke: #59d26b;
	}

	.blue .value {
		stroke: #4088ee;
	}

	.red .value {
		stroke: #ff3938;
	}

	.score-content {
		position: relative;
		display: grid;
		gap: 4px;
		text-align: center;
	}

	strong {
		color: #070100;
		font-size: 34px;
		font-weight: 700;
		letter-spacing: 0;
	}

	span {
		color: rgba(7, 1, 0, 0.58);
		font-size: 13px;
		font-weight: 600;
	}
</style>
