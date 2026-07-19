<script lang="ts">
	import Icon from './Icon.svelte';

	const steps = [
		{ number: 1, label: '발표 기본 정보' },
		{ number: 2, label: '자료 업로드' },
		{ number: 3, label: 'AI 청중 설정' },
		{ number: 4, label: '세션 확인' }
	];

	let { currentStep }: { currentStep: number } = $props();

	const statusFor = (step: number) => {
		if (step < currentStep) return 'complete';
		if (step === currentStep) return 'current';
		return 'upcoming';
	};
</script>

<ol class="rehear-stepper" aria-label="Session setup progress">
	{#each steps as step, index}
		<li class="rehear-step">
			{#if index > 0}
				<span
					class="rehear-step-line rehear-step-line-left"
					class:active={step.number <= currentStep}
				></span>
			{/if}
			<span class={`rehear-step-dot ${statusFor(step.number)}`}>
				{#if step.number < currentStep}
					<Icon name="check" size={22} strokeWidth={2.4} />
				{:else}
					{step.number}
				{/if}
			</span>
			{#if index < steps.length - 1}
				<span
					class="rehear-step-line rehear-step-line-right"
					class:active={step.number < currentStep}
				></span>
			{/if}
			<span class={`rehear-step-label ${statusFor(step.number)}`}>{step.label}</span>
		</li>
	{/each}
</ol>
