import { getProfile, listProfiles, type Endorsement } from './records';

export type ChallengeBand = 'Synthetic' | 'Production' | 'Expert candidate' | 'Expert';
export type MatchStatus = 'Verified' | 'Candidate';

export interface ChallengeMatch {
  personSlug: string;
  personName: string;
  endorsement: Endorsement;
  status: MatchStatus;
}

export interface Challenge {
  slug: string;
  title: string;
  band: ChallengeBand;
  description: string;
  requirements: string;
  matches: ChallengeMatch[];
}

const challengeDefinitions: Omit<Challenge, 'matches'>[] = [
  {
    slug: 'ctf-participant', title: 'CTF Participant', band: 'Synthetic',
    description: 'Participated in a recognized capture-the-flag competition.',
    requirements: 'Take part in a recognized CTF competition. Talks or research that only discuss CTFs do not qualify.',
  },
  {
    slug: 'ctf-champion', title: 'CTF Champion', band: 'Synthetic',
    description: 'Won a recognized capture-the-flag competition or placement.',
    requirements: 'Have a competition-placement record that explicitly confirms a winning CTF placement.',
  },
  {
    slug: 'cve-researcher', title: 'CVE Researcher', band: 'Production',
    description: 'Received named credit for a published CVE record.',
    requirements: 'Discover or report a vulnerability and receive named credit in a published CVE record.',
  },
  {
    slug: 'critical-discovery', title: 'Critical Discovery', band: 'Production',
    description: 'Received named credit for a published CVE rated CRITICAL.',
    requirements: 'Discover a vulnerability, receive named credit for a published CVE, and have that vulnerability rated CRITICAL.',
  },
  {
    slug: 'top-conference-speaker', title: 'Top Conference Speaker', band: 'Production',
    description: 'Presented at a selected leading cybersecurity conference.',
    requirements: 'Have a presentation endorsement from one of the configured top conference assessors.',
  },
  {
    slug: 'bounty-hunter', title: 'Bounty Hunter', band: 'Production',
    description: 'Received a confirmed payment for a security bug bounty.',
    requirements: 'Have a bug-bounty record that explicitly confirms a bounty payment. Hall of Fame recognition alone is insufficient.',
  },
  {
    slug: 'leaderboard-elite', title: 'Leaderboard Elite', band: 'Expert candidate',
    description: 'Earned a recognized bug-bounty leaderboard ranking.',
    requirements: 'Have a recognition record naming a bug-bounty leaderboard and an explicit ranking.',
  },
  {
    slug: 'pwn2own-champion', title: 'Pwn2Own Champion', band: 'Expert',
    description: 'Won an actual Pwn2Own competition or category.',
    requirements: 'Have a Pwn2Own competition-result record whose description explicitly confirms an actual competition or category victory. Participation, demonstrations, and Master of Pwn points do not qualify.',
  },
  {
    slug: 'academic-researcher', title: 'Academic Researcher', band: 'Production',
    description: 'Presented accepted academic security research.',
    requirements: 'Have a conference-academic presentation record that establishes an accepted research paper.',
  },
  {
    slug: 'security-toolsmith', title: 'Security Toolsmith', band: 'Production',
    description: 'Released a security tool with independent use or review.',
    requirements: 'Identify a released security tool and provide evidence of independent use or review.',
  },
  {
    slug: 'open-source-contributor', title: 'Open-Source Contributor', band: 'Production',
    description: 'Made an accepted or merged security-related code contribution.',
    requirements: 'Have an endorsement that explicitly identifies an accepted or merged security-related code contribution.',
  },
  {
    slug: 'threat-researcher', title: 'Threat Researcher', band: 'Production',
    description: 'Produced original threat, malware, or security research with recognition.',
    requirements: 'Identify original published threat, malware, or security research with independent recognition.',
  },
];

export function listChallenges(): Challenge[] {
  const grouped = new Map<string, ChallengeMatch[]>();
  for (const definition of challengeDefinitions) grouped.set(definition.slug, []);
  for (const profile of listProfiles()) {
    const person = getProfile(profile.slug);
    for (const definition of challengeDefinitions) {
      const tag = definition.slug === 'critical-discovery'
        ? 'critical-cve-discovery'
        : definition.slug;
      if (person.tags?.includes(tag)) {
        const tagged = [...(person.endorsements ?? [])].sort((a, b) => (b.year ?? 0) - (a.year ?? 0))[0];
        if (!tagged) continue;
        grouped.get(definition.slug)?.push({
          personSlug: profile.slug,
          personName: person.name,
          endorsement: tagged,
          status: 'Verified',
        });
      }
    }
  }
  return challengeDefinitions.map((definition) => ({
    ...definition,
    matches: (grouped.get(definition.slug) ?? []).sort((a, b) => a.personName.localeCompare(b.personName)),
  }));
}

export function getChallenge(slug: string): Challenge {
  const challenge = listChallenges().find((item) => item.slug === slug);
  if (!challenge) throw new Error(`Unknown challenge: ${slug}`);
  return challenge;
}

