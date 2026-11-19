<script lang="ts">
  import { onMount } from 'svelte';
  type Entry = { id: string; korean: string; english: string; section: string; path: string };
  let entries = $state<Entry[]>([]), values = $state<Record<string,string>>({}), saved = $state<Record<string,string>>({});
  let version = $state(0), email = $state(''), password = $state(''), account = $state('');
  let reviewers = $state<string[]>([]), newReviewer = $state(''), showReviewers = $state(false), reviewerStatus = $state('');
  let query = $state(''), selectedId = $state(''), busy = $state(''), message = $state(''), accessError = $state(''), checking = $state(true);
  let previewFrame = $state<HTMLIFrameElement>(), previewDocument: Document | null = null;
  let picking = $state(false), previewMessage = $state(''), matches = $state<Entry[]>([]);
  let previewViewport = $state<HTMLDivElement>(), viewportWidth = $state(700), viewportHeight = $state(520);
  let manualZoom = $state<number | null>(null);
  const previewWidth = 1280;
  const zoom = $derived(manualZoom ?? Math.min(1, viewportWidth / previewWidth));
  function changeZoom(delta: number) {
    manualZoom = Math.max(0.25, Math.min(1.5, Math.round((zoom + delta) * 20) / 20));
  }
  const filtered = $derived(entries.filter(e => `${e.korean}\n${values[e.id] ?? e.english}`.toLowerCase().includes(query.trim().toLowerCase())));
  const selected = $derived(entries.find(e => e.id === selectedId));
  const dirty = $derived(entries.filter(e => values[e.id] !== saved[e.id]).length);
  const normalize = (s: string) => s.replace(/\s+/g, ' ').trim();
  async function load(preserve = false) {
    checking = true; accessError = '';
    try {
      const response = await fetch('/rehear-translations?review=1', {cache:'no-store'});
      if (!response.ok) { account = ''; accessError = response.status === 403 ? '번역 검수 권한이 있는 계정으로 로그인해 주세요.' : '검수 화면을 불러오지 못했습니다.'; return; }
      const data = await response.json();
      const nextSaved: Record<string,string> = {};
      for (const entry of data.entries as Entry[]) nextSaved[entry.id] = data.overrides[entry.id] ?? entry.english;
      const nextValues = {...nextSaved};
      if (preserve) for (const id of Object.keys(values)) if (values[id] !== saved[id]) nextValues[id] = values[id];
      entries = data.entries; version = data.version; account = data.email; reviewers = data.reviewers ?? []; saved = nextSaved; values = nextValues;
      if (!selectedId || !entries.some(e => e.id === selectedId)) selectedId = entries[0]?.id ?? '';
    } catch { accessError = '서버에 연결할 수 없습니다. 연결을 확인해 주세요.'; }
    finally { checking = false; }
  }
  async function login() {
    busy = 'login'; accessError = '';
    try {
      const response = await fetch('/auth/login', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email:email.trim(),password})});
      const result = await response.json();
      if (!response.ok || !result.success) { accessError = '이메일 또는 비밀번호를 확인해 주세요.'; return; }
      password = ''; await load();
    } catch { accessError = '로그인 서버에 연결할 수 없습니다.'; }
    finally { busy = ''; }
  }
  async function save(entry: Entry, next = false) {
    if (busy || !values[entry.id]?.trim() || values[entry.id] === saved[entry.id]) return;
    busy = entry.id; message = '';
    try {
      const response = await fetch('/rehear-translations', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({id:entry.id,english:values[entry.id],version})});
      const data = await response.json();
      if (response.status === 409) { await load(true); message = '다른 변경이 먼저 저장됐어요. 내용을 확인한 뒤 다시 저장해 주세요.'; return; }
      if (!response.ok) { message = data.error || '저장하지 못했습니다.'; return; }
      version = data.version;
      for (const e of entries) saved[e.id] = data.overrides[e.id] ?? e.english;
      values[entry.id] = saved[entry.id]; message = '저장되어 사이트에 반영됐어요.';
      if ('BroadcastChannel' in window) { const channel = new BroadcastChannel('rehear-translation-updates'); channel.postMessage('updated'); channel.close(); }
      if (next) move(1);
    } catch { message = '연결을 확인한 뒤 다시 저장해 주세요.'; }
    finally { busy = ''; }
  }
  function select(entry: Entry) { selectedId = entry.id; message = ''; matches = []; }
  function move(delta: number) {
    const index = filtered.findIndex(e => e.id === selectedId);
    const entry = filtered[index + delta]; if (entry) select(entry);
  }
  async function changeReviewer(action: 'add-reviewer' | 'remove-reviewer', target: string) {
    busy = 'reviewer'; reviewerStatus = '';
    try {
      const response = await fetch('/rehear-translations', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action,email:target})});
      const data = await response.json();
      if (!response.ok) { reviewerStatus = data.error || '권한을 변경하지 못했습니다.'; return; }
      reviewers = data.reviewers; newReviewer = ''; reviewerStatus = action === 'add-reviewer' ? '검수자를 추가했습니다.' : '검수자를 제거했습니다.';
    } catch { reviewerStatus = '서버에 연결할 수 없습니다.'; }
    finally { busy = ''; }
  }
  function pick(event: MouseEvent) {
    if (!picking) return;
    event.preventDefault(); event.stopImmediatePropagation();
    picking = false;
    let el = event.target as HTMLElement | null;
    while (el && el !== previewDocument?.body) {
      const texts = [el.getAttribute('placeholder'), el.getAttribute('aria-label'), el.innerText].filter((s): s is string => !!s && !!normalize(s));
      for (const text of texts) {
        const found = entries.filter(e => normalize(saved[e.id] ?? e.english) === normalize(text));
        if (found.length) {
          query = ''; selectedId = found[0].id; matches = found.length > 1 ? found : [];
          previewMessage = found.length > 1 ? '같은 영어 문구가 여러 곳에 있어요. 원문을 확인하고 선택해 주세요.' : '문구를 선택했어요. 편집하거나 사이트를 계속 이동할 수 있어요.';
          message = ''; return;
        }
      }
      el = el.parentElement;
    }
    matches = []; previewMessage = '연결된 문구를 찾지 못했어요. 문구 목록에서 검색해 주세요.';
  }
  function attachPreview() {
    previewDocument?.removeEventListener('click', pick, true);
    try { previewDocument = previewFrame?.contentDocument ?? null; previewDocument?.addEventListener('click', pick, true); }
    catch { previewDocument = null; }
  }
  $effect(() => {
    const viewport = previewViewport;
    if (!viewport) return;
    const observer = new ResizeObserver(() => { viewportWidth = viewport.clientWidth; viewportHeight = viewport.clientHeight; });
    observer.observe(viewport);
    return () => observer.disconnect();
  });
  onMount(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', warn); void load();
    return () => { window.removeEventListener('beforeunload', warn); previewDocument?.removeEventListener('click', pick, true); };
  });
