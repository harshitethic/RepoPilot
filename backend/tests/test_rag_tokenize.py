import unittest

from services.rag.tokenize import distinct_query_terms, tokenize


class RagTokenizationTests(unittest.TestCase):
    def test_snake_and_camel_case_symbols_are_searchable(self):
        tokens = tokenize("createRepository buildIndex user_ID")
        self.assertIn("createrepository", tokens)
        self.assertIn("create", tokens)
        self.assertIn("repository", tokens)
        self.assertIn("build", tokens)
        self.assertIn("index", tokens)
        self.assertIn("user_id", tokens)

    def test_unicode_casefold_supports_identifiers(self):
        self.assertIn("strasse", tokenize("Straße"))
        self.assertEqual(tokenize(""), ())

    def test_duplicates_and_query_budget(self):
        self.assertEqual(distinct_query_terms("foo foo Bar", 2), ("foo", "bar"))
        with self.assertRaises(ValueError):
            distinct_query_terms("foo", 0)


if __name__ == "__main__":
    unittest.main()
