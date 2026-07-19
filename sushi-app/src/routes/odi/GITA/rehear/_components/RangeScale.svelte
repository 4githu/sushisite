<script lang="ts">
	type Marker = {
		value: number;
		label: string;
	};

	let {
		value = 20,
		min = 1,
		max = 50,
		name = '청중 규모',
		markers = [
			{ value: 1, label: '1' },
			{ value: 10, label: '10' },
			{ value: 20, label: '20' },
			{ value: 30, label: '30' },
			{ value: 40, label: '40' },
			{ value: 50, label: '50 +' }
		]
	}: {
		value?: number;
		min?: number;
		max?: number;
		name?: string;
		markers?: Marker[];
	} = $props();

	let selected = $state(20);
	const ticks = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50];

	const position = (tick: number) => `${((tick - min) / (max - min)) * 100}%`;
	const progress = () => ((selected - min) / (max - min)) * 100;

	$effect(() => {
		selected = value;
	});
</script>

<div class="rehear-range" style={`--progress: ${progress()}%`}>
	<div class="rehear-range-track" aria-hidden="true">
		{#each ticks as tick}
			<span
				class="rehear-range-tick"
				class:active={tick <= selected}
				class:selected={tick === selected}
				style={`left: ${position(tick)}`}
			></span>
		{/each}
	</div>
	<input type="range" {min} {max} bind:value={selected} aria-label={name} />
	<div class="rehear-range-labels">
		{#each markers as marker}
			<span class:active={marker.value === selected} style={`left: ${position(marker.value)}`}>
				{marker.label}
			</span>
		{/each}
	</div>
</div>
