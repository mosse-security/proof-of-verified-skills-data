"""Page-owned Insomni'hack parsers with legacy compatibility exports."""
from .. import insomnihack_runner as _legacy

InsomnihackScraper = _legacy.InsomnihackScraper
InsomnihackEndorsement = _legacy.InsomnihackEndorsement
_member = _legacy._member
_year = _legacy._year

from .edition_2013 import parse_page as parse_2013
from .edition_2014 import parse_page as parse_2014
from .edition_2015 import parse_page as parse_2015
from .edition_2016 import parse_page as parse_2016
from .edition_2017 import parse_page as parse_2017
from .edition_2018 import parse_page as parse_2018
from .edition_2019 import parse_page as parse_2019
from .edition_2020 import parse_page as parse_2020
from .edition_2022 import parse_page as parse_2022
from .edition_2023 import parse_page as parse_2023
from .edition_2024 import parse_page as parse_2024
from .edition_2025 import parse_page as parse_2025
from .edition_2026 import parse_page as parse_2026

PAGE_PARSERS = {
    2013: parse_2013, 2014: parse_2014, 2015: parse_2015,
    2016: parse_2016, 2017: parse_2017, 2018: parse_2018,
    2019: parse_2019, 2020: parse_2020, 2022: parse_2022,
    2023: parse_2023, 2024: parse_2024, 2025: parse_2025,
    2026: parse_2026,
}

