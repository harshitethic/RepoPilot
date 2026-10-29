import unittest
from services.github import validate_github_url

class Regression(unittest.TestCase):
    def test_ambiguous_slashes(self):
        for url in ('https://github.com/owner/repo/', 'https://github.com//owner/repo', 'https://github.com/owner//repo'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_github_url(url)
        self.assertEqual(validate_github_url('https://github.com/owner/repo'), 'https://github.com/owner/repo.git')
