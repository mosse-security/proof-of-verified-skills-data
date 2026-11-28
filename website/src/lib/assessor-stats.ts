import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { listProfiles } from './records';

export type AssessorStats = {
  id: string; name: string; records: number; people: number;
  unknownDomain: number; unknownLocation: number; noWorkLink: number; noYear: number;
  years: Record<string, number>; domains: Record<string, number>; captureStatus: string | null; lastCapture: string | null;
  rejectedNames: number | null; reviewNames: number | null; sourceUrls: number;
  pages: { url: string; status: 'parsed' | 'failed' | 'unknown'; records: number | null; published: number }[];
};

const assessorDir = [resolve(process.cwd(), 'data/assessors'), resolve(process.cwd(), '../data/assessors'), resolve(process.cwd(), '../../data/assessors')].find(existsSync);
let cached: AssessorStats[] | undefined;

function countLines(path: string): number | null {
  if (!existsSync(path)) return null;
  return readFileSync(path, 'utf8').split(/\r?\n/).filter((line) => line.trim() && !line.trim().startsWith('#')).length;
}

export function listAssessorStats(): AssessorStats[] {
  if (cached) return cached;
  if (!assessorDir) throw new Error('Could not locate assessor metadata.');
  const assessors = new Map<string, AssessorStats>();
  const pageIndexes = new Map<string, Map<string, AssessorStats['pages'][number] | null>>();
  for (const folder of readdirSync(assessorDir, { withFileTypes: true })) {
    if (!folder.isDirectory()) continue;
    const dir = join(assessorDir, folder.name);
    const path = join(dir, `${folder.name}.json`);
    if (!existsSync(path)) continue;
    const metadata = JSON.parse(readFileSync(path, 'utf8')) as { id?: string; name?: string; links?: { processUrl?: string; processUrls?: string[] } };
    if (!metadata.id || !metadata.name) continue;
    const runPath = join(dir, 'stats.json');
    const run = existsSync(runPath) ? JSON.parse(readFileSync(runPath, 'utf8')) as { status?: string; 'last-run'?: string; scrapers?: { 'page-results'?: { url: string; status: string; records: number | null }[] }[] } : {};
    const urls = Array.isArray(metadata.links?.processUrls) ? metadata.links.processUrls : [];
    const configuredUrls = [...new Set(urls.filter((url) => typeof url === 'string' && /^https?:\/\//i.test(url)))];
    const results = new Map((run.scrapers || []).flatMap((scraper) => scraper['page-results'] || []).map((page) => [page.url, page]));
    const pages: AssessorStats['pages'] = configuredUrls.map((url) => { const result = results.get(url); return { url, status: result?.status === 'parsed' ? 'parsed' : result?.status === 'failed' ? 'failed' : 'unknown', records: result?.status === 'parsed' && typeof result.records === 'number' ? result.records : null, published: 0 }; });
    const sourceUrls = pages.length;
    const pageIndex = new Map<string, AssessorStats['pages'][number] | null>();
    const addSource = (url: string, page: AssessorStats['pages'][number]) => {
      try {
        const parsed = new URL(url); parsed.hash = '';
        const existing = pageIndex.get(parsed.href);
        pageIndex.set(parsed.href, existing === undefined || existing === page ? page : null);
      } catch { /* Ignore malformed source URLs. */ }
    };
    const mappingPath = join(dir, 'page-source-links.json');
    const mappings: Record<string, string[]> = existsSync(mappingPath) ? JSON.parse(readFileSync(mappingPath, 'utf8')) : {};
    const directUrls = new Set<string>();
    for (const page of pages) { addSource(page.url, page); try { const parsed = new URL(page.url); parsed.hash = ''; directUrls.add(parsed.href); } catch { /* Ignore malformed configured URLs. */ } }
    for (const page of pages) for (const url of mappings[page.url] ?? []) {
      try { const parsed = new URL(url); parsed.hash = ''; if (!directUrls.has(parsed.href)) addSource(url, page); } catch { /* Ignore malformed source URLs. */ }
    }
    pageIndexes.set(metadata.id, pageIndex);
    assessors.set(metadata.id, { id: metadata.id, name: metadata.name, records: 0, people: 0, unknownDomain: 0, unknownLocation: 0, noWorkLink: 0, noYear: 0, years: {}, domains: {}, captureStatus: run.status || null, lastCapture: run['last-run'] || null, rejectedNames: countLines(join(dir, 'parsing-errors.txt')), reviewNames: countLines(join(dir, 'individuals-not-validated.txt')), sourceUrls, pages });
  }
  for (const person of listProfiles()) {
    for (const [id, quality] of Object.entries(person.assessorQuality)) {
      let stats = assessors.get(id);
      if (!stats) {
        stats = { id, name: person.assessorNames[id] || id, records: 0, people: 0, unknownDomain: 0, unknownLocation: 0, noWorkLink: 0, noYear: 0, years: {}, domains: {}, captureStatus: null, lastCapture: null, rejectedNames: null, reviewNames: null, sourceUrls: 0, pages: [] };
        assessors.set(id, stats);
      }
      stats.people++;
      stats.records += quality.records;
      stats.unknownDomain += quality.unknownDomain;
      stats.unknownLocation += quality.unknownLocation;
      stats.noWorkLink += quality.noWorkLink;
      stats.noYear += quality.noYear;
      for (const [year, count] of Object.entries(quality.years)) stats.years[year] = (stats.years[year] ?? 0) + count;
      for (const [domain, count] of Object.entries(quality.domains)) stats.domains[domain] = (stats.domains[domain] ?? 0) + count;
      for (const [url, count] of Object.entries(quality.sources)) {
        const page = pageIndexes.get(id)?.get(url);
        if (page) page.published += count;
      }
    }
  }
  cached = [...assessors.values()].sort((a, b) => a.name.localeCompare(b.name));
  return cached;
}
