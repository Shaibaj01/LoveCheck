"""Lightweight tests for structured VLM output parsing."""
import json
import unittest

from .structured_output import (
    apply_structured_enrichment,
    build_dense_caption,
    extract_json_object,
    merge_perception_into_structured,
    process_vlm_response,
    _infer_objects_from_summary,
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

    def test_recovers_scene_summary_when_json_missing_comma(self):
        raw = '''```json
{
  "scene_summary": "A man in a black suit speaks in Times Square."
  "objects": [{"type": "camera", "count": 1, "notes": ""}],
  "actions": [],
  "events": [],
  "hazards": [],
  "attributes": {}
}
```'''
        result = process_vlm_response(raw)
        self.assertIn("black suit", result["dense_caption"].lower())
        self.assertNotIn("```json", result["dense_caption"])
        self.assertIn("black suit", result["vlm_structured"])

    def test_enrich_sparse_structured_from_summary(self):
        payload = {
            "scene_summary": (
                "A man in a black suit speaks animatedly while being filmed by another man "
                "with a camera in a bustling plaza."
            ),
            "objects": [],
            "actions": [],
            "events": [],
            "hazards": [],
            "attributes": {},
        }
        enriched = apply_structured_enrichment(payload)
        self.assertTrue(enriched["objects"] or enriched["actions"])
        self.assertTrue(enriched["actions"])
        self.assertNotEqual(
            build_dense_caption(enriched),
            enriched["scene_summary"],
        )

    def test_merge_perception_fills_objects(self):
        data = {"scene_summary": "Warehouse activity.", "objects": [], "actions": [], "events": [], "hazards": [], "attributes": {}}
        perception = {
            "perception_ok": True,
            "object_counts": '{"person": 2, "forklift": 1}',
            "perception_summary": "Detected: person x2, forklift",
        }
        merged = merge_perception_into_structured(data, perception)
        self.assertEqual(len(merged["objects"]), 2)
        self.assertTrue(merged["actions"])

    def test_infer_objects_from_summary(self):
        summary = (
            "A bustling urban square with pedestrians, digital billboards, and a statue, "
            "where a man in a suit gestures while speaking to a cameraman."
        )
        objects = _infer_objects_from_summary(summary)
        labels = {obj["type"] for obj in objects}
        self.assertIn("person", labels)
        self.assertIn("signboard", labels)
        self.assertIn("statue", labels)

    def test_recover_partial_structured_extracts_objects(self):
        raw = '''```json
{
  "scene_summary": "Two performers in costumes in a plaza."
  "objects": [
    {"type": "gorilla", "count": 1, "notes": ""},
    {"type": "minnie mouse", "count": 1, "notes": ""}
  ],
  "actions": ["posing"],
  "events": [],
  "hazards": [],
  "attributes": {}
}
```'''
        result = process_vlm_response(raw)
        parsed = json.loads(result["vlm_structured"])
        labels = {obj["type"] for obj in parsed["objects"]}
        self.assertIn("gorilla", labels)
        self.assertTrue(result["structured_parse_ok"])


if __name__ == "__main__":
    unittest.main()
