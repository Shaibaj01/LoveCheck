# Video Frontend

An Angular web application that provides the user interface for the VSS Blueprint.

## What It Does

- **Video Search**: Semantic search with **Text**, **Visual**, or **Hybrid** modes (dense caption vs frame embeddings)
- **Video Upload**: Upload videos with metadata (camera_id, capture_type, location) and optional custom AI prompt
- **Video Playback**: Play video segments with reasoning text overlays
- **User Authentication**: Login with VAST credentials (username + S3 secret key)
- **Settings Management**: Configure LLM settings, system prompts, and video streaming
- **Metadata Filtering**: Filter search results by camera, location, capture type, and time

## Easy to Adjust

### Frontend Configuration

- **Backend API**: `/api/v1/config` for app settings; `/api/v1/suggestions` for live search examples and key events (from VastDB `vss2-prompts-events`, refreshed by the prompt-suggester DataEngine function)

### User Settings (Browser Storage)

Users can customize these settings in the UI (stored in browser localStorage):

- **Advanced Search & AI Settings**: max clip cards, LLM clips analyzed, caption/video weight, minimum similarity
- **System Prompt**: Custom LLM system prompt for search result synthesis
- **Time Filters**: Preset or custom date ranges for filtering

### Build Configuration

Edit `angular.json` or `package.json` for:
- Build output directory
- Development server port
- Production build optimizations

## About the Application

- **Framework**: Angular 18
- **UI Library**: Angular Material
- **State Management**: Services with RxJS observables
- **Authentication**: JWT tokens stored in localStorage
- **API Communication**: REST API calls to backend service
- **Features**:
  - Search page with vector search and LLM synthesis
  - Upload dialog with metadata input
  - Video player with segment navigation
  - Settings dialogs for customization
  - Streaming service integration

## What Runs It

- **Runtime**: Nginx web server (containerized)
- **Image**: `your.registry/vss-video-frontend:v1` (placeholder — build and push from this directory; see [K8s deployment guide](../../../deployments/vss-k8s-application/README.md#step-2-docker-images))
- **Deployment**: Kubernetes deployment (see main README Part 2)
- **Access**: Via ingress at `http://video-lab.<cluster_name>.vastdata.com`
- **Build**: Angular CLI builds static files served by Nginx
- **Dependencies**: Node.js for build, Nginx for serving

