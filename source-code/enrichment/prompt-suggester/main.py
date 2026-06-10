from datetime import datetime, timezone

from vast_runtime.vast_event import VastEvent  # type: ignore

from common.llm_suggester import generate_suggestions
from common.models import Settings
from common.vastdb_client import VastDBClient


def init(ctx):
    """Initialize the serverless function."""
    with ctx.tracer.start_as_current_span("Prompt Suggester Initialization"):
        settings = Settings.from_ctx_secrets(ctx.secrets)
        ctx.settings = settings
        ctx.vastdb_client = VastDBClient(settings)
        ctx.logger.info(
            f"[INIT] segments={settings.vdbcollection} prompts={settings.vdbpromptscollection} "
            f"cosmos={settings.cosmos_model} @ {settings.cosmos_host}:{settings.cosmos_port}"
        )


def handler(ctx, event: VastEvent):
    """Main handler for vast serverless runtime (scheduled trigger)."""

    with ctx.tracer.start_as_current_span("Prompt Suggester Handler") as handler_span:
        try:
            data = event.get_data()
            event_type = getattr(event, "get_type", lambda: "scheduled_trigger")()
            handler_span.set_attribute("event_type", event_type)
            if data:
                handler_span.set_attribute("trigger_payload_keys", ",".join(sorted(data.keys())))

            ctx.logger.info("[SUGGEST] Starting scheduled prompt/event generation")

            with ctx.tracer.start_as_current_span("Fetch Corpus") as fetch_span:
                segments = ctx.vastdb_client.fetch_corpus()
                processed_videos = ctx.vastdb_client.list_processed_videos()
                existing_prompts = ctx.vastdb_client.list_existing_search_prompts()
                segments = ctx.vastdb_client.filter_unprocessed_corpus(segments, processed_videos)
                videos = ctx.vastdb_client.list_distinct_videos(segments)
                fetch_span.set_attributes({
                    "segments_sampled": len(segments),
                    "unique_videos": len(videos),
                    "videos_already_processed": len(processed_videos),
                    "lookback_hours": ctx.settings.suggestions_lookback_hours,
                })
                ctx.logger.info(
                    f"[SUGGEST] Corpus: {len(segments)} sample segments, {len(videos)} new videos "
                    f"({len(processed_videos)} already processed, skipped)"
                )

            if not segments:
                ctx.logger.info(
                    "[SUGGEST] No new videos in lookback window "
                    "(all already have suggestions or no segments)"
                )
                return {
                    "status": "success",
                    "skipped": True,
                    "reason": "no_new_videos",
                    "videos_already_processed": len(processed_videos),
                    "segments_scanned": 0,
                    "search_prompts": 0,
                    "key_events": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            with ctx.tracer.start_as_current_span("LLM Suggestions") as llm_span:
                search_prompts, key_events, batch_id = generate_suggestions(ctx.settings, segments)
                llm_span.set_attributes({
                    "batch_id": batch_id,
                    "search_prompts": len(search_prompts),
                    "key_events": len(key_events),
                })

            with ctx.tracer.start_as_current_span("VastDB Storage") as storage_span:
                table_full = (
                    f"{ctx.vastdb_client.bucket}.{ctx.vastdb_client.schema_name}."
                    f"{ctx.vastdb_client.prompts_table_name}"
                )
                ctx.logger.info(f"[VASTDB] Writing suggestions to {table_full}")
                rows_written = ctx.vastdb_client.store_suggestions(
                    batch_id,
                    search_prompts,
                    key_events,
                    skip_prompt_texts=existing_prompts,
                    skip_videos=processed_videos,
                )
                storage_span.set_attributes({
                    "table_name": table_full,
                    "rows_written": rows_written,
                    "batch_id": batch_id,
                })

            result = {
                "status": "success",
                "batch_id": batch_id,
                "segments_scanned": len(segments),
                "unique_videos": len(videos),
                "search_prompts": len(search_prompts),
                "key_events": len(key_events),
                "rows_written": rows_written,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            ctx.logger.info(
                f"[COMPLETE] batch={batch_id} prompts={len(search_prompts)} "
                f"events={len(key_events)} rows={rows_written}"
            )
            return result

        except Exception as exc:
            handler_span.set_attribute("error", True)
            handler_span.set_attribute("error.message", str(exc))
            handler_span.record_exception(exc)
            ctx.logger.error(f"[SUGGEST] Failed: {exc}")
            return {"status": "error", "error": str(exc)}
