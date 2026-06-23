# Notes

## With two more days

- Move ingestion to a background job and stream progress to the UI.
- Batch Ollama embedding requests where supported and add article-scoped chat selection.
- Pin and scan container image digests in CI.
- Add browser-level UI tests and accessibility checks.

## AI-agent corrections made during development

The agent initially missed browser CORS, used a removed `QdrantClient.search` API, generated invalid Qdrant IDs (`hash::chunk`), and used the wrong keyword/return shape for `scroll`. These were caught through live-stack verification and corrected with tests. The agent also identified that a Qdrant-only Compose file and ad-hoc smoke scripts did not satisfy the submitted brief, then added the enforced coverage suite and full-stack wiring.
