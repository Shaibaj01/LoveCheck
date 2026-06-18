# Video Frontend

Angular web UI for the VSS Blueprint: **Search**, **Explore**, and **Dashboard** modes from the toolbar.

## Application Modes

Three top-level modes share the same scope pills (**All Videos** / **My Videos** / **Public Only**) and a dedicated **Refresh** button (reloads the current view without switching mode).

| Mode | Route | Purpose |
|------|-------|---------|
| **Search** | `/search` | Hybrid semantic search; clip cards grouped by upload with segment timeline; LLM synthesis |
| **Explore** | `/explore` | Browse indexed uploads by day — no query; metadata on cards; **Summarize Video** on demand |
| **Dashboard** | `/dashboard` | VastDB stats, ingest quality, S3 pipeline inventory, key events from prompt-suggester |

### Search

- Empty state shows **live search suggestions** from `GET /api/v1/suggestions` (prompt-suggester → `vss2-prompts-events`). Clicking a suggestion fills the search bar only (does not auto-run search).
- After a search, results persist when navigating away and back; suggestions stay hidden while results are shown.
- **Refresh** clears results and restores the suggestion panel.

### Explore

- Hero: **Browse by upload date** — indexed clips day by day; summarize any video on demand.
- Date rail filters by upload day; cards show upload time, metadata (camera, capture type, location, tags), and object chips — no segment timeline on cards.
- Player opens in explore mode (no jump-to-moment bar); **Summarize Video** runs `POST /api/v1/videos/synthesize`.

### Dashboard

- Scope-scoped VastDB statistics; KPI panels hidden when the collection is unreadable (amber warning instead of misleading zeros).
- **Key events** table: search icon opens the event clip directly via segment metadata (falls back to hybrid search); **Uploaded** column shows parent video upload time.
- S3 pipeline panel compares chunk/segment MP4 counts to indexed clips.

## Other Features

- **Video Upload**: metadata (camera_id, capture_type, location) + optional custom AI prompt
- **Video Playback**: segment player with timeline (search mode) or browse player (explore mode)
- **Authentication**: VAST username + password → app JWT
- **Settings**: Advanced Search & AI, system prompt, streaming, batch sync
- **Blueprint diagram**: Settings → Show Blueprint Diagram (`src/assets/blueprint.html`)

## Configuration

- **Backend API**: `/api/v1/config`
- **Suggestions / key events**: `/api/v1/suggestions` (polls every 5 min on Search + Dashboard)

User settings in browser `localStorage`: Advanced Search & AI, system prompt, time filters.

## Stack

- Angular 18 · Angular Material · RxJS services · JWT in localStorage
- Deployed as static files behind Nginx — see [K8s deployment guide](../../../deployments/vss-k8s-application/README.md)
