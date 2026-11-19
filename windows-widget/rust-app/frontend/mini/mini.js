const invoke=(action)=>window.__TAURI__.core.invoke('mini_call',{action});
document.getElementById('memo').onclick=()=>void invoke('memo');
document.getElementById('restore').onclick=()=>void invoke('restore');
document.getElementById('grip').onmousedown=e=>{if(e.button===0)void window.__TAURI__.window.getCurrentWindow().startDragging();};
