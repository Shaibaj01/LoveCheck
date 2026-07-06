# Video detector (YOLO11)

Runs object detection on each segment MP4 before the VLM reasoner.

## Flow

1. Receive S3 segment land event (same shape as reasoner).
2. Presign segment GET URL and call `POST http://<yolo_host>:8022/v1/infer` with `include_frames: true`.
3. Write gzipped sidecar JSON to `detections/{segment_stem}.json.gz` on the segments bucket.
4. Emit summary fields (`object_classes`, `object_counts`, `perception_ok`, …) plus metadata pass-through to **video-reasoner**.

## Pipeline link

`video-segment-land-trigger → video-detector → video-reasoner → video-embedder → video-vastdb-writer`

## Secret keys (`vss2-secret`)

| Key | Description |
|-----|-------------|
| `yolo_infer_host` | GPU host running YOLO11 infer service |
| `yolo_infer_port` | Default `8022` |
| `yolo_conf` | Confidence threshold (passed to infer service if supported) |
| `yolo_model` | Model id label (logging) |
| `yolo_presign_ttl` | Presigned GET TTL seconds |
| `detection_sidecar_prefix` | S3 key prefix, default `detections/` |
| `detection_store_frames` | `true` to write frame bboxes sidecar |

Also requires S3 keys (`s3accesskey`, `s3secretkey`, `s3endpoint`) and optional VastDB keys for idempotency skip.

## Build

```bash
cd source-code/ingest/video-detector
vastde functions build vss-video-detector
```

Or `./source-code/scripts/build-vastde-functions.sh`.
