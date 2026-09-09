import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent_world.controller_watchdog import recover_controllers


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "runs/jobs/test/job.json"
        self.path.parent.mkdir(parents=True)
        self.job = {"controller": {"status": "running", "session": "controller"},
                    "cells": [{"controller_state": "waiting_quota"}]}
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.job))

    @patch("agent_world.controller_watchdog._launch_job_controller")
    @patch("agent_world.controller_watchdog._tmux_active", return_value=False)
    def test_lost_quota_controller_revived_without_resuming_cells(self, alive, launch):
        self.assertTrue(recover_controllers(self.root, now=100))
        launch.assert_called_once_with(self.job)
        # Cooldown also protects against repeated crashes immediately after launch.
        recover_controllers(self.root, now=110)
        launch.assert_called_once()

    @patch("agent_world.controller_watchdog._launch_job_controller")
    @patch("agent_world.controller_watchdog._tmux_active", return_value=True)
    def test_live_untouched(self, alive, launch):
        recover_controllers(self.root)
        launch.assert_not_called()

    @patch("agent_world.controller_watchdog._launch_job_controller")
    @patch("agent_world.controller_watchdog._tmux_active", side_effect=[False, True])
    def test_rechecks_under_lock(self, alive, launch):
        recover_controllers(self.root)
        launch.assert_not_called()

    @patch("agent_world.controller_watchdog._launch_job_controller")
    @patch("agent_world.controller_watchdog._tmux_active", return_value=False)
    def test_attention_completed_and_deferred_not_restarted(self, alive, launch):
        for state in ["needs_attention", "completed", "paused_by_operator", "waiting_startup_gate"]:
            self.job["cells"][0]["controller_state"] = state
            self.save()
            self.assertFalse(recover_controllers(self.root))
        self.job["cells"][0]["controller_state"] = "running"
        self.job["deferral"] = {"status": "deferred"}
        self.save()
        self.assertFalse(recover_controllers(self.root))
        launch.assert_not_called()

    @patch("agent_world.controller_watchdog._launch_job_controller", side_effect=RuntimeError("offline"))
    @patch("agent_world.controller_watchdog._tmux_active", return_value=False)
    def test_failed_launch_retries_after_cooldown(self, alive, launch):
        with self.assertLogs("agent_world.controller_watchdog", level="ERROR"):
            recover_controllers(self.root, now=100)
        recover_controllers(self.root, now=120)
        launch.assert_called_once()
        with self.assertLogs("agent_world.controller_watchdog", level="ERROR"):
            recover_controllers(self.root, now=161)
        self.assertEqual(launch.call_count, 2)
