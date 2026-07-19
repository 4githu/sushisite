<script lang="ts">
	type SliderMode = "node" | "range";

	type Tick = {
		value: number;
		label: string;
	};

	let {
		label,
		mode = "node",

		min,
		max,
		step,

		majorTicks,

		value = $bindable(min),

		showValue = false,
		valueSuffix = "",
		showCurrentTick = false
	}: {
		label?: string;

		mode?: SliderMode;

		min: number;
		max: number;
		step: number;

		majorTicks: Tick[];

		value?: number;

		showValue?: boolean;
		valueSuffix?: string;

		showCurrentTick?: boolean;
	} = $props();

	const progress = $derived(
		((value - min) / (max - min)) * 100
	);

	function left(v: number) {
		return `${((v - min) / (max - min)) * 100}%`;
	}

	const styleVars = $derived(
		`--progress:${progress}%;`
	);

	const minorTicks = $derived.by(() => {
		if (mode === "node") return [];

		return majorTicks.slice(0, -1).map((tick, index) => ({
			value: (tick.value + majorTicks[index + 1].value) / 2
		}));
	});

	function isPassed(v: number) {
		return v <= value;
	}
</script>

<div class="slider">

	{#if label}

		<div class="header">

			<p class="text-title-small">
				{label}
			</p>

			{#if showValue}

				<p class="text-title-small current-value">
					{value}{valueSuffix}
				</p>

			{/if}

		</div>

	{/if}

	<div
		class="track-area"
		style={styleVars}
	>

		<div class="track"></div>

		<div class="progress"></div>

		<div class="thumb"></div>

		{#each majorTicks as tick}

			<div
				class="major"
				class:passed={isPassed(tick.value)}
				class:hidden={!showCurrentTick && tick.value === value}
				style:left={left(tick.value)}
			></div>

		{/each}

		{#if mode === "range"}

			{#each minorTicks as tick}

				<div
					class="minor"
					class:passed={isPassed(tick.value)}
					style:left={left(tick.value)}
				></div>

			{/each}

		{/if}

		<input
			type="range"
			min={min}
			max={max}
			step={step}
			bind:value
		/>

	</div>

	<div class="labels">

		{#each majorTicks as tick, index}

			<span
				class="text-caption-medium slider-label"
				class:active={tick.value === value}
				class:first={index === 0}
				class:last={index === majorTicks.length - 1}
				style:left={left(tick.value)}
			>
				{tick.label}
			</span>

		{/each}

	</div>

</div>

<style>
	.slider {
		width: 100%;

		display: inline-flex;
		flex-direction: column;

		gap: var(--space-4);
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.current-value {
		color: var(--primary);
	}

	.track-area {
		position: relative;

		height: 32px;

		--progress: 0%;
	}

	.track {
		position: absolute;

		top: 15px;
		left: 0;
		right: 0;

		height: 2px;

		background: var(--cool-grey-light-active);
	}

	.progress {
		position: absolute;

		top: 15px;
		left: 0;

		width: var(--progress);
		height: 2px;

		background: var(--primary);
	}

	.thumb {
		position: absolute;

		left: var(--progress);
		top: 15px;

		transform: translate(-50%, -50%);

		width: 30px;
		height: 30px;

		border-radius: var(--radius-full);

		background: var(--primary);

		z-index: 4;

		pointer-events: none;
	}
		.major,
	.minor {
		position: absolute;

		top: 15px;

		transform: translate(-50%, -50%);

		border-radius: var(--radius-full);

		pointer-events: none;

		z-index: 2;

		transition:
			background var(--transition-fast),
			opacity var(--transition-fast);
	}

	.major {
		width: 10px;
		height: 10px;

		background: var(--cool-grey-light-active);
	}

	.minor {
		width: 6px;
		height: 6px;

		background: var(--cool-grey-light-active);
	}

	.major.passed,
	.minor.passed {
		background: var(--primary);
	}

	.major.hidden {
		opacity: 0;
	}

	input {
		position: absolute;

		inset: 0;

		width: 100%;
		height: 32px;

		margin: 0;

		opacity: 0;

		cursor: pointer;

		z-index: 5;

		appearance: none;
		-webkit-appearance: none;
	}

	input::-webkit-slider-runnable-track {
		height: 32px;

		background: transparent;
	}

	input::-webkit-slider-thumb {
		appearance: none;
		-webkit-appearance: none;

		width: 30px;
		height: 30px;
	}

	input::-moz-range-track {
		height: 32px;

		background: transparent;

		border: none;
	}

	input::-moz-range-thumb {
		width: 30px;
		height: 30px;

		border: none;

		background: transparent;
	}

	.labels {
		position: relative;

		height: 24px;
	}

	.slider-label {
		position: absolute;

		transform: translateX(-50%);

		color: var(--text-secondary);

		white-space: nowrap;

		transition: color var(--transition-fast);
	}

	.slider-label.active {
		color: var(--primary);
	}

	.slider-label.first {
		transform: none;
	}

	.slider-label.last {
		transform: translateX(-100%);
	}
</style>