"""Tests for plain-text reasoning prompt builder."""
import unittest

from common.reasoning_prompt import (
    REASONING_CONTENT_MAX_CHARS,
    build_reasoning_prompt,
    normalize_reasoning_content,
)


class ReasoningPromptTests(unittest.TestCase):
    def test_build_reasoning_prompt_includes_objects(self):
        prompt = build_reasoning_prompt("Describe traffic.", "car,person,car")
        self.assertIn("Describe traffic.", prompt)
        self.assertIn("car, person", prompt)
        self.assertIn("plain prose", prompt.lower())
        self.assertIn("searchable atoms", prompt.lower())
        self.assertIn("brand", prompt.lower())
        self.assertIn("next move", prompt.lower())
        self.assertIn(str(REASONING_CONTENT_MAX_CHARS), prompt)

    def test_normalize_strips_json_fence(self):
        raw = '```json\n{"scene_summary": "Busy intersection with taxis."}\n```'
        out = normalize_reasoning_content(raw)
        self.assertIn("intersection", out.lower())
        self.assertNotIn("{", out)

    def test_normalize_truncates_long_text(self):
        raw = "word " * 200
        out = normalize_reasoning_content(raw)
        self.assertLessEqual(len(out), REASONING_CONTENT_MAX_CHARS + 3)


if __name__ == "__main__":
    unittest.main()
