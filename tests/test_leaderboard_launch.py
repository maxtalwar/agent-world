import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from agent_world.leaderboard import make_server
from agent_world.leaderboard_launch import LaunchService, LaunchError, dispatch_once
from agent_world.leaderboard_supervisor import AstraClient, SupervisorBusy, SupervisorConnectionError, supervisor_environment, MODEL, EFFORT


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.service = LaunchService(self.root, settings={"supervisor_binary": "/fake/codex", "monitor_thread_id": "shared-monitor"})
        self.identifier = "a" * 32
        folder = self.service.folder / self.identifier
        folder.mkdir()
        config = folder / "config.json"
        config.write_text("{}")
        self.request = {
            "run_id": "web-test", "recipe_id": "participant-test", "recipe_key": "participant-test@hash",
            "digest": "hash", "source": str(self.root), "commit": "a" * 40,
            "model": "gpt-test", "brain": "codex", "seeds": [11, 41],
            "defaults": {"ticks": 60, "agents": 10, "reasoning_effort": "medium"},
            "config_path": str(config), "config_hash": __import__("hashlib").sha256(b"{}").hexdigest(),
            "created_at": "2026-09-06T00:00:00Z", "session": "aw-web-test",
            "supervisor_thread_id": None,
        }
        with self.service.connection() as db:
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?)", (
                self.identifier, "web-test", "review", time.time(), time.time(), json.dumps(self.request)))

    def test_confirmation_is_idempotent(self):
        with patch.object(self.service, "validate_source"), patch.object(self.service, "ensure_worker") as start:
            a = self.service.start({"request_id": self.identifier})
            b = self.service.start({"request_id": self.identifier})
        self.assertEqual(a["run_id"], b["run_id"])
        self.assertEqual(a["state"], "queued")
        start.assert_called_once_with(self.identifier)

    def test_duplicate_active_model_is_rejected(self):
        other = "b" * 32
        with self.service.connection() as db:
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?)", (
                other, "another-run", "supervising", time.time(), time.time(), json.dumps({
                    **self.request, "run_id": "another-run"})))
        with self.assertRaisesRegex(LaunchError, "already has an active"):
            self.service.start({"request_id": self.identifier})

    def test_muse_tiers_share_active_launch_and_job_identity(self):
        self.service.update(self.identifier, brain="muse", model="muse-spark-1.2-contributor")
        other = "b" * 32
        with self.service.connection() as db:
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?)", (
                other, "standard-run", "supervising", time.time(), time.time(), json.dumps({
                    **self.request, "run_id": "standard-run", "brain": "muse", "model": "muse-spark-1.2"})))
        with self.assertRaisesRegex(LaunchError, "already has an active"):
            self.service.start({"request_id": self.identifier})
        with self.service.connection() as db:
            db.execute("DELETE FROM requests WHERE id=?", (other,))
        path = self.root / "runs/jobs/standard-run/job.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"run_id": "standard-run", "protocol": "participant-test",
            "config": {"model": {"brain": "muse", "id": "muse-spark-1.2"}},
            "controller": {"status": "running"}}))
        with self.assertRaisesRegex(LaunchError, "unfinished study"):
            self.service.start({"request_id": self.identifier})
        self.assertEqual(self.service.get(self.identifier)["model"], "muse-spark-1.2-contributor")

    def test_review_expiry_and_extra_parameters(self):
        with self.service.connection() as db:
            db.execute("UPDATE requests SET created=?", (time.time() - 601,))
        with self.assertRaisesRegex(LaunchError, "expired"):
            self.service.start({"request_id": self.identifier})
        with self.assertRaises(LaunchError):
            self.service.start({"request_id": self.identifier, "seeds": [99]})
        with self.assertRaises(LaunchError):
            self.service.preview({"recipe": "x", "brain": "codex", "model": "x", "world": {}})

    def test_modified_review_config_cannot_launch(self):
        Path(self.request["config_path"]).write_text('{"seeds":[99]}')
        with patch("agent_world.leaderboard_launch.git", side_effect=[self.request["commit"], ""]):
            with self.assertRaisesRegex(LaunchError, "configuration changed"):
                self.service.validate_source(self.request)

    def test_branch_change_cannot_launch(self):
        with patch("agent_world.leaderboard_launch.git", return_value="other-commit"):
            with self.assertRaisesRegex(LaunchError, "source changed"):
                self.service.validate_source(self.request)




    def test_astra_request_uses_exact_model_low_effort_and_automatic_review(self):
        client = AstraClient.__new__(AstraClient)
        client.root = self.root
        client.native_windows = False
        client.rpc = Mock(return_value={"model": MODEL, "thread": {"id": "thread-1"}})
        self.assertEqual(client.attach(), "thread-1")
        params = client.rpc.call_args.args[1]
        self.assertEqual(params["model"], "gpt-6-astra")
        self.assertEqual(params["config"]["model_reasoning_effort"], "low")
        self.assertEqual(params["approvalsReviewer"], "auto_review")
        self.assertEqual(params["sandbox"], "workspace-write")

    def test_page_post_requires_origin_token_and_reviewed_request(self):
        launch_service = Mock()
        launch_service.settings = {}
        launch_service.public_options.return_value = {"enabled": True, "recipes": []}
        launch_service.preview.return_value = {"id": "preview"}
        server = make_server(self.root, port=0, launch_service=launch_service)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        base = "http://127.0.0.1:" + str(server.server_port)
        options = json.load(urlopen(base + "/api/launch/options"))

        def post(origin=None, token=None):
            headers = {"Content-Type": "application/json"}
            if origin: headers["Origin"] = origin
            if token: headers["X-Leaderboard-Token"] = token
            return urlopen(Request(base + "/api/launch/preview", data=b"{}", headers=headers))

        for origin, token in [(None, None), (base, "wrong"), ("http://evil.example", options["token"])]:
            with self.assertRaises(HTTPError) as error:
                post(origin, token)
            self.assertEqual(error.exception.code, 403)
        launch_service.preview.assert_not_called()
        with post(base, options["token"]) as response:
            self.assertEqual(response.status, 200)
        launch_service.preview.assert_called_once_with({})
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(base + "/api/launch/options", headers={"Host": "evil.example"}))
        self.assertEqual(error.exception.code, 403)






    def test_inbox_waits_without_opening_a_writer(self):
        self.service.update(self.identifier, state="queued", handoff_retry_at=time.time()+999)
        with patch("agent_world.leaderboard_launch.AstraClient") as client, \
             patch("agent_world.leaderboard_launch.subprocess.run") as launch:
            dispatch_once(self.service)
        client.assert_not_called()
        launch.assert_not_called()
        r = self.service.get(self.identifier)
        self.assertEqual(r["state"], "queued")
        self.assertEqual(r["supervisor_state"], "awaiting_monitor")
        self.assertFalse(self.service.monitoring_worklist()[0]["assignment_ready"])

    def test_atomic_batch_acceptance_and_single_launch(self):
        other = "b" * 32
        with self.service.connection() as db:
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?)", (
                other, "web-second", "queued", time.time(), time.time(),
                json.dumps({**self.request, "run_id": "web-second", "model": "claude-test"})))
        self.service.update(self.identifier, state="queued")
        with patch.object(self.service, "validate_source"):
            with self.assertRaises(LaunchError):
                self.service.monitoring_accept([self.identifier, "missing"], "shared-monitor")
            self.assertFalse(self.service.get(self.identifier).get("assignment_ready"))
            with self.assertRaises(LaunchError):
                self.service.monitoring_accept([self.identifier], "other-monitor")
            self.service.monitoring_accept([self.identifier, other], "shared-monitor")
            with patch("agent_world.leaderboard_launch.AstraClient") as client, \
                 patch("agent_world.leaderboard_launch.subprocess.run") as launch:
                dispatch_once(self.service)
                self.service.monitoring_accept([self.identifier, other], "shared-monitor")
                dispatch_once(self.service)
                self.assertEqual(launch.call_count, 2)
                client.assert_not_called()
        self.assertEqual(self.service.get(other)["state"], "supervising")
        self.assertEqual(len(self.service.monitoring_worklist()), 2)

    def test_acceptance_rejects_unconfirmed_or_modified_requests(self):
        with self.assertRaises(LaunchError):
            self.service.monitoring_accept([self.identifier], "shared-monitor")
        self.service.update(self.identifier, state="queued", dispatch_ready=False)
        with self.assertRaises(LaunchError):
            self.service.monitoring_accept([self.identifier], "shared-monitor")
        self.service.update(self.identifier, dispatch_ready=True)
        with patch.object(self.service, "validate_source", side_effect=LaunchError("changed")):
            with self.assertRaises(LaunchError):
                self.service.monitoring_accept([self.identifier], "shared-monitor")
        self.assertFalse(self.service.get(self.identifier).get("assignment_ready"))

    def test_acknowledged_existing_job_is_not_relaunched_after_restart(self):
        self.service.update(self.identifier, state="launching", assignment_ready=True,
                            supervisor_thread_id="shared-monitor")
        path = self.root / "runs/jobs/web-test/job.json"
        path.parent.mkdir(parents=True)
        path.write_text("{}")
        with patch("agent_world.leaderboard_launch.subprocess.run") as launch:
            dispatch_once(self.service)
        launch.assert_not_called()
        self.assertEqual(self.service.get(self.identifier)["state"], "supervising")

    def test_detached_windows_client_uses_persistent_interop(self):
        with patch.dict("os.environ", {"WSL_INTEROP": "/run/WSL/expired_interop"}), \
             patch("pathlib.Path.is_socket", return_value=True):
            self.assertEqual(supervisor_environment(True)["WSL_INTEROP"], "/run/WSL/1_interop")
            self.assertEqual(supervisor_environment(False)["WSL_INTEROP"], "/run/WSL/expired_interop")
        with patch.dict("os.environ", {"WSL_INTEROP": "/run/WSL/current_interop"}), \
             patch("pathlib.Path.is_socket", return_value=False):
            self.assertEqual(supervisor_environment(True)["WSL_INTEROP"], "/run/WSL/current_interop")

    def test_rpc_classifies_active_writer_conflict(self):
        client = AstraClient.__new__(AstraClient)
        client.sequence = 0
        client.send = Mock()
        client.receive = Mock(return_value={"id": 1, "error": {
            "message": "thread shared-monitor already has an active writer"}})
        with self.assertRaises(SupervisorBusy):
            client.rpc("thread/resume", {})

    def test_worklist_requires_terminal_or_attention_before_acknowledgment(self):
        self.service.update(self.identifier, state="supervising")
        self.assertEqual(len(self.service.monitoring_worklist()), 1)
        with self.assertRaises(LaunchError):
            self.service.monitoring_ack(self.identifier)
        self.service.update(self.identifier, state="needs_attention")
        with self.assertRaisesRegex(LaunchError, "Repairable faults"):
            self.service.monitoring_ack(self.identifier)
        self.assertEqual(len(self.service.monitoring_worklist()), 1)
        self.service.monitoring_ack(self.identifier, "external_blocker", "User must renew expired provider login")
        self.assertEqual(self.service.monitoring_worklist(), [])

    def test_batch_holds_requests_until_all_are_accepted(self):
        with patch.object(self.service, "validate_source"), patch.object(self.service, "ensure_worker") as start:
            result = self.service.start_batch({"request_ids": [self.identifier, "missing"]})
        self.assertEqual(result["results"][0]["request"]["state"], "queued")
        self.assertIn("error", result["results"][1])
        self.assertTrue(self.service.get(self.identifier)["dispatch_ready"])
        start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
