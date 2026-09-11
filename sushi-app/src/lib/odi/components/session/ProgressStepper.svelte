<script lang="ts">
	import StepIndicator from './StepIndicator.svelte';

	type Step = {
		label: string;
	};

	type StepStatus = 'inactive' | 'active' | 'done';

	let {
		steps = [],
		currentStep = 0
	}: {
		steps?: Step[];
		currentStep?: number;
	} = $props();

	function getStatus(index: number): StepStatus {
		if (index < currentStep) return 'done';
		if (index === currentStep) return 'active';
		return 'inactive';
	}
</script>

<div class="progress-stepper">
	{#each steps as step, index}
		<div class="step-wrapper">
			<StepIndicator step={index + 1} label={step.label} status={getStatus(index)} />

			{#if index < steps.length - 1}
				<div class="connector" class:completed={index <= currentStep}></div>
			{/if}
		</div>
	{/each}
</div>

<style>
	.progress-stepper {
		width: 100%;

		display: flex;
		align-items: flex-start;

		padding: clamp(20px, 2vw, 31px) clamp(18px, 2.6vw, 40px);

		background: var(--surface);

		border-radius: var(--radius-md);

		box-shadow: var(--shadow-sm);
	}

	@media (max-width: 640px) {
		.progress-stepper {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 20px 12px;
			padding: 20px 14px;
		}

		.step-wrapper {
			min-width: 0;
		}

		.connector {
			display: none;
		}
	}

	.step-wrapper {
		display: flex;
		align-items: flex-start;
		flex: 1;
	}

	.connector {
		flex: 1;

		height: 1px;

		margin-top: 20px;

		background: var(--border);

		transition: background var(--transition-fast);
	}

	.connector.completed {
		background: var(--primary);
	}
</style>
