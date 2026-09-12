import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor
from agent_world.leaderboard_model_cache import saved_catalog, REFRESH_SECONDS


class ModelCacheTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "catalog.json"
        self.old = {"key": "claude:old", "brain": "claude"}
        self.new = {"key": "claude:new", "brain": "claude"}

    def test_daily_cache_survives_new_callers_and_removes_retired_models_on_success(self):
        discover = Mock(return_value=([self.old], []))
        with patch("agent_world.leaderboard_model_cache.time.time", return_value=100):
            self.assertEqual(saved_catalog(self.path, discover), ([self.old], []))
        new_process = Mock(return_value=([self.new], []))
        with patch("agent_world.leaderboard_model_cache.time.time", return_value=200):
            self.assertEqual(saved_catalog(self.path, new_process), ([self.old], []))
        new_process.assert_not_called()
        with patch("agent_world.leaderboard_model_cache.time.time", return_value=101 + REFRESH_SECONDS):
            self.assertEqual(saved_catalog(self.path, new_process), ([self.new], []))
        new_process.assert_called_once()

    def test_partial_failure_preserves_saved_models_and_does_not_retry(self):
        self.path.write_text(json.dumps({"models": [self.old]}))
        discover = Mock(return_value=([self.new], ["Claude rate limited"]))
        models, warnings = saved_catalog(self.path, discover)
        self.assertEqual(models, [self.old, self.new])
        self.assertEqual(warnings, ["Claude rate limited"])
        saved_catalog(self.path, discover)
        discover.assert_called_once()

    def test_exception_preserves_catalog_and_backs_off(self):
        self.path.write_text(json.dumps({"models": [self.old]}))
        discover = Mock(side_effect=RuntimeError("offline"))
        self.assertEqual(saved_catalog(self.path, discover)[0], [self.old])
        saved_catalog(self.path, discover)
        discover.assert_called_once()

    def test_concurrent_requests_discover_once(self):
        discover = Mock(return_value=([self.old], []))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: saved_catalog(self.path, discover), range(4)))
        self.assertTrue(all(r == ([self.old], []) for r in results))
        discover.assert_called_once()
