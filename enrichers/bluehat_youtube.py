from endorsement_scraper.enrichment import BaseEnricher, EnricherContext, EnrichmentResult
from enrichers._youtube_common import collect_youtube


class BlueHatYouTubeRecordings(BaseEnricher):
    enricher_id = "bluehat-youtube-recordings"

    def run(self, context: EnricherContext) -> EnrichmentResult:
        return collect_youtube(context, assessor_id="bluehat", enricher_id=self.enricher_id)
