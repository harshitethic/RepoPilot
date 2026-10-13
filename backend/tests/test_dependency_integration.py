"""Small network-free compatibility checks for patched HTTP and form parsers."""
import unittest


class PatchedDependencyIntegrationTests(unittest.TestCase):
    def test_requests_still_encodes_query_params(self):
        import requests
        request = requests.Request(
            "GET", "https://github.com/example/repo",
            params={"q": "hello world"},
        ).prepare()
        self.assertIn("q=hello+world", request.url)

    def test_multipart_boundary_header_parsing(self):
        from python_multipart.multipart import parse_options_header
        media, parameters = parse_options_header(
            b"multipart/form-data; boundary=example123"
        )
        self.assertEqual(media, b"multipart/form-data")
        self.assertEqual(parameters[b"boundary"], b"example123")


if __name__ == "__main__":
    unittest.main()
