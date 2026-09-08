import json
from pathlib import Path
import tempfile
import argparse
import unittest
from unittest.mock import Mock, patch
from agent_world.leaderboard_event_monitor import signal, watch_once


class EventMonitorTests(unittest.TestCase):
    def request(self, **extra):
        return {"request_id": "request", "run_id": "run", "state": "supervising",
                "assignment_ready": True, "controller_status": "running",
                "cells": [{"id": "seed-11", "controller_state": "running"}], **extra}

    def test_healthy_and_quota_waits_never_wake_agent(self):
        self.assertIsNone(signal(self.request()))
        for status in ["running", "needs_attention"]:
            self.assertIsNone(signal(self.request(controller_status=status, cells=[
                {"controller_state": "waiting_quota"}, {"controller_state": "completed"}])))
        self.assertIsNone(signal(self.request(monitor_reviewed=True, state="needs_attention")))

    def test_new_launch_and_attention_are_actionable(self):
        self.assertEqual(signal(self.request(state="queued", assignment_ready=False))["kind"], "launch")
        self.assertEqual(signal(self.request(controller_status="needs_attention"))["kind"], "attention")

    def test_no_agent_calls_for_repeated_terminal_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            service = Mock(folder=Path(directory), root=Path(directory))
            request = self.request(controller_status="completed_with_blockers",
                readiness={"status": "needs_provenance_review", "blockers": ["missing trace"]})
            service.monitoring_worklist.return_value = [request]
            def command(args, **kwargs):
                return Mock(returncode=1 if args[1]=="has-session" else 0)
            with patch("agent_world.leaderboard_event_monitor.subprocess.run", side_effect=command) as run:
                for _ in range(100):
                    watch_once(service)
                launches = [c for c in run.call_args_list if c.args[0][1]=="new-session"]
                self.assertEqual(len(launches), 1)
                request["readiness"]["blockers"] = ["different dependency"]
                watch_once(service)
                self.assertEqual(sum(c.args[0][1]=="new-session" for c in run.call_args_list), 2)

    def test_same_failure_after_resume_is_a_new_incident(self):
        with tempfile.TemporaryDirectory() as directory:
            service = Mock(folder=Path(directory), root=Path(directory))
            request = self.request(cells=[{"id":"seed-11", "controller_state":"needs_attention",
                "controller_attention":"authentication_required", "resume_count":0}])
            service.monitoring_worklist.return_value = [request]
            def command(args, **kwargs):
                return Mock(returncode=1 if args[1]=="has-session" else 0)
            with patch("agent_world.leaderboard_event_monitor.subprocess.run", side_effect=command) as run:
                watch_once(service)
                # Progress in a different healthy seed must not re-dispatch the blocked seed.
                request["cells"][0]["controller_last_tick"] = 6
                watch_once(service)
                self.assertEqual(sum(c.args[0][1]=="new-session" for c in run.call_args_list), 1)
                request["cells"][0]["resume_count"] = 1
                for _ in range(20): watch_once(service)
                self.assertEqual(sum(c.args[0][1]=="new-session" for c in run.call_args_list), 2)

    def test_review_scope_changes_only_with_material_progress(self):
        from agent_world.leaderboard_launch import LaunchService
        job={"controller":{"status":"needs_attention","last_check_at_utc":"old"},
             "cells":[{"id":"seed-11","resume_count":0,"controller_last_tick":5}]}
        before=LaunchService.monitoring_incident(job)
        job["controller"]["last_check_at_utc"]="new"
        self.assertEqual(before,LaunchService.monitoring_incident(job))
        job["cells"][0]["resume_count"]=1
        self.assertNotEqual(before,LaunchService.monitoring_incident(job))

    def test_simultaneous_launches_are_batched(self):
        with tempfile.TemporaryDirectory() as directory:
            service = Mock(folder=Path(directory), root=Path(directory))
            service.monitoring_worklist.return_value = [self.request(state="queued", assignment_ready=False),
                self.request(request_id="second", run_id="second", state="queued", assignment_ready=False)]
            with patch("agent_world.leaderboard_event_monitor.subprocess.run", side_effect=[Mock(returncode=1), Mock(returncode=0)]):
                watch_once(service)
            records = list((Path(directory)/"events").glob("*/event.json"))
            self.assertEqual(len(records), 1)
            self.assertEqual(len(json.loads(records[0].read_text())["events"]), 2)

    def test_worker_uses_ephemeral_low_astra_and_retains_notes(self):
        from agent_world.leaderboard_event_monitor import worker
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"event.json").write_text(json.dumps({"status":"pending", "events":[{"request_id":"one", "kind":"launch"}]}))
            service = Mock(settings={"monitor_thread_id":"monitor", "supervisor_binary":"/fake/codex"})
            def execute(command, **kwargs):
                self.assertIn("complete the provenance review and leaderboard admission", kwargs["input"])
                self.assertNotIn("do not admit leaderboard scores", kwargs["input"])
                self.assertIn("--ephemeral", command)
                self.assertIn("--approve-for-me", command)
                self.assertIn("gpt-6-astra", command)
                self.assertIn('model_reasoning_effort="low"', command)
                (root/"response.txt").write_text("Accepted batch")
                return Mock(returncode=0)
            with patch("agent_world.leaderboard_event_monitor.LaunchService", return_value=service), \
                 patch("agent_world.leaderboard_event_monitor.subprocess.run", side_effect=execute):
                worker(root,root)
            self.assertEqual(json.loads((root/"event.json").read_text())["status"], "completed")
            service.update.assert_called_once_with("one", supervisor_message="Accepted batch")

    def test_no_events_while_quota_paused(self):
        with tempfile.TemporaryDirectory() as directory:
            service = Mock(folder=Path(directory), root=Path(directory))
            service.monitoring_worklist.return_value = [self.request(cells=[{"controller_state": "waiting_quota"}])]
            with patch("agent_world.leaderboard_event_monitor.subprocess.run", return_value=Mock(returncode=1)) as run:
                for _ in range(100): watch_once(service)
            self.assertFalse(any(c.args[0][1]=="new-session" for c in run.call_args_list))


if __name__ == "__main__": unittest.main()
