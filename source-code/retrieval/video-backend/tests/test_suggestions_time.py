"""Tests for suggestions timestamp normalization."""
import unittest
from datetime import datetime, timezone

from src.services.suggestions_service import normalize_generated_at


class SuggestionsTimeTests(unittest.TestCase):
    def test_naive_datetime_treated_as_utc(self):
        naive = datetime(2026, 6, 8, 14, 30, 0)
        self.assertEqual(normalize_generated_at(naive), "2026-06-08T14:30:00Z")

    def test_aware_datetime_normalized_to_z(self):
        aware = datetime(2026, 6, 8, 17, 30, 0, tzinfo=timezone.utc)
        self.assertEqual(normalize_generated_at(aware), "2026-06-08T17:30:00Z")

    def test_iso_without_zone_gets_z_suffix(self):
        self.assertEqual(normalize_generated_at("2026-06-08T14:30:00"), "2026-06-08T14:30:00Z")

    def test_iso_with_z_unchanged(self):
        self.assertEqual(normalize_generated_at("2026-06-08T14:30:00Z"), "2026-06-08T14:30:00Z")


if __name__ == "__main__":
    unittest.main()
