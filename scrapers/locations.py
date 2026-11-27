"""Conservative, event-specific endorsement location classification.

Do not infer a person's location or assign all of an assessor's countries to
each record. Unknown, virtual, and ambiguous events can remain unclassified.
"""
from __future__ import annotations

import re


def endorsement_location(assessor_id: str, url: str, subtitle: str | None, year: int, assessor_countries: tuple[str, ...] = ()) -> str | None:
    source = f"{url} {subtitle or ''}".lower()
    if assessor_id == "def-con":
        return "United States"
    if assessor_countries == ("Worldwide",):
        return "Worldwide"
    if assessor_id == "black-hat":
        if year == 2020:
            return None  # Virtual editions must not be assigned a host country.
        if re.search(r"black hat usa|blackhat\.com/(?:archive/usa/|(?:html/)?bh-us-|us-)", source):
            return "United States"
        if re.search(r"black hat asia|blackhat\.com/(?:archive/asia/|asia-|(?:html/)?bh-asia-)", source):
            return "Singapore" if year >= 2014 else None
        if re.search(r"black hat europe|blackhat\.com/(?:archive/europe/|(?:html/)?bh-eu-|eu-)", source):
            return {2013: "Netherlands", 2014: "Netherlands", 2015: "Netherlands", 2016: "United Kingdom", 2017: "United Kingdom", 2018: "United Kingdom", 2022: "United Kingdom", 2024: "United Kingdom"}.get(year)
        if re.search(r"blackhat\.com/(?:ad-12|html/bh-ad-12)", source):
            return "United Arab Emirates"
        return None
    if assessor_id == "hitb":
        match = re.search(r"hitbsecconf(2022sin|2023ams|2023hkt|2024bkk)", source)
        return {"2022sin": "Singapore", "2023ams": "Netherlands", "2023hkt": "Thailand", "2024bkk": "Thailand"}.get(match.group(1)) if match else None
    if assessor_id == "acm-ccs":
        return "Netherlands" if year == 2026 and "ccs2026" in source else None
    if assessor_id == "rsa-conference":
        return "United States" if "/flow/rsac/us26/" in source else None
    if assessor_id == "bluehat":
        return "United States" if year in {2014, 2016, 2017, 2018, 2019, 2023} and "microsoft.com" in source else None
    if assessor_id == "pwn2own":
        if "zerodayinitiative.com" not in source:
            return None
        if year == 2017 and "welcome-to-mobile-pwn2own-2017" in source:
            return "Japan"
        if year == 2021 and "pwn2own-2021-schedule-and-live-results" in source:
            return "Worldwide"
        for marker, location in (("pwn2own-vancouver", "Canada"), ("pwn2own-toronto", "Canada"), ("pwn2own-berlin", "Germany"), ("pwn2own-ireland", "Ireland"), ("pwn2own-tokyo", "Japan"), ("pwn2own-miami", "United States"), ("pwn2ownaustin", "United States")):
            if marker in source:
                return location
        if "pwn2own-automotive" in source and year in {2024, 2025, 2026}:
            return "Japan"
        return None
    fixed = {
        "ccc": "Germany", "derbycon": "United States", "grrcon": "United States",
        "blue-team-con": "United States", "offensivecon": "Germany",
        "insomnihack": "Switzerland", "layer-one": "United States", "cansecwest": "Canada",
    }
    if assessor_id in fixed:
        if year in {2020, 2021} and not (assessor_id == "insomnihack" and year == 2020) and not (assessor_id == "blue-team-con" and year == 2021) and not (assessor_id == "offensivecon" and year == 2020):
            return None
        return fixed[assessor_id]
    if year == 2026 and assessor_id in {"ieee-sp", "ndss", "usenix-security"}:
        return "United States"
    return None
