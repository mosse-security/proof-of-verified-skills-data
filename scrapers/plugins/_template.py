"""Copy this file to a non-underscore filename to activate the scraper."""

from html.parser import HTMLParser
from urllib.parse import urljoin

from scrapers import BaseScraper, Endorsement, PageResult, Request, Response


class ExampleParser(HTMLParser):
    """Replace this with site-specific parsing logic or a parser dependency."""

    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, str]] = []
        self.next_url: str | None = None


class ExampleScraper(BaseScraper):
    assessor_id = "replace-with-assessor-id"
    scraper_id = "replace-with-unique-scraper-id"
    start_urls = ("https://example.com/endorsements",)

    # For conference archives, override start_requests instead:
    # def start_requests(self):
    #     for year in range(2000, 2027):
    #         yield Request(f"https://example.com/events/{year}", meta={"year": year})

    def parse(self, response: Response, request: Request) -> PageResult:
        parser = ExampleParser()
        parser.feed(response.text)
        endorsements = [
            Endorsement(
                assessor_id=self.assessor_id,
                kind="conference_presentation",
                title=item["title"],
                description=item["description"],
                recipient=item.get("speaker"),
                year=int(item["year"]),
                subtitle=item.get("conference"),
                source_url=response.url,
                external_id=item.get("id"),
                details=item,
            )
            for item in parser.items
        ]
        follow = (
            (Request(urljoin(response.url, parser.next_url)),)
            if parser.next_url
            else ()
        )
        return PageResult.build(endorsements, follow)


