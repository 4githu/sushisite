<!-- src/lib/odi/components/report/MetricBadge.svelte -->

<script lang="ts">
	let {
		label,
		type = "normal",
		size = "sm"
	}: {
		label: string;
		type?: "good" | "normal" | "bad";
		size?: "sm" | "lg";
	} = $props();
</script>

<span class={`badge ${type} ${size}`}>
	{label}
</span>

<style>
	.badge {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius-full);
		font-weight: var(--font-medium);
		line-height: 1;
		white-space: nowrap;
	}

	.badge.sm {
		min-width: 42px;
		height: 24px;
		padding: 2px 8px;
		font-size: 14px;
	}

	.badge.lg {
		min-width: 48px;
		height: 28px;
		padding: 2px 8px;
		font-size: 17px;
	}

	.badge.good {
		color: #44c699;
		background: rgba(68, 198, 153, 0.15);
	}

	.badge.normal {
		color: #d6a800;
		background: rgba(255, 215, 54, 0.18);
	}

	.badge.bad {
		color: #ff4343;
		background: rgba(255, 67, 67, 0.15);
	}
</style>