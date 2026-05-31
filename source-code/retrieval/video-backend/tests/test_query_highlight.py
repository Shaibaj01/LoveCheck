import unittest

from src.utils.query_highlight import extract_highlight_terms, term_in_text


class QueryHighlightTests(unittest.TestCase):
    def test_extracts_hyphenated_brand_phrase(self):
        query = "a gorilla is standing next to a T-Mobile store"
        terms = extract_highlight_terms(query)
        self.assertIn("gorilla", terms)
        self.assertIn("t-mobile store", terms)
        self.assertIn("t-mobile", terms)

    def test_matches_hyphenated_brand_in_caption(self):
        text = "The background includes storefronts like T-Mobile and American Eagle."
        self.assertTrue(term_in_text("t-mobile", text))
        self.assertTrue(term_in_text("gorilla", "a person in a gorilla costume"))

    def test_does_not_match_stopword_substrings(self):
        text = "displaying photos in a cartoon scene"
        self.assertFalse(term_in_text("is", text))
        self.assertFalse(term_in_text("to", text))


if __name__ == "__main__":
    unittest.main()
