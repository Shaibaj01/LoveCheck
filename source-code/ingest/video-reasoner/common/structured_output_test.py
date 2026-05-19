"""Lightweight tests for structured VLM output parsing."""
import json
import unittest

from .structured_output import (
    build_dense_caption,
    extract_json_object,
    process_vlm_response,
    wrap_prompt_with_structured_output,
)


class StructuredOutputTests(unittest.TestCase):
    def test_extract_json_from_fence(self):
        raw = '```json\n{"scene_summary": "Worker on ladder.", "objects": [], "actions": [], "events": [], "hazards": [], "attributes": {}}\n```'
        data = extract_json_object(raw)
        self.assertEqual(data["scene_summary"], "Worker on ladder.")

    def test_process_vlm_response_builds_dense_caption(self):
        payload = {
            "scene_summary": "Forklift moves pallet in warehouse aisle.",
            "objects": [{"type": "forklift", "count": 1, "notes": "yellow"}],
            "actions": ["driving forward"],
            "events": [],
            "hazards": ["no visible hard hat"],
            "attributes": {"setting": "warehouse"},
        }
        raw = json.dumps(payload)
        result = process_vlm_response(raw)
        self.assertTrue(result["structured_parse_ok"])
        self.assertIn("forklift", result["dense_caption"].lower())
        self.assertIn("Forklift", result["reasoning_content"])

    def test_fallback_on_invalid_json(self):
        result = process_vlm_response("This is plain prose without JSON.")
        self.assertFalse(result["structured_parse_ok"])
        self.assertEqual(result["dense_caption"], "This is plain prose without JSON.")


if __name__ == "__main__":
    unittest.main()
