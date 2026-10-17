"""Contract for one parser per archived HTML page.

Page modules are deliberately small and page-owned. They may call shared
normalization helpers, but they must provide their own extraction function and
must validate every emitted endorsement before it can be written.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .schema import validate_endorsement_record


PageParserFunction = Callable[[bytes, str], Iterable[dict[str, object]]]


@dataclass(frozen=True, slots=True)
class ArchivedPageParser:
    assessor_id: str
    page_id: str
    archive_member: str
    parse: PageParserFunction

    def parse_validated(self, body: bytes, source_url: str) -> list[dict[str, object]]:
        records = list(self.parse(body, source_url))
        for index, record in enumerate(records):
            validate_endorsement_record(record, source=f"{self.assessor_id}/{self.page_id}[{index}]")
        return records
