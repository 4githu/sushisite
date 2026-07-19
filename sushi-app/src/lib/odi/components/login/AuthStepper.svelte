<!-- src/lib/odi/components/login/AuthStepper.svelte -->
<script lang="ts">
	let {
		currentStep = 0,
		steps = []
	}: {
		currentStep?: number;
		steps?: string[];
	} = $props();
</script>

<div class="stepper">
	{#each steps as step, index}
		<div class="step" class:active={index === currentStep} class:done={index < currentStep}>
			<div class="circle text-body-active">{index + 1}</div>
			<p class="text-caption-medium">{step}</p>
		</div>

		{#if index < steps.length - 1}
			<div class="line" class:done={index < currentStep}></div>
		{/if}
	{/each}
</div>

<style>
	.stepper {
		width: 100%;
		min-height: 82px;
		padding: var(--space-5) 120px;
		display: flex;
		align-items: center;
		justify-content: center;
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		background: var(--surface);
		box-shadow: var(--shadow-sm);
	}

	.step {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-2);
		color: var(--text-secondary);
		white-space: nowrap;
	}

	.circle {
		width: 36px;
		height: 36px;
		display: flex;
		align-items: center;
		justify-content: center;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-full);
		background: var(--surface);
		color: var(--text-secondary);
	}

	.step.active .circle,
	.step.done .circle {
		border-color: var(--primary);
		background: var(--primary);
		color: var(--text-on-primary);
	}

	.step.active p,
	.step.done p {
		color: var(--brand-black);
		font-weight: var(--font-bold);
	}

	.line {
		flex: 1;
		max-width: 380px;
		height: 2px;
		margin: 0 var(--space-4) var(--space-8);
		background: var(--cool-grey-light-active);
	}

	.line.done {
		background: var(--primary);
	}
</style>