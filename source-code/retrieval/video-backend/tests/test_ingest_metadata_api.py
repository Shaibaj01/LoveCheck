"""Tests for ingest metadata API config."""
import unittest

from src.ingest_metadata import ingest_config_for_api


class IngestMetadataApiTests(unittest.TestCase):
    def test_ingest_config_for_api_shape(self):
        payload = ingest_config_for_api()
        self.assertEqual(payload["custom_prompt_max_length"], 800)
        self.assertGreater(len(payload["capture_types"]), 0)
        self.assertGreater(len(payload["analysis_scenarios"]), 0)
        self.assertIn("camera_id", payload["labels"])
        self.assertIn("location", payload["placeholders"])
        keys = [f["key"] for f in payload["filterable_fields"]]
        self.assertEqual(keys, ["camera_id", "capture_type", "location"])


if __name__ == "__main__":
    unittest.main()
