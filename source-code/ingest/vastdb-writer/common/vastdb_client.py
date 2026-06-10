import logging
import hashlib
import json
import vastdb
import pyarrow as pa
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

from common import vastdb_patch  # noqa: F401 — apply SDK patch before select/insert
from common.segment_index import pk_for_source


def _resolve_segment_times(
    embedding_event: Dict[str, Any],
    segment_number: int,
    segment_duration: float,
) -> Tuple[float, float]:
    """Resolve timeline position in parent video from pipeline metadata or derive."""
    start_raw = embedding_event.get("segment_start_sec")
    end_raw = embedding_event.get("segment_end_sec")
    if start_raw is not None and end_raw is not None:
        try:
            return float(start_raw), float(end_raw)
        except (TypeError, ValueError):
            pass

    step = embedding_event.get("segment_step_sec")
    try:
        step_sec = float(step) if step is not None else 5.0
    except (TypeError, ValueError):
        step_sec = 5.0

    sn = segment_number if segment_number > 0 else 1
    start = (sn - 1) * step_sec
    end = start + segment_duration
    return start, end


class VastDBClient:
    """VastDB client for storing video reasoning vectors"""

    def __init__(self, settings):
        self.settings = settings
        self.table_name = settings.vdbcollection
        self.bucket = settings.vdbbucket
        self.schema_name = settings.vdbschema
        self.visual_dim = (
            settings.visual_embedding_dimensions
            if getattr(settings, "visual_embedding_dimensions", 0) > 0
            else settings.embeddingdimensions
        )

        self.schema_columns = pa.schema([
            ("pk", pa.utf8()),
            ("source", pa.utf8()),
            ("filename", pa.utf8()),
            ("segment_number", pa.uint32()),
            ("segment_start_sec", pa.float64()),
            ("segment_end_sec", pa.float64()),
            ("reasoning_content", pa.utf8()),
            ("dense_caption", pa.utf8()),
            ("vlm_structured", pa.string()),
            ("structured_parse_ok", pa.bool_()),
            ("perception_json", pa.string()),
            ("object_classes", pa.utf8()),
            ("object_counts", pa.utf8()),
            ("max_detection_conf", pa.float32()),
            ("perception_ok", pa.bool_()),
            ("vectors", pa.list_(pa.field(name="item", type=pa.float32(), nullable=False), self.settings.embeddingdimensions)),
            ("vectors_visual", pa.list_(pa.field(name="item", type=pa.float32(), nullable=False), self.visual_dim)),
            ("cosmos_model", pa.utf8()),
            ("embedding_model", pa.utf8()),
            ("visual_embedding_model", pa.utf8()),
            ("tokens_used", pa.int32()),
            # usage.prompt_tokens_details.cached_tokens (vLLM). Add column on existing tables before deploy.
            ("cached_prompt_tokens", pa.int32()),
            ("processing_time", pa.float64()),
            ("timestamp", pa.utf8()),
            ("allowed_users", pa.list_(pa.utf8())),
            ("is_public", pa.bool_()),
            ("upload_timestamp", pa.timestamp('ns')),
            ("duration", pa.float64()),
            ("total_segments", pa.uint32()),
            ("original_video", pa.utf8()),
            ("tags", pa.list_(pa.utf8())),
            ("camera_id", pa.utf8()),
            ("capture_type", pa.utf8()),
            ("location", pa.utf8()),
            ("extra_metadata", pa.string())
        ])

        self._initialize_connection()
        self._schema_ready = False

    def _initialize_connection(self):
        """Initialize VastDB connection"""
        endpoint = self.settings.vdbendpoint
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"

        self.session = vastdb.connect(
            endpoint=endpoint,
            access=self.settings.vdbaccesskey,
            secret=self.settings.vdbsecretkey,
            ssl_verify=False
        )

    def ensure_schema_and_table(self) -> bool:
        """Ensure schema and table exist, creating them if needed."""
        if self._schema_ready:
            return True
        try:
            with self.session.transaction() as tx:
                bucket = tx.bucket(self.bucket)
                
                schema = bucket.schema(self.schema_name, fail_if_missing=False)
                if schema is None:
                    schema = bucket.create_schema(self.schema_name, fail_if_exists=False)
                
                table = schema.table(self.table_name, fail_if_missing=False)
                if table is None:
                    try:
                        schema.create_table(self.table_name, columns=self.schema_columns)
                    except Exception as e:
                        if "409" in str(e) or "Conflict" in str(e) or "already exists" in str(e).lower():
                            table = schema.table(self.table_name, fail_if_missing=False)
                            if table is None:
                                raise RuntimeError("Failed to get table after creation conflict")
                        else:
                            raise
                
                self._schema_ready = True
                return True
                
        except Exception as e:
            logging.error(f"Error ensuring schema/table: {e}")
            return False

    def store_vector(self, embedding_event: Dict[str, Any]) -> bool:
        """Store video reasoning with vector in VastDB. Skips duplicate source."""
        try:
            source = embedding_event.get("source", "")
            filename = embedding_event.get("filename", "")
            reasoning_content = embedding_event.get("reasoning_content", "")
            dense_caption = (embedding_event.get("dense_caption") or "").strip()
            vlm_structured = embedding_event.get("vlm_structured", "") or ""
            structured_parse_ok = bool(embedding_event.get("structured_parse_ok", False))
            embedding = embedding_event.get("embedding", [])
            visual_embedding = embedding_event.get("visual_embedding") or []
            visual_embedding_ok = bool(embedding_event.get("visual_embedding_ok", False))
            visual_embedding_model = embedding_event.get("visual_embedding_model", "") or ""
            
            if not reasoning_content and not dense_caption:
                return True
            
            if not embedding:
                logging.warning("No embedding vector to store")
                return False

            pk = pk_for_source(source)
            timestamp = datetime.utcnow().isoformat() + "Z"
            
            is_public = embedding_event.get("is_public", True)
            allowed_users_str = embedding_event.get("allowed_users", "")
            tags_str = embedding_event.get("tags", "")
            original_video = embedding_event.get("original_video", filename)
            upload_timestamp_str = embedding_event.get("upload_timestamp", "")
            segment_duration_event = embedding_event.get("segment_duration", 5.0)
            segment_number_event = embedding_event.get("segment_number")
            total_segments_event = embedding_event.get("total_segments")
            
            camera_id = embedding_event.get("camera_id", "")
            capture_type = embedding_event.get("capture_type", "")
            location = embedding_event.get("location", "")
            
            allowed_users = [u.strip() for u in allowed_users_str.split(",") if u.strip()] if allowed_users_str else []
            tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
            
            # Parse segment metadata
            if segment_number_event is not None:
                segment_number = int(segment_number_event) if segment_number_event else 0
            else:
                segment_number = 0
                if "_segment_" in filename:
                    try:
                        parts = filename.split("_segment_")[1].split("_of_")
                        segment_number = int(parts[0])
                    except:
                        pass
            
            if total_segments_event is not None:
                total_segments = int(total_segments_event) if total_segments_event else 1
            else:
                total_segments = 1
                if "_segment_" in filename and "_of_" in filename:
                    try:
                        parts = filename.split("_of_")[1].split(".")[0]
                        total_segments = int(parts)
                    except:
                        pass
            
            segment_duration = float(segment_duration_event) if segment_duration_event else 5.0
            segment_start_sec, segment_end_sec = _resolve_segment_times(
                embedding_event, segment_number, segment_duration
            )
            
            if upload_timestamp_str:
                try:
                    upload_timestamp = datetime.fromisoformat(upload_timestamp_str.replace('Z', '+00:00'))
                except:
                    upload_timestamp = datetime.utcnow()
            else:
                upload_timestamp = datetime.utcnow()
            
            if not visual_embedding or len(visual_embedding) != self.visual_dim:
                visual_embedding = [0.0] * self.visual_dim

            extra_metadata = {
                "status": embedding_event.get("status", "success"),
                "embedding_dimensions": embedding_event.get("embedding_dimensions", 0),
                "visual_embedding_dimensions": len(visual_embedding),
                "visual_embedding_ok": visual_embedding_ok,
            }
            stream_id = str(embedding_event.get("stream_id") or "").strip()
            if stream_id:
                extra_metadata["stream_id"] = stream_id
            if embedding_event.get("chunk_index") is not None:
                extra_metadata["chunk_index"] = embedding_event.get("chunk_index")
            chunk_start = embedding_event.get("chunk_start_sec")
            if chunk_start is not None:
                try:
                    chunk_start_f = float(chunk_start)
                    extra_metadata["chunk_start_sec"] = chunk_start_f
                    extra_metadata["stream_position_sec"] = round(chunk_start_f + float(segment_start_sec), 3)
                except (TypeError, ValueError):
                    pass
            ingest_kind = str(embedding_event.get("ingest_kind") or "").strip()
            if ingest_kind:
                extra_metadata["ingest_kind"] = ingest_kind
            
            record = {
                "pk": pk,
                "source": source,
                "filename": filename,
                "segment_number": segment_number,
                "segment_start_sec": segment_start_sec,
                "segment_end_sec": segment_end_sec,
                "reasoning_content": reasoning_content,
                "dense_caption": dense_caption or reasoning_content,
                "vlm_structured": vlm_structured if isinstance(vlm_structured, str) else str(vlm_structured),
                "structured_parse_ok": structured_parse_ok,
                "perception_json": embedding_event.get("perception_json", "") or "",
                "object_classes": embedding_event.get("object_classes", "") or "",
                "object_counts": embedding_event.get("object_counts", "{}") or "{}",
                "max_detection_conf": float(embedding_event.get("max_detection_conf") or 0.0),
                "perception_ok": bool(embedding_event.get("perception_ok", False)),
                "vectors": embedding,
                "vectors_visual": visual_embedding,
                "cosmos_model": embedding_event.get("cosmos_model", ""),
                "embedding_model": embedding_event.get("embedding_model", ""),
                "visual_embedding_model": visual_embedding_model,
                "tokens_used": embedding_event.get("tokens_used", 0),
                "cached_prompt_tokens": int(embedding_event.get("cached_prompt_tokens") or 0),
                "processing_time": embedding_event.get("processing_time", 0.0),
                "timestamp": timestamp,
                "allowed_users": allowed_users,
                "is_public": is_public,
                "upload_timestamp": upload_timestamp,
                "duration": segment_duration,
                "total_segments": total_segments,
                "original_video": original_video,
                "tags": tags,
                "camera_id": camera_id,
                "capture_type": capture_type,
                "location": location,
                "extra_metadata": json.dumps(extra_metadata, ensure_ascii=False),
            }
            
            if not self.ensure_schema_and_table():
                return False
            
            arrow_table = pa.Table.from_pylist([record], schema=self.schema_columns)
            
            with self.session.transaction() as tx:
                bucket = tx.bucket(self.bucket)
                schema = bucket.schema(self.schema_name)
                table = schema.table(self.table_name)
                if self._skip_or_dedupe_existing_segment(table, source):
                    return True
                table.insert(arrow_table)

            return True
            
        except Exception as e:
            logging.error(f"Error storing vector: {e}")
            return False

    def _skip_or_dedupe_existing_segment(self, table, source: str) -> bool:
        """Return True when insert should be skipped. Runs inside an open transaction."""
        existing = table.select(
            predicate=(table["source"] == source),
            columns=["source"],
            internal_row_id=False,
        ).read_all()
        if existing.num_rows == 0:
            return False
        logging.info("[VASTDB] Skip duplicate index: %s", source)
        return True

    def close(self):
        """Close VastDB connection"""
        if hasattr(self, 'session') and hasattr(self.session, 'close'):
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

