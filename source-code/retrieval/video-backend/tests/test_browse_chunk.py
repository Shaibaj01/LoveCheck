"""Tests for browse chunk helpers."""
import unittest

from src.utils.browse_chunk import (
    BROWSE_SEGMENT_FIELDS,
    fully_indexed_videos,
    prepare_browse_segments,
    row_to_browse_segment,
)


class BrowseChunkTests(unittest.TestCase):
    def test_row_to_browse_segment_field_set(self):
        row = row_to_browse_segment(
            {
                "filename": "a.mp4",
                "segment_number": 1,
                "total_segments": 1,
                "perception_ok": True,
                "cosmos_model": "cosmos",
                "tokens_used": 99,
            },
            "s3://bucket/a.mp4",
        )
        self.assertEqual(frozenset(row.keys()), BROWSE_SEGMENT_FIELDS)
        self.assertNotIn("perception_ok", row)
        self.assertNotIn("cosmos_model", row)

    def test_prepare_browse_segments_partial(self):
        rows = [{"segment_number": i, "total_segments": 3} for i in range(1, 3)]
        self.assertIsNone(prepare_browse_segments(rows, "s3://bucket/a.mp4"))

    def test_fully_indexed_videos(self):
        rows_by_video = {
            "complete": [{"segment_number": 1, "total_segments": 1}],
            "partial": [{"segment_number": 1, "total_segments": 3}],
        }
        self.assertEqual(fully_indexed_videos(rows_by_video), {"complete"})


if __name__ == "__main__":
    unittest.main()
