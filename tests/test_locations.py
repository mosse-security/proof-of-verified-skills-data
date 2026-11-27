from __future__ import annotations

import unittest
from pathlib import Path

from scrapers.locations import endorsement_location
from scrapers.assessors.black_hat import BlackHatEndorsement
from scrapers.schema import AssessorMetadata, build_endorsement_record


class EndorsementLocationTests(unittest.TestCase):
    def test_black_hat_parser_writes_location_to_endorsement(self):
        assessor = AssessorMetadata.from_file(Path('data/assessors/black-hat/black-hat.json'))
        row = BlackHatEndorsement('Alice Example', 'Example Talk', 'Example description', 'https://blackhat.com/asia-24/briefings/', 2024, 'Black Hat Asia 2024')
        self.assertEqual(row.to_record(assessor)['location'], 'Singapore')

    def test_unknown_location_is_explicit_in_new_records(self):
        assessor = AssessorMetadata('example', 'Example', 'conference_community', 'medium', 'community_review')
        record = build_endorsement_record(name='Alice Example', label='Example Talk', description='Example description', endorsement_type='presentation', assessor=assessor, url='https://example.com/talk', year=2026, domains=())
        self.assertEqual(record['location'], 'Unknown')

    def test_black_hat_locations_depend_on_edition(self):
        location = endorsement_location
        self.assertEqual(location('black-hat', 'https://blackhat.com/us-15/briefings.html', 'Black Hat Usa 2015', 2015), 'United States')
        self.assertEqual(location('black-hat', 'https://blackhat.com/archive/europe/2015/briefings.html', 'Black Hat Europe 2015', 2015), 'Netherlands')
        self.assertEqual(location('black-hat', 'https://blackhat.com/archive/europe/2024/briefings/schedule/', 'Black Hat Europe 2024', 2024), 'United Kingdom')
        self.assertEqual(location('black-hat', 'https://blackhat.com/asia-24/briefings/', 'Black Hat Asia 2024', 2024), 'Singapore')
        self.assertIsNone(location('black-hat', 'https://blackhat.com/archive/europe/2020/', 'Black Hat Europe 2020', 2020))
        self.assertIsNone(location('black-hat', 'https://blackhat.com/archive/europe/2002/', 'Black Hat Europe 2002', 2002))

    def test_event_location_and_worldwide_are_not_assessor_footprints(self):
        self.assertEqual(endorsement_location('def-con', 'https://defcon.org/html/defcon-safemode/dc-safemode-speakers.html', 'DEF CON 28', 2020, ('United States',)), 'United States')
        self.assertEqual(endorsement_location('def-con', 'https://defcon.org/html/defcon-29/dc-29-speakers.html', 'DEF CON 29', 2021, ('United States',)), 'United States')
        self.assertEqual(endorsement_location('acm-ccs', 'https://www.sigsac.org/ccs/CCS2026/program/accepted-papers.html', 'ACM CCS 2026', 2026, ('United States', 'Netherlands')), 'Netherlands')
        self.assertEqual(endorsement_location('hitb', 'https://conference.hitb.org/hitbsecconf2023hkt/session/example/', 'HITB 2023', 2023), 'Thailand')
        self.assertEqual(endorsement_location('mitre', 'https://cve.org/example', None, 2025, ('Worldwide',)), 'Worldwide')
        self.assertEqual(endorsement_location('pwn2own', 'https://www.zerodayinitiative.com/blog/2017/10/31/welcome-to-mobile-pwn2own-2017-day-one', 'Pwn2Own 2017', 2017), 'Japan')
        self.assertEqual(endorsement_location('pwn2own', 'https://www.zerodayinitiative.com/blog/2021/4/2/pwn2own-2021-schedule-and-live-results', 'Pwn2Own 2021', 2021), 'Worldwide')
        self.assertIsNone(endorsement_location('unknown', 'https://example.com', None, 2025, ('United States', 'Singapore')))


if __name__ == '__main__':
    unittest.main()
