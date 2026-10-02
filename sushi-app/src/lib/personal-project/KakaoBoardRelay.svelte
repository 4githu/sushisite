<script lang="ts">
 import {onMount} from 'svelte';
 import {request} from './shared/api';
 let {boards}:{boards:{id:number;name:string}[]}=$props();
 type Route={id:number;board_id:number;room:string;mention:string;enabled:number;ack:number;last_scan:string|null;error:string|null;counts:Record<string,number>;issues:{error:string}[]};
 let routes=$state<Route[]>([]),visible=$state(false),error=$state(''),busy=$state(false),bid=$state(0),mention=$state('김지후'),ack=$state(true);
 async function load(){routes=await request<Route[]>('/kakao-bridge/board-relay');visible=true;const r=routes[0];bid=r?.board_id || boards.find(b=>b.name.includes('자료'))?.id || boards[0]?.id;mention=r?.mention || mention;ack=r ? !!r.ack:true;}
 onMount(()=>{void load().catch(()=>{});});
 async function save(enabled:boolean){busy=true;error='';try{await request('/kakao-bridge/board-relay',{method:'PUT',body:{board_id:bid,room:'대학생 자료 공유방',mention,enabled,ack}});await load();}catch(e){error=String(e);}finally{busy=false;}}
</script>
{#if visible}<section>
 <h2>카카오톡 자료 공유</h2>
 <p>새 글은 ‘대학생 자료 공유방’으로 전송됩니다. 이 방에서 실제 @{mention} 멘션이 표시된 줄은 제목, 같은 메시지의 다음 줄부터 본문으로 등록합니다. 일반 대화는 본문에 포함하지 않습니다.</p>
 <p>연결 시점 이후의 글부터 처리합니다. Mac 카카오톡이 로그인된 채 실행되어 있어야 하며, 화면에 불러온 대화만 감지합니다. 실제 멘션의 강조 표시를 확인하며 알림 팝업을 직접 읽지는 않습니다. 약 1분간 변경이 없으면 등록합니다.</p>
 {#if error}<p role="alert">{error}</p>{/if}
 <label>게시판<select bind:value={bid} disabled={busy || !!routes[0]?.enabled}>{#each boards as b}<option value={b.id}>{b.name}</option>{/each}</select></label>
 <label>내 멘션 이름<input bind:value={mention} maxlength="50" disabled={busy || !!routes[0]?.enabled}/></label>
 <label><input type="checkbox" bind:checked={ack} disabled={busy}/>등록 완료 메시지 보내기</label>
 <button disabled={busy || !bid || !mention.trim()} onclick={()=>save(!routes[0]?.enabled)}>{busy?'변경 중…':routes[0]?.enabled?'자동 연동 끄기':'자동 연동 켜기'}</button>
 <button disabled={busy} onclick={()=>load().catch(e=>error=String(e))}>상태 새로고침</button>
 {#each routes as r}<p>연동 {r.enabled?'켜짐':'꺼짐'} · 등록 {r.counts.published || 0}건 · 대기 {r.counts.pending || 0}건 · 최근 확인 {r.last_scan ? r.last_scan+' UTC':'아직 없음'}</p>{#if r.error}<p role="alert">{r.error}</p>{/if}{#each r.issues as issue}<p role="alert">수집 대기: {issue.error}</p>{/each}{/each}
 <p>전송 실패·확인 불가 상태는 게시판의 카카오톡 연결에서 확인할 수 있습니다. 확인 불가 메시지는 중복 방지를 위해 자동 재전송하지 않습니다.</p>
</section>{/if}
<style>section{padding:20px 0;border-bottom:1px solid #8884}label{display:inline-flex;gap:8px;margin:8px;align-items:center;flex-wrap:wrap}button{margin:4px}p{line-height:1.6;overflow-wrap:anywhere}</style>
