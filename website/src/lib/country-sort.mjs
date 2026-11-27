/** @typedef {{ name: string, slug: string, totalRecords: number, endorsers: number, achievements: number }} SortablePerson */
/**
 * Sort a filtered result set without mutating the source list.
 * @param {SortablePerson[]} people
 * @param {'name' | 'totalRecords' | 'endorsers' | 'achievements'} key
 * @param {'asc' | 'desc'} direction
 */
export function sortCountryPeople(people, key, direction) {
  return [...people].sort((a, b) => {
    const difference = key === 'name' ? a.name.localeCompare(b.name) : a[key] - b[key];
    return (direction === 'asc' ? difference : -difference) || a.name.localeCompare(b.name) || a.slug.localeCompare(b.slug);
  });
}
