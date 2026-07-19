<script>
  import { page } from "$app/state";
  import { saveSessionConfig } from "$lib/api/sessionApi";

  let topic = $state("");
  let presenterName = $state("");
  let durationMin = $state(5);
  let difficulty = $state("normal");

  let saved = $state(false);
  let errorMessage = $state("");

  let sessionId = $derived(page.params.sessionId);

  async function startUnity() {
    errorMessage = "";

    const config = {
      topic,
      presenterName,
      durationMin: Number(durationMin),
      difficulty,
      status: "started"
    };

    try {
      await saveSessionConfig(sessionId, config);
      saved = true;
    } catch (error) {
      errorMessage = error.message;
    }
  }
</script>

<main>
  {#if saved}
    <h1>시작 요청 완료</h1>
    <p>Unity 화면으로 돌아가세요.</p>
    <p>Session ID: {sessionId}</p>
  {:else}
    <h1>발표 설정</h1>
    <p>Session ID: {sessionId}</p>

    <label>
      발표자 이름
      <input bind:value={presenterName} />
    </label>

    <label>
      발표 주제
      <input bind:value={topic} />
    </label>

    <label>
      발표 시간
      <input type="number" bind:value={durationMin} min="1" />
    </label>

    <label>
      난이도
      <select bind:value={difficulty}>
        <option value="easy">easy</option>
        <option value="normal">normal</option>
        <option value="hard">hard</option>
      </select>
    </label>

    <button type="button" onclick={startUnity}>
      시작
    </button>

    {#if errorMessage}
      <p>{errorMessage}</p>
    {/if}
  {/if}
</main>