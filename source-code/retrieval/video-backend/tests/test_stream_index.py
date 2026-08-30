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
        self.assertNotIn("s3://bucket/upload.mp4", meta)


if __name__ == "__main__":
    unittest.main()
