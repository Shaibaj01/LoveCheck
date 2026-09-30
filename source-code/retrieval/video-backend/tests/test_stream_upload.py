"""Upload stream numbering is 1-based and stored as a 0-based chunk index."""
import unittest

from src.utils.stream_upload import stream_s3_metadata


class StreamUploadTests(unittest.TestCase):
    def test_omitted_when_no_stream(self):
        self.assertEqual(stream_s3_metadata("", None), {})

    def test_first_chunk_is_index_zero(self):
        meta = stream_s3_metadata("game-2026-03-21", 1)
        self.assertEqual(meta["stream_id"], "game-2026-03-21")
        self.assertEqual(meta["chunk_index"], "0")
        self.assertEqual(meta["ingest_kind"], "stream_chunk")

    def test_later_chunk_is_one_plus_index(self):
        meta = stream_s3_metadata("game-2026-03-21", 4)
        self.assertEqual(meta["chunk_index"], "3")
        self.assertEqual(int(meta["chunk_index"]) + 1, 4)

    def test_chunk_number_requires_stream(self):
        with self.assertRaises(ValueError):
            stream_s3_metadata("", 1)

    def test_stream_requires_chunk_number(self):
        with self.assertRaises(ValueError):
            stream_s3_metadata("game", None)

    def test_zero_is_rejected(self):
        with self.assertRaises(ValueError):
            stream_s3_metadata("game", 0)


if __name__ == "__main__":
    unittest.main()