</script>
<svelte:head><title>번역 검수 | Re:hear</title><meta name="robots" content="noindex,nofollow" /></svelte:head>
<main>
  <header><div class="brand"><a href="/odi">← Re:hear</a><h1>영문 번역 검수</h1></div>{#if account}<div class="account"><span>{account}</span><button class="text-button" onclick={() => showReviewers = !showReviewers}>권한 관리</button></div>{/if}</header>
  {#if checking && !account}<p class="state">계정 확인 중…</p>
  {:else if !account}
    <form class="login" onsubmit={(event) => { event.preventDefault(); void login(); }}>
      <div class="eyebrow">RE:HEAR</div><h2>로그인</h2><p>초밥 계정으로 로그인해 주세요.<br />번역 검수 권한이 있는 계정만 이용할 수 있어요.</p>
      <label>이메일<input type="email" autocomplete="username" bind:value={email} required /></label>
      <label>비밀번호<input type="password" autocomplete="current-password" bind:value={password} required /></label>
      {#if accessError}<p class="error" role="alert">{accessError}</p>{/if}
      <button class="primary" disabled={busy === 'login'}>{busy === 'login' ? '확인 중…' : '로그인'}</button>
      <a class="google-login" href="/auth/google/start?purpose=login&amp;return_to=%2Ftranslation-review">Google로 계속하기</a>
    </form>
  {:else}
    {#if showReviewers}<section class="reviewers"><div><h2>검수 권한 관리</h2><p>추가한 이메일로 가입하고 이메일 인증을 마친 계정이 번역을 수정할 수 있습니다.</p></div><form onsubmit={(event) => { event.preventDefault(); void changeReviewer('add-reviewer', newReviewer); }}><label>이메일<input type="email" required bind:value={newReviewer} placeholder="name@example.com" /></label><button disabled={!!busy}>추가</button></form>{#each reviewers as reviewer (reviewer)}<div class="reviewer-row"><span>{reviewer}</span><button disabled={!!busy} onclick={() => changeReviewer('remove-reviewer', reviewer)}>제거</button></div>{/each}<span role="status">{reviewerStatus}</span></section>{/if}
    <div class="intro"><div><h2>사이트를 보며 문구를 다듬어 보세요</h2><p>저장한 영어 문구는 사이트에 바로 반영됩니다.</p></div>{#if dirty}<span class="dirty">저장하지 않은 수정 {dirty}개</span>{/if}</div>
    <div class="workspace">
      <section class="preview" aria-label="사이트 미리보기"><div class="panel-head"><div><h3>사이트 미리보기</h3><p>{picking ? '수정할 문구를 누르면 선택 후 이동 모드로 돌아갑니다.' : '사이트를 자유롭게 이동하고, 문구 선택으로 번역을 고치세요.'}</p></div><div class="preview-actions"><button class:active={picking} aria-pressed={picking} onclick={() => { picking = !picking; previewMessage = ''; }}>{picking ? '선택 취소' : '문구 선택'}</button><a href="/odi?review_preview=en" target="_blank" rel="noopener">새 창 ↗</a></div></div>
        <div class="zoom-bar" aria-label="미리보기 배율"><span>화면 크기</span><div class="zoom-controls"><button aria-label="축소" disabled={zoom <= 0.25} onclick={() => changeZoom(-0.1)}>−</button><span aria-live="polite">{Math.round(zoom * 100)}%</span><button aria-label="확대" disabled={zoom >= 1.5} onclick={() => changeZoom(0.1)}>+</button><button class:zoom-active={manualZoom === null} onclick={() => manualZoom = null}>화면에 맞춤</button></div></div>
        {#if previewMessage}<div class="notice" role="status">{previewMessage}</div>{/if}<div class="preview-viewport" bind:this={previewViewport}><div class="preview-canvas" style:width={`${previewWidth * zoom}px`} style:height={`${viewportHeight}px`}><iframe bind:this={previewFrame} onload={attachPreview} title="Re:hear 사이트 미리보기" src="/odi?review_preview=en" style:width={`${previewWidth}px`} style:height={`${viewportHeight / zoom}px`} style:transform={`scale(${zoom})`}></iframe></div></div></section>
      <section class="editor" aria-label="번역 편집"><div class="panel-head"><div><h3>문구 편집</h3><p>한국어 원문과 영어를 비교하고 수정하세요.</p></div></div>
        <div class="search"><label for="search">문구 찾기</label><input id="search" type="search" placeholder="한국어 또는 영어 검색" bind:value={query} /></div>
        {#if matches.length > 1}<div class="duplicates"><strong>어떤 문구인가요?</strong>{#each matches as match (match.id)}<button onclick={() => select(match)}>{match.korean}</button>{/each}</div>{/if}
        <div class="list-head"><span>문구 목록</span><span>{filtered.length}개</span></div>
        <div class="list" aria-label="문구 목록">{#each filtered as entry (entry.id)}<button class:selected={selectedId === entry.id} class="row" onclick={() => select(entry)}><span class="row-source">{entry.korean}</span><span class="row-en">{values[entry.id]}</span>{#if values[entry.id] !== saved[entry.id]}<span class="dot" aria-label="저장되지 않은 수정"></span>{/if}</button>{:else}<p class="empty">검색 결과가 없습니다.</p>{/each}</div>
        {#if selected}<div class="detail"><div class="detail-head"><span>선택한 문구</span><div><button aria-label="이전 문구" disabled={filtered.findIndex(e => e.id === selectedId) <= 0} onclick={() => move(-1)}>←</button><button aria-label="다음 문구" disabled={filtered.findIndex(e => e.id === selectedId) < 0 || filtered.findIndex(e => e.id === selectedId) >= filtered.length - 1} onclick={() => move(1)}>→</button></div></div><div class="source"><span>한국어 원문</span><p>{selected.korean}</p></div><label class="translation">영어 번역<textarea rows="4" maxlength="2000" disabled={!!busy} bind:value={values[selected.id]} onkeydown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); void save(selected); } }}></textarea></label><div class="detail-foot"><span>{values[selected.id]?.length ?? 0} / 2000자 · ⌘/Ctrl + Enter 저장</span><button class="primary" disabled={!!busy || !values[selected.id]?.trim() || values[selected.id] === saved[selected.id]} onclick={() => save(selected)}>{busy === selected.id ? '저장 중…' : '저장하고 반영'}</button></div><p class="save-message" role="status" aria-live="polite">{message}</p></div>{/if}
      </section>
    </div>
  {/if}
</main>
<style>
  :global(body){margin:0;background:#f5f6fa;color:#23273a;font-family:system-ui,-apple-system,sans-serif} *{box-sizing:border-box} main{max-width:1800px;margin:auto;padding:0 28px 28px} header{min-height:72px;display:flex;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid #e2e5ed}.brand{display:flex;align-items:center;gap:24px}.brand a{font-size:13px;color:#615dc4;text-decoration:none;font-weight:650}.brand h1{font-size:18px;margin:0}.account{display:flex;align-items:center;gap:14px;color:#777c8d;font-size:13px}.text-button{border:0;background:transparent;color:#5955c1;padding:4px}.intro{display:flex;align-items:end;justify-content:space-between;gap:12px;margin:24px 0 17px}.intro h2{font-size:20px;margin:0 0 6px}.intro p,.panel-head p{margin:0;color:#7c8294;font-size:13px}.dirty{font-size:12px;color:#a5640b;background:#fff3dc;border-radius:20px;padding:7px 12px}.workspace{display:grid;grid-template-columns:minmax(0,1.13fr) minmax(390px,.87fr);gap:16px;align-items:start}.preview,.editor,.reviewers,.login{background:#fff;border:1px solid #e0e3ec;border-radius:12px;box-shadow:0 2px 12px #23273a08;overflow:hidden}.preview{position:sticky;top:16px}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:17px 20px;border-bottom:1px solid #edf0f5}.panel-head h3{font-size:15px;margin:0 0 5px}.preview-actions{display:flex;align-items:center;gap:12px;white-space:nowrap}.preview-actions a{font-size:12px;color:#686d7c;text-decoration:none}.zoom-bar{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 20px;color:#777e90;font-size:12px;border-bottom:1px solid #edf0f5}.zoom-controls{display:flex;align-items:center;gap:6px}.zoom-controls button{padding:5px 9px}.zoom-controls span{min-width:40px;text-align:center;color:#41475a;font-variant-numeric:tabular-nums}.zoom-controls .zoom-active{color:#5651bd;background:#f1f0ff;border-color:#dcd9fa}.preview-viewport{height:calc(100vh - 270px);min-height:480px;overflow:auto;background:#f4f5f8}.preview-canvas{position:relative;overflow:hidden}.preview iframe{display:block;border:0;transform-origin:top left;background:white}.notice{background:#f1f0ff;color:#4a47a2;padding:10px 20px;font-size:12px}.search{padding:16px 20px 12px}.search label,.translation{display:grid;gap:8px;font-weight:700;font-size:12px;color:#545a70}.search input,.login input,.reviewers input,textarea{width:100%;border:1px solid #d9deea;border-radius:8px;background:#fff;font:inherit;color:#25293a;padding:11px 12px;outline:none}.search input:focus,.login input:focus,textarea:focus,.reviewers input:focus{border-color:#746fdb;box-shadow:0 0 0 3px #6f69d51c}.list-head{display:flex;justify-content:space-between;padding:0 20px 8px;color:#8b90a1;font-size:11px;font-weight:700}.list{margin:0 20px;border:1px solid #e8eaf1;border-radius:8px;max-height:215px;overflow:auto}.row{position:relative;display:block;text-align:left;width:100%;border:0;border-radius:0;border-bottom:1px solid #f0f1f5;padding:10px 14px;background:white}.row:last-child{border-bottom:0}.row.selected{background:#f2f1ff;box-shadow:inset 3px 0 #625bd2}.row-source,.row-en{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row-source{font-size:13px;font-weight:650}.row-en{font-size:12px;color:#858a9b;margin-top:3px}.dot{position:absolute;right:10px;top:13px;width:7px;height:7px;background:#e0a23a;border-radius:50%}.detail{padding:18px 20px 16px}.detail-head{display:flex;align-items:center;justify-content:space-between;font-size:13px;font-weight:700}.detail-head div{display:flex;gap:5px}.detail-head button{padding:3px 10px}.source{background:#f7f8fb;border-radius:8px;margin:12px 0 15px;padding:13px}.source span{font-size:11px;color:#8b90a1;font-weight:700}.source p{font-size:14px;line-height:1.5;white-space:pre-wrap;margin:6px 0 0}.translation textarea{resize:vertical;min-height:96px;line-height:1.5;font-size:14px;font-weight:400}.detail-foot{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:10px}.detail-foot span{font-size:11px;color:#969bab}.save-message{min-height:18px;margin:8px 0 0;font-size:12px;color:#5553b6}.duplicates{margin:0 20px 12px;padding:12px;border:1px solid #e2dffb;border-radius:8px;display:grid;gap:6px;font-size:12px}.duplicates button{text-align:left}.empty,.state{padding:20px;color:#858a9b;font-size:13px}button{border:1px solid #d8dce7;background:white;border-radius:7px;padding:9px 12px;font:inherit;color:#35394c;cursor:pointer;font-size:12px;font-weight:650}button:hover:not(:disabled){border-color:#817bda}button:disabled{opacity:.45;cursor:not-allowed}.primary,.active{background:#5d58c9;border-color:#5d58c9;color:white}.reviewers{margin-top:18px;padding:18px 20px}.reviewers h2{font-size:15px;margin:0}.reviewers p{font-size:12px;color:#777e90}.reviewers form{display:flex;align-items:end;gap:8px}.reviewers label{display:grid;gap:6px;font-size:12px;flex:1}.reviewer-row{display:flex;justify-content:space-between;align-items:center;padding-top:8px;font-size:12px}.login{max-width:420px;margin:90px auto;padding:32px}.eyebrow{font-size:11px;letter-spacing:.12em;color:#6963ca;font-weight:800}.login h2{font-size:24px;margin:12px 0}.login p{font-size:13px;line-height:1.7;color:#777e90}.login label{display:grid;gap:7px;margin-top:18px;font-size:13px;font-weight:650}.login .primary{margin-top:22px;width:100%;font-size:14px}.google-login{display:block;margin-top:10px;padding:10px;text-align:center;border:1px solid #d8dce7;border-radius:7px;color:#35394c;text-decoration:none;font-size:13px}.error{color:#b42318!important}@media(max-width:900px){main{padding:0 16px 24px}.workspace{grid-template-columns:1fr}.preview{position:static}.preview-viewport{height:440px;min-height:0}.intro{align-items:start;flex-direction:column}.brand{gap:12px}.account span{display:none}}@media(max-width:480px){.panel-head{align-items:start;flex-direction:column}.preview-actions{width:100%;justify-content:space-between}.detail-foot{align-items:end;flex-direction:column}.detail-foot .primary{width:100%}}
</style>
