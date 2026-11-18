import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

// Astro relocates server modules into dist/ during static generation. Resolve
// from the workspace instead of the compiled module location.
const dataDir = resolve(process.cwd(), '../data/individuals');

export interface Endorsement {
  name?: string;
  label?: string;
  description?: string;
  type?: string;
  assessor?: string;
  'assessor-id'?: string;
  'assessor-category'?: string;
  'assessor-rigor-level'?: string;
  reviewType?: string;
  subtitle?: string;
  year?: number;
  domains?: string[];
  subspecialties?: Record<string, string[]>;
  url?: string;
  evidence?: boolean;
  'evidence-links'?: Array<{ title?: string; url?: string }>;
  povs?: {
    level?: number;
    milestones?: Record<string, boolean>;
    explanation?: string;
  };
}
export interface Person {
  name: string;
  biography?: string;
  tags?: string[];
  contact?: Array<{ label?: string; url?: string }>;
  endorsements?: Endorsement[];
  stats?: { endorsements?: number; assessors?: number; 'by-domain'?: Record<string, number> };
  'last-updated'?: string;
}
export interface Summary {
  slug: string;
  name: string;
  endorsements: number;
  endorsers: number;
  levelCounts: { synthetic: number; productionLike: number; expert: number; unrated: number };
  domains: string[];
  domainCounts: Record<string, number>;
  assessors: string[];
  assessorIds: string[];
  assessorNames: Record<string, string>;
}

let summaries: Summary[] | undefined;
export function listProfiles(): Summary[] {
  if (summaries) return summaries;
  summaries = readdirSync(dataDir)
    .filter((file) => file.endsWith('.json'))
    .map((file) => {
      const raw = JSON.parse(readFileSync(join(dataDir, file), 'utf8')) as Person;
      const p = raw;
      const assessors = [...new Set(p.endorsements.map((item) => item.assessor).filter((assessor): assessor is string => Boolean(assessor)))].sort();
      const assessorNames = Object.fromEntries(p.endorsements.filter((item): item is Endorsement & { 'assessor-id': string; assessor: string } => Boolean(item['assessor-id'] && item.assessor)).map((item) => [item['assessor-id'], item.assessor]));
      const assessorIds = [...new Set(p.endorsements.map((item) => item['assessor-id']).filter((assessorId): assessorId is string => Boolean(assessorId)))].sort();
      return {
        slug: file.slice(0, -5),
        name: p.name,
        endorsements: p.stats?.endorsements ?? p.endorsements.length,
        endorsers: p.stats?.assessors ?? new Set(p.endorsements.map((item) => item['assessor-id'] || item.assessor).filter(Boolean)).size,
        levelCounts: p.endorsements.reduce((counts, endorsement) => {
          const level = endorsement.povs?.level ?? 0;
          if (level <= 2 && level > 0) counts.synthetic += 1;
          else if (level <= 4 && level > 0) counts.productionLike += 1;
          else if (level >= 5) counts.expert += 1;
          else counts.unrated += 1;
          return counts;
        }, { synthetic: 0, productionLike: 0, expert: 0, unrated: 0 }),
        domains: Object.entries(p.stats?.['by-domain'] ?? {})
          .filter(([, count]) => count > 0).map(([domain]) => domain),
        domainCounts: Object.fromEntries(Object.entries(p.stats?.['by-domain'] ?? {}).filter(([, count]) => count > 0)),
        assessors,
        assessorIds,
        assessorNames,
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
  return summaries;
}

export function getProfile(slug: string): Person {
  // Only allow slugs that come from actual filenames, never arbitrary paths.
  if (!listProfiles().some((record) => record.slug === slug)) {
    throw new Error(`Unknown individual slug: ${slug}`);
  }
  return JSON.parse(readFileSync(join(dataDir, `${slug}.json`), 'utf8')) as Person;
}

export const PER_PAGE = 100;
export function pageCount() { return Math.ceil(listProfiles().length / PER_PAGE); }
export function listPage(page: number) {
  return listProfiles().slice((page - 1) * PER_PAGE, page * PER_PAGE);
}

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words.slice(0, 2).map((word) => word[0]).join('').toUpperCase() || '?';
}

export function formatDomain(domain: string): string {
  const formatted = domain.replaceAll('-', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  const normalized = domain.replaceAll('_', '-').toLocaleLowerCase();
  if (normalized === 'grc') return 'GRC';
  if (normalized === 'devsecops' || normalized === 'dev-sec-ops') return 'DevSecOps';
  return formatted;
}

export function formatLabel(value?: string): string {
  if (!value) return 'Not specified';
  return value
    .replaceAll('-', ' ')
    .replaceAll('_', ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function levelBand(level?: number): string {
  if (!level) return 'Not Verified';
  if (level <= 2) return 'Synthetic';
  if (level <= 4) return 'Production-like';
  return 'Expert';
}

export function highestLevel(person: Person): number {
  return Math.max(0, ...(person.endorsements ?? []).map((item) => item.povs?.level ?? 0));
}

export function evidenceCount(person: Person): number {
  return (person.endorsements ?? []).filter((item) => item.evidence || (item['evidence-links']?.length ?? 0) > 0).length;
}

export function endorsementDomains(item: Endorsement): string[] {
  return item.domains ?? [];
}

export function safeExternalUrl(value?: string): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : undefined;
  } catch { return undefined; }
}
