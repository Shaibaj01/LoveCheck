# Prompt Suggester (DataEngine scheduled function)

Reads recent segment captions from `vss2-collection`, calls Cosmos Reason2, writes search prompts and key events to `vss2-prompts-events`. Served by video-backend `GET /api/v1/suggestions`.

Structure matches other DataEngine functions (`vastdb-writer`, `fraud-detector`). See `.cursor/skills/dataengine-function/SKILL.md`.

## Secret keys (`vss2-secret`)

| Key | Default | Purpose |
|-----|---------|---------|
| `vdbpromptscollection` | `vss2-prompts-events` | Output table |
| `suggestions_max_segments` | `100` | Max caption lines sent to LLM |
| `suggestions_search_count` | `10` | Search prompts per run |
| `suggestions_events_count` | `25` | Key events per run |
| `suggestions_lookback_hours` | `168` | Only segments newer than this |

Plus standard VastDB and Cosmos keys (`vdbendpoint`, `vdbcollection`, `cosmos_host`, `cosmos_port`, `cosmos_model`, …).

## Deploy

1. Build/register function `prompt-suggester` (`main.py` entry).
2. Create **Schedule** trigger in DataEngine; link in `deployments/dataengine-vss-enrichment-pipeline/vss-enrichment-pipeline-file.yaml`.
3. Redeploy video-backend / frontend (no search-suggestions ConfigMap).
