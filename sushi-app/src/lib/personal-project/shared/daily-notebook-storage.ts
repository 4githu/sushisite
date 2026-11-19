import { createDriveAdapter } from '$lib/notebook/drive-adapter';
import { request } from './api';
import { verifiedPrivateOwner, samePrivateOwner } from './private-owner';
export function legacyDailyPages(data: any) {
 return (data?.pages || [{id:'daily',strokes:[],notes:[]}]).map((p:any)=>({id:p.id,w:420,h:760,source:null,paper:{pattern:'blank',color:'white'},items:[
 ...(p.strokes||[]).map((s:any)=>({...s,kind:'stroke',highlight:s.kind==='highlight',points:s.points.map((q:any)=>({x:q.x,y:(p.height||760)-q.y,p:q.pressure??q.p}))})),
 ...(p.notes||[]).map((n:any)=>({id:n.id,kind:'text',x:n.x,y:(p.height||760)-n.y-n.size,w:300,h:60,html:'<p>'+String(n.text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!)).replace(/\n/g,'<br>')+'</p>'}))
 ]}));
}
export function dailyNotebookStorage(date:string){
 const adapter=createDriveAdapter(`day-ink:${date}`,true);let owner='';
 return {
 async read(){owner=await verifiedPrivateOwner();const saved=await adapter.read('');if(saved)return saved;
 const old=await request<any>(`/documents/${encodeURIComponent('pdf:day-ink:'+date)}`);
 if(!await samePrivateOwner(owner))throw Error('계정이 변경됐어요.');
 return {title:date,pages:legacyDailyPages(old.data),pageIndex:0};},
 async save(value:any){if(!await samePrivateOwner(owner))throw Error('계정이 변경됐어요.');await adapter.save(value);}
 };
}
