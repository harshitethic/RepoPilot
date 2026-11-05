import tempfile
import unittest
from pathlib import Path

from services.rag.answer import answer_question


class RagAnswerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "auth.py").write_text(
            "def authorize_user(token):\n    return bool(token)\n", encoding="utf-8"
        )

    def test_no_evidence_short_circuits_without_model_call(self):
        def unavailable(_prompt):
            raise AssertionError("Should not call the model with no evidence")
        result = answer_question(self.root, "z_xyzz_abc", model_chat=unavailable)
        self.assertFalse(result["model_used"])
        self.assertEqual(result["sources"], [])

    def test_model_receives_line_citations_and_untrusted_boundary(self):
        prompts = []
        def stub(prompt):
            prompts.append(prompt)
            return "authorize_user is defined in auth.py:L1-L2"
        result = answer_question(self.root, "authorize_user", model_chat=stub)
        self.assertTrue(result["model_used"])
        self.assertEqual(result["sources"][0]["path"], "auth.py")
        self.assertIn("UNTRUSTED REPOSITORY", prompts[0])
        self.assertIn("auth.py:L1-L2", prompts[0])

    def test_empty_model_answer_is_error(self):
        with self.assertRaises(RuntimeError):
            answer_question(self.root, "authorize_user", model_chat=lambda prompt: "")


if __name__ == "__main__":
    unittest.main()
