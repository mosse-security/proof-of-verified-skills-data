import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

// Astro can run generation from the repository root, website directory, or a
// relocated build directory. Select the first workspace-relative data path
// that actually exists instead of assuming a single current working directory.
const dataDir = [
  resolve(process.cwd(), 'data/individuals'),
  resolve(process.cwd(), '../data/individuals'),
  resolve(process.cwd(), '../../data/individuals'),
].find((candidate) => existsSync(candidate));

if (!dataDir) throw new Error('Could not locate the data/individuals directory.');

const contactInfoDir = [
  resolve(process.cwd(), 'data/contact-information'),
  resolve(process.cwd(), '../data/contact-information'),
  resolve(process.cwd(), '../../data/contact-information'),
].find((candidate) => existsSync(candidate));

export const bands = ['indirect', 'observable', 'independently-reviewed'] as const;
export type EvidenceBand = typeof bands[number];
export type EvidenceCounts = Record<EvidenceBand, number>;
export const bandLabels: Record<EvidenceBand, string> = {
  indirect: 'Indirect', observable: 'Observable', 'independently-reviewed': 'Independently reviewed',
};
type PropertyValue = boolean | 'unknown';
interface Taxonomy {
  evidence: EvidenceBand;
  trusted: PropertyValue;
  production: PropertyValue;
  competition: PropertyValue;
  verifiable: PropertyValue;
  explanation: string;
}
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
  'evidence-links'?: Array<{ title?: string; url?: string }>;
  'povs-taxonomy': Taxonomy;
}
export interface Person {
  name: string;
  biography?: string;
  tags?: string[];
  contact?: Array<{ label?: string; url?: string; email?: string; source?: string }>;
  image?: { url?: string; source_url?: string; source_type?: string; conference?: string; year?: number; region?: string; verified?: boolean; verified_at?: string };
  endorsements?: Endorsement[];
  stats?: { endorsements?: number; assessors?: number; 'by-domain'?: Record<string, number> };
  'last-updated'?: string;
}
export interface Summary {
  slug: string;
  name: string;
  endorsements: number;
  endorsers: number;
  evidenceCounts: EvidenceCounts;
  domains: string[];
  domainCounts: Record<string, number>;
  assessors: string[];
  assessorIds: string[];
  assessorNames: Record<string, string>;
  achievements: number;
}

const ACHIEVEMENT_TAGS = new Set([
  'ctf-participant',
  'ctf-champion',
  'cve-researcher',
  'critical-cve-discovery',
  'top-conference-speaker',
  'bounty-hunter',
  'leaderboard-elite',
  'academic-researcher',
  'security-toolsmith',
  'open-source-contributor',
  'threat-researcher',
]);

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
        evidenceCounts: countEvidence(p.endorsements ?? []),
        domains: Object.entries(p.stats?.['by-domain'] ?? {})
          .filter(([, count]) => count > 0).map(([domain]) => domain),
        domainCounts: Object.fromEntries(Object.entries(p.stats?.['by-domain'] ?? {}).filter(([, count]) => count > 0)),
        assessors,
        assessorIds,
        assessorNames,
        achievements: (p.tags ?? []).filter((tag) => ACHIEVEMENT_TAGS.has(tag)).length,
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
  const profile = JSON.parse(readFileSync(join(dataDir, `${slug}.json`), 'utf8')) as Person;
  if (contactInfoDir) {
    const contactPath = join(contactInfoDir, `${slug}.json`);
    if (existsSync(contactPath)) {
      const recovered = JSON.parse(readFileSync(contactPath, 'utf8')) as Pick<Person, 'contact' | 'image'>;
      if (recovered.contact?.length) profile.contact = recovered.contact;
      if (recovered.image?.url) profile.image = recovered.image;
    }
  }
  return profile;
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
  const normalized = domain.replaceAll('_', '-').toLocaleLowerCase();
  if (normalized === 'unknown' || normalized === 'unclassified') return 'Cyber domain not classified';
  const formatted = domain.replaceAll('-', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
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

export function countEvidence(items: Endorsement[]): EvidenceCounts {
  const counts = { indirect: 0, observable: 0, 'independently-reviewed': 0 };
  for (const item of items) counts[item['povs-taxonomy'].evidence]++;
  return counts;
}

export function evidenceCount(person: Person): number {
  return (person.endorsements ?? []).filter((item) => (item['evidence-links']?.length ?? 0) > 0).length;
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
