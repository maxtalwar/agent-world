from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_world.run_finalization import (
    _classify_v6_gifts,
    _validate_v6_rows,
    finalize_job,
    start_finalization,
)


class V6ClassificationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gift = {
            "type": "gift",
            "tick": 7,
            "actor_id": "agent-1",
            "message": "Paying for shelter access now.",
            "data": {"to": "agent-2", "items": {"coin": 3}},
        }

    def test_normalizes_schema_item_entries_to_frozen_items(self) -> None:
        output = {
            "classifications": [
                {
                    "gift_index": 0,
                    "tick": 7,
                    "giver": "agent-1",
                    "recipient": "agent-2",
                    "item_entries": [{"resource": "coin", "quantity": 3}],
                    "verdict": "payment_for_service",
                    "evidence_quote": "Paying for shelter access now.",
                    "reasoning": "The ledger explicitly names consideration.",
                }
            ]
        }
        rows = _validate_v6_rows(output, [self.gift], [self.gift])
        self.assertEqual(rows[0]["items"], {"coin": 3})
        self.assertNotIn("item_entries", rows[0])

    def test_rejects_commercial_verdict_without_ledger_quote(self) -> None:
        output = {
            "classifications": [
                {
                    "gift_index": 0,
                    "tick": 7,
                    "giver": "agent-1",
                    "recipient": "agent-2",
                    "item_entries": [{"resource": "coin", "quantity": 3}],
                    "verdict": "payment_for_service",
                    "evidence_quote": "inferred but absent",
                    "reasoning": "Inference only.",
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "verbatim ledger evidence"):
            _validate_v6_rows(output, [self.gift], [self.gift])


class ManagedFinalizationTests(unittest.TestCase):
    @patch("agent_world.run_finalization.subprocess.run")
    @patch("agent_world.run_finalization.shutil.which", return_value="/usr/bin/tmux")
    @patch("agent_world.run_finalization._tmux_active", side_effect=[False, True])
    @patch("agent_world.run_finalization.load_job")
    def test_finalization_launches_under_detached_supervisor(
        self, load_job, _active, _which, run
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            job_dir = root / "runs" / "jobs" / "test"
            job_dir.mkdir(parents=True)
            load_job.return_value = {
                "run_id": "test",
                "source_root": str(root),
                "job_dir": str(job_dir),
            }
            result = start_finalization("test")
            self.assertEqual(result["status"], "launched")
            saved = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["finalization_supervisor"]["status"], "running")
            self.assertIn("run_finalization worker test", (job_dir / "finalize.sh").read_text())
            run.assert_called_once()

    @patch("agent_world.run_finalization.subprocess.run")
    @patch("agent_world.run_finalization.shutil.which", return_value="/usr/bin/tmux")
    @patch("agent_world.run_finalization.load_job")
    def test_manual_finalization_refuses_controller_owned_attempt(
        self, load_job, _which, run
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            job_dir = root / "runs" / "jobs" / "test"
            job_dir.mkdir(parents=True)
            load_job.return_value = {
                "run_id": "test",
                "source_root": str(root),
                "job_dir": str(job_dir),
                "controller": {
                    "finalization_in_progress_signature": [11, 41],
                },
            }

            with self.assertRaisesRegex(
                RuntimeError, "Automatic finalization is already running"
            ):
                start_finalization("test")

            run.assert_not_called()

    def test_existing_failed_v6_attempt_prevents_rejudge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            events = root / "run.jsonl"
            events.write_text(json.dumps({"type": "gift"}) + "\n", encoding="utf-8")
            (root / "gift-classification-attempt.json").write_text(
                json.dumps({"status": "failed"}), encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "Refusing to re-judge"):
                _classify_v6_gifts({"events": str(events)}, root)

    def _cell(self, root: Path, seed: int) -> dict:
        output = root / f"seed-{seed}"
        output.mkdir()
        events = output / "run.jsonl"
        events.write_text(
            json.dumps(
                {
                    "type": "gift",
                    "tick": 3,
                    "actor_id": "agent-1",
                    "message": "A declared gift.",
                    "data": {"to": "agent-2", "items": {"food": 1}, "kind": "gift"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        snapshot = output / "run-snapshot.json"
        snapshot.write_text(json.dumps({"tick": 50}), encoding="utf-8")
        manifest = output / "run-manifest.json"
        manifest.write_text(
            json.dumps({"status": "completed", "resolved_models": {"glm-5.3": 500}}),
            encoding="utf-8",
        )
        return {
            "id": f"seed-{seed}",
            "seed": seed,
            "target_ticks": 50,
            "events": str(events),
            "snapshot": str(snapshot),
            "run_manifest": str(manifest),
            "checkpoint": str(output / "run-checkpoint.pkl"),
            "log": str(output / "run.log"),
            "session": None,
        }

    @patch("agent_world.run_finalization.write_report")
    @patch("agent_world.run_finalization.load_run_files", return_value=([], {}, []))
    @patch("agent_world.run_finalization.cell_status")
    @patch("agent_world.run_finalization.load_job")
    def test_v7_two_clean_seeds_finalize_ready(
        self, load_job, status, _load_files, write_report
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            job_dir = root / "runs" / "jobs" / "test"
            job_dir.mkdir(parents=True)
            cells = [self._cell(root, 11), self._cell(root, 41)]
            load_job.return_value = {
                "schema_version": 1,
                "run_id": "test",
                "kind": "benchmark",
                "protocol": "participant-v7",
                "launch_commit": "a" * 40,
                "job_dir": str(job_dir),
                "config": {"model": {"id": "glm-5.3"}},
                "cells": cells,
            }
            status.return_value = {
                "state": "completed",
                "supervisor_active": False,
            }
            write_report.return_value = {
                "run": {"completed": True, "final_tick": 50},
                "reliability": {
                    "benchmark_integrity_status": "clean",
                    "usage_record_coverage_pct": 100.0,
                },
                "benchmarks": {"trial": {"protocol_compliant": True}},
                "usage": {"total_cost_usd": 0},
            }
            result = finalize_job("test", root=root)
            self.assertEqual(result["analysis_readiness"]["status"], "ready")
            self.assertEqual(result["analysis_readiness"]["completed_seeds"], [11, 41])
            saved = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["analysis_readiness"]["status"], "ready")

    @patch("agent_world.run_finalization._classify_v6_gifts")
    @patch("agent_world.run_finalization.cell_status")
    @patch("agent_world.run_finalization.load_job")
    def test_v6_dry_run_reports_classifier_blocker_without_model_call(
        self, load_job, status, classify
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            job_dir = root / "runs" / "jobs" / "test"
            job_dir.mkdir(parents=True)
            cell = self._cell(root, 11)
            report_path = Path(cell["events"]).with_name("run-report.json")
            report_path.write_text(
                json.dumps(
                    {
                        "run": {"completed": True, "final_tick": 50},
                        "reliability": {
                            "benchmark_integrity_status": "clean",
                            "usage_record_coverage_pct": 100.0,
                        },
                        "benchmarks": {"trial": {"protocol_compliant": True}},
                        "usage": {"total_cost_usd": 0},
                    }
                ),
                encoding="utf-8",
            )
            load_job.return_value = {
                "schema_version": 1,
                "run_id": "test",
                "kind": "benchmark",
                "protocol": "participant-v6",
                "launch_commit": "a" * 40,
                "source_root": str(root),
                "job_dir": str(job_dir),
                "config": {"model": {"id": "glm-5.3"}},
                "cells": [cell],
            }
            status.return_value = {"state": "completed", "supervisor_active": False}
            result = finalize_job("test", root=root, dry_run=True)
            classify.assert_not_called()
            self.assertFalse(
                result["analysis_readiness"]["transfer_accounting"]["complete"]
            )
            self.assertTrue(
                any("transfer accounting" in blocker for blocker in result["analysis_readiness"]["blockers"])
            )


if __name__ == "__main__":
    unittest.main()
