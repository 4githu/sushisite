<script lang="ts">
 import { onMount } from 'svelte';
 import StudentCommunity from '$lib/personal-project/shared/StudentCommunity.svelte';
 import { request } from '$lib/personal-project/shared/api';
 type Profile = { is_student: boolean; school: string; department: string };
 type Lesson = { title: string; weekday: number; start: string; end: string; location: string };
 type Preview = { events: {title:string;startTime:string;endTime:string;location:string}[]; skipped:{date:string;title:string;reason:string}[] };
 let profile = $state<Profile>({ is_student:false, school:'',department:'' });
 let enabled = $state(false), loading = $state(true), busy = $state(false), error = $state(''), notice = $state('');
 const year = new Date().getFullYear();
 const initialTerm = new Date().getMonth() < 7 ? 1 : 2;
 let term = $state(initialTerm);
 let name = $state(`${year}학년도 ${initialTerm}학기`);
 let starts = $state(`${year}-${initialTerm===1?'03':'09'}-01`), ends = $state(`${year}-${initialTerm===1?'06':'12'}-30`);
 let exclusions = $state(''), skipHolidays = $state(true);
 let lessons = $state<Lesson[]>([{title:'',weekday:0,start:'09:00',end:'10:30',location:''}]);
 let preview = $state<Preview | null>(null), previewInput = $state('');
 const payload = $derived({ name, starts_on:starts, ends_on:ends, skip_holidays:skipHolidays, excluded_dates:exclusions.split(/[,\s]+/).filter(Boolean), lessons });
 const changed = $derived(JSON.stringify(payload) !== previewInput);
 async function run(action:()=>Promise<void>) {
  if(busy) return; busy=true; error=''; notice='';
  try { await action(); } catch(e) { error=e instanceof Error?e.message:'요청을 완료하지 못했습니다.'; } finally { busy=false; }
 }
 onMount(async()=> { try { profile=await request<Profile>('/student/profile'); enabled=Boolean(profile.is_student); } catch(e) { error=e instanceof Error?e.message:'설정을 불러오지 못했습니다.'; } finally { loading=false; } });
 function semester() { name=`${year}학년도 ${term}학기`; starts=`${year}-${term===1?'03':'09'}-01`; ends=`${year}-${term===1?'06':'12'}-30`; }
