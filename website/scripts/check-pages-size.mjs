import { opendir, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../dist/', import.meta.url));
async function sizeOf(directory) {
  let size = 0;
  for await (const entry of await opendir(directory)) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) size += await sizeOf(path);
    else if (entry.isFile()) size += (await stat(path)).size;
  }
  return size;
}
const size = await sizeOf(root);
console.log(`GitHub Pages output: ${(size / 1_000_000).toFixed(1)} MB (limit: 1,000 MB).`);
if (size > 1_000_000_000) throw new Error('Site exceeds the GitHub Pages 1 GB published-site limit.');
