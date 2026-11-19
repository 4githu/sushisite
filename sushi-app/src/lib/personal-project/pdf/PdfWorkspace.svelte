<script lang="ts">
 import NotebookWorkspace from '$lib/notebook/NotebookWorkspace.svelte';
 let {resourceId,url,name,onclose}:{resourceId:string;url:string;name:string;onclose?:()=>void}=$props();
</script>
<NotebookWorkspace {resourceId} {url} {name} {onclose}/>
