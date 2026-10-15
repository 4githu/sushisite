<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	onMount(() => goto('/personal-project/calendar/boards', { replaceState: true }));
</script>

<a href="/personal-project/calendar/boards">게시판으로 이동</a>
