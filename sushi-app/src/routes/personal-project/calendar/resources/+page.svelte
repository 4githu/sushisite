<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	onMount(() => {
		void goto('/personal-project/calendar/boards', { replaceState: true });
	});
</script>

<p>게시판으로 이동합니다.</p>
