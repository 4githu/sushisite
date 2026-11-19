<script lang="ts">
 let {value=$bindable(''),options=[]}:{value:string;options:string[]}=$props();
 let open=$state(false),active=$state(-1);
 const key=(s:string)=>s.normalize('NFC').replace(/[\s·ㆍ.()]/g,'').toLowerCase();
 const initials=(s:string)=>Array.from(s).map(c=>{const n=c.charCodeAt(0)-44032;return n>=0&&n<11172?'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'[Math.floor(n/588)]:c;}).join('');
 const matches=$derived(options.filter(d=>key(d).includes(key(value)) || initials(key(d)).includes(key(value))));
 function choose(d:string){value=d;open=false;active=-1;}
 function keys(e:KeyboardEvent){
  if(e.isComposing)return;
  if(e.key==='Escape'){open=false;return;}
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();open=true;active=Math.max(0,Math.min(matches.length-1,active+(e.key==='ArrowDown'?1:-1)));}
  if(e.key==='Enter'&&open&&active>=0&&matches[active]){e.preventDefault();choose(matches[active]);}
 }
</script>
<div class="picker">
 <label for="department-search">학과·전공</label>
 <input id="department-search" role="combobox" aria-autocomplete="list" aria-expanded={open} aria-controls="department-options" aria-activedescendant={open&&active>=0?`department-${active}`:undefined} bind:value maxlength="120" placeholder="학과 이름이나 초성으로 검색" autocomplete="off" onfocus={()=>{open=true;active=-1;}} oninput={()=>{open=true;active=-1;}} onkeydown={keys} onblur={()=>{open=false;}} />
 {#if open}<div id="department-options" role="listbox" aria-label="학과 선택" class="options">
  {#each matches as d,i}<button id={`department-${i}`} type="button" role="option" aria-selected={value===d} class:active={i===active} tabindex="-1" onpointerdown={(e)=>e.preventDefault()} onclick={()=>choose(d)}>{d}</button>{/each}
  {#if !matches.length}<p>일치하는 학과가 없습니다. 입력한 이름으로 저장할 수 있습니다.</p>{/if}
 </div>{/if}
 <small>목록에서 선택하면 정확한 이름이 입력됩니다.</small>
</div>
<style>.picker{position:relative;margin:16px 0}label{display:block;margin-bottom:7px}input{width:100%;box-sizing:border-box}small{display:block;margin-top:6px;color:var(--muted,#777)}.options{position:absolute;z-index:20;top:74px;left:0;right:0;max-height:260px;overflow:auto;background:var(--surface,#fff);border:1px solid var(--border,#ddd);border-radius:10px;box-shadow:0 6px 24px #0002;padding:5px}.options button{display:block;width:100%;text-align:left;border:0;background:transparent;padding:10px}.options button:hover,.options button.active{background:var(--surface-hover,#eee)}.options p{padding:8px;margin:0;font-size:13px}</style>
