from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from corroborate_linkedin_sample import corroborated, result_matches_candidate


class LinkedInCorroborationTests(unittest.TestCase):
    def test_matching_profile_post_must_mention_the_persons_talk(self):
        person = {'candidates': [{'url': 'https://www.linkedin.com/in/alice-example'}],
                  'source_records': ['Finding vulnerabilities in connected industrial control systems']}
        result = {'url': 'https://www.linkedin.com/posts/alice-example_my-talk-activity-123',
                  'title': 'Alice Example', 'snippet': 'Finding vulnerabilities in connected industrial control systems'}
        self.assertEqual(len(corroborated(person, [result])), 1)
        result['snippet'] = 'A cybersecurity conference'
        self.assertEqual(corroborated(person, [result]), [])

    def test_rejects_other_people_and_lookalike_domains(self):
        profile = 'https://www.linkedin.com/in/alice-example'
        self.assertFalse(result_matches_candidate('https://www.linkedin.com/posts/bob_other-123', profile))
        self.assertFalse(result_matches_candidate('https://notlinkedin.com/posts/alice-example_foo', profile))


if __name__ == '__main__':
    unittest.main()
