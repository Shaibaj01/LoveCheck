"""Tests for stream/chunk index helpers."""
import unittest

from src.utils.stream_index import build_stream_meta_by_video


class StreamIndexTests(unittest.TestCase):
    def test_build_stream_meta_by_video(self):
        rows_by_video = {
            "s3://bucket/a.mp4": [
                {"extra_metadata": '{"stream_id":"s1","chunk_index":0}'},
            ],
            "s3://bucket/b.mp4": [
                {"extra_metadata": '{"stream_id":"s1","chunk_index":66}'},
            ],
            "s3://bucket/upload.mp4": [
                {"extra_metadata": "{}"},
            ],
        }
        meta = build_stream_meta_by_video(rows_by_video)
        self.assertEqual(meta["s3://bucket/a.mp4"]["chunk_index"], 0)
        self.assertEqual(meta["s3://bucket/a.mp4"]["stream_chunk_total"], 67)
        self.assertEqual(meta["s3://bucket/b.mp4"]["stream_chunk_total"], 67)
        self.assertIsNone(meta["s3://bucket/a.mp4"]["prev_chunk_index"])
        self.assertEqual(meta["s3://bucket/a.mp4"]["next_chunk_index"], 66)
        self.assertEqual(meta["s3://bucket/b.mp4"]["prev_chunk_index"], 0)
        self.assertIsNone(meta["s3://bucket/b.mp4"]["next_chunk_index"])
        self.assertNotIn("s3://bucket/upload.mp4", meta)

    def test_neighbors_skip_missing_indexes(self):
        rows_by_video = {
            "s3://bucket/c0.mp4": [{"extra_metadata": '{"stream_id":"s1","chunk_index":0}'}],
            "s3://bucket/c2.mp4": [{"extra_metadata": '{"stream_id":"s1","chunk_index":2}'}],
            "s3://bucket/c5.mp4": [{"extra_metadata": '{"stream_id":"s1","chunk_index":5}'}],
        }
        meta = build_stream_meta_by_video(rows_by_video)
        self.assertEqual(meta["s3://bucket/c0.mp4"]["next_chunk_index"], 2)
        self.assertEqual(meta["s3://bucket/c2.mp4"]["prev_chunk_index"], 0)
        self.assertEqual(meta["s3://bucket/c2.mp4"]["next_chunk_index"], 5)
        self.assertEqual(meta["s3://bucket/c5.mp4"]["prev_chunk_index"], 2)


if __name__ == "__main__":
    unittest.main()
