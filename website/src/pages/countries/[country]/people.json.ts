import { listCountries } from '../../../lib/countries';

export function getStaticPaths() {
  return listCountries().map((country) => ({ params: { country: country.slug }, props: { people: country.people } }));
}

export function GET({ props }: { props: { people: unknown[] } }) {
  return new Response(JSON.stringify(props.people), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
}
