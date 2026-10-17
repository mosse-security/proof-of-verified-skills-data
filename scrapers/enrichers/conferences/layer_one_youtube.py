from __future__ import annotations

from scrapers.enrichment import BaseEnricher, EnricherContext, EnrichmentResult
from scrapers.enrichers._youtube_common import collect_youtube


class LayerOneYouTubeRecordings(BaseEnricher):
    enricher_id = "layer-one-youtube-recordings"

    def run(self, context: EnricherContext) -> EnrichmentResult:
        return collect_youtube(context, assessor_id="layer-one", enricher_id=self.enricher_id)
