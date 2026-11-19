<script lang="ts">
 import NotebookWorkspace from '$lib/notebook/NotebookWorkspace.svelte';
 import { dailyNotebookStorage } from './daily-notebook-storage';
 import { dailyEventLayout } from '../pdf/daily-events';
 import type { CalendarEvent } from './types';
 import { onMount, untrack } from 'svelte';
 let {date,events,onempty,onevent,oneventdrag}:{date:string;events:CalendarEvent[];onempty:(minute:number)=>void;onevent:(e:CalendarEvent)=>void;oneventdrag:(event:CalendarEvent,e:DragEvent)=>void}=$props();
 const storage=untrack(()=>dailyNotebookStorage(date));
 const rows=$derived(dailyEventLayout(events,date));
 let currentTime = $state(new Date());
 onMount(()=>{const timer=setInterval(()=>currentTime=new Date(),30000);return ()=>clearInterval(timer)});
 const currentY=$derived.by(()=>{const start=new Date(`${date}T08:00:00`).getTime();const minutes=(currentTime.getTime()-start)/60000;return minutes>=0&&minutes<1080?22+minutes*2/3:null});
 const clock=(value:string)=>new Date(value).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false});
</script>
{#snippet background()}
 <svg viewBox="0 0 420 760" aria-hidden="true">{#each Array.from({length:19},(_,i)=>i) as i}<line x1="42" x2="414" y1={22+i*40} y2={22+i*40} stroke="#e2e3e7"/><text x="4" y={26+i*40} font-size="13" fill="#696b73">{String((8+i)%24).padStart(2,'0')}:00</text>{/each}</svg>
 {#if currentY!==null}<div class="daily-current-time" style:top={currentY+'px'} aria-label={'현재 시각 '+clock(currentTime.toISOString())}><span>{clock(currentTime.toISOString())}</span><i></i></div>{/if}
 {#each rows as r (r.event.id)}<button style:left={r.x+'px'} style:top={r.y+'px'} style:width={r.width+'px'} style:height={r.height+'px'} onpointerdown={e=>e.stopPropagation()} onclick={()=>onevent(r.event)} draggable={r.event.type==='netaq-plan'} ondragstart={e=>oneventdrag(r.event,e)}><strong>{r.event.title}</strong><small>{clock(r.event.startTime)}–{r.event.endTime?clock(r.event.endTime):''}</small></button>{/each}
{/snippet}
<NotebookWorkspace daily remoteStorage documentStorage={storage} name="하루 시간표" {background} ondailytap={(x,y)=>{if(x>42)onempty(Math.max(480,Math.min(1545,480+Math.round((y-22)/10)*15)))}}/>

<style>
.daily-current-time{position:absolute;left:0;right:6px;display:flex;align-items:center;gap:4px;transform:translateY(-50%);color:#c4412c;font-size:11px;font-weight:700;pointer-events:none;z-index:3}
.daily-current-time span{width:39px;text-align:right;background:white}.daily-current-time i{height:2px;background:#c4412c;flex:1}
</style>
