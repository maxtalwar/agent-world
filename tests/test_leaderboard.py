import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from agent_world.leaderboard import LeaderboardStore, make_server, within


class LeaderboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = LeaderboardStore(self.root)

    def fixture(self, *, complete=True, digest="abc", recipe="participant-test"):
        output = self.root / "runs/managed/test/seed-11"
        output.mkdir(parents=True)
        report = {
            "run": {"completed": complete},
            "benchmarks": {"protocol": {"id": recipe, "recipe_fingerprint_sha256": digest}},
        }
        (output / "run-report.json").write_text(json.dumps(report))
        (output / "run-manifest.json").write_text(json.dumps({"status": "completed", "final_tick": 60}))
        job_dir = self.root / "runs/jobs/test"
        job_dir.mkdir(parents=True)
        job = {
            "run_id": "test", "kind": "benchmark", "recipe": "participant-test",
            "protocol": "participant-test", "recipe_fingerprint_sha256": "abc",
            "config": {"model": {"id": "gpt-test"}}, "launch_commit": "abc123",
            "cells": [{"id": "seed-11", "seed": 11, "output_dir": str(output),
                       "run_manifest": str(output / "run-manifest.json"), "target_ticks": 60}],
        }
        path = job_dir / "job.json"
        path.write_text(json.dumps(job))
        return job, path

    def test_canonical_rankings_match_database_and_variant_is_labeled(self):
        root = Path(__file__).resolve().parents[1]
        boards = LeaderboardStore(root).canonical_boards()
        board = next(b for b in boards if b["recipe"] == "participant-v6")
        self.assertEqual(len(board["rows"]), 19)
        self.assertEqual(board["rows"][0]["model"], "Fable 5")
        self.assertEqual(board["rows"][0]["scores"]["sustained_competence"], 86.21)
        variant = next(r for r in board["rows"] if "Luna Max" in r["model"])
        self.assertEqual(variant["status"], "Controlled variant")
        self.assertEqual(variant["seeds"], [11, 41])
        spark = next(r for r in board["rows"] if "Spark" in r["model"])
        self.assertIsNone(spark["cost"])

    def test_partial_reports_never_reach_scorer(self):
        job, path = self.fixture(complete=False)
        with patch.object(self.store, "aggregate") as scorer:
            run, rows, result = self.store.managed_run(job, path)
        scorer.assert_not_called()
        self.assertFalse(rows)
        self.assertIsNone(result)

    def test_mismatched_recipe_and_digest_never_reach_scorer(self):
        for key, value in [("digest", "different"), ("recipe", "another-recipe")]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                self.store = LeaderboardStore(self.root)
                job, path = self.fixture(**{key: value})
                with patch.object(self.store, "aggregate") as scorer:
                    run, rows, result = self.store.managed_run(job, path)
                scorer.assert_not_called()
                self.assertFalse(rows)
                self.assertTrue(run["warnings"])

    def test_provisional_and_duplicate_replications_are_not_ranked(self):
        job, path = self.fixture()
        for status in ["provisional", "incomplete_replication"]:
            with self.subTest(status=status), patch.object(self.store, "aggregate", return_value={
                "results": [{"certified": False, "status": status}], "rejected": []}):
                run, rows, result = self.store.managed_run(job, path)
                self.assertFalse(rows)
                self.assertFalse(run["ranked"])

    def test_stale_running_heartbeat_is_not_presented_as_live(self):
        job, path = self.fixture(complete=False)
        manifest = Path(job["cells"][0]["run_manifest"])
        manifest.write_text('{"status":"running"}')
        path.with_name("controller-heartbeat.json").write_text(json.dumps({
            "checked_at_utc": "2000-01-01T00:00:00+00:00",
            "cells": [{"id": "seed-11", "state": "running", "tick": 12}],
        }))
        run, _, _ = self.store.managed_run(job, path)
        self.assertEqual(run["cells"][0]["state"], "status_stale")
        self.assertEqual(run["cells"][0]["tick"], 12)

    def test_terminal_manifest_wins_over_stale_heartbeat(self):
        job, path = self.fixture(complete=False)
        path.with_name("controller-heartbeat.json").write_text(json.dumps({
            "checked_at_utc": "2000-01-01T00:00:00+00:00",
            "cells": [{"id": "seed-11", "state": "running", "tick": 12}],
        }))
        run, _, _ = self.store.managed_run(job, path)
        self.assertEqual(run["cells"][0]["state"], "completed")
        self.assertEqual(run["cells"][0]["tick"], 60)

    def test_recipe_digests_remain_separate_boards(self):
        job, path = self.fixture(complete=False)
        job2 = {**job, "run_id": "test-other", "recipe_fingerprint_sha256": "different"}
        other = self.root / "runs/jobs/test-other"
        other.mkdir()
        (other / "job.json").write_text(json.dumps(job2))
        with patch.object(self.store, "canonical_boards", return_value=[]):
            payload = self.store.get()
        self.assertEqual({b["id"] for b in payload["boards"]},
                         {"participant-test@abc", "participant-test@different"})

    def test_cache_refreshes_but_does_not_rebuild_per_request(self):
        with patch.object(self.store, "build", side_effect=[{"v": 1}, {"v": 2}]) as build:
            self.assertEqual(self.store.get(), {"v": 1})
            self.assertEqual(self.store.get(), {"v": 1})
            self.store.next_refresh = 0
            self.assertEqual(self.store.get(), {"v": 2})
            self.assertEqual(build.call_count, 2)

    def test_paths_cannot_escape_repository(self):
        with self.assertRaises(ValueError):
            within(self.root, "../private-file")
        link = self.root / "escape"
        link.symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            within(self.root, "escape/private-file")

    def test_http_only_exposes_app_assets_and_read_only_api(self):
        server = make_server(self.root, port=0)
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        base = "http://127.0.0.1:" + str(server.server_port)
        for route in ["/", "/leaderboard.js", "/leaderboard.css", "/inter-latin.woff2", "/healthz"]:
            with urlopen(base + route) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        for route in ["/.env", "/runs/jobs/test/job.json", "/../pyproject.toml"]:
            with self.assertRaises(HTTPError) as exc:
                urlopen(base + route)
            self.assertEqual(exc.exception.code, 404)
        with self.assertRaises(HTTPError) as exc:
            urlopen(base + "/api/leaderboards", data=b"{}")
        self.assertEqual(exc.exception.code, 501)


if __name__ == "__main__":
    unittest.main()
