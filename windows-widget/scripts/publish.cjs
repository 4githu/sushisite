// Publish completed artifacts atomically, so an in-progress build cannot corrupt a download.
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const version=require('../package.json').version;
async function publish(){
 const input=path.resolve(__dirname,'..',process.argv[2]||'build-release'),output=path.resolve(__dirname,'../dist');
 const names=[`NETAQ-Widget-Setup-${version}.exe`,`NETAQ-Widget-${version}-x64.zip`];
 for(const name of names){const file=await fs.open(path.join(input,name),'r');const bytes=Buffer.alloc(2);await file.read(bytes,0,2,0);await file.close();if(bytes.toString('ascii')!==(name.endsWith('.exe')?'MZ':'PK'))throw new Error('Invalid release artifact: '+name);}
 await fs.mkdir(output,{recursive:true});
 for(const name of names){const temporary=path.join(output,'.'+name+'.tmp');await fs.copyFile(path.join(input,name),temporary);await fs.rename(temporary,path.join(output,name));}
 const hashes=[];for(const name of names){const bytes=await fs.readFile(path.join(output,name));hashes.push(crypto.createHash('sha256').update(bytes).digest('hex')+'  '+name);}
 await fs.writeFile(path.join(output,'SHA256SUMS.txt'),hashes.join('\n')+'\n');console.log('Published complete NETAQ installers and checksums.');
}
publish().catch(error=>{console.error(error.message);process.exitCode=1;});
