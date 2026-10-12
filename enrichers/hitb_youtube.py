from __future__ import annotations

from endorsement_scraper.enrichment import BaseEnricher, EnricherContext, EnrichmentResult
from enrichers._youtube_common import collect_youtube


class HitbYouTubeRecordings(BaseEnricher):
    enricher_id = "hitb-youtube-recordings"

    def run(self, context: EnricherContext) -> EnrichmentResult:
        return collect_youtube(context, assessor_id="hitb", enricher_id=self.enricher_id)
