<script lang="ts">
 import {onMount,onDestroy} from 'svelte';
 import {beforeNavigate} from '$app/navigation';
 import {privateCacheUser} from '$lib/personal-project/shared/auth';
 import {request} from '$lib/personal-project/shared/api';
 import type {Stroke,InkPoint} from '$lib/personal-project/pdf/model';
 import {erase} from '$lib/personal-project/pdf/model';
 type Box={page:number;x:number;y:number;w:number;h:number;number:string;points:number};
 type Question={number:string;points:number;deduction:number|null;comment:string;reviewed:boolean};
 type Sheet={id:string;name:string;pages:number;revision:number;data:{ink?:Record<string,Stroke[]>;questions?:Question[];feedback?:string;feedbackReviewed?:boolean}};
 type Round={id:string;name:string;revision:number;data:{answer?:string;first?:number;last?:number;boxes?:Box[]};files:Sheet[]};
 let rounds=$state<{id:string;name:string}[]>([]),round=$state<Round|null>(null),file=$state<Sheet|null>(null),name=$state(''),page=$state(0),busy=$state(false),error=$state(''),notice=$state('');
 let mode=$state<'pen'|'highlight'|'erase'|'box'>('pen'),color=$state('#dc2626'),points=$state(5),number=$state('1-1'),penOnly=$state(true);
 let ink=$state<Stroke[]>([]),active=$state<Stroke|null>(null),startPoint:InkPoint|null=null,preview=$state<Box|null>(null),width=$state(612),height=$state(792),canvas=$state<HTMLCanvasElement>(null!);
 let past:Stroke[][]=[];
 let saved=$state(''),restored=$state(false),disposed=false;
 const snapshot=$derived(file?JSON.stringify({...file.data,ink:{...file.data.ink,[page]:ink}}):'');
 const dirty=$derived(!!file && snapshot!==saved);
 const localKey=()=>`ondo-private:${privateCacheUser()}:grading:${file?.id}`;
 $effect(()=>{const data=snapshot;if(!file||!dirty||restored)return;if(privateCacheUser())try{localStorage.setItem(localKey(),JSON.stringify({data:JSON.parse(data),revision:file.revision}));}catch{error='로컬 복구본을 저장하지 못했습니다. 저장 버튼을 눌러주세요.';}if(!busy&&!error&&!active){const timer=setTimeout(()=>void run(persist),700);return()=>clearTimeout(timer);}});
 beforeNavigate(({cancel})=>{if(dirty&&!confirm('저장되지 않은 필기가 있습니다. 복구본을 남기고 이동할까요?'))cancel();});
 onDestroy(()=>{disposed=true;});

 const boxes=$derived((round?.data.boxes||[]).filter(b=>b.page===page));
 async function run(fn:()=>Promise<void>){if(busy)return;busy=true;error='';try{await fn();}catch(e){error=String(e);}finally{busy=false;}}
 async function load(){rounds=await request('/aura/grading');}
 onMount(()=>{void run(load);});
 async function openRound(id:string){await persist();round=await request(`/aura/grading/rounds/${id}`);file=null;page=0;ink=[];}
 async function persist(){if(!file)return;if(restored)throw Error('복구본을 먼저 불러오거나 삭제해주세요.');
 file.data.ink={...file.data.ink,[page]:ink};const encoded=JSON.stringify(file.data);
 const result=await request<{revision:number}>(`/aura/grading/files/${file.id}`,{method:'PUT',body:{data:JSON.parse(encoded),revision:file.revision}});
 file.revision=result.revision;saved=encoded;if(privateCacheUser()&&snapshot===encoded)localStorage.removeItem(localKey());notice='저장됨';}

 async function saveRound(){if(!round)return;const result=await request<{revision:number}>(`/aura/grading/rounds/${round.id}`,{method:'PUT',body:{data:round.data,revision:round.revision}});round.revision=result.revision;}
 async function selectFile(next:Sheet){await persist();file=next;page=0;saved=JSON.stringify(next.data);restored=false;if(privateCacheUser()){const local=localStorage.getItem(localKey());if(local){restored=true;notice='이 기기에 저장 대기 중인 복구본이 있습니다.';}}ink=structuredClone($state.snapshot(next.data.ink?.['0']||[]));past=[];}
 async function changePage(next:number){await persist();page=next;ink=structuredClone($state.snapshot(file?.data.ink?.[String(page)]||[]));past=[];}
 function point(e:PointerEvent):InkPoint{const r=canvas.getBoundingClientRect();return {x:(e.clientX-r.left)*width/r.width,y:(e.clientY-r.top)*height/r.height,pressure:e.pressure||.5};}
 function down(e:PointerEvent){if(busy || (penOnly && e.pointerType!=='pen' && mode!=='box'))return;e.preventDefault();canvas.setPointerCapture(e.pointerId);const p=point(e);startPoint=p;past.push(structuredClone($state.snapshot(ink)));if(mode==='box'){preview={page,x:p.x,y:p.y,w:0,h:0,number,points};}else if(mode==='erase'||e.button===5||(e.buttons&32)){ink=erase(ink,p,10);}else{active={id:crypto.randomUUID(),kind:mode==='highlight'?'highlight':'pen',color,width:mode==='highlight'?12:2,points:[p]};ink=[...ink,active];}}
 function move(e:PointerEvent){if(!canvas.hasPointerCapture(e.pointerId)||!startPoint)return;e.preventDefault();const p=point(e);if(preview){preview={...preview,x:Math.min(startPoint.x,p.x),y:Math.min(startPoint.y,p.y),w:Math.abs(p.x-startPoint.x),h:Math.abs(p.y-startPoint.y)};}else if(mode==='erase'||e.button===5||(e.buttons&32)){ink=erase(ink,p,10);}else if(active){active.points.push(p);ink=[...ink];}}
 function up(e:PointerEvent){if(!canvas.hasPointerCapture(e.pointerId))return;canvas.releasePointerCapture(e.pointerId);if(preview&&round&&preview.w>30&&preview.h>35&&page+1>=(round.data.first||1)&&page+1<=(round.data.last||file!.pages)){round.data.boxes=[...(round.data.boxes||[]),preview];void run(saveRound);}preview=null;startPoint=null;active=null;}
 $effect(()=>{if(!canvas)return;const ctx=canvas.getContext('2d');if(!ctx)return;ctx.clearRect(0,0,width,height);for(const s of ink){ctx.strokeStyle=s.color;ctx.lineWidth=s.width;ctx.globalAlpha=s.kind==='highlight'?.3:1;ctx.lineCap='round';ctx.beginPath();s.points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();}ctx.globalAlpha=1;});
 async function upload(files:FileList|null){if(!round||!files)return;await persist();for(const f of Array.from(files)){const body=new FormData();body.append('file',f);const res=await fetch(`/api/personal/aura/grading/rounds/${round.id}/files`,{method:'POST',body,credentials:'include'});if(!res.ok)throw Error((await res.json()).detail||'업로드 실패');}round=await request(`/aura/grading/rounds/${round.id}`);}
 async function recognize(){await persist();if(!file)return;const id=file.id;
 const job=await request<{id:string}>(`/aura/grading/files/${id}/recognize-jobs`,{method:'POST'});
 notice='필기를 변환하고 있습니다. 원본과 필기는 보존됩니다.';
 while(!disposed){const r=await request<{state:string;result:{questions:Question[]}|null;error?:string}>(`/aura/grading/jobs/${job.id}`);
 if(r.state==='failed')throw Error(r.error||'변환 실패');
 if(r.state==='done'){if(file?.id===id&&r.result){file.data.questions=r.result.questions;file.data.feedbackReviewed=false;await persist();notice='점수와 코멘트를 확인한 뒤 확인 체크를 선택해주세요.';}return;}
 await new Promise(resolve=>setTimeout(resolve,2000));}
 }
 async function polish(){await persist();if(!file)return;const result=await request<{feedback:string}>(`/aura/grading/files/${file.id}/feedback`,{method:'POST'});file.data.feedback=result.feedback;file.data.feedbackReviewed=false;await persist();notice='생성한 피드백을 확인하고 확정해주세요.';}
 function manualReview(){if(!file||!round)return;if(file.data.questions?.length&&!confirm('현재 입력한 점수·코멘트를 비우고 다시 입력할까요?'))return;file.data.questions=(round.data.boxes||[]).filter(b=>b.page+1>=(round!.data.first||1)&&b.page+1<=(round!.data.last||file!.pages)).map(b=>({number:b.number,points:b.points,deduction:null,comment:'',reviewed:false}));}
 function cancelStroke(e:PointerEvent){if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);if(startPoint){const previous=past.pop();if(previous)ink=previous;}preview=null;startPoint=null;active=null;}

 async function download(kind:'xlsx'|'json'|'pdf'){await persist();const path=kind==='pdf'?`files/${file?.id}/pdf`:`rounds/${round?.id}/${kind==='json'?'results':'xlsx'}`;const res=await fetch(`/api/personal/aura/grading/${path}`,{credentials:'include'});if(!res.ok)throw Error((await res.json()).detail||'내보내기 실패');const url=URL.createObjectURL(await res.blob());const a=document.createElement('a');a.href=url;a.download=`${kind==='pdf'?file?.name:round?.name}.${kind}`;a.click();URL.revokeObjectURL(url);}
