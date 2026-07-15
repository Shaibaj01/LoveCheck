"""Tests for YOLO object-count estimation."""
import unittest

from common.object_counts import estimate_unique_object_counts


class ObjectCountEstimateTests(unittest.TestCase):
    def test_max_per_frame_from_detections(self):
        frames = [
            {
                "frame_index": 0,
                "detections": [
                    {"label": "person"},
                    {"label": "person"},
                    {"label": "car"},
                ],
            },
            {
                "frame_index": 1,
                "detections": [
                    {"label": "person"},
                    {"label": "person"},
                    {"label": "person"},
                    {"label": "car"},
                    {"label": "car"},
                ],
            },
        ]
        counts = estimate_unique_object_counts(
            frames,
            raw_counts={"person": 500, "car": 300},
            frame_count=2,
        )
        self.assertEqual(counts["person"], 3)
        self.assertEqual(counts["car"], 2)

    def test_fallback_divides_by_frame_count(self):
        counts = estimate_unique_object_counts(
            None,
            raw_counts={"person": 1786, "car": 78},
            frame_count=300,
        )
        self.assertEqual(counts["person"], 6)
        self.assertEqual(counts["car"], 1)


if __name__ == "__main__":
    unittest.main()
