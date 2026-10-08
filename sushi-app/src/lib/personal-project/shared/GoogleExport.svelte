<script lang="ts">
  import { request } from './api';
  let { accountId, calendars }: { accountId: number; calendars: { calendar_id: string; name: string; writable: number }[] } = $props();
  type Preview = { preview_token: string; calendar_name: string; create: number; update: number; unchanged: number; items: {event_id:number;title:string;action:string}[] };
  let target = $state('');
  let start = $state(`${new Date().getFullYear()}-01-01`);
  let end = $state(`${new Date().getFullYear()}-12-31`);
  let preview = $state<Preview | null>(null);
  let busy = $state(false);
  let error = $state('');
  let notice = $state('');
  async function transfer(execute = false) {
    if (busy || !target || !start || !end) return;
    busy = true; error = ''; notice = '';
    try {
      const body = {calendar_id:target, starts_on:start, ends_on:end};
      if (execute && preview) {
        const result = await request<{exported:number}>(`/google/accounts/${accountId}/transfer`, {method:'POST',body:{...body,preview_token:preview.preview_token}});
        notice = `${result.exported}건을 Google에 반영했습니다.`; preview = null;
      } else preview = await request<Preview>(`/google/accounts/${accountId}/transfer`, {method:'POST',body});
    } catch (e) { error = e instanceof Error ? e.message : '내보내기를 완료하지 못했습니다.'; preview = null; }
    finally { busy = false; }
  }
</script>
<details class="export">
  <summary>내 캘린더 → Google 내보내기</summary>
  <p>선택한 기간에 시작하는 내가 소유한 일정을 복사합니다. 이전에 내보낸 사본은 현재 앱 내용으로 덮어씁니다. Google에서 가져온 일정은 제외하며, 다른 Google 일정과 기존 사본을 삭제하지 않습니다.</p>
  <div class="fields">
    <label>대상 Google 캘린더<select bind:value={target} disabled={busy} onchange={() => preview=null}><option value="">선택하세요</option>{#each calendars.filter(c=>c.writable) as cal}<option value={cal.calendar_id}>{cal.name}</option>{/each}</select></label>
    <label>시작일 (한국 시간)<input type="date" bind:value={start} disabled={busy} onchange={() => preview=null} /></label>
    <label>종료일<input type="date" bind:value={end} disabled={busy} onchange={() => preview=null} /></label>
  </div>
  <button disabled={busy || !target || !start || !end} onclick={() => transfer()}>내보내기 미리보기</button>
  {#if preview}
    <div class="preview" aria-live="polite">
      <strong>{preview.calendar_name}: 추가 {preview.create}건 · 덮어쓰기 {preview.update}건 · 동일 {preview.unchanged}건</strong>
      <details><summary>대상 일정 {preview.items.length}건 확인</summary><ul>{#each preview.items as item}<li>{item.title} — {item.action==='create'?'추가':item.action==='update'?'덮어쓰기':'동일'}</li>{/each}</ul></details>
      <p>덮어쓰기 대상의 Google 제목·시간·설명·장소는 앱 내용으로 바뀝니다. 자동 내보내기는 하지 않습니다.</p>
      <button disabled={busy || !preview.items.length} onclick={() => transfer(true)}>확인한 내용으로 Google에 반영</button>
    </div>
  {/if}
  {#if error}<p role="alert">{error}</p>{/if}
  {#if notice}<p role="status">{notice}</p>{/if}
</details>
<style>
  .export {margin-top:1rem;padding-top:1rem;border-top:1px solid var(--personal-line, #d3d4d8)}
  summary {cursor:pointer;font-weight:600;padding:.5rem 0}
  p {font-size:.85rem;line-height:1.6;opacity:.8;margin:.6rem 0}
  .fields {display:flex;flex-wrap:wrap;gap:.6rem;margin:.75rem 0}
  label {display:grid;gap:.35rem;font-size:.8rem;min-width:0;flex:1 1 145px}
  input,select,button {font:inherit;border:1px solid var(--personal-line, #d3d4d8);border-radius:8px;background:transparent;color:inherit;padding:.65rem;min-width:0;max-width:100%}
  button {cursor:pointer;font-size:.85rem} button:disabled {opacity:.5;cursor:default}
  .preview {margin-top:.8rem;padding:.8rem;border:1px solid var(--personal-line, #d3d4d8);border-radius:8px;font-size:.85rem}
  ul {max-height:180px;overflow:auto;padding-left:1.2rem} [role=alert] {color:#c84444}
</style>
