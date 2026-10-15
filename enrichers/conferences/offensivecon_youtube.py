from __future__ import annotations

from endorsement_scraper.enrichment import BaseEnricher, EnricherContext, EnrichmentResult
from enrichers._youtube_common import collect_youtube


class OffensiveConYouTubeEnricher(BaseEnricher):
    enricher_id = "offensivecon-youtube-recordings"

    def run(self, context: EnricherContext) -> EnrichmentResult:
        return collect_youtube(context, assessor_id="offensivecon", enricher_id=self.enricher_id)
