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

Each endorsement can include:

- the person and assessor;
- a source URL and description;
- the type of record, such as a presentation, CVE, bounty, or competition result;
- cybersecurity domains and sub-specialties;
- evidence links; and
- a POVS level when the available evidence supports one.

The same person can have many endorsements from different assessors.

## Synthetic, production, and expert

POVS is a taxonomy for codifying distinctions that the cybersecurity industry
already uses, understands, and recognizes when evaluating the significance of
technical work. These categories describe the environment and recognition
associated with the work; they are not a single linear scale of human worth or
potential.

### Synthetic

Synthetic describes work that has not been performed on, or used by, production
systems. This includes conceptual work, laboratory research, controlled
experiments, training exercises, simulations, and work performed in other
non-production environments.

Synthetic is a neutral category, not a negative judgment and not a lesser form
of production work. It identifies a distinct type of evidence: work that may be
technically valuable, but has not yet been demonstrated in production use.

### Production

Production describes work that has been used in a production environment. This
includes work performed on production software, production infrastructure,
production networks, or systems serving real users or organizations.

The category is concerned with actual operational use, not with whether a work
is described as practical, realistic, or production-like. A proposal,
demonstration, laboratory exercise, or controlled test remains synthetic unless
the evidence establishes production use.

### Expert

Expert describes production work that has received the highest available forms
of recognition or acclaim appropriate to its context. It is therefore a
recognized subset of production work, not a separate environment.

The expert category requires both demonstrated production use and exceptional
external recognition. Seniority, confidence, technical complexity, or a job
title alone is insufficient to establish expert status.

## Endorsement eligibility criteria

An endorsement may be included in the POVS database only when it satisfies all
of the following criteria:

1. **Peer-reviewed work.** The endorsement must concern a specific piece of
   work that has undergone peer review, or an equivalent assessment process in
   which qualified peers evaluate the work before recognition is issued.
2. **Independent verifiability.** The endorsement must be supported by public
   evidence that can be independently verified. Records that cannot be
   independently verified may be retained for completeness, but must be
   classified as **Not Verified** and must not be treated as verified evidence.
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
