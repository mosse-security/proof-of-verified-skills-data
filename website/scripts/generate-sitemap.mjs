import { readdir, writeFile } from 'node:fs/promises';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { siteUrl } from '../site-config.mjs';

const dist = fileURLToPath(new URL('../dist/', import.meta.url));
const escapeXml = (value) => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&apos;');

async function htmlFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return htmlFiles(path);
    return entry.isFile() && entry.name.endsWith('.html') ? [path] : [];
  }));
  return files.flat();
}

const files = await htmlFiles(dist);
const urls = files.map((file) => relative(dist, file).split(sep).join('/'))
  .filter((path) => path !== '404.html')
  .map((path) => path === 'index.html' ? '' : path.endsWith('/index.html') ? path.slice(0, -'index.html'.length) : path)
  .map((path) => new URL(path, siteUrl).href)
  .sort();

const chunks = [];
for (let i = 0; i < urls.length; i += 50000) chunks.push(urls.slice(i, i + 50000));
if (!chunks.length) throw new Error('No HTML pages found; refusing to generate an empty sitemap.');
const header = '<?xml version="1.0" encoding="UTF-8"?>\n';
const urlset = (items) => `${header}<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${items.map((url) => `  <url><loc>${escapeXml(url)}</loc></url>`).join('\n')}\n</urlset>\n`;
if (chunks.length === 1) {
  await writeFile(join(dist, 'sitemap.xml'), urlset(chunks[0]));
} else {
  const names = chunks.map((_, index) => `sitemap-${index + 1}.xml`);
  await Promise.all(chunks.map((chunk, index) => writeFile(join(dist, names[index]), urlset(chunk))));
  await writeFile(join(dist, 'sitemap.xml'), `${header}<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${names.map((name) => `  <sitemap><loc>${escapeXml(new URL(name, siteUrl).href)}</loc></sitemap>`).join('\n')}\n</sitemapindex>\n`);
}
console.log(`Generated sitemap for ${urls.length} pages.`);
