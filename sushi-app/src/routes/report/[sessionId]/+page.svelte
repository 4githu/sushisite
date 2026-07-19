<script>
  import { page } from "$app/state";
  import { onMount } from "svelte";
  import { getSessionResult } from "$lib/api/sessionApi";

  let sessionId = $derived(page.params.sessionId);

  let result = $state(null);
  let loading = $state(true);
  let errorMessage = $state("");

  onMount(async () => {
    try {
      result = await getSessionResult(sessionId);
    } catch (error) {
      errorMessage = error.message;
    } finally {
      loading = false;
    }
  });
</script>

<main>
  <h1>결과 화면</h1>
  <p>Session ID: {sessionId}</p>

  {#if loading}
    <p>결과 불러오는 중...</p>
  {:else if errorMessage}
    <p>{errorMessage}</p>
  {:else if result}
    <h2>Unity에서 입력한 텍스트</h2>
    <p>{result.text}</p>

    <h2>원본 데이터</h2>
    <pre>{JSON.stringify(result, null, 2)}</pre>
  {:else}
    <p>결과가 없습니다.</p>
  {/if}
</main>