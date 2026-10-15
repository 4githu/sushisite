// Only content-hashed build assets are cached. No HTML, auth or user data.
const ASSET_CACHE = 'netaq-static-v1';
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{
 const url = new URL(event.request.url);
 if(event.request.method==='GET' && url.origin===self.location.origin && url.pathname.startsWith('/_app/immutable/')) {
   event.respondWith(caches.open(ASSET_CACHE).then(async cache => {
     const cached = await cache.match(event.request);
     if(cached) return cached;
     const response = await fetch(event.request);
     if(response.ok) {
       await cache.put(event.request,response.clone());
       const keys = await cache.keys();
       await Promise.all(keys.slice(0,Math.max(0,keys.length-150)).map(key=>cache.delete(key)));
     }
     return response;
   }));
   return;
 }
 if(event.request.mode!=='navigate'||!new URL(event.request.url).pathname.startsWith('/personal-project/'))return;
 event.respondWith(fetch(event.request).catch(()=>new Response(`<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>연결을 확인해주세요</title><body style="font:16px system-ui;padding:12vh 24px;max-width:480px;margin:auto;color:#253244"><h1>인터넷 연결이 필요합니다.</h1><p>최신 일정을 불러오려면 네트워크에 연결해주세요.</p><button onclick="location.reload()" style="padding:12px 20px">다시 시도</button></body></html>`,{headers:{'Content-Type':'text/html; charset=utf-8'}})));
});
