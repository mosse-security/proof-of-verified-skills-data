import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from review_public_contact_candidates import ranked_candidates


class ContactCandidateReviewTests(unittest.TestCase):
    def test_rejects_other_persons_linkedin_post(self):
        person = {'name': 'Alice Example', 'results': [
            {'url': 'https://linkedin.com/posts/bob_123', 'title': 'Alice Example on Acme Security', 'snippet': 'Alice Example Acme'},
            {'url': 'https://example.org/alice', 'title': 'Alice Example', 'snippet': 'Acme'}]}
        self.assertEqual(ranked_candidates(person), [])

    def test_rejects_personal_site_as_its_own_corroboration(self):
        person = {'name': 'Alice Example', 'results': [
            {'url': 'https://aliceexample.com/', 'title': 'Alice Example', 'snippet': 'Founder at AcmeCorp'},
            {'url': 'https://aliceexample.com/about', 'title': 'Alice Example', 'snippet': 'Founder at AcmeCorp'}]}
        self.assertEqual(ranked_candidates(person), [])


if __name__ == '__main__':
    unittest.main()
