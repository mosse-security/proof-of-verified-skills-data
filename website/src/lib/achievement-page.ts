import { getChallenge, listChallenges } from './challenges';
import { listProfiles } from './records';

export function achievementLetters(slug: string): string[] {
  const people = achievementPeople(slug);
  return [...new Set(people.map((person) => person.name.trim().charAt(0).toLocaleUpperCase()))]
    .filter((letter) => /[A-Z]/.test(letter))
    .sort();
}

export function achievementPaths() {
  return listChallenges().flatMap((challenge) => achievementLetters(challenge.slug).map((letter) => ({
    params: { slug: challenge.slug, letter: letter.toLocaleLowerCase() },
  })));
}

export function achievementPeople(slug: string) {
  const challenge = getChallenge(slug);
  const profiles = new Map(listProfiles().map((person) => [person.slug, person]));
  return challenge.matches
    .map((match) => profiles.get(match.personSlug))
    .filter((person): person is ReturnType<typeof listProfiles>[number] => Boolean(person));
}
