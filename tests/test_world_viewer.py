import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from agent_world.leaderboard import make_server
from agent_world.maps import STANDARD_MAP_16, TERRAIN_GLYPHS
from agent_world.models import WorldConfig
from agent_world.rules import RECIPES, TERRAIN_RULES
from agent_world.world_viewer import STATIC, WorldViewer, SnapshotUnavailable


class WorldViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.viewer = WorldViewer(self.root)

    def fixture(self, run_id="test", state="running"):
        output = self.root / "runs/managed" / run_id / "seed-11"
        output.mkdir(parents=True)
        snapshot = self.viewer.snapshot()["snapshot"]
        snapshot["agents"][next(iter(snapshot["agents"]))]["memory"] = ["private prompt"]
        path = output / "run-snapshot.json"
        path.write_text(json.dumps(snapshot))
        manifest = output / "run-manifest.json"
        manifest.write_text(json.dumps({"status": state}))
        job_dir = self.root / "runs/jobs" / run_id
        job_dir.mkdir(parents=True)
        job = {"run_id": run_id, "config": {"model": {"id": "Test model"}},
               "cells": [{"id": "seed-11", "seed": 11, "snapshot": str(path),
                          "run_manifest": str(manifest), "target_ticks": 120}]}
        job_path = job_dir / "job.json"
        job_path.write_text(json.dumps(job))
        return path, job_path, job

    def server(self):
        server = make_server(self.root, port=0)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return "http://127.0.0.1:" + str(server.server_port)

    def test_discovery_includes_recipe_and_honors_hidden_studies(self):
        from unittest.mock import patch
        _, path, job = self.fixture()
        job["config"]["protocol"] = "participant-v8-revised"
        path.write_text(json.dumps(job))
        self.assertEqual(self.viewer.worlds()["worlds"][0]["recipe"], "participant-v8-revised")
        with patch("agent_world.world_viewer.STATIC", self.root):
            (self.root / "leaderboard-activity-archive.json").write_text(json.dumps({"test": {"hidden": True}}))
            self.assertEqual(self.viewer.worlds()["worlds"], [])
            self.assertEqual(self.viewer.snapshot("test")["world"]["run_id"], "test")


    def test_archived_world_uses_catalog_evidence_and_checks_boundaries(self):
        import sqlite3
        path, _, _ = self.fixture()
        report = path.with_name("run-report.json").relative_to(self.root).as_posix()
        (self.root / "data").mkdir()
        with sqlite3.connect(self.root / "data/model-benchmarks.sqlite") as conn:
            conn.executescript("""
                CREATE TABLE runs (run_id TEXT, source_report TEXT, seed INTEGER, target_ticks INTEGER, completed INTEGER);
                CREATE TABLE models (model_key TEXT, label TEXT);
                CREATE TABLE run_cohorts (run_id TEXT, model TEXT);
                INSERT INTO models VALUES ('model', 'Historical model');
                INSERT INTO run_cohorts VALUES ('original', 'model');
            """)
            conn.execute("INSERT INTO runs VALUES (?, ?, 11, 120, 1)", ("original", report))
        ref = self.viewer.evidence_reference(report, 11)
        result = self.viewer.snapshot(ref["run_id"], ref["cell_id"])
        self.assertEqual(result["world"]["title"], "Historical model")
        self.assertFalse(result["world"]["demo"])
        self.assertEqual(result["snapshot"]["tick"], 48)
        self.assertNotIn("memory", next(iter(result["snapshot"]["agents"].values())))
        with self.assertRaises(FileNotFoundError):
            self.viewer.snapshot(ref["run_id"], "seed-41")
        with self.assertRaises(FileNotFoundError):
            self.viewer.snapshot("archive-unknown")
        with self.assertRaises(FileNotFoundError):
            self.viewer.evidence_reference("../outside/run-report.json", 11)
        path.unlink()
        with self.assertRaises(SnapshotUnavailable):
            self.viewer.snapshot(ref["run_id"], ref["cell_id"])

    def test_demo_is_native_standard_world_with_valid_settlement(self):
        result = self.viewer.snapshot()
        self.assertTrue(result["world"]["demo"])
        s = result["snapshot"]
        self.assertEqual(len(s["agents"]), 10)
        self.assertGreater(s["tick"], 0)
        self.assertLess(s["tick"], result["world"]["target_ticks"])
        config = WorldConfig(**s["config"])
        self.assertEqual([[t["terrain"] for t in row] for row in s["tiles"]],
                         [[TERRAIN_GLYPHS[t] for t in row] for row in STANDARD_MAP_16])
        for agent in s["agents"].values():
            x, y = agent["position"].values()
            self.assertTrue(TERRAIN_RULES[s["tiles"][y][x]["terrain"]].passable)
        for sid, structure in s["structures"].items():
            x, y = structure["position"].values()
            tile = s["tiles"][y][x]
            self.assertIn(sid, tile["structures"])
            self.assertIn(structure["type"], RECIPES)
            self.assertIn(structure["owner_id"], s["agents"])
            recipe = RECIPES[structure["type"]]
            self.assertTrue(not recipe.required_terrain or tile["terrain"] in recipe.required_terrain)
            if structure["type"] == "farm_plot":
                self.assertLessEqual(tile["resources"]["food"], config.farm_food_capacity)
            self.assertLessEqual(structure["stored_weight"], structure["capacity"])
        self.assertTrue(any(s["status"] == "under_construction" for s in s["structures"].values()))

    def test_checked_in_demo_matches_reproducible_generator(self):
        path = Path(__file__).resolve().parents[1] / "scripts/build-world-demo.py"
        spec = importlib.util.spec_from_file_location("build_world_demo", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.build_demo(), json.loads((STATIC / "world-demo.json").read_text()))

    def test_live_snapshot_updates_without_mutating_run_or_exposing_memories(self):
        path, job_path, _ = self.fixture()
        before = {p: p.read_bytes() for p in (path, job_path)}
        result = self.viewer.snapshot("test", "seed-11")
        self.assertEqual(result["snapshot"]["tick"], 48)
        self.assertFalse(result["world"]["demo"])
        self.assertNotIn("memory", next(iter(result["snapshot"]["agents"].values())))
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        snapshot = json.loads(path.read_text())
        snapshot["tick"] = 49
        path.write_text(json.dumps(snapshot))
        self.assertEqual(self.viewer.snapshot("test", "seed-11")["snapshot"]["tick"], 49)

    def test_missing_and_corrupt_snapshots_do_not_turn_into_demo(self):
        path, _, _ = self.fixture()
        path.write_text("{")
        with self.assertRaises(SnapshotUnavailable):
            self.viewer.snapshot("test", "seed-11")
        with self.assertRaises(FileNotFoundError):
            self.viewer.snapshot("test", "seed-41")
        with self.assertRaises(FileNotFoundError):
            self.viewer.snapshot("missing")

    def test_status_marks_stale_and_preserves_terminal_states(self):
        _, job_path, _ = self.fixture()
        self.assertEqual(self.viewer.snapshot("test")["world"]["state"], "status_stale")
        job_path.with_name("controller-heartbeat.json").write_text(json.dumps({
            "checked_at_utc": "2000-01-01T00:00:00Z",
            "cells": [{"id": "seed-11", "state": "running"}]}))
        manifest = self.root / "runs/managed/test/seed-11/run-manifest.json"
        manifest.write_text('{"status":"completed"}')
        self.assertEqual(self.viewer.snapshot("test")["world"]["state"], "completed")

    def test_discovery_ignores_unavailable_worlds_and_rejects_path_escape(self):
        path, job_path, job = self.fixture()
        self.assertEqual(len(self.viewer.worlds()["worlds"]), 1)
        job["cells"][0]["snapshot"] = str(self.root.parent / "private.json")
        job_path.write_text(json.dumps(job))
        self.assertEqual(self.viewer.worlds()["worlds"], [])
        with self.assertRaises(FileNotFoundError):
            self.viewer.snapshot("test")
        with self.assertRaises(FileNotFoundError):
            self.viewer.snapshot("../test")
        # Symlinks cannot turn a managed path into an arbitrary file endpoint.
        path.unlink()
        path.symlink_to(self.root.parent / "private.json")
        job["cells"][0]["snapshot"] = str(path)
        job_path.write_text(json.dumps(job))
        with self.assertRaises(FileNotFoundError):
            self.viewer.snapshot("test")

    def test_http_navigation_api_failures_and_read_only_contract(self):
        path, _, _ = self.fixture()
        base = self.server()
        for route in ["/", "/laboratory", "/leaderboards", "/world", "/world/",
                      "/world-renderer.js", "/world-viewer.css", "/world-viewer.js", "/world-preview.js"]:
            with urlopen(base + route) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        with urlopen(base + "/api/world?run=test&cell=seed-11") as response:
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(json.load(response)["snapshot"]["tick"], 48)
        for route in ["/api/world?run=missing", "/api/world?run=../test",
                      "/api/world?run=test&cell=missing", "/world-demo.json"]:
            with self.assertRaises(HTTPError) as exc:
                urlopen(base + route)
            self.assertEqual(exc.exception.code, 404)
        for route in ["/api/world", "/api/worlds"]:
            with self.assertRaises(HTTPError) as exc:
                urlopen(Request(base + route, data=b"{}", method="POST"))
            self.assertEqual(exc.exception.code, 404)
        path.write_text("{")
        with self.assertRaises(HTTPError) as exc:
            urlopen(base + "/api/world?run=test")
        self.assertEqual(exc.exception.code, 503)


if __name__ == "__main__":
    unittest.main()
