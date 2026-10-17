from scrapers.enrichment import BaseEnricher, EnricherContext, EnrichmentResult
from scrapers.enrichers._youtube_common import collect_youtube


class CanSecWestYouTubeRecordings(BaseEnricher):
    enricher_id = "cansecwest-youtube-recordings"

    def run(self, context: EnricherContext) -> EnrichmentResult:
        return collect_youtube(context, assessor_id="cansecwest", enricher_id=self.enricher_id)
