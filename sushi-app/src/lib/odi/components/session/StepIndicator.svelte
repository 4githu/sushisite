<script lang="ts">
	type Status = "inactive" | "active" | "done";

	let {
		step = 1,
		label = "text",
		status = "inactive"
	}: {
		step?: number;
		label?: string;
		status?: Status;
	} = $props();
</script>

<div class="step-indicator">
	<div
		class="circle"
		class:active={status === "active"}
		class:done={status === "done"}
	>
		{#if status === "done"}
			<svg
				width="24"
				height="24"
				viewBox="0 0 24 24"
				fill="none"
				aria-hidden="true"
			>
				<path
					d="M20.2948 6.29468C20.6843 6.68413 20.6843 7.31556 20.2948 7.70501L10.4142 17.5856C9.63316 18.3667 8.36684 18.3667 7.58579 17.5856L4.20543 14.2053C3.81583 13.8157 3.81583 13.184 4.20543 12.7944C4.59469 12.4052 5.22569 12.4048 5.61543 12.7935L8.29323 15.4648C8.68376 15.8544 9.316 15.8541 9.70624 15.4643L18.8848 6.29434C19.2743 5.90521 19.9055 5.90535 20.2948 6.29468Z"
					fill="white"
				/>
			</svg>
		{:else}
			<span class="step-number">{step}</span>
		{/if}
	</div>

	<span
		class={status === "active"
			? "text-body-active label active"
			: "text-body-medium label inactive"}
	>
		{label}
	</span>
</div>

<style>
	.step-indicator {
		min-width: 120px;

		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 13px;
	}

	.circle {
		width: 40px;
		height: 40px;

		display: flex;
		align-items: center;
		justify-content: center;

		border-radius: var(--radius-full);

		background: var(--surface);
		border: 1px solid var(--border);

		transition:
			background var(--transition-fast),
			border-color var(--transition-fast),
			color var(--transition-fast);
	}

	.circle.active,
	.circle.done {
		background: var(--primary);
		border-color: var(--primary);
	}

	.step-number {
		font-size: 20px;
		font-weight: var(--font-medium);
		color: var(--text-secondary);

		transition: color var(--transition-fast);
	}

	.circle.active .step-number {
		color: var(--text-on-primary);
	}

	.label {
		text-align: center;
		transition: color var(--transition-fast);
	}

	.label.inactive {
		color: var(--text-secondary);
	}

	.label.active {
		color: var(--brand-black);
	}
</style>