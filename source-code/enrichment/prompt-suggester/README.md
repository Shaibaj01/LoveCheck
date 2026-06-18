# Prompt Suggester (DataEngine scheduled function)

Reads recent segment captions from `vss2-collection`, calls Cosmos Reason2, writes search prompts and key events to `vss2-prompts-events`. Served by video-backend `GET /api/v1/suggestions` and shown in the UI:

- **Search** empty state — clickable suggestion chips (fill query only)
- **Dashboard** — key events table with in-place segment preview

Structure matches other DataEngine functions (`vastdb-writer`, `fraud-detector`). See `.cursor/skills/dataengine-function/SKILL.md`.

## Secret keys (`vss2-secret`)

| Key | Default | Purpose |
|-----|---------|---------|
| `vdbpromptscollection` | `vss2-prompts-events` | Output table |
| `suggestions_max_segments` | `48` | Max segment lines in LLM corpus (sampled per video) |
| `suggestions_search_count` | `10` | Search prompts per run |
| `suggestions_events_count` | `30` | Max unique key events per run |
| `suggestions_max_events_per_video` | `3` | Cap per video in LLM prompt |
| `suggestions_lookback_hours` | `168` | Only segments newer than this |

Plus standard VastDB and Cosmos keys (`vdbendpoint`, `vdbcollection`, `cosmos_host`, `cosmos_port`, `cosmos_model`, …).

## Deploy

1. Build/register function `prompt-suggester` (`main.py` entry).
2. Create **Schedule** trigger in DataEngine; link in `deployments/dataengine-vss-enrichment-pipeline/vss-enrichment-pipeline-file.yaml`.
3. Redeploy video-backend / frontend (no search-suggestions ConfigMap).
