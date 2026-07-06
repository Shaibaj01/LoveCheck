"""Tests for segment timeline deduplication."""
import unittest

from src.utils.segment_timeline import (
    dedupe_by_segment_number,
    dedupe_segment_dicts,
    is_chunk_fully_indexed,
)


class SegmentTimelineTests(unittest.TestCase):
    def test_dedupe_segment_dicts_keeps_one_per_number(self):
        rows = [
            {"segment_number": 1, "upload_timestamp": "2026-01-01", "dense_caption": "old", "source": "s3://a/1"},
            {"segment_number": 1, "upload_timestamp": "2026-01-02", "dense_caption": "newer", "source": "s3://a/1b"},
            {"segment_number": 2, "upload_timestamp": "2026-01-02", "dense_caption": "seg2", "source": "s3://a/2"},
            {"segment_number": 2, "upload_timestamp": "2026-01-01", "dense_caption": "seg2-old", "source": "s3://a/2old"},
        ]
        out = dedupe_segment_dicts(rows)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["source"], "s3://a/1b")
        self.assertEqual(out[1]["source"], "s3://a/2")

    def test_dedupe_by_segment_number_keeps_best_score(self):
        class Hit:
            def __init__(self, sn, score):
                self.segment_number = sn
                self.similarity_score = score

        hits = [Hit(5, 0.3), Hit(5, 0.48), Hit(3, 0.2)]
        out = dedupe_by_segment_number(
            hits,
            segment_number=lambda h: h.segment_number,
            rank_key=lambda h: h.similarity_score,
        )
        self.assertEqual(len(out), 2)
        seg5 = next(h for h in out if h.segment_number == 5)
        self.assertEqual(seg5.similarity_score, 0.48)

    def test_is_chunk_fully_indexed_complete(self):
        rows = [
            {"segment_number": i, "total_segments": 6}
            for i in range(1, 7)
        ]
        self.assertTrue(is_chunk_fully_indexed(rows))

    def test_is_chunk_fully_indexed_partial(self):
        rows = [
            {"segment_number": i, "total_segments": 6}
            for i in range(1, 5)
        ]
        self.assertFalse(is_chunk_fully_indexed(rows))

    def test_is_chunk_fully_indexed_gap(self):
        rows = [
            {"segment_number": 1, "total_segments": 3},
            {"segment_number": 2, "total_segments": 3},
            {"segment_number": 3, "total_segments": 3},
        ]
        rows_missing = [rows[0], rows[2]]
        self.assertTrue(is_chunk_fully_indexed(rows))
        self.assertFalse(is_chunk_fully_indexed(rows_missing))


if __name__ == "__main__":
    unittest.main()
