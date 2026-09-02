from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_world.run_controller import ControllerPolicy, reconcile_once


NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


class RunControllerTests(unittest.TestCase):
    def _cell(
        self,
        root: Path,
        seed: int,
        *,
        status: str | None = "running",
        stop_reason: str | None = None,
        tick: int = 0,
        event: dict | None = None,
        session: str | None = None,
        checkpoint: bool = True,
    ) -> dict:
        output = root / f"seed-{seed}"
        output.mkdir()
        events = output / "run.jsonl"
        events.write_text(
            (json.dumps(event) + "\n") if event is not None else "",
            encoding="utf-8",
        )
        snapshot = output / "run-snapshot.json"
        snapshot.write_text(json.dumps({"tick": tick}), encoding="utf-8")
        manifest = output / "run-manifest.json"
        if status is not None:
            manifest.write_text(
                json.dumps(
                    {
                        "status": status,
                        "final_tick": tick,
                        "stop_reason": stop_reason,
                    }
                ),
                encoding="utf-8",
            )
        checkpoint_path = output / "run-checkpoint.pkl"
        if checkpoint:
            checkpoint_path.write_bytes(b"checkpoint")
        return {
            "id": f"seed-{seed}",
            "seed": seed,
            "target_ticks": 50,
            "output_dir": str(output),
            "events": str(events),
            "snapshot": str(snapshot),
            "checkpoint": str(checkpoint_path),
            "run_manifest": str(manifest),
            "log": str(output / "run.log"),
            "session": session,
            "resume_count": 0,
            "worktree": str(root / "worktree"),
        }

    def _job(
        self,
        root: Path,
        cells: list[dict],
        *,
        kind: str = "experiment",
        startup_gate: dict | None = None,
    ) -> Path:
        job_dir = root / "runs" / "jobs" / "test"
        job_dir.mkdir(parents=True)
        controller = {
            "schema_version": 1,
            "status": "running",
            "session": "aw-test-controller",
            "heartbeat": str(job_dir / "controller-heartbeat.json"),
            "events": str(job_dir / "controller-events.jsonl"),
            "log": str(job_dir / "controller.log"),
        }
        job = {
            "schema_version": 1,
            "run_id": "test",
            "kind": kind,
            "protocol": "participant-v7" if kind == "benchmark" else None,
            "launch_commit": "a" * 40,
            "source_root": str(root),
            "job_dir": str(job_dir),
            "config": {"model": {"id": "test-model"}},
            "cells": cells,
            "controller": controller,
        }
        if startup_gate is not None:
            job["startup_gate"] = startup_gate
        path = job_dir / "job.json"
        path.write_text(json.dumps(job), encoding="utf-8")
        return path

    @patch("agent_world.managed_runs._tmux_active", return_value=True)
    def test_records_progress_check_every_ten_ticks(self, _active) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self._job(
                root,
                [self._cell(root, 11, tick=21, session="aw-seed-11")],
            )

            terminal = reconcile_once(path, now=NOW)

            self.assertFalse(terminal)
            job = json.loads(path.read_text(encoding="utf-8"))
            events = [
                json.loads(line)
                for line in Path(job["controller"]["events"]).read_text().splitlines()
            ]
            self.assertEqual(
                [event["tick"] for event in events if event["type"] == "progress_check"],
                [10, 20],
            )
            heartbeat = json.loads(
                Path(job["controller"]["heartbeat"]).read_text(encoding="utf-8")
            )
            self.assertEqual(heartbeat["cells"][0]["tick"], 21)

    @patch("agent_world.run_controller._launch_cell")
    @patch("agent_world.managed_runs._tmux_active", return_value=False)
    def test_interrupted_cell_is_resumed_after_backoff(self, _active, launch) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self._job(
                root,
                [self._cell(root, 11, status=None, tick=17)],
            )
            policy = ControllerPolicy(resume_backoff_seconds=(60.0,))

            reconcile_once(path, policy=policy, now=NOW)
            launch.assert_not_called()
            reconcile_once(path, policy=policy, now=NOW + timedelta(seconds=61))

            launch.assert_called_once()
            self.assertTrue(launch.call_args.kwargs["resume"])
            job = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(job["cells"][0]["auto_resume_count"], 1)
            self.assertNotIn("next_auto_resume_at_utc", job["cells"][0])

    @patch("agent_world.run_controller._launch_cell")
    @patch("agent_world.managed_runs._tmux_active", return_value=False)
    def test_authentication_failure_requires_attention(self, _active, launch) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            event = {
                "type": "run_stopped",
                "message": "Cursor Agent is not logged in; run cursor-agent login.",
                "data": {"reason": "provider_unavailable"},
            }
            path = self._job(
                root,
                [self._cell(
                    root, 11, status="stopped", stop_reason="provider_unavailable",
                    event=event,
                )],
            )

            terminal = reconcile_once(path, now=NOW)

            self.assertTrue(terminal)
            launch.assert_not_called()
            job = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                job["cells"][0]["controller_attention"], "authentication_required"
            )
            self.assertEqual(job["controller"]["status"], "needs_attention")

    @patch("agent_world.run_controller._launch_cell")
    @patch("agent_world.managed_runs._tmux_active", return_value=False)
    def test_exhausted_quota_wait_is_not_restarted(self, _active, launch) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            event = {
                "type": "run_paused",
                "message": "Quota wait budget exhausted.",
                "data": {"reason": "insufficient_quota"},
            }
            path = self._job(
                root,
                [self._cell(
                    root, 11, status="paused_checkpoint", stop_reason="insufficient_quota",
                    event=event,
                )],
            )

            reconcile_once(path, now=NOW)

            launch.assert_not_called()
            job = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                job["cells"][0]["controller_attention"],
                "quota_wait_budget_exhausted",
            )

    @patch("agent_world.run_controller._launch_cell")
    @patch("agent_world.managed_runs._tmux_active", return_value=False)
    def test_interrupted_quota_sleep_resumes_only_after_recorded_wait(
        self, _active, launch
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            event = {
                "type": "run_quota_wait",
                "message": "Waiting five minutes before retrying the same tick.",
                "data": {
                    "reason": "insufficient_quota",
                    "wait_seconds": 300.0,
                },
            }
            cell = self._cell(
                root,
                11,
                status=None,
                tick=17,
                event=event,
                session="aw-dead-seed-11",
            )
            os.utime(cell["events"], (NOW.timestamp(), NOW.timestamp()))
            path = self._job(root, [cell])

            reconcile_once(path, now=NOW + timedelta(seconds=60))

            launch.assert_not_called()
            waiting = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(waiting["cells"][0]["controller_state"], "waiting_quota")
            self.assertEqual(
                waiting["cells"][0]["next_auto_resume_at_utc"],
                _iso(NOW + timedelta(seconds=300)),
            )

            reconcile_once(path, now=NOW + timedelta(seconds=301))
            launch.assert_called_once()

    @patch("agent_world.run_controller._launch_cell")
    @patch("agent_world.managed_runs._tmux_active", return_value=True)
    def test_passed_gate_launches_deferred_seed_independently(self, _active, launch) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            health = {
                "type": "run_health_check",
                "data": {"status": "passed"},
            }
            seed11 = self._cell(
                root, 11, tick=5, event=health, session="aw-seed-11"
            )
            seed41 = self._cell(
                root, 41, status=None, checkpoint=False, session=None
            )
            path = self._job(
                root,
                [seed11, seed41],
                kind="benchmark",
                startup_gate={"status": "pending", "source_cell": "seed-11"},
            )

            reconcile_once(path, now=NOW)

            launch.assert_called_once()
            self.assertFalse(launch.call_args.kwargs.get("resume", False))
            job = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(job["startup_gate"]["status"], "passed")

    @patch("agent_world.run_controller._kill_session", return_value=True)
    @patch("agent_world.managed_runs._tmux_active", return_value=True)
    def test_stalled_non_quota_process_is_reaped(self, _active, kill) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cell = self._cell(root, 11, tick=8, session="aw-seed-11")
            cell["controller_last_tick"] = 8
            cell["controller_last_progress_at_utc"] = _iso(
                NOW - timedelta(hours=2)
            )
            path = self._job(root, [cell])
            policy = ControllerPolicy(stall_seconds=3600)

            reconcile_once(path, policy=policy, now=NOW)

            kill.assert_called_once_with("aw-seed-11")
            job = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(job["cells"][0]["controller_state"], "stalled_process_reaped")
            self.assertEqual(job["cells"][0]["next_auto_resume_at_utc"], _iso(NOW))

    @patch("agent_world.run_finalization.finalize_job")
    @patch("agent_world.managed_runs._tmux_active", return_value=False)
    def test_completed_benchmark_is_finalized_once_and_controller_exits(
        self, _active, finalize
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self._job(
                root,
                [
                    self._cell(root, 11, status="completed", tick=50),
                    self._cell(root, 41, status="completed", tick=50),
                ],
                kind="benchmark",
            )

            self.assertFalse(reconcile_once(path, now=NOW))
            finalize.assert_called_once_with("test")
            job = json.loads(path.read_text(encoding="utf-8"))
            job["analysis_readiness"] = {"status": "ready"}
            path.write_text(json.dumps(job), encoding="utf-8")

            self.assertTrue(reconcile_once(path, now=NOW + timedelta(seconds=30)))
            finalize.assert_called_once()
            job = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(job["controller"]["status"], "completed")

    @patch("agent_world.run_finalization.finalize_job")
    @patch("agent_world.managed_runs._tmux_active", return_value=False)
    def test_stale_automatic_finalization_marker_is_recovered(
        self, _active, finalize
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self._job(
                root,
                [self._cell(root, 11, status="completed", tick=50)],
                kind="benchmark",
            )
            job = json.loads(path.read_text(encoding="utf-8"))
            job["controller"]["finalization_in_progress_signature"] = [11]
            path.write_text(json.dumps(job), encoding="utf-8")

            self.assertFalse(reconcile_once(path, now=NOW))

            finalize.assert_called_once_with("test")
            saved = json.loads(path.read_text(encoding="utf-8"))
            events = [
                json.loads(line)
                for line in Path(saved["controller"]["events"]).read_text().splitlines()
            ]
            self.assertIn(
                "automatic_finalization_recovered",
                [event["type"] for event in events],
            )

    @patch("agent_world.run_finalization.finalize_job")
    @patch("agent_world.managed_runs._tmux_active", return_value=False)
    def test_recent_manual_finalization_blocks_automatic_finalization(
        self, _active, finalize
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self._job(
                root,
                [self._cell(root, 11, status="completed", tick=50)],
                kind="benchmark",
            )
            job = json.loads(path.read_text(encoding="utf-8"))
            job["finalization_supervisor"] = {
                "status": "running",
                "session": "aw-test-finalize",
                "started_at_utc": _iso(NOW),
            }
            path.write_text(json.dumps(job), encoding="utf-8")

            self.assertFalse(reconcile_once(path, now=NOW + timedelta(seconds=1)))

            finalize.assert_not_called()
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["controller"]["status"], "running")


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


if __name__ == "__main__":
    unittest.main()
