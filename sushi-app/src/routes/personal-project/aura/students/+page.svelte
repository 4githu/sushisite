<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	onMount(() => goto('/personal-project/aura/schools', { replaceState: true }));
</script>

<p>학교별 리포트 화면으로 이동하는 중입니다…</p>
