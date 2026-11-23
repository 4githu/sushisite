const http=require('node:http'),fs=require('node:fs');
http.createServer((req,res)=>{
 if(req.url.startsWith('/report?')){fs.writeFileSync(process.env.PROOF_PATH,req.url);res.end('ok');return;}
 res.setHeader('Content-Type','text/html');res.end(`<!doctype html><body>NETAQ smoke<script>
(async()=>{let exposed=false;try{let host=chrome.webview.hostObjects.sync.RainmeterAPI;host.GetVariable('CURRENTCONFIG');exposed=true}catch(e){}await fetch('/report?exposed='+exposed)})();
</script>`);
}).listen(4279,'127.0.0.1');
