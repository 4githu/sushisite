<script lang="ts">
 import { onMount } from 'svelte';
 import { request } from '../shared/api';
 import CampusServices from './CampusServices.svelte';
 let cohort=$state(new Date().getFullYear()),track=$state('major'),content=$state(''),source=$state(''),revision=$state(0),error=$state(''),notice=$state(''),busy=$state(false);
 let versions=$state<{edition:string;revision:number;content:string;source_url:string;created_at:string}[]>([]);
 let loaded=$state('');
 async function load(){const key=`${cohort}:${track}`;const d=await request<{versions:typeof versions}>(`/student/curriculum?cohort=${cohort}&track=${track}`);if(key!==`${cohort}:${track}`)return;versions=d.versions;const v=versions.find(v=>v.edition==='community');content=v?.content || '';source=v?.source_url || '';revision=v?.revision || 0;loaded=key;}
 async function run(fn:()=>Promise<void>){busy=true;error='';notice='';try{await fn();}catch(e){error=String(e);}finally{busy=false;}}
 onMount(()=>{void run(async()=>{const p=await request<{admission_year:number}>('/student/profile');cohort=p.admission_year || cohort;await load();});});
</script>
<section class="panel">
 <h2>학과 수강 규정 함께 만들기</h2><p>학교 설정에 저장한 학교·학과별 자료입니다. 공식 자료가 없으면 직접 정리하고 원문 출처를 연결하세요. 사용자 작성본을 공식 졸업 판정으로 사용하지 않습니다.</p>
 <a href="/personal-project/calendar/student">학교·학과 설정</a>
 {#if error}<p role="alert">{error}</p>{/if}{#if notice}<p role="status">{notice}</p>{/if}
 <form onsubmit={(e)=>{e.preventDefault();void run(load);}}><label>규정 적용 학번<input type="number" min="2000" max="2100" bind:value={cohort}/></label><label>전공<select bind:value={track}><option value="major">주전공</option><option value="double">복수전공</option><option value="minor">부전공</option></select></label><button disabled={busy}>기존 내용 불러오기</button></form>
 {#each versions.filter(v=>v.edition==='official') as v}<details><summary>사이트 검토본 · {v.revision}판</summary><p class="preserve">{v.content}</p></details>{/each}
 <form onsubmit={(e)=>{e.preventDefault();void run(async()=>{await request('/student/curriculum',{method:'POST',body:{cohort,track,edition:'community',content,source_url:source,base_revision:revision}});await load();notice='사용자 작성본을 저장했습니다.';});}}>
 <label>사용자 작성본 · {revision}판<textarea bind:value={content} required maxlength="30000" rows="12" placeholder="필수 과목, 학점, 선택 조건 등을 출처와 함께 정리하세요."></textarea></label><label>출처<input type="url" bind:value={source} placeholder="https://"/></label><button disabled={busy || loaded!==`${cohort}:${track}`}>규정 저장</button></form>
 <p>버전 충돌 시 현재 입력은 유지됩니다. 복사해 보관한 뒤 최신 내용을 불러와 합쳐주세요.</p>
</section>
<CampusServices />
<style>form{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}.panel label{display:flex;flex-direction:column;align-items:stretch;gap:6px;flex:1 1 220px;min-width:0}textarea,input,select{width:100%}.preserve{white-space:pre-wrap}section{margin-top:20px}</style>
