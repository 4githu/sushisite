const invoke = (action, args = {}) => window.__TAURI__.core.invoke('widget_call', { action, args });
window.netaq = Object.freeze({
 state:()=>invoke('state'), desktopState:()=>invoke('desktop-state'), desktop:()=>invoke('attach-desktop'), float:()=>invoke('detach-desktop'), update:()=>invoke('update'), version:()=>invoke('version'), claim:(code,origin)=>invoke('claim',{code,origin}), feed:(view,date)=>invoke('feed',{view,date}), cached:(view,date)=>invoke('cached',{view,date}),
 complete:(source,id,done)=>invoke('complete',{source,id:String(id),done}), capture:(id,text)=>invoke('capture',{id,text}),
 draft:value=>invoke('draft',{value}), disconnect:()=>invoke('disconnect'), settings:value=>invoke('settings',{value}),
 open:route=>invoke('open',{route}), window:action=>invoke('window',{action})
});

window.addEventListener('DOMContentLoaded',()=>{document.getElementById('resize-window').addEventListener('mousedown',event=>{if(event.button===0)window.__TAURI__.window.getCurrentWindow().startResizeDragging('SouthEast').catch(()=>{});});});
