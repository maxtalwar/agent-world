from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_world.managed_runs import (
    build_cell_command,
    build_launch_plan,
    _launch_cell,
    _launch_job_controller,
    cell_status,
    load_run_config,
    _health_gate_status,
    supervise_startup_gate,
)


def _config(kind: str = "experiment") -> dict:
    effort = "low" if kind == "benchmark" else "max"
    value = {
        "schema_version": 1,
        "run_id": "glm-probe",
        "kind": kind,
        "model": {"brain": "zcode", "id": "glm-5.3", "reasoning_effort": effort},
        "seeds": [11],
        "runtime": {"ticks": 8, "agents": 3, "max_workers": 4},
        "harness": {"connector_profile": "connector-v3"},
    }
    if kind == "experiment":
        value["question"] = "Does the installed ZCode boundary return valid decisions?"
    else:
        value["model"] = {"brain": "codex", "id": "fixture-model", "reasoning_effort": "low"}
        value["protocol"] = "participant-v7"
        value["seeds"] = [11, 41]
        value["runtime"] = {}
        value["harness"] = {}
    return value


class ManagedRunConfigTests(unittest.TestCase):
    def _load(self, value: dict) -> dict:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "run.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return load_run_config(path)

    def test_experiment_defaults_to_seed_11(self) -> None:
        value = _config()
        value.pop("seeds")
        self.assertEqual(self._load(value)["seeds"], [11])

    def test_benchmark_defaults_current_protocol_and_certification_seeds(self) -> None:
        value = _config("benchmark")
        value.pop("protocol")
        value.pop("seeds")
        loaded = self._load(value)
        self.assertEqual(loaded["protocol"], "participant-v7")
        self.assertEqual(loaded["seeds"], [11, 41])

    def test_experiment_requires_question(self) -> None:
        value = _config()
        value.pop("question")
        with self.assertRaisesRegex(ValueError, "concrete question"):
            self._load(value)

    def test_unknown_field_is_rejected(self) -> None:
        value = _config()
        value["runtime"]["mystery"] = 1
        with self.assertRaisesRegex(ValueError, "Unknown runtime"):
            self._load(value)

    def test_benchmark_rejects_mixed_population(self) -> None:
        value = _config("benchmark")
        value["model"] = {"population": ["5@codex:a", "5@codex:b"]}
        with self.assertRaisesRegex(ValueError, "uniform model"):
            self._load(value)

    def test_benchmark_rejects_protocol_owned_overrides(self) -> None:
        value = _config("benchmark")
        value["world"] = {"preset": "baseline"}
        with self.assertRaisesRegex(ValueError, "protocol owns"):
            self._load(value)

    def test_benchmark_accepts_operational_worker_overrides(self) -> None:
        value = _config("benchmark")
        value["runtime"] = {
            "max_workers": 2,
            "provider_max_workers": {"zcode": 2},
        }

        loaded = self._load(value)
        command = build_cell_command(loaded, 11, Path("/tmp/out"))

        self.assertEqual(loaded["runtime"]["max_workers"], 2)
        self.assertEqual(
            command[command.index("--max-workers") + 1],
            "2",
        )
        self.assertEqual(command[command.index("--zcode-max-workers") + 1], "2")

    def test_benchmark_rejects_wrong_reasoning_effort(self) -> None:
        value = _config("benchmark")
        value["model"]["reasoning_effort"] = "medium"
        with self.assertRaisesRegex(ValueError, "requires model.reasoning_effort"):
            self._load(value)

    def test_benchmark_rejects_undeclared_seed(self) -> None:
        value = _config("benchmark")
        value["seeds"] = [12]
        with self.assertRaisesRegex(ValueError, "not declared"):
            self._load(value)

    def test_v6_recipe_does_not_require_pinned_source_commit(self) -> None:
        value = _config("benchmark")
        value["protocol"] = "participant-v6"
        value["model"]["reasoning_effort"] = "medium"
        self.assertEqual(self._load(value)["protocol"], "participant-v6")

    def test_historical_protocol_accepts_pinned_source_commit(self) -> None:
        value = _config("benchmark")
        value["protocol"] = "participant-v6"
        value["source"] = {"commit": "abc123"}
        value["model"]["reasoning_effort"] = "medium"
        self.assertEqual(self._load(value)["protocol"], "participant-v6")

    def test_command_maps_structured_blocks(self) -> None:
        command = build_cell_command(self._load(_config()), 11, Path("/tmp/out"))
        self.assertIn("--brain", command)
        self.assertIn("zcode", command)
        self.assertIn("--max-workers", command)
        self.assertIn("--connector-profile", command)
        self.assertEqual(command[-1], "--progress")

    @patch("agent_world.managed_runs._git")
    def test_plan_pins_commit_and_creates_one_cell_per_seed(self, git) -> None:
        git.side_effect = ["a" * 40, ""]
        plan = build_launch_plan(_config("benchmark"), Path("/repo"))
        self.assertEqual(plan["launch_commit"], "a" * 40)
        self.assertEqual([cell["seed"] for cell in plan["cells"]], [11, 41])
        self.assertTrue(all(cell["target_ticks"] == 50 for cell in plan["cells"]))
        self.assertNotEqual(
            plan["cells"][0]["cohort_id"], plan["cells"][1]["cohort_id"]
        )