</script>
<svelte:head><title>시험지 채점 · 아우라</title></svelte:head>
<main><header><h1>시험지 채점</h1><form onsubmit={e=>{e.preventDefault();void run(async()=>{const r=await request<{id:string}>('/aura/grading',{method:'POST',body:{name}});await load();await openRound(r.id);name='';});}}><input aria-label="새 회차 이름" placeholder="회차 이름" bind:value={name} required/><button disabled={busy}>회차 추가</button></form></header>
<nav>{#each rounds as r}<button class:active={round?.id===r.id} disabled={busy} onclick={()=>run(()=>openRound(r.id))}>{r.name}</button>{/each}</nav>
{#if error}<p role="alert">{error}</p>{/if}{#if notice}<p role="status">{notice}</p>{/if}
{#if round}<section class="settings"><label>PDF·ZIP 추가<input type="file" accept=".pdf,.zip" multiple disabled={busy} onchange={e=>{const files=e.currentTarget.files;void run(()=>upload(files));}}/></label>
<label>답지<select value={round.data.answer||''} disabled={busy} onchange={e=>{if(round!.data.boxes?.length&&!confirm('답지를 바꾸면 문항 영역을 다시 지정해야 합니다. 바꿀까요?')){e.currentTarget.value=round!.data.answer||'';return;}round!.data.answer=e.currentTarget.value;round!.data.first=1;round!.data.last=round!.files.find(f=>f.id===round!.data.answer)?.pages||1;round!.data.boxes=[];void run(saveRound);}}><option value="">답지 선택</option>{#each round.files as f}<option value={f.id}>{f.name}</option>{/each}</select></label>
<label>문제 시작 페이지<input type="number" min="1" bind:value={round.data.first} onchange={()=>run(saveRound)}/></label><label>문제 끝 페이지<input type="number" min={round.data.first||1} bind:value={round.data.last} onchange={()=>run(saveRound)}/></label>
<button disabled={busy} onclick={()=>run(()=>download('json'))}>JSON 내보내기</button><button disabled={busy} onclick={()=>run(()=>download('xlsx'))}>엑셀 내보내기</button></section>
<div class="workspace"><aside>{#each round.files as f}<button class:active={file?.id===f.id} disabled={busy} onclick={()=>run(()=>selectFile(f))}>{f.id===round.data.answer?'답지 · ':''}{f.name}</button>{/each}</aside><section>
{#if file}{#if restored}<p role="status">저장되지 않은 필기가 있습니다. <button onclick={()=>{try{const local=JSON.parse(localStorage.getItem(localKey())||'null');if(local){file!.data=local.data;ink=structuredClone(local.data.ink?.[page]||[]);restored=false;notice='복구본을 불러왔습니다. 확인 후 저장해주세요.';}}catch(e){error=String(e);}}}>복구본 불러오기</button><button onclick={()=>{localStorage.removeItem(localKey());restored=false;}}>서버 내용 유지</button></p>{/if}<div class="tools"><input aria-label="학생·PDF 이름" bind:value={file.name}/><button disabled={busy} onclick={()=>run(async()=>{await request(`/aura/grading/files/${file!.id}/name`,{method:'PUT',body:{name:file!.name}});})}>이름 저장</button>
<button disabled={busy||page===0} onclick={()=>run(()=>changePage(page-1))}>이전</button><span>{page+1} / {file.pages}</span><button disabled={busy||page+1===file.pages} onclick={()=>run(()=>changePage(page+1))}>다음</button>
{#each [['pen','펜'],['highlight','형광펜'],['erase','획 지우개']] as [id,label]}<button class:active={mode===id} onclick={()=>mode=id as typeof mode}>{label}</button>{/each}
{#if file.id===round.data.answer}<button class:active={mode==='box'} onclick={()=>mode='box'}>문항 박스</button><input aria-label="문항 번호" bind:value={number}/><input aria-label="배점" type="number" min="0" max="1000" bind:value={points}/>{/if}
<input type="color" aria-label="펜 색" bind:value={color}/><label><input type="checkbox" bind:checked={penOnly}/>펜으로만 필기</label><button onclick={()=>{const p=past.pop();if(p)ink=p;}}>실행 취소</button>
<button disabled={busy} onclick={()=>run(persist)}>임시저장</button><button disabled={busy||file.id===round.data.answer||!round.data.answer} onclick={()=>run(recognize)}>변환·OCR</button><button disabled={busy||file.id===round.data.answer} onclick={manualReview}>직접 점수·코멘트 입력</button><button disabled={busy} onclick={()=>run(()=>download('pdf'))}>필기 PDF</button></div>
<div class="page" style:aspect-ratio={`${width}/${height}`}>
<img src={`/api/personal/aura/grading/files/${file.id}/pages/${page}`} alt={`${file.name} ${page+1}페이지`} onload={e=>{width=(e.currentTarget as HTMLImageElement).naturalWidth;height=(e.currentTarget as HTMLImageElement).naturalHeight;}}/>
<canvas bind:this={canvas} {width} {height} style:touch-action="none" onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={cancelStroke} aria-label="시험지 필기"></canvas>
{#if page+1 >= (round.data.first||1) && page+1 <= (round.data.last||file.pages)}{#each [...boxes,...(preview?[preview]:[])] as b}<div class="question" style:left={`${b.x/width*100}%`} style:top={`${b.y/height*100}%`} style:width={`${b.w/width*100}%`} style:height={`${b.h/height*100}%`}><span>{b.number} · {b.points}점</span><div class="deduction" style:width={`${70/b.w*100}%`} style:height={`${30/b.h*100}%`}></div></div>{/each}{/if}
</div>
{#if file.id===round.data.answer}<div>{#each round.data.boxes||[] as b,i}<button onclick={()=>run(async()=>{round!.data.boxes=round!.data.boxes!.filter((_,n)=>n!==i);await saveRound();})}>{b.page+1}쪽 {b.number} 박스 삭제</button>{/each}</div>{/if}
{#each file.data.questions||[] as q}<div class="review"><strong>{q.number} · {q.points}점</strong><label>감점<input type="number" min="0" max={q.points} step="0.5" bind:value={q.deduction}/></label><textarea aria-label={`${q.number} 코멘트`} bind:value={q.comment}></textarea><label><input type="checkbox" bind:checked={q.reviewed}/>인식 결과 확인</label></div>{/each}
{#if file.data.questions?.length}<div class="feedback"><button disabled={busy} onclick={()=>run(polish)}>검수한 코멘트로 AI 피드백 생성</button><small>이름·PDF는 전송하지 않고 검수한 문항별 코멘트만 전송합니다.</small>{#if file.data.feedback}<textarea aria-label="학생 피드백" bind:value={file.data.feedback}></textarea><label><input type="checkbox" bind:checked={file.data.feedbackReviewed}/>피드백 확인 · 엑셀에 사용</label>{/if}<button disabled={busy} onclick={()=>run(persist)}>검수 결과 저장</button></div>{/if}
{:else}<p>답지를 선택해 문항 영역을 지정한 뒤 학생 PDF를 열어 채점하세요.</p>{/if}
</section></div>{/if}</main>
<style>main{padding:24px;max-width:1500px;margin:auto}form{display:flex;gap:8px;flex-wrap:wrap}input[type=file]{max-width:100%}.settings label{flex-wrap:wrap;min-width:0}.workspace>section{min-width:0}header,nav,.settings,.tools,.review{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:16px}button,input,select,textarea{border:1px solid #8885;border-radius:7px;background:var(--surface,#fff);color:inherit;padding:7px 10px;min-height:36px}input[type=checkbox]{min-height:0;padding:0;width:16px;height:16px}button{cursor:pointer}button.active{background:#8b5cf61a;border-color:#8b5cf6}button:disabled{opacity:.45}label{display:flex;gap:6px;align-items:center}input[type=number]{width:80px}.workspace{display:grid;grid-template-columns:180px minmax(0,1fr);gap:20px}aside{display:flex;flex-direction:column;gap:8px}.page{position:relative;max-width:850px;background:white}.page img,.page canvas{position:absolute;inset:0;width:100%;height:100%}.question{position:absolute;border:1px dashed #7c3aed;pointer-events:none}.question>span{position:absolute;left:0;top:-22px;font-size:12px;color:#6d28d9;background:white}.deduction{border:1px solid #c084fc;position:absolute;top:0;left:0}.tools{position:sticky;top:0;background:var(--surface,#fff);z-index:5;padding:8px}.feedback{display:grid;gap:10px;margin-block:20px}.feedback textarea{min-height:160px}.review textarea{flex:1;min-width:200px}@media(max-width:700px){.workspace{grid-template-columns:1fr}aside{flex-direction:row;overflow:auto}main{padding:12px}}</style>
