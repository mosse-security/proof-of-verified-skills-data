{
  "name": "Name of the person",
  "label": "Title",
  "description": "Detailed description or abstract of the endorsement",
  "type": "presentation|tool|cve|...",
  "assessor": "Name of assessor from where the endorsement was retrieved",
  "assessor-id": "ID of the assessor in the data folder",
  "assessor-category": "category of the assessor in the data folder",
  "assessor-rigor-level": "rigorLevel of the assessor in the data folder",
  "reviewType": "reviewType of the assessor in the data folder",
  "subtitle": "Optional field to specify additional information like conference year",
  "url": "URL to verify the record",
  "evidence-links": [
    {
      "title": "Related recording",
      "url": "https://example.com/recording"
    }
  ],
  "evidence": true,
  "povs": {
    "milestones": {
      "verifiable": true,
      "defended": true,
      "recognized": true,
      "trusted": false
    },
    "level": 2,
    "explanation": "The speaker’s proposal was accepted through the conference’s independent review process. They publicly presented and defended the work at the event, providing verifiable and recognized evidence of the endorsement. We could not verify whether the work is used in industry in situations of real consequence."
  },
  "year": "Year of the record",
  
  "domains": [
    "penetration-testing",
    "vulnerability-research"
  ],
  "subspecialties": {
    "penetration-testing": [
      "web-application-penetration-testing",
      "api-penetration-testing"
    ],
    "vulnerability-research": [
      "vulnerability-discovery"
    ]
  }
}
