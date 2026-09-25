<script lang="ts">
 import { beforeNavigate } from '$app/navigation';
 import { request } from './api';
 type Version={edition:'community'|'official';revision:number;content:string;source_url:string;created_at:string};
 type Post={id:number;title:string;content:string;start_time:string|null;end_time:string|null;canDelete:boolean;created_at:string};
 let versions=$state<Version[]>([]), posts=$state<Post[]>([]), loaded=$state(false), busy=$state(false), error=$state(''), notice=$state('');
 let cohort=$state(new Date().getFullYear()),track=$state('major'), loadedKey=$state(''), canPublish=$state(false);
 let edition=$state<'community'|'official'>('community'),content=$state(''),source=$state(''),revision=$state(0),saved=$state('');
 let title=$state(''),body=$state(''),starts=$state(''),ends=$state('');
 const dirty=$derived(`${content}\n${source}`!==saved && Boolean(loadedKey));
 beforeNavigate(({cancel})=>{if((dirty||title||body)&&!confirm('저장하지 않은 학과 자료가 있습니다. 이동할까요?'))cancel();});
 async function run(action:()=>Promise<void>){if(busy)return;busy=true;error='';notice='';try{await action();}catch(e){error=e instanceof Error?e.message:'요청 실패';}finally{busy=false;}}
 function editVersion(){const item=versions.find(v=>v.edition===edition);content=item?.content||'';source=item?.source_url||'';revision=item?.revision||0;saved=`${content}\n${source}`;}
 async function load(){if(dirty&&!confirm('저장하지 않은 규정 편집을 버리고 다시 불러올까요?'))return;const result=await request<{versions:Version[];canPublishOfficial:boolean}>(`/student/curriculum?cohort=${cohort}&track=${track}`);versions=result.versions;canPublish=result.canPublishOfficial;posts=await request<Post[]>('/student/board');loadedKey=`${cohort}:${track}`;loaded=true;editVersion();}
</script>
<svelte:window onbeforeunload={(e)=>{if(dirty||title||body)e.preventDefault();}} />
<section class="community">
 <h2>학과 자료와 게시판</h2><p>가입자가 입력한 학교·학과로 구분하는 커뮤니티입니다. 재학 인증된 비공개 게시판은 아닙니다.</p>
 <label>입학 연도<input type="number" min="2000" max="2100" bind:value={cohort} /></label><label>전공 유형<select bind:value={track}><option value="major">주전공</option><option value="double">복수전공</option><option value="minor">부전공</option></select></label>
 <button disabled={busy} onclick={()=>run(load)}>학과 자료 불러오기</button>
 {#if error}<p role="alert">{error}</p>{/if}{#if notice}<p role="status">{notice}</p>{/if}
 {#if loaded}
 <h3>교과목 이수규정</h3>
 {#each ['official','community'] as kind}<article><h4>{kind==='official'?'사이트 검토본':'사용자 편집본'}</h4>{#each versions.filter(v=>v.edition===kind) as v}<small>버전 {v.revision} · {v.created_at}</small><p class="content">{v.content}</p>{#if /^https:\/\/[^\s\\]+$/.test(v.source_url)}<a href={v.source_url} target="_blank" rel="noreferrer">원문 출처 ↗</a>{/if}{:else}<p>{kind==='official'?'검토된 규정을 아직 제공하지 않습니다.':'등록된 사용자 편집본이 없습니다.'}</p>{/each}</article>{/each}
 <details><summary>규정 편집</summary><form onsubmit={(e)=>{e.preventDefault();void run(async()=>{const result=await request<{versions:Version[]}>('/student/curriculum',{method:'POST',body:{cohort,track,edition,content,source_url:source,base_revision:revision}});versions=result.versions;editVersion();notice='새 버전으로 저장했습니다.';});}}>
 {#if canPublish}<label>발행 대상<select value={edition} onchange={(e)=>{if(!dirty||confirm('작성 중인 내용을 버릴까요?')){edition=e.currentTarget.value as typeof edition;editVersion();}else e.currentTarget.value=edition;}}><option value="community">사용자 편집본</option><option value="official">사이트 검토본</option></select></label>{/if}
 <label>규정 내용<textarea bind:value={content} maxlength="30000" required rows="8"></textarea></label><label>원문 출처<input type="url" bind:value={source} placeholder="https://" /></label>
 <button disabled={busy || loadedKey!==`${cohort}:${track}`}>새 버전 저장</button><p>학번·전공 유형을 바꾸면 자료를 다시 불러와주세요. 과거 버전은 서버에 보존됩니다.</p></form></details>
 <h3>학과 게시판·일정</h3><form onsubmit={(e)=>{e.preventDefault();void run(async()=>{posts=await request<Post[]>('/student/board',{method:'POST',body:{title,content:body,start:starts?new Date(starts).toISOString():null,end:ends?new Date(ends).toISOString():null}});title=body=starts=ends='';notice='학과 게시판에 등록했습니다.';});}}>
 <label>글 제목<input bind:value={title} required maxlength="120" /></label><label>글 내용<textarea bind:value={body} maxlength="5000" rows="4"></textarea></label><label>일정 시작 (선택)<input type="datetime-local" bind:value={starts} /></label><label>일정 종료 (선택)<input type="datetime-local" bind:value={ends} min={starts} /></label><button disabled={busy}>학과 게시판에 등록</button></form>
 {#each posts as post}<article><h4>{post.title}</h4><p class="content">{post.content}</p>{#if post.start_time}<p>{new Date(post.start_time).toLocaleString('ko-KR')}</p><button disabled={busy} onclick={()=>run(async()=>{const result=await request<{alreadyAdded:boolean}>(`/student/board/${post.id}/calendar`,{method:'POST'});notice=result.alreadyAdded?'이미 추가한 학과 일정입니다.':'내 캘린더에 추가했습니다.';})}>내 캘린더에 추가</button>{/if}{#if post.canDelete}<button disabled={busy} onclick={()=>run(async()=>{await request(`/student/board/${post.id}`,{method:'DELETE'});posts=posts.filter(p=>p.id!==post.id);})}>내 글 삭제</button>{/if}</article>{:else}<p>첫 학과 소식을 등록해보세요.</p>{/each}
 {/if}
</section>
<style>
 .community {border:1px solid #d8dce1;border-radius:12px;padding:20px;margin:20px 0;} label {display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0;} input,textarea,select {border:1px solid #bdc4cd;border-radius:7px;padding:9px;max-width:100%;background:white;color:#25262b;min-width:0;} textarea {width:100%;} button {padding:10px 14px;border:1px solid #9da6b1;border-radius:7px;margin:6px 8px 6px 0;background:#f3f5f7;color:#25262b;} button:disabled {opacity:.5;} article {border-top:1px solid #d8dce1;padding:12px 0;} .content {white-space:pre-wrap;overflow-wrap:anywhere;} [role=alert] {color:#b42335;}
</style>
