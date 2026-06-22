# Prompt suggester (DataEngine enrichment)

Reads recent segment captions from `vss-collection`, calls Cosmos Reason2, writes search prompts and key events to `vss-prompts-events`. Served by video-backend `GET /api/v1/suggestions` and shown in the UI:

- **Search** — suggestion chips on empty state
- **Dashboard** — key events table with in-place segment preview

## Secret keys (`vss2-secret`)

DataEngine secret **name** stays `vss2-secret`; table/bucket **values** use the `vss-*` namespace:

| Key | Example value | Purpose |
|-----|---------------|---------|
| `vdbcollection` | `vss-collection` | Source segments |
| `vdbpromptscollection` | `vss-prompts-events` | Output table |
| `vdbbucket` / `vdbschema` | `vss-db` / `vss-schema` | VastDB location |

## Deploy

1. Build image: `source-code/scripts/build-vastde-functions.sh` (includes prompt-suggester)
2. Create **Schedule** trigger in DataEngine; link in `deployments/dataengine-vss-enrichment-pipeline/vss-enrichment-pipeline-file.yaml`.

Do **not** commit filled secret files — use `*-secret-file-template.yaml` and keep credentials local.
