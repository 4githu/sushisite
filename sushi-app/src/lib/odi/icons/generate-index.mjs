import fs from "node:fs";
import path from "node:path";

const dir = path.dirname(new URL(import.meta.url).pathname);
const index = path.join(dir, "index.ts");

const files = fs.readdirSync(dir)
  .filter(f => /\.(svg|png)$/.test(f))
  .sort();

const keep = fs.existsSync(index) ? fs.readFileSync(index, "utf8") : "";

const lines = [keep.trim(), "", "// auto generated"];

const exported = new Set(
  [...keep.matchAll(/export\s+\{\s*default\s+as\s+(\w+)/g)].map(m => m[1])
);

for (const file of files) {
  const name = path.parse(file).name;

  if (exported.has(name)) continue;

  lines.push(`export { default as ${name} } from "./${file}";`);
}

fs.writeFileSync(index, lines.join("\n") + "\n");

console.log("done");