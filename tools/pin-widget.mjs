// Pin all bundled widget entry points. The host never exposes credentials to widget code.
import { createHash } from 'node:crypto';
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
const [widgetDir, packageDir] = process.argv.slice(2);
if (!widgetDir || !packageDir) throw new Error('Usage: node tools/pin-widget.mjs WIDGET_DIR PACKAGE_DIR');
const manifest=JSON.parse(await readFile(path.join(widgetDir,'vitrine.json'),'utf8'));
const allowed=['today','week','month','tasks','memo'];
if(manifest.id!=='app.chobab.netaq.widgets'||manifest.widgets.length!==allowed.length||!allowed.every(id=>manifest.widgets.some(w=>w.id===id)))throw Error('Unexpected widget set');
const rows=[];
for(const id of allowed){const js=await readFile(path.join(widgetDir,'dist/widgets',id,'index.js'));rows.push(`    ("${id}", "${createHash('sha256').update(js).digest('hex')}"),`)}
const sourceFile=path.resolve(import.meta.dirname,'../crates/vitrine-app/src/netaq.rs');
const old=await readFile(sourceFile,'utf8');
const next=old.replace(/const BUNDLE_DIGESTS: &\[\(&str, &str\)\] = &\[[\s\S]*?\];/,`const BUNDLE_DIGESTS: &[(&str, &str)] = &[\n${rows.join('\n')}\n];`);
if(old===next&&!old.includes(rows[0]))throw Error('Could not find digest table');
await writeFile(sourceFile,next);await mkdir(packageDir,{recursive:true});
await copyFile(path.join(widgetDir,`widgets-${manifest.version}.vitrine`),path.join(packageDir,`widgets-${manifest.version}.vitrine`));
console.log(`Pinned ${rows.length} widgets (${manifest.version})`);
