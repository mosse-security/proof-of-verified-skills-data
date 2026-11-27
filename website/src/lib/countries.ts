import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { listProfiles, type EvidenceCounts } from './records';

export type CountryPerson = { slug: string; name: string; records: number; domains: Record<string, number>; direct: boolean; totalRecords: number; endorsers: number; achievements: number; evidenceCounts: EvidenceCounts };
export type CountryAssessor = { id: string; name: string; people: number; records: number };
export type CountryData = { name: string; slug: string; assessors: number; assessorList: CountryAssessor[]; records: number; domains: Record<string, number>; people: CountryPerson[] };

const assessorDir = [resolve(process.cwd(), 'data/assessors'), resolve(process.cwd(), '../data/assessors'), resolve(process.cwd(), '../../data/assessors')].find(existsSync);
const slugFor = (name: string) => name.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
let cached: CountryData[] | undefined;

export function listCountries(): CountryData[] {
  if (cached) return cached;
  if (!assessorDir) throw new Error('Could not locate assessor metadata.');
  const assessorNames = new Map<string, string>();
  const countries = new Map<string, { people: Map<string, CountryPerson>; assessors: Map<string, CountryAssessor> }>();
  function ensure(name: string) {
    if (!countries.has(name)) countries.set(name, { people: new Map(), assessors: new Map() });
    return countries.get(name)!;
  }
  for (const entry of readdirSync(assessorDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const path = join(assessorDir, entry.name, `${entry.name}.json`);
    if (!existsSync(path)) continue;
    const data = JSON.parse(readFileSync(path, 'utf8')) as { id?: string; name?: string; countries?: string[] };
    if (!data.id || !Array.isArray(data.countries)) continue;
    const names = data.countries.filter((name): name is string => typeof name === 'string' && !!name.trim());
    assessorNames.set(data.id, data.name || data.id);
    for (const name of names) ensure(name);
  }
  for (const person of listProfiles()) {
    const profile = { slug: person.slug, name: person.name, totalRecords: person.endorsements, endorsers: person.endorsers, achievements: person.achievements, evidenceCounts: person.evidenceCounts };
    for (const [name, byAssessor] of Object.entries(person.locationEvidence)) {
      for (const [assessor, evidence] of Object.entries(byAssessor)) {
        const country = ensure(name);
        const organization = country.assessors.get(assessor) ?? { id: assessor, name: assessorNames.get(assessor) || assessor, people: 0, records: 0 };
        organization.people++;
        organization.records += evidence.records;
        country.assessors.set(assessor, organization);
        const entry = country.people.get(person.slug) ?? { ...profile, records: 0, domains: {}, direct: false };
        entry.records += evidence.records;
        for (const [domain, count] of Object.entries(evidence.domains)) entry.domains[domain] = (entry.domains[domain] ?? 0) + count;
        country.people.set(person.slug, entry);
      }
    }
    // A future verified person-country field is independent of assessor coverage.
    for (const name of new Set(person.countries)) {
      const country = ensure(name);
      const entry: CountryPerson = { ...profile, records: person.endorsements, domains: {}, direct: true };
      for (const [domain, count] of Object.entries(person.domainCounts)) {
        if (!['unknown', 'unclassified'].includes(domain.toLowerCase())) entry.domains[domain] = count;
      }
      country.people.set(person.slug, entry);
    }
  }
  const slugs = new Set<string>();
  cached = [...countries].map(([name, country]) => {
    const slug = slugFor(name);
    if (!slug || slugs.has(slug)) throw new Error(`Duplicate or invalid country slug: ${name}`);
    slugs.add(slug);
    const people = [...country.people.values()].sort((a, b) => a.name.localeCompare(b.name));
    const domains: Record<string, number> = {};
    for (const person of people) for (const [domain, count] of Object.entries(person.domains)) domains[domain] = (domains[domain] ?? 0) + count;
    const assessorList = [...country.assessors.values()].sort((a, b) => a.name.localeCompare(b.name));
    return { name, slug, assessors: assessorList.length, assessorList, records: people.reduce((sum, person) => sum + person.records, 0), domains, people };
  }).sort((a, b) => a.name.localeCompare(b.name));
  return cached;
}
