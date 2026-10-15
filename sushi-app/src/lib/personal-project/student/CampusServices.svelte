<script lang="ts">
 import { onMount } from 'svelte';
 import { request } from '../shared/api';
 type Status={school:string;catalog:boolean;meals:boolean;rules:boolean;catalogTerms:string[];catalogUpdatedAt:string;officialLinks:{label:string;url:string}[]};
 let data=$state<Status|null>(null),error=$state('');
 async function load(){error='';try{data=await request('/student/school-services');}catch(e){error=e instanceof Error?e.message:'연동 정보를 불러오지 못했습니다.';}}
 onMount(load);
</script>
<section class="panel">
 <h2>학교 서비스 연동</h2>
 {#if error}<p role="alert">{error}</p><button onclick={load}>다시 불러오기</button>
 {:else if data}
 <p class="muted">{data.school || '학교를 선택해주세요.'}</p>
 <dl>{#each [['강의 검색',data.catalog],['학식',data.meals],['공식 이수규정',data.rules]] as [name,connected]}<div><dt>{name}</dt><dd class:connected>{connected?'연동됨':'미연동'}</dd></div>{/each}</dl>
 {#if data.catalogTerms.length}<p class="muted">제공 학기: {data.catalogTerms.join(' · ')}</p>{/if}
 {#if data.catalogUpdatedAt}<p class="muted">강의 자료 갱신: {new Date(data.catalogUpdatedAt).toLocaleDateString('ko-KR')}</p>{/if}
 {#if data.officialLinks.length}<details><summary>학교 공식 안내</summary>{#each data.officialLinks as link}<p><a href={link.url} target="_blank" rel="noopener noreferrer">{link.label} ↗</a></p>{/each}</details>{/if}
 {:else}<p role="status">연동 상태 확인 중…</p>{/if}
</section>
<style>section{margin-top:20px}dl{margin:0}dl div{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border,#ddd)}dd{margin:0;color:var(--muted,#777)}dd.connected{color:var(--accent,#287853);font-weight:600}details{margin-top:16px}p{overflow-wrap:anywhere}</style>
