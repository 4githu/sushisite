<script lang="ts">
	import StepIndicator from "./StepIndicator.svelte";

	type Step = {
		label: string;
	};

	type StepStatus = "inactive" | "active" | "done";

	let {
		steps = [],
		currentStep = 0
	}: {
		steps?: Step[];
		currentStep?: number;
	} = $props();

	function getStatus(index: number): StepStatus {
		if (index < currentStep) return "done";
		if (index === currentStep) return "active";
		return "inactive";
	}
</script>

<div class="progress-stepper">
	{#each steps as step, index}
		<div class="step-wrapper">
			<StepIndicator
				step={index + 1}
				label={step.label}
				status={getStatus(index)}
			/>

			{#if index < steps.length - 1}
				<div
					class="connector"
					class:completed={index <= currentStep}
				></div>
			{/if}
		</div>
	{/each}
</div>

<style>
	.progress-stepper {
		width: 100%;

		display: flex;
		align-items: flex-start;

		padding: 31px 40px;

		background: var(--surface);

		border-radius: var(--radius-md);

		box-shadow: var(--shadow-sm);
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