// Publish only a completed, signed NSIS bundle. Versioned files are never overwritten.
import {copyFile, mkdir, readFile, writeFile, rename} from 'node:fs/promises';
import {constants} from 'node:fs';
import {resolve, join} from 'node:path';
const [version, binary] = process.argv.slice(2);
if (!version || !/^\d+\.\d+\.\d+$/.test(version) || !binary) throw Error('Usage: node scripts/stage-update.mjs VERSION /path/to/signed-setup.exe');
const dist=resolve('dist');await mkdir(dist,{recursive:true});
const filename=`NETAQ-${version}-x64-setup.exe`, signature=(await readFile(binary+'.sig','utf8')).trim();
if (!signature) throw Error('Missing updater signature');
await copyFile(binary,join(dist,filename),constants.COPYFILE_EXCL);
const manifest={version,notes:'NETAQ 업데이트',platforms:{'windows-x86_64':{signature,url:`https://netaq.chobab.app/downloads/windows-updates/${version}`}}};
const temp=join(dist,`updater-manifest.${process.pid}.tmp`);await writeFile(temp,JSON.stringify(manifest));await rename(temp,join(dist,'updater-manifest.json'));
console.log(`Prepared signed update ${version}`);