</script>
<svelte:head><title>학생 서비스 · NETAQ</title></svelte:head>
<main class="student-settings">
 <header><h1>학생 서비스</h1><p>학교를 등록하면 시간표와 학교별 서비스를 사용할 수 있습니다.</p></header>
 {#if error}<p role="alert">{error}</p>{/if}{#if notice}<p role="status">{notice}</p>{/if}
 <form onsubmit={(e)=>{e.preventDefault(); void run(async()=>{ profile=await request<Profile>('/student/profile',{method:'PUT',body:profile}); enabled=Boolean(profile.is_student); notice='학생 서비스 설정을 저장했습니다.'; });}}>
 <fieldset disabled={busy || loading}><legend>내 학교</legend>
 <label><input type="checkbox" bind:checked={profile.is_student} />학생인가요?</label>
 {#if profile.is_student}<label>학교<input bind:value={profile.school} required maxlength="120" placeholder="예: 서울대학교" /></label><label>학과<input bind:value={profile.department} maxlength="120" /></label>{/if}
 <button>설정 저장</button></fieldset></form>
 {#if enabled}
 <section><h2>학교별 서비스</h2>
 {#if ['서울대학교','서울대'].includes(profile.school.trim())}<a href="https://snuco.snu.ac.kr/foodmenu/" target="_blank" rel="noreferrer">서울대학교 공식 학식 확인 ↗</a><p>학과 이수규정은 아래 학과 자료에서 확인하거나 사용자 편집본을 등록할 수 있습니다.</p>
 {:else}<p>이 학교의 학식 조회는 아직 지원하지 않습니다. 시간표와 사용자 편집 이수규정은 등록할 수 있습니다.</p>{/if}
 </section>
 <form onsubmit={(e)=>{ e.preventDefault(); void run(async()=>{ const input=JSON.stringify(payload); preview=await request<Preview>('/student/timetable/preview',{method:'POST',body:JSON.parse(input)}); previewInput=input; }); }}>
 <fieldset disabled={busy}><legend>나의 시간표 가져오기</legend>
 <p>SNUTT·에브리타임 자동 연결은 준비 중입니다. 먼저 수업을 직접 입력할 수 있습니다.</p>
 <label>학기 기본값<select bind:value={term} onchange={semester}><option value={1}>1학기</option><option value={2}>2학기</option></select></label>
 <label>시간표 이름<input bind:value={name} required maxlength="80" /></label>
 <div class="fields"><label>개강일<input type="date" bind:value={starts} required /></label><label>종강일<input type="date" bind:value={ends} required min={starts} /></label></div>
 <label><input type="checkbox" bind:checked={skipHolidays} />한국 공휴일·대체공휴일 제외</label>
 <label>추가 휴강일<input bind:value={exclusions} placeholder="2026-10-02, 2026-11-16" /></label>
 <p>서울 시간 기준입니다. 학교별 휴강일·임시공휴일은 추가 휴강일에 입력하세요.</p>
 {#each lessons as lesson,i}<div class="lesson"><label>과목명<input bind:value={lesson.title} required maxlength="120" /></label><label>요일<select bind:value={lesson.weekday}>{#each ['월','화','수','목','금','토','일'] as day,index}<option value={index}>{day}</option>{/each}</select></label><label>시작<input type="time" bind:value={lesson.start} required /></label><label>종료<input type="time" bind:value={lesson.end} required /></label><label>강의실<input bind:value={lesson.location} maxlength="500" /></label><button type="button" disabled={lessons.length===1} onclick={()=>lessons=lessons.filter((_,index)=>index!==i)}>수업 삭제</button></div>{/each}
 <button type="button" disabled={lessons.length>=60} onclick={()=>lessons=[...lessons,{title:'',weekday:0,start:'09:00',end:'10:30',location:''}]}>수업 추가</button>
 <button>학기 일정 미리보기</button></fieldset></form>
 {#if preview}<section><h2>등록 전 확인</h2><p>생성할 일정 {preview.events.length}개 · 휴강 {preview.skipped.length}개</p>{#if changed}<p>입력 내용이 바뀌었습니다. 미리보기를 다시 확인해주세요.</p>{/if}
 <details><summary>수업 일정 보기</summary>{#each preview.events as event}<p>{event.startTime.slice(0,16).replace('T',' ')} — {event.title} · {event.location}</p>{/each}</details>
 <details><summary>제외한 휴강일</summary>{#each preview.skipped as day}<p>{day.date} · {day.title} · {day.reason}</p>{/each}</details>
 <button disabled={busy || changed || !preview.events.length} onclick={()=>run(async()=>{ const result=await request<{created:number;alreadyImported:boolean}>('/student/timetable/import',{method:'POST',body:payload}); notice=result.alreadyImported?'이미 가져온 시간표입니다.':`${result.created}개 수업을 캘린더에 등록했습니다.`; })}>내 캘린더에 시간표 추가</button><a href="/personal-project/calendar/week">주간 시간표 보기</a>
 </section>{/if}
 {#if profile.department}{#key profile.school+profile.department}<StudentCommunity />{/key}{:else}<p>학과를 저장하면 이수규정 위키와 학과 게시판을 사용할 수 있습니다.</p>{/if}
 {/if}
</main>
<style>
 .student-settings { max-width: 960px; margin:auto; padding:24px; color:var(--cw-text, #25262b); }
 h1 {font-size:26px;} h2,legend {font-size:18px;font-weight:700;} p {line-height:1.6;} section,fieldset {border:1px solid #d8dce1;border-radius:12px;padding:20px;margin:20px 0;min-width:0;}
 label {display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:12px 0;} input:not([type=checkbox]),select {border:1px solid #bdc4cd;border-radius:7px;padding:9px;max-width:100%;min-width:0;background:white;color:#25262b;}
 button {padding:10px 14px;border:1px solid #9da6b1;border-radius:7px;margin:6px 8px 6px 0;background:#f3f5f7;color:#25262b;} button:disabled {opacity:.5;}
 .fields,.lesson {display:flex;gap:12px;flex-wrap:wrap;} .lesson {border-top:1px solid #d8dce1;margin-top:16px;} .lesson label {display:grid;} a {text-decoration:underline;} [role=alert] {color:#b42335;} @media(max-width:600px) {.student-settings {padding:14px;} fieldset,section {padding:12px;} .lesson label {max-width:100%;}}
</style>
