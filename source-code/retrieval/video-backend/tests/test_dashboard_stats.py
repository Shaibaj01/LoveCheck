"""Tests for dashboard statistics aggregation."""
import unittest

from src.utils.dashboard_stats import (
    attach_s3_inventory,
    build_dashboard_stats,
    empty_dashboard_stats,
    segmenter_output_bucket,
)


class DashboardStatsTests(unittest.TestCase):
    def test_build_dashboard_stats_aggregates_objects_metadata_and_time(self):
        rows = [
            {
"source": "s3://bucket/a_seg_001.mp4",
                "original_video": "s3://bucket/a.mp4",
                "filename": "a_seg_001.mp4",
                "segment_number": 1,
                "total_segments": 2,
                "upload_timestamp": "2026-05-31T10:00:00",
                "camera_id": "cam-01",
                "capture_type": "streets",
                "location": "midtown",
                "object_classes": "person,forklift",
                "structured_parse_ok": True,
                "perception_ok": True,
                "is_public": True,
            },
            {
"source": "s3://bucket/a_seg_001.mp4",
                "original_video": "s3://bucket/a.mp4",
                "filename": "a_seg_001.mp4",
                "segment_number": 1,
                "total_segments": 2,
                "upload_timestamp": "2026-05-31T11:00:00",
                "camera_id": "cam-01",
                "capture_type": "streets",
                "location": "midtown",
                "object_classes": "person",
                "structured_parse_ok": False,
                "perception_ok": False,
                "is_public": True,
            },
            {
"source": "s3://bucket/a_seg_002.mp4",
                "original_video": "s3://bucket/a.mp4",
                "filename": "a_seg_002.mp4",
                "segment_number": 2,
                "total_segments": 2,
                "upload_timestamp": "2026-05-31T10:00:00",
                "camera_id": "",
                "capture_type": "",
                "location": "",
                "object_classes": "",
                "structured_parse_ok": True,
                "perception_ok": True,
                "is_public": False,
            },
        ]

        stats = build_dashboard_stats(rows)
        self.assertEqual(stats["overview"]["segment_rows"], 3)
        self.assertEqual(stats["overview"]["unique_videos"], 1)
        self.assertEqual(stats["overview"]["indexed_clips"], 2)
        self.assertEqual(stats["overview"]["re_ingest_rows"], 1)

        labels = {item["label"]: item["segment_count"] for item in stats["objects"]}
        self.assertEqual(labels["person"], 2)
        self.assertEqual(labels["forklift"], 1)

        self.assertEqual(len(stats["uploads_by_day"]), 1)
        self.assertEqual(stats["recent_videos"][0]["indexed_clips"], 2)
        self.assertEqual(stats["recent_videos"][0]["re_ingest_rows"], 1)

    def test_stream_session_grouping(self):
        rows = [
            {
"source": "s3://bucket/chunk1_seg_001.mp4",
                "original_video": "s3://bucket/chunk1.mp4",
                "filename": "chunk1_seg_001.mp4",
                "segment_number": 1,
                "total_segments": 6,
                "extra_metadata": '{"stream_id":"s1","chunk_index":0,"chunk_start_sec":0,"stream_position_sec":0,"ingest_kind":"stream_chunk"}',
                "is_public": True,
            },
            {
"source": "s3://bucket/chunk2_seg_001.mp4",
                "original_video": "s3://bucket/chunk2.mp4",
                "filename": "chunk2_seg_001.mp4",
                "segment_number": 1,
                "total_segments": 6,
                "extra_metadata": '{"stream_id":"s1","chunk_index":1,"chunk_start_sec":30,"stream_position_sec":30,"ingest_kind":"stream_chunk"}',
                "is_public": True,
            },
        ]
        stats = build_dashboard_stats(rows)
        self.assertEqual(stats["overview"]["stream_sessions"], 1)
        self.assertEqual(len(stats["recent_videos"]), 1)
        self.assertEqual(stats["recent_videos"][0]["chunk_count"], 2)
        self.assertEqual(stats["recent_videos"][0]["indexed_clips"], 2)

    def test_empty_dashboard_stats_zeros(self):
        stats = empty_dashboard_stats()
        self.assertEqual(stats["overview"]["total_rows"], 0)
        self.assertEqual(stats["objects"], [])
        self.assertEqual(stats["recent_videos"], [])

    def test_attach_s3_inventory_alignment(self):
        payload = build_dashboard_stats(
            [
                {
    "source": "s3://b/a_seg_001.mp4",
                    "original_video": "s3://b/a.mp4",
                    "filename": "a_seg_001.mp4",
                    "segment_number": 1,
                    "total_segments": 1,
                    "is_public": True,
                },
                {
    "source": "s3://b/a_seg_001.mp4",
                    "original_video": "s3://b/a.mp4",
                    "filename": "a_seg_001.mp4",
                    "segment_number": 1,
                    "total_segments": 1,
                    "is_public": True,
                },
            ]
        )
        attach_s3_inventory(
            payload,
            upload_bucket="vss2-chunks",
            segments_bucket="vss2-segments",
            bucket_counts={
                "vss2-chunks": 9,
                "vss2-segments": 0,
                "vss2-chunks-segments": 54,
            },
            bucket_errors={},
        )
        self.assertEqual(segmenter_output_bucket("vss2-chunks"), "vss2-chunks-segments")
        self.assertEqual(payload["s3_inventory"]["chunks_mp4"], 9)
        self.assertEqual(payload["pipeline_alignment"]["segments_s3_mp4"], 54)
        self.assertEqual(payload["pipeline_alignment"]["indexed_clips"], 1)
        self.assertEqual(payload["pipeline_alignment"]["pending_index"], 53)
        self.assertFalse(payload["pipeline_alignment"]["segments_bucket_matches_segmenter"])
        self.assertFalse(payload["pipeline_alignment"]["healthy"])


if __name__ == "__main__":
    unittest.main()
