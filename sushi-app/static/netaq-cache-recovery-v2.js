// Recover only NETAQ's old public asset cache; leave account data and drafts untouched.
(async () => {
  if (!('serviceWorker' in navigator) || !('caches' in window)) return;
  const key = 'netaq-static-repair-v2';
  try {
    const current = await navigator.serviceWorker.getRegistration('/personal-project/');
    const previous = navigator.serviceWorker.controller || current?.active;
    if (!previous || !new URL(previous.scriptURL).pathname.endsWith('/personal-sw.js')) return;
    if (sessionStorage.getItem(key)) return;
    const registration = await navigator.serviceWorker.register('/personal-sw-v2.js', {scope:'/personal-project/', updateViaCache:'none'});
    const worker = registration.installing || registration.waiting || registration.active;
    if (!worker) return;
    if (worker.state !== 'activated') await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('worker activation timed out')), 10000);
      worker.addEventListener('statechange', () => { if (worker.state === 'activated') { clearTimeout(timer); resolve(); } });
    });
    await caches.delete('netaq-static-v1');
    sessionStorage.setItem(key, 'done');
    location.reload();
  } catch (error) { console.error('NETAQ 정적 파일 복구 실패', error); }
})();
