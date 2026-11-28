import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { createServer } from 'vite';

const server = await createServer({ configFile: false, server: { middlewareMode: true }, appType: 'custom' });
try {
  const { listAssessorStats } = await server.ssrLoadModule('/src/lib/assessor-stats.ts');
  const stats = listAssessorStats();
  const selected = ['black-hat', 'acm-ccs', 'mitre', 'usenix-security'];
  const expectedDomains = Object.fromEntries(selected.map((id) => [id, {}]));
  const usenixPage = 'https://www.usenix.org/conference/usenixsecurity26/technical-sessions';
  const usenixMapping = JSON.parse(readFileSync(resolve('../data/assessors/usenix-security/page-source-links.json'), 'utf8'));
  const usenixSources = new Set(usenixMapping[usenixPage]);
  let usenixRecords = 0;
  const expected = Object.fromEntries(selected.map((id) => [id, { records: 0, people: 0, unknownDomain: 0, unknownLocation: 0, noWorkLink: 0, noYear: 0 }]));
  const directory = resolve('../data/individuals');
  for (const file of readdirSync(directory).filter((name) => name.endsWith('.json'))) {
    const person = JSON.parse(readFileSync(join(directory, file), 'utf8'));
    const seen = new Set();
    for (const record of person.endorsements ?? []) {
      const count = expected[record['assessor-id']];
      if (!count) continue;
      if (record['assessor-id'] === 'usenix-security' && usenixSources.has((record.url ?? '').split('#')[0])) {
        usenixRecords++;
      }
      seen.add(record['assessor-id']);
      count.records++;
      for (const domain of new Set((record.domains ?? []).map((value) => value.trim().toLowerCase()).filter((value) => value && !['unknown', 'unclassified'].includes(value)))) {
        const domains = expectedDomains[record['assessor-id']];
        domains[domain] = (domains[domain] ?? 0) + 1;
      }
      if (!(record.domains ?? []).some((domain) => !['unknown', 'unclassified'].includes(domain.toLowerCase()))) count.unknownDomain++;
      if (!record.location?.trim() || record.location.trim().toLowerCase() === 'unknown') count.unknownLocation++;
      if (!record['evidence-links']?.length) count.noWorkLink++;
      if (!record.year) count.noYear++;
    }
    for (const id of seen) expected[id].people++;
  }
  const usenix = stats.find((item) => item.id === 'usenix-security').pages.find((page) => page.url === usenixPage);
  assert.ok(usenixRecords > 0, 'USENIX source links must match published records');
  assert.equal(usenix.published, usenixRecords, 'USENIX page person-record count');
  assert.ok(stats.find((item) => item.id === 'blue-team-con').pages.every((page) => page.published > 0), 'Blue Team Con archive mappings must still work');
  for (const assessor of stats) {
    assert.ok(assessor.pages.reduce((sum, page) => sum + page.published, 0) <= assessor.records, `${assessor.id}: a record was attributed to more than one page`);
  }
  for (const id of ['usenix-security', 'blue-team-con', 'def-con', 'pwn2own', 'rsa-conference']) {
    const assessor = stats.find((item) => item.id === id);
    assert.equal(assessor.pages.reduce((sum, page) => sum + page.published, 0), assessor.records, `${id}: published records not accounted for by listed pages`);
  }
  for (const id of selected) {
    const actual = stats.find((item) => item.id === id);
    assert.ok(actual, `Missing assessor ${id}`);
    for (const [key, value] of Object.entries(expected[id])) assert.equal(actual[key], value, `${id}: ${key}`);
    assert.deepEqual(actual.domains, expectedDomains[id], `${id}: endorsement counts by domain`);
    assert.equal(Object.values(actual.years).reduce((a, b) => a + b, 0) + actual.noYear, actual.records);
  }
  const notRun = stats.find((item) => item.id === 'apple-security-bounty');
  assert.equal(notRun.records, 0);
  assert.equal(notRun.reviewNames, 0, 'Comment-only review files are empty');
  assert.equal(notRun.rejectedNames, 0, 'Comment-only error files are empty');
  console.log(`Validated ${stats.length} assessors and independently checked ${selected.join(', ')}.`);
} finally {
  await server.close();
}
