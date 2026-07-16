from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from agent_world.run_catalog import refresh_catalog_for_output, write_run_catalog


class RunCatalogTests(unittest.TestCase):
    def test_catalog_indexes_report_and_matching_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runs"
            run_dir = root / "experiments" / "sample"
            run_dir.mkdir(parents=True)
            (run_dir / "run-report.json").write_text(
                json.dumps(
                    {
                        "run": {"completed": True, "final_tick": 3, "target_ticks": 3},
                        "config": {"seed": 7},
                        "reliability": {
                            "quality_status": "clean",
                            "invalid_actions_per_proposed_action_pct": 4.2,
                        },
                        "usage": {"calls": 6, "total_cost_usd": 0},
                        "turn_dynamics": {"mode": "shuffled-sequential-v1"},
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "run-manifest.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "observation_mode": "compact-v2",
                        "population": {
                            "groups": [{"type": "codex", "model": "gpt-5.6-luna"}]
                        },
                    }
                ),
                encoding="utf-8",
            )

            catalog = write_run_catalog(root)

            self.assertEqual(catalog["run_count"], 1)
            self.assertEqual(catalog["root"], str(root.resolve()))
            record = catalog["runs"][0]
            self.assertEqual(record["turn_mode"], "shuffled-sequential-v1")
            self.assertEqual(record["models"], ["gpt-5.6-luna"])
            self.assertTrue((root / "catalog.json").exists())
            self.assertIn("sample", (root / "catalog.md").read_text(encoding="utf-8"))

    def test_refresh_only_runs_for_outputs_below_runs_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outside = root / "other" / "run.jsonl"
            outside.parent.mkdir()
            self.assertIsNone(refresh_catalog_for_output(outside))


if __name__ == "__main__":
    unittest.main()
