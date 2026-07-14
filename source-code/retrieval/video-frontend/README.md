# Video Frontend

Angular web UI for the VSS Blueprint: **Search**, **Explore**, and **Dashboard** modes from the toolbar.

## Application Modes

Three top-level modes share the same scope pills (**All Videos** / **My Videos** / **Public Only**) and a dedicated **Refresh** button (reloads the current view without switching mode).

| Mode | Route | Purpose |
|------|-------|---------|
| **Search** | `/search` | Hybrid semantic search; clip cards with match timeline; Cosmos-Reason2 synthesis |
| **Explore** | `/explore` | Browse fully indexed uploads by day and location; summarize on demand |
| **Dashboard** | `/dashboard` | VastDB stats, ingest quality, object **instance** heatmap (peak count sums), grounded key events |

### Search

- Empty state shows **search suggestions** from `GET /api/v1/suggestions` (prompt-suggester grounded rephrases → `vss-prompts-events`). Clicking a suggestion fills the search bar only.
- Clip cards: **upload time** badge (config timezone), **% match** badge, match timeline with segment jumps, reasoning caption and class chips.
- Search animation phases follow the live request; model names come from `GET /api/v1/config` (Cosmos-Embed1, Cosmos-Reason2).
- After a search, results persist when navigating away and back.

### Explore

- Hero: **Browse by upload date** — indexed clips day by day.
- **Date rail** and **location rail** filter the list.
- Only **fully indexed** chunks appear (all segments present in VastDB).
- Cards: upload time badge, segment timeline (jump to moment), metadata and object chips, **Play chunk N/M** and **Summarize** actions.
- Player plays the **full parent chunk** (`original_video`); segment timeline and bbox overlay (OFF/ON toggle in the timeline header).

### Video playback (Search + Explore)

- **Search:** segment MP4s for hover preview; player opens at best match; match timeline with query highlights.
- **Explore:** full-chunk stream; segment clicks seek within the parent file.
- **Bbox overlay:** `GET /api/v1/videos/detections?source=…` sidecar; toggle persisted in `localStorage`.
- Segment list under the player: selectable reasoning text; object chips show peak counts when present (`person 3`).
- Autoplay is **muted** by default; users can unmute via native controls.
- Only the video preview on result cards opens the player (description is selectable).

### Dashboard

- Scope-scoped VastDB statistics; KPI panels hidden when the collection is unreadable.
- **Object heatmap** sums YOLO `object_counts` (instance totals); tooltips include segment presence.
- **Key events** table: grounded ≤8-word phrases; search icon opens the event clip; upload time uses `display_timezone` from config.

## Other Features

- **Video Upload / Streaming / Batch Sync**: shared metadata form — `GET /api/v1/metadata/ingest-config` with defaults fallback ([`ingest_metadata.defaults.ts`](src/app/shared/utils/ingest-metadata.defaults.ts))
- **Authentication**: VAST username + password → app JWT
- **Settings**: Advanced Search & AI, system prompt, streaming, batch sync
- **Blueprint diagram**: Settings → Show Blueprint Diagram (`src/assets/blueprint.html`)

## Configuration

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/config` | Embedding/synthesis endpoints, `app.display_timezone`, default system prompt |
| `GET /api/v1/metadata/ingest-config` | Upload dialog field definitions |
| `GET /api/v1/metadata/schema` | Search filter columns |
| `GET /api/v1/suggestions` | Search prompts + key events (polls every 5 min on Search + Dashboard) |

User settings in browser `localStorage`: Advanced Search & AI, system prompt, bbox overlay preference, time filters.

## Stack

- Angular 18 · Angular Material · RxJS services · JWT in localStorage
- Shared utilities: `video-hover-preview.util.ts`, `detection-overlay.util.ts`, `time.util.ts`
- Deployed as static files behind Nginx — see [K8s deployment guide](../../../deployments/vss-k8s-application/README.md) or `source-code/scripts/build-retrieval-images.sh`
