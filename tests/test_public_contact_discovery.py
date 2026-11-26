import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from discover_public_contacts import classify_url, corroborated_links


class PublicContactDiscoveryTests(unittest.TestCase):
    def test_classifies_personal_profiles_and_rejects_lookalike_hosts(self):
        self.assertEqual(classify_url('https://twitter.com/alice/status/123', 'Alice Example'), ('twitter', 'https://x.com/alice'))
        self.assertIsNone(classify_url('https://notlinkedin.com/in/alice', 'Alice Example'))
        self.assertIsNone(classify_url('https://linkedin.com/company/alice', 'Alice Example'))
        self.assertEqual(classify_url('https://aliceexample.com/', 'Alice Example'), ('website', 'https://aliceexample.com/'))
        self.assertIsNone(classify_url('https://conference.com/speakers/alice', 'Alice Example'))

    def test_requires_specific_talk_in_account_result(self):
        person = {'name': 'Alice Example', 'source_records': ['Finding vulnerabilities in connected industrial control systems']}
        result = {'url': 'https://x.com/alice/status/123', 'title': 'Alice Example', 'snippet': 'Finding vulnerabilities in connected industrial control systems'}
        self.assertEqual(corroborated_links(person, [result])[0]['url'], 'https://x.com/alice')
        result['snippet'] = 'Cybersecurity conference'
        self.assertEqual(corroborated_links(person, [result]), [])


if __name__ == '__main__':
    unittest.main()
