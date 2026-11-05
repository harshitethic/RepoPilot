import unittest

from services.rag.chunk import chunk_source


class RagChunkTests(unittest.TestCase):
    def test_line_ranges_and_overlap(self):
        text = "\n".join(f"line {i}" for i in range(1, 11))
        chunks = list(chunk_source("src/app.py", text, lines_per_chunk=4, overlap_lines=1))
        self.assertEqual([(c.start_line, c.end_line) for c in chunks], [(1, 4), (4, 7), (7, 10)])
        self.assertEqual(chunks[0].citation, "src/app.py:L1-L4")
        self.assertIn("line 4", chunks[1].text)

    def test_empty_file_and_long_line(self):
        self.assertEqual(list(chunk_source("empty.py", "")), [])
        chunk = list(chunk_source("one.py", "x" * 500, max_line_chars=20))[0]
        self.assertEqual(len(chunk.text), 20)

    def test_invalid_geometry_is_rejected(self):
        for pair in [(0, 0), (1, 1), (2, -1)]:
            with self.subTest(pair=pair), self.assertRaises(ValueError):
                list(chunk_source("a.py", "data", lines_per_chunk=pair[0], overlap_lines=pair[1]))


if __name__ == "__main__":
    unittest.main()
