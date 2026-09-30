"""Tests for explore-card video deletion planning."""
import unittest

from src.utils.video_delete import (
    allowed_delete_buckets,
    detection_family_prefix,
    plan_object_deletes,
    segment_family_prefix,
    user_can_delete_video,
)


class VideoDeletePlanTests(unittest.TestCase):
    def test_owner_in_allowed_users_can_delete_public_video(self):
        rows = [{"allowed_users": ["vss-user"], "is_public": True}]
        self.assertTrue(
            user_can_delete_video(
                "vss-user",
                "s3://vss-chunks/vss-user/20260929_094846_c31983cc.mp4",
                rows,
            )
        )

    def test_other_user_cannot_delete_public_video(self):
        rows = [{"allowed_users": ["vss-user"], "is_public": True}]
        self.assertFalse(
            user_can_delete_video(
                "someone-else",
                "s3://vss-chunks/vss-user/20260929_094846_c31983cc.mp4",
                rows,
            )
        )

    def test_stream_with_no_recorded_owner_can_be_deleted(self):
        rows = [{"allowed_users": [], "is_public": True}]
        self.assertTrue(
            user_can_delete_video(
                "vss-user",
                "s3://vss-chunks/captures/chunk_0001.mp4",
                rows,
            )
        )

    def test_key_prefix_allows_delete_when_allowed_users_missing(self):
        rows = [{"allowed_users": []}]
        self.assertTrue(
            user_can_delete_video(
                "vss-user",
                "s3://vss-chunks/vss-user/clip.mp4",
                rows,
            )
        )

    def test_plan_includes_parent_segments_and_family_prefixes(self):
        parent = "s3://vss-chunks/vss-user/clip.mp4"
        segment = (
            "s3://vss-chunks-segments/segments/clip_segment_001_of_006.mp4"
        )
        sidecar = "s3://vss-chunks-segments/detections/clip_segment_001_of_006.json.gz"
        keys, prefixes, skipped = plan_object_deletes(
            parent,
            [{"source": segment, "detection_sidecar_uri": sidecar}],
            allowed_delete_buckets("vss-chunks", "vss-chunks-segments"),
        )
        self.assertEqual(skipped, [])
        self.assertIn("vss-user/clip.mp4", keys["vss-chunks"])
        self.assertIn("segments/clip_segment_001_of_006.mp4", keys["vss-chunks-segments"])
        self.assertIn("detections/clip_segment_001_of_006.json.gz", keys["vss-chunks-segments"])
        self.assertIn("segments/clip_segment_", prefixes["vss-chunks-segments"])
        self.assertEqual(
            segment_family_prefix("segments/clip_segment_001_of_006.mp4"),
            "segments/clip_segment_",
        )
        self.assertEqual(
            detection_family_prefix("segments/clip_segment_001_of_006.mp4"),
            "detections/clip_segment_",
        )

    def test_unknown_bucket_is_skipped(self):
        keys, prefixes, skipped = plan_object_deletes(
            "s3://other-bucket/vss-user/clip.mp4",
            [],
            allowed_delete_buckets("vss-chunks", "vss-chunks-segments"),
        )
        self.assertEqual(keys, {})
        self.assertEqual(prefixes, {})
        self.assertEqual(skipped, ["s3://other-bucket/vss-user/clip.mp4"])


if __name__ == "__main__":
    unittest.main()