class ManagedRunControllerLaunchTests(unittest.TestCase):
    def _job(self, root: Path) -> dict:
        job_dir = root / "runs" / "jobs" / "test"
        job_dir.mkdir(parents=True)
        return {
            "schema_version": 1,
            "run_id": "test",
            "source_root": str(root),
            "job_dir": str(job_dir),
            "cells": [],
        }

    @patch("agent_world.managed_runs.subprocess.run")
    @patch("agent_world.managed_runs.shutil.which", return_value="/usr/bin/tmux")
    @patch(
        "agent_world.managed_runs._tmux_active",
        side_effect=[False, False, True],
    )
    def test_controller_uses_durable_capped_crash_backoff(
        self, _active, _which, run
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            job = self._job(Path(temp_dir))

            _launch_job_controller(job)

            script = Path(job["job_dir"], "supervise-job.sh").read_text(
                encoding="utf-8"
            )
            self.assertIn("while true", script)
            self.assertIn("delay > 300", script)
            self.assertEqual(job["controller"]["status"], "running")
            run.assert_called_once()

    @patch("agent_world.managed_runs.subprocess.run")
    @patch("agent_world.managed_runs.shutil.which", return_value="/usr/bin/tmux")
    @patch(
        "agent_world.managed_runs._tmux_active",
        side_effect=[False, False, False],
    )
    def test_fast_terminal_controller_does_not_look_like_launch_failure(
        self, _active, _which, run
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            job = self._job(Path(temp_dir))

            def finish_immediately(*_args, **_kwargs):
                job_path = Path(job["job_dir"], "job.json")
                saved = json.loads(job_path.read_text(encoding="utf-8"))
                saved["controller"]["status"] = "needs_attention"
                job_path.write_text(json.dumps(saved), encoding="utf-8")

            run.side_effect = finish_immediately

            _launch_job_controller(job)

            self.assertEqual(job["controller"]["status"], "needs_attention")

    @patch("agent_world.managed_runs.subprocess.run")
    @patch("agent_world.managed_runs._write_launcher")
    @patch("agent_world.managed_runs._prepare_cell")
    @patch("agent_world.managed_runs.shutil.which", return_value="/usr/bin/tmux")
    @patch("agent_world.managed_runs._tmux_active", side_effect=[False, True])
    def test_resume_archives_terminal_manifest_before_starting_supervisor(
        self, _active, _which, _prepare, write_launcher, run
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            job_dir = root / "runs" / "jobs" / "test"
            output_dir = root / "output"
            job_dir.mkdir(parents=True)
            output_dir.mkdir()
            launcher = job_dir / "resume.sh"
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")
            write_launcher.return_value = launcher
            manifest = output_dir / "run-manifest.json"
            manifest.write_text(
                json.dumps({"status": "paused_checkpoint"}),
                encoding="utf-8",
            )
            job = {
                "run_id": "test",
                "source_root": str(root),
                "job_dir": str(job_dir),
            }
            cell = {
                "id": "seed-11",
                "resume_count": 2,
                "run_manifest": str(manifest),
                "log": str(job_dir / "seed-11.log"),
            }

            _launch_cell(job, cell, resume=True)

            archived = output_dir / "run-manifest.before-resume-2.json"
            self.assertFalse(manifest.exists())
            self.assertTrue(archived.exists())
            self.assertEqual(cell["previous_run_manifests"], [str(archived)])
            self.assertTrue(cell["session"].startswith("aw-test-seed-11-r2-"))
            run.assert_called_once()


class ManagedRunStatusTests(unittest.TestCase):
    def test_health_gate_reads_recorded_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            events = Path(temp_dir) / "run.jsonl"
            events.write_text(
                json.dumps({"type": "run_health_check", "data": {"status": "passed"}}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(_health_gate_status({"events": str(events)}), "passed")

    @patch("agent_world.managed_runs._launch_cell")
    def test_passed_gate_releases_deferred_cell(self, launch_cell) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            events = root / "seed-11.jsonl"
            events.write_text(
                json.dumps({"type": "run_health_check", "data": {"status": "passed"}}) + "\n",
                encoding="utf-8",
            )
            job_path = root / "job.json"
            job_path.write_text(
                json.dumps({
                    "startup_gate": {"status": "pending"},
                    "cells": [
                        {"id": "seed-11", "events": str(events)},
                        {"id": "seed-41", "output_dir": str(root / "seed-41")},
                    ],
                }),
                encoding="utf-8",
            )
            supervise_startup_gate(job_path, poll_seconds=0)
            launch_cell.assert_called_once()
            saved = json.loads(job_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["startup_gate"]["status"], "passed")

    @patch("agent_world.managed_runs._tmux_active", return_value=False)
    def test_checkpoint_without_supervisor_is_interrupted(self, _active) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            checkpoint = root / "run-checkpoint.pkl"
            checkpoint.write_bytes(b"checkpoint")
            snapshot = root / "run-snapshot.json"
            snapshot.write_text(json.dumps({"tick": 17}), encoding="utf-8")
            status = cell_status({
                "id": "seed-11", "seed": 11, "session": "aw-test",
                "run_manifest": str(root / "run-manifest.json"),
                "snapshot": str(snapshot), "checkpoint": str(checkpoint),
                "log": str(root / "run.log"),
            })
            self.assertEqual(status["state"], "interrupted")
            self.assertEqual(status["tick"], 17)

    @patch("agent_world.managed_runs._tmux_active", return_value=False)
    def test_completed_manifest_is_terminal(self, _active) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = root / "run-manifest.json"
            manifest.write_text(json.dumps({"status": "completed", "final_tick": 50}), encoding="utf-8")
            status = cell_status({
                "id": "seed-41", "seed": 41, "session": "aw-test",
                "run_manifest": str(manifest),
                "snapshot": str(root / "missing.json"),
                "checkpoint": str(root / "missing.pkl"),
                "log": str(root / "run.log"),
            })
            self.assertEqual(status["state"], "completed")
            self.assertEqual(status["tick"], 50)

    @patch("agent_world.managed_runs._tmux_active", return_value=True)
    def test_completed_manifest_overrides_stale_supervisor(self, _active) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = root / "run-manifest.json"
            manifest.write_text(
                json.dumps({"status": "completed", "final_tick": 50}),
                encoding="utf-8",
            )
            status = cell_status({
                "id": "seed-41", "seed": 41, "session": "aw-stale",
                "run_manifest": str(manifest),
                "snapshot": str(root / "missing.json"),
                "checkpoint": str(root / "missing.pkl"),
                "log": str(root / "run.log"),
            })

            self.assertEqual(status["state"], "completed")
            self.assertFalse(status["supervisor_active"])
            self.assertTrue(status["stale_supervisor"])


if __name__ == "__main__":
    unittest.main()
