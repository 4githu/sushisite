<script lang="ts">
 import { onMount } from 'svelte';
 import { request } from '../shared/api';
 let data=$state<{school:string;catalog:boolean;meals:boolean;links:{id:number;label:string;url:string;kind:string;canDelete:boolean}[]} | null>(null);
 let label=$state(''),url=$state(''),kind=$state('portal'),error=$state(''),busy=$state(false);
 async function load(){data=await request('/student/school-services');}
 async function run(fn:()=>Promise<void>){if(busy)return;busy=true;error='';try{await fn();}catch(e){error=String(e);}finally{busy=false;}}
 onMount(()=>{void run(load);});
</script>
<section class="panel">
 <h2>내 학교 서비스 연결</h2>
 {#if error}<p role="alert">{error}</p>{/if}
 {#if data}
 <p>{data.school || '학교를 먼저 저장하세요.'} · {data.catalog?'강의·규정 조회 지원':'강의·규정 데이터 미등록 — 시간표 직접 입력 가능'}</p>
 <p class="muted">사용자가 등록한 외부 링크입니다. 주소를 확인한 뒤 이용하세요. 계정 비밀번호를 저장하거나 자동 로그인하지 않습니다.</p>
 {#each data.links as link}<div class="service-row"><a href={link.url} target="_blank" rel="noopener noreferrer">{link.label} ↗</a><small>{new URL(link.url).hostname}</small>{#if link.canDelete}<button disabled={busy} onclick={()=>run(async()=>{await request(`/student/school-services/${link.id}`,{method:'DELETE'});await load();})}>연결 삭제</button>{/if}</div>{:else}<p>등록된 서비스가 없습니다.</p>{/each}
 <form onsubmit={(e)=>{e.preventDefault();void run(async()=>{await request('/student/school-services',{method:'POST',body:{label,url,kind}});label='';url='';await load();});}}>
 <label>분류<select bind:value={kind}><option value="portal">학교 포털</option><option value="timetable">강의·시간표</option><option value="meals">학식</option><option value="rules">수강 규정</option><option value="other">기타</option></select></label>
 <label>이름<input bind:value={label} required maxlength="80" placeholder="예: 학사 포털" /></label><label>주소<input type="url" bind:value={url} required placeholder="https://" /></label><button disabled={busy || !data.school}>서비스 링크 추가</button>
 </form>{:else}<p>불러오는 중…</p>{/if}
</section>
<style>.service-row,form{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:12px 0}.panel label{display:flex;flex-direction:column;align-items:stretch;gap:6px;flex:1 1 180px;min-width:0}input,select{max-width:100%;width:100%}small{overflow-wrap:anywhere}section{margin-top:20px}</style>
