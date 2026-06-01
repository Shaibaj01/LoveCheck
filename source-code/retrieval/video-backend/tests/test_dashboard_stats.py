"""Tests for dashboard statistics aggregation."""
import unittest

from src.utils.dashboard_stats import build_dashboard_stats, empty_dashboard_stats


class DashboardStatsTests(unittest.TestCase):
    def test_build_dashboard_stats_aggregates_objects_metadata_and_time(self):
        rows = [
            {
                "row_kind": "segment",
                "original_video": "s3://bucket/a.mp4",
                "source": "s3://bucket/a_seg_001.mp4",
                "filename": "a.mp4",
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
                "row_kind": "segment",
                "original_video": "s3://bucket/a.mp4",
                "source": "s3://bucket/a_seg_001_dup.mp4",
                "filename": "a.mp4",
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
                "row_kind": "segment",
                "original_video": "s3://bucket/a.mp4",
                "source": "s3://bucket/a_seg_002.mp4",
                "filename": "a.mp4",
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
            {
                "row_kind": "video_summary",
                "original_video": "s3://bucket/a.mp4",
                "source": "summary://s3://bucket/a.mp4",
                "segment_number": 0,
            },
        ]

        stats = build_dashboard_stats(rows)
        self.assertEqual(stats["overview"]["segment_rows"], 3)
        self.assertEqual(stats["overview"]["unique_videos"], 1)
        self.assertEqual(stats["overview"]["duplicate_segment_slots"], 1)
        self.assertEqual(stats["overview"]["duplicate_segment_rows"], 1)
        self.assertEqual(stats["overview"]["video_summary_rows"], 1)

        labels = {item["label"]: item["segment_count"] for item in stats["objects"]}
        self.assertEqual(labels["person"], 2)
        self.assertEqual(labels["forklift"], 1)

        camera = stats["metadata"]["camera_id"]
        self.assertTrue(any(item["label"] == "cam-01" and item["count"] == 2 for item in camera))
        self.assertTrue(any(item["label"] == "(empty)" for item in stats["metadata"]["location"]))

        self.assertEqual(len(stats["uploads_by_day"]), 1)
        self.assertEqual(stats["uploads_by_day"][0]["segment_rows"], 3)
        self.assertEqual(stats["recent_videos"][0]["duplicate_rows"], 1)

    def test_empty_dashboard_stats_zeros(self):
        stats = empty_dashboard_stats()
        self.assertEqual(stats["overview"]["total_rows"], 0)
        self.assertEqual(stats["objects"], [])
        self.assertEqual(stats["recent_videos"], [])


if __name__ == "__main__":
    unittest.main()
