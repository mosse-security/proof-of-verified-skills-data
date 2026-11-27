import sharp from 'sharp';
import { mkdir, readdir, readFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { MIN_SOCIAL_CARD_ENDORSEMENTS } from '../src/lib/social-card.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const individuals = resolve(root, '../data/individuals');
const output = resolve(process.env.SOCIAL_CARD_OUTPUT || join(root, 'dist/social'));
const limit = Number(process.env.SOCIAL_CARD_LIMIT || 0);
const selectedSlug = process.env.SOCIAL_CARD_SLUG;
const defaultOnly = process.env.SOCIAL_CARD_DEFAULT_ONLY === '1';
const workers = Math.max(1, Math.min(8, Number(process.env.SOCIAL_CARD_WORKERS || 4)));
const escapeXml = (value) => String(value).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&apos;');

function wrapName(name) {
  const lines = [];
  for (const word of name.trim().split(/\s+/)) {
    const last = lines.at(-1);
    if (last && `${last} ${word}`.length <= 24) lines[lines.length - 1] += ` ${word}`;
    else lines.push(word);
  }
  return lines.length ? lines : ['Unknown'];
}

function textSvg(name, summaryLines = [], centerY = 300) {
  const lines = wrapName(name);
  const size = Math.min(name.length > 28 ? 72 : 104, 180 / lines.length);
  const lineHeight = size * 1.2;
  const start = centerY - (lines.length - 1) * lineHeight / 2;
  const summaryY = start + (lines.length - 1) * lineHeight + size * .95;
  const texts = lines.map((line, i) => `<text x="600" y="${start + i * lineHeight}" text-anchor="middle" dominant-baseline="middle" font-family="Arial, sans-serif" font-weight="700" font-size="${size}" fill="#021338"${line.length * size * .62 > 1070 ? ' textLength="1070" lengthAdjust="spacingAndGlyphs"' : ''}>${escapeXml(line)}</text>`).join('');
  const summaryText = summaryLines.map((line, i) => `<text x="600" y="${summaryY + i * 49}" text-anchor="middle" font-family="Arial, sans-serif" font-weight="600" font-size="40" fill="#35465e"${line.length * 22 > 1070 ? ' textLength="1070" lengthAdjust="spacingAndGlyphs"' : ''}>${escapeXml(line)}</text>`).join('');
  return Buffer.from(`<svg width="1200" height="630" xmlns="http://www.w3.org/2000/svg">${texts}${summaryText}</svg>`);
}

async function main() {
  const background = await sharp(join(root, 'assets/social-background.png')).resize(1200, 630, { fit: 'cover' }).png().toBuffer();
  const pixels = await sharp(background).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  for (let i = 3; i < pixels.data.length; i += 4) pixels.data[i] = Math.min(255, pixels.data[i] * 5);
  const strongerBackground = await sharp(pixels.data, { raw: pixels.info }).png().toBuffer();
  async function makeBase(logoWidth, veilOpacity, backgroundImage = background) {
    const logo = await sharp(join(root, 'public/vct-logo.png')).resize({ width: logoWidth }).png().toBuffer();
    const veil = Buffer.from(`<svg width="1200" height="630" xmlns="http://www.w3.org/2000/svg"><rect width="1200" height="630" fill="white" fill-opacity="${veilOpacity}"/></svg>`);
    return sharp({ create: { width: 1200, height: 630, channels: 3, background: '#fff' } }).composite([{ input: backgroundImage }, { input: veil }, { input: logo, top: 64, left: Math.round((1200 - logoWidth) / 2) }]).png().toBuffer();
  }
  await mkdir(output, { recursive: true });
  async function render(base, filename, name, summaryLines, centerY) {
    await sharp(base).composite([{ input: textSvg(name, summaryLines, centerY), left: 0, top: 0 }]).jpeg({ quality: 78, mozjpeg: true }).toFile(join(output, filename));
  }
  const defaultBase = await makeBase(680, 0.30, strongerBackground);
  await render(defaultBase, 'default.jpg', 'Proof of Verified Cybersecurity Skills', [], 350);
  if (defaultOnly) return;
  const base = await makeBase(440, 0.88);
  let files = (await readdir(individuals)).filter((file) => file.endsWith('.json')).sort();
  if (selectedSlug) {
    files = files.filter((file) => file === `${selectedSlug}.json`);
    if (!files.length) throw new Error('Selected profile was not found.');
  }
  if (limit > 0) files = files.slice(0, limit);
  let next = 0;
  let generated = 0;
  const start = Date.now();
  async function worker() {
    while (next < files.length) {
      const file = files[next++];
      const person = JSON.parse(await readFile(join(individuals, file), 'utf8'));
      const endorsements = person.endorsements ?? [];
      const count = endorsements.length;
      if (count < MIN_SOCIAL_CARD_ENDORSEMENTS) continue;
      const assessors = person.stats?.assessors ?? new Set(endorsements.map((item) => item['assessor-id'] || item.assessor)).size;
      const summary = [`${count} public ${count === 1 ? 'record' : 'records'} of work,`, `assessed by ${assessors} independent ${assessors === 1 ? 'organization' : 'organizations'}.`];
      await render(base, `${file.slice(0, -5)}.jpg`, person.name || 'Unknown', summary);
      generated++;
    }
  }
  await Promise.all(Array.from({ length: Math.min(workers, files.length) }, worker));
  console.log(`Generated ${generated} profile cards and one default from ${files.length} profiles in ${((Date.now() - start) / 1000).toFixed(1)}s.`);
}

await main();
