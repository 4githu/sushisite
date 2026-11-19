<script lang="ts">
	import CalendarWorkspace from '$lib/personal-project/shared/CalendarWorkspace.svelte';
	import CaptureList from '$lib/personal-project/shared/CaptureList.svelte';
</script>

<CalendarWorkspace initialView="tasks" />
<div class="captured-tasks"><CaptureList tasksOnly /></div>

<style>
	.captured-tasks {
		margin: 32px auto 0;
		max-width: 1280px;
		padding-top: 24px;
		border-top: 1px solid var(--ondo-line);
	}
</style>
