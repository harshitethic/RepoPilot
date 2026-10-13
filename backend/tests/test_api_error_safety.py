"""Ensure repository and LLM errors never leak internal tracebacks."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from app import Analyze, Ask, Search, app, health, do_analyze, do_search, do_ask, arch
from fastapi.testclient import TestClient


class SafeApiErrorTests(unittest.TestCase):
    def test_health_probe_failure_reports_degraded_ollama_without_trace(self):
        with patch("app.available", side_effect=RuntimeError("PRIVATE_SYSTEM_PATH")), patch("app.logger"):
            self.assertEqual(health(), {"ok": True, "ollama": False})
            response = TestClient(app).get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "ollama": False})
        self.assertNotIn("PRIVATE_SYSTEM_PATH", response.text)

    def test_health_probe_healthy_returns_true(self):
        with patch("app.available", return_value=True):
            self.assertEqual(health(), {"ok": True, "ollama": True})

    def test_import_error_does_not_reflect_private_paths(self):
        with patch("app.clone_repo", side_effect=RuntimeError(
            "PRIVATE_TOKEN at /home/admin/.aws/credentials"
        )), patch("app.logger"):
            with self.assertRaises(HTTPException) as caught:
                do_analyze(Analyze(url="https://github.com/example/project"))
        self.assertEqual(caught.exception.status_code, 500)
        self.assertNotIn("PRIVATE_TOKEN", caught.exception.detail)
        self.assertNotIn("/home/admin", caught.exception.detail)

    def test_capacity_error_stays_a_client_error(self):
        with patch("app.clone_repo", side_effect=ValueError("PRIVATE_DB_URL capacity reached")):
            with self.assertRaises(HTTPException) as caught:
                do_analyze(Analyze(url="https://github.com/example/project"))
        self.assertEqual(caught.exception.status_code, 400)
        self.assertNotIn("PRIVATE_DB_URL", caught.exception.detail)

    def test_search_invalid_and_missing_import_statuses(self):
        with patch("app.safe_repo_path", side_effect=ValueError("SECRET_INTERNAL")):
            with self.assertRaises(HTTPException) as invalid:
                do_search(Search(repo_id="aaaaaaaaaaaa", query="hello"))
        self.assertEqual(invalid.exception.status_code, 400)
        self.assertNotIn("SECRET_INTERNAL", invalid.exception.detail)

        with patch("app.safe_repo_path", side_effect=FileNotFoundError("private /tmp/repo")):
            with self.assertRaises(HTTPException) as absent:
                do_search(Search(repo_id="aaaaaaaaaaaa", query="hello"))
        self.assertEqual(absent.exception.status_code, 404)
        self.assertNotIn("/tmp/repo", absent.exception.detail)

    def test_search_server_failure_is_generic(self):
        with patch("app.safe_repo_path", side_effect=RuntimeError("API_KEY=private")), patch("app.logger"):
            with self.assertRaises(HTTPException) as caught:
                do_search(Search(repo_id="aaaaaaaaaaaa", query="hello"))
        self.assertEqual(caught.exception.status_code, 500)
        self.assertNotIn("private", caught.exception.detail)

    def test_ask_and_architecture_do_not_expose_ollama_debug_logs(self):
        x = Ask(repo_id="aaaaaaaaaaaa", question="How does it work?")
        with patch("app.ai", side_effect=RuntimeError("SECRET_TOKEN from Ollama")), patch("app.logger"):
            for route in (do_ask, arch):
                with self.subTest(route=route.__name__), self.assertRaises(HTTPException) as err:
                    route(x)
                self.assertEqual(err.exception.status_code, 503)
                self.assertNotIn("SECRET_TOKEN", err.exception.detail)


if __name__ == "__main__":
    unittest.main()
