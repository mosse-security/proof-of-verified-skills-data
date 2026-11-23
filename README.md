# Proof of Verified Skills (POVS)

Proof of Verified Skills (POVS) is a scientifically developed theoretical
taxonomy and evidence model, currently awaiting peer review. It examines how
the cybersecurity industry can develop strong signals of competence: signals
grounded in observable evidence and costly to fake.

This repository is an experimental knowledgebase implementation of that
taxonomy and evidence model. It documents publicly verifiable cybersecurity
work and recognition so that the proposed approach can be explored, tested,
and refined.

The project brings together conference acceptances, vulnerability research,
bug-bounty records, competition results, security tools, and other public
evidence into a consistent, inspectable registry of people and their work.

The work is intended to address the scientifically documented weakness of
many commonly used competence signals and the resulting information
asymmetries between buyers and sellers of cybersecurity services, professionals
and employers, and sellers of courses and buyers of certifications.

POVS is not yet peer-reviewed and is not a hiring recommendation, formal
certification, or claim that a person has demonstrated every skill in a
particular domain.

## Scope and non-claims

POVS is not a competency framework, occupational standard, curriculum, or
regulatory scheme. It does not define what a cybersecurity professional is or
is not, prescribe the skills required for a role, or establish requirements
for employment, training, procurement, or professional practice.

POVS does not require organizational adoption and has no certification,
credential, examination, or accreditation mechanism. A POVS record is an
evidence record, not a qualification issued to an individual.

POVS is also deliberately not designed to map to, or receive mappings from,
NIST NICE, SFIA, DoD 8140, or comparable competency and workforce frameworks.
Those frameworks may describe roles, capabilities, curricula, or workforce
policies, but POVS does not assume that their categories constitute empirical
evidence of competence. The project does not identify empirical validation
showing that these frameworks, by themselves, produce strong, independently
verifiable, and costly-to-fake competence signals. Accordingly, conformance or
interoperability with such frameworks is outside the purpose of POVS.

The research objective is narrower: to examine whether observable,
independently verifiable evidence and accountable assessment processes can
produce stronger signals of demonstrated competence and reduce information
asymmetry between participants in the cybersecurity market.

## How the model works

The basic unit is an endorsement: a public record from an assessor that names
a person and describes a specific piece of work or recognition.

POVS records the contribution, the assessor, the source, and any links to the
work. Each endorsement receives one evidence band and four properties. A person
can have endorsements in several bands for different contributions.

## Evidence bands

Select the highest band supported for the achievement the assessor credits to
the individual.

| Band | Meaning | Example |
|---|---|---|
| 1 · Indirect | An independent source credits the person with an achievement. The underlying work may be unavailable. | A programme names an award recipient. |
| 2 · Observable | A reader can inspect the attributed work or a sufficiently detailed record of it. | A conference recording, the full paper, or a repository containing the code. |
| 3 · Independently reviewed | A qualified independent party formally assessed the work. | A peer-reviewed paper, a validated vulnerability finding, or a judged competition attempt. |

A link to the work itself establishes **at least Observable**. A public copy
of a peer-reviewed paper therefore remains Independently reviewed. A conference
schedule can substantiate selection to present. A recording lets readers
observe the delivery. The band describes the evidence for that contribution.
For a judged attempt, the organiser's recorded result tells readers how the
attempt went.

## Endorsement properties

Each property can be **Yes**, **No**, or **Unknown**. Unknown means the
available record leaves the question open.

| Property | Question |
|---|---|
| Trusted | Did a third party rely on the work in a documented decision or action, such as issuing a fix? |
| Production | Was the work performed on production systems or released production software, or subsequently used in production? |
| Competition | Was the endorsed activity part of an organised contest? |
| Independently verifiable | Can a reader inspect the work and judge the endorsed claim for themselves? |

POVS classifies a bug bounty award as independently reviewed, trusted production
work. The issuing programme reviewed the finding and acted on it by granting
the award. Readers can independently verify the technical work when they can
inspect the finding itself.

A privately judged submission can receive band 3 even when readers cannot
inspect it. The evidence mix on a profile counts endorsements in each band.

## Endorsement eligibility criteria

1. **Specific achievement.** The source must credit a person with identifiable
   work, participation or recognition.
2. **Independent attribution.** A reader must be able to check that an
   independent assessor issued the endorsement. A source that documents only
   recognition can support an Indirect endorsement.

3. **Assessor accountability.** The assessor - the organization issuing the
   endorsement - must face meaningful consequences for issuing weak or
   inaccurate endorsements. Its incentives, reputation, or institutional
   standing must create a credible feedback mechanism that discourages repeated
   errors.
4. **Named individual identity.** The endorsement must identify an individual
   by name. Handles, unresolvable aliases, organizations, and other identities
   that cannot be attributed to a specific person are excluded from the
   individual registry.

## Achievements

The website groups verified records into achievement categories that are
already generally accepted and understood across the cybersecurity industry.
POVS is not attempting to invent new forms of recognition or redefine what the
industry considers an achievement. The purpose is to help people quickly
understand who has achieved what using categories that the industry already
recognises, such as:

- CVE researcher;
- critical discovery;
- top conference speaker;
- bounty hunter;
- leaderboard elite;
- security toolsmith; and
- open-source contributor.

Achievements are derived from explicit record properties and project rules.
They provide a fast way to navigate the registry, but they do not replace the
underlying evidence or establish a new qualification system.

## Limitations

The first release of POVS is based exclusively on open-source data. This is a
deliberate initial scope, not a claim that public records represent the full
range of valuable cybersecurity work. Much of the strongest work performed by
practitioners occurs privately, including work conducted under confidential
client engagements. A mechanism for incorporating appropriately substantiated
private evidence is planned for a subsequent phase.

The current knowledgebase is also produced with automated parsing and
categorization. As a result, records may be missing, incomplete, or incorrect,
and individual fields may contain extraction errors. Automated categorization
can also produce errors or require revision as the underlying evidence is
better understood.

POVS does not currently scrape every source on a daily basis. There may
therefore be a substantial delay between a new endorsement becoming available
and its appearance in the knowledgebase. As the project matures, we aim to
refresh the relevant sources twice a year.

POVS is intended to improve incrementally through additional sources, review,
correction, and better parsing and categorization methods. The quality of the
data should therefore be understood as an active research and maintenance
process rather than a claim of perfect completeness or accuracy.

## Contact

For profile corrections, new endorsement submissions, general inquiries,
contributions, or bug reports, contact
[contact@vetted-cyber-talent.com](mailto:contact@vetted-cyber-talent.com).
