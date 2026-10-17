from scrapers.enrichment import BaseEnricher, EnricherContext, EnrichmentResult
from scrapers.enrichers._youtube_common import collect_youtube


class BlackHatYouTubeRecordings(BaseEnricher):
    enricher_id = "black-hat-youtube-recordings"

    def run(self, context: EnricherContext) -> EnrichmentResult:
        return collect_youtube(context, assessor_id="black-hat", enricher_id=self.enricher_id)
