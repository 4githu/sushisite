<script lang="ts">

 import {request} from '../shared/api';
 import type {Course} from './catalog';
 let {code,initial,onchange}:{code:string;initial?:NonNullable<Course['personalTags']>;onchange?:()=>void}=$props();
 let tags=$state<NonNullable<Course['personalTags']>>([]), kind=$state<'major_select'|'major_required'|'general'>('major_select'), major=$state(''),area=$state('수학'),busy=$state(false),error=$state('');
 let loaded=$state(false);
 async function load(){if(loaded)return;try { if(initial){tags=initial;loaded=true;return;} const all=await request<Record<string,NonNullable<Course['personalTags']>>>('/student/course-tags'); tags=all[code.toUpperCase()]||[];loaded=true; }catch(e){error=String(e);}}
 async function save(next:NonNullable<Course['personalTags']>){busy=true;error='';try {await request(`/student/course-tags/${encodeURIComponent(code)}`,{method:'PUT',body:{tags:next}});tags=next;onchange?.();}catch(e){error=String(e);}finally{busy=false;}}
</script>
<details class="course-tags" ontoggle={(e)=>{if(e.currentTarget.open)void load();}}><summary>학점 분류 ＋</summary>
 <p>일반 학점에 추가로 인정할 전공·교양을 지정합니다. 공식 규정은 바꾸지 않습니다.</p>
 {#each tags as tag,i}<span class="tag">{tag.kind==='general'?`교양 · ${tag.area}`:`${tag.major} · ${tag.kind==='major_required'?'전공필수':'전공선택'}`}<button disabled={busy} aria-label="분류 삭제" onclick={()=>save(tags.filter((_,n)=>n!==i))}>×</button></span>{/each}
 <select aria-label="학점 종류" bind:value={kind}><option value="major_select">전공선택</option><option value="major_required">전공필수</option><option value="general">교양</option></select>
 {#if kind==='general'}<select aria-label="교양 영역" bind:value={area}>{#each ['수학','과학','외국어','글쓰기','베리타스','지성의 열쇠'] as value}<option>{value}</option>{/each}</select>{:else}<input aria-label="인정 전공" placeholder="인정할 전공 이름" bind:value={major} />{/if}
 <button disabled={busy || !loaded || (kind!=='general'&&!major.trim())} onclick={()=>save([...tags,{kind,major:kind==='general'?'':major.trim(),area:kind==='general'?area:''}])}>분류 추가</button>
 {#if error}<p role="alert">{error}</p>{/if}
</details>
<style>.course-tags{font-size:13px;width:100%;margin-top:8px}summary{cursor:pointer}p{color:#666}.tag{display:inline-flex;gap:6px;border-radius:16px;background:#8b5cf618;padding:4px 8px;margin:4px}button,select,input{border:1px solid #8885;border-radius:6px;min-height:32px;padding:4px 8px;color:inherit;background:var(--surface,#fff)}</style>
