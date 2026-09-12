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
        (self.root / "agent_world").mkdir()
        (self.root / "agent_world/recipe-execution-locks.json").write_text(json.dumps({"recipes": {"participant-test": {"recipe_digest": "hash"}}}))
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

    @patch("agent_world.leaderboard_launch.subprocess.run")
    def test_recovery_checks_controllers_without_queued_requests(self, run):
        run.return_value = Mock(returncode=0, stdout='{"active": true}', stderr="")
        with patch.object(self.service, "ensure_worker") as ensure:
            self.service.recover()
        ensure.assert_called_once()
        self.assertIn("agent_world.controller_watchdog", run.call_args.args[0])

    def test_working_indicator_requires_recent_event_heartbeat(self):
        event=self.service.folder/"event.json"
        event.write_text(json.dumps({"status":"working","heartbeat_unix":time.time()}))
        self.service.update(self.identifier, monitor_event_path=str(event.relative_to(self.root)))
        self.assertEqual(self.service.public_request(self.service.get(self.identifier))["monitor_event_state"], "working")
        event.write_text(json.dumps({"status":"working","heartbeat_unix":time.time()-120}))
        self.assertEqual(self.service.public_request(self.service.get(self.identifier))["monitor_event_state"], "interrupted")
        event.write_text(json.dumps({"status":"completed","heartbeat_unix":time.time()}))
        self.assertEqual(self.service.public_request(self.service.get(self.identifier))["monitor_event_state"], "completed")

    def test_recipe_discovery_uses_committed_checkout_during_edits(self):
        released=self.root/"released"
        (released/"agent_world/recipes").mkdir(parents=True)
        (released/"agent_world/recipes/participant-test.json").write_text("{}")
        info={"digest":"hash","recipe":{"defaults":{},"replications":{"required_seeds":[11,41]}},"brains":["codex"]}
        def git_result(path, *args):
            if args[0]=="rev-parse": return "a"*40
            return " M agent_world/engine.py" if Path(path)==self.root else ""
        with patch.object(self.service,"launch_checkout",return_value=released) as checkout, \
             patch("agent_world.leaderboard_launch.git",side_effect=git_result), \
             patch("agent_world.leaderboard_launch.subprocess.check_output",return_value=json.dumps(info)):
            options=self.service.sources()
        self.assertIn("participant-test@hash",options)
        self.assertEqual(options["participant-test@hash"]["source"],str(released))
        checkout.assert_called_once_with({"commit":"a"*40})

    def test_blocked_recipe_remains_visible_but_cannot_preview(self):
        recipes = self.root / "agent_world/recipes"
        recipes.mkdir()
        (recipes / "participant-test.json").write_text("{}")
        info = {"digest": "hash", "brains": ["claude"],
                "recipe": {"defaults": {}, "replications": {"required_seeds": [11, 41]}},
                "execution_blocker": "implementation changed: agent_world/usage.py"}
        with patch.object(self.service, "launch_checkout", return_value=self.root), \
             patch("agent_world.leaderboard_launch.git", side_effect=lambda root, *args: "a"*40 if args[0] == "rev-parse" else ""), \
             patch("agent_world.leaderboard_launch.subprocess.check_output", return_value=json.dumps(info)):
            sources = self.service.sources()
        source = sources["participant-test@hash"]
        self.assertIn("compatibility review", source["launch_blocker"])
        catalog = {"sources": sources, "blocker": None, "models": [],
                   "warnings": ["Some Claude model availability checks failed; old rate limit warning"]}
        with patch.object(self.service, "catalog", return_value=catalog), \
             patch("agent_world.leaderboard_launch.for_recipe", return_value=[{"name": "Claude Sonnet 5", "brain": "claude"}]):
            options = self.service.public_options()
            self.assertEqual(options["recipes"][0]["models"][0]["name"], "Claude Sonnet 5")
            self.assertNotIn("execution_blocker", options["recipes"][0])
            self.assertNotIn("rate limit", options["warnings"][0])
            with self.assertRaisesRegex(LaunchError, "compatibility review"):
                self.service.preview({"recipe": source["id"], "brain": "claude", "model": "claude-sonnet-5"})

    def test_empty_recipe_catalog_has_an_explicit_blocker(self):
        self.service.settings.update(launch_enabled=True, supervisor_binary=__file__)
        with patch.object(self.service, "sources", return_value={}), \
             patch("agent_world.leaderboard_launch.shutil.which", return_value="tmux"), \
             patch("agent_world.leaderboard_launch.saved_catalog", return_value=([], [])):
            options = self.service.public_options()
        self.assertFalse(options["enabled"])
        self.assertIn("recipes could not be loaded", options["blocker"])

    def test_info_preserves_metadata_when_execution_verification_fails(self):
        from agent_world.leaderboard_launch import INFO
        from contextlib import redirect_stdout
        from io import StringIO
        out = StringIO()
        recipe = Mock(digest="hash")
        recipe.to_dict.return_value = {"id": "participant-test"}
        with patch("agent_world.protocols.get_recipe", return_value=recipe), \
             patch("agent_world.recipe_execution.verify_recipe_execution", side_effect=ValueError("changed implementation")), \
             patch("sys.argv", ["info", "participant-test"]), redirect_stdout(out):
            exec(INFO, {})
        info = json.loads(out.getvalue())
        self.assertEqual(info["recipe"]["id"], "participant-test")
        self.assertEqual(info["execution_blocker"], "changed implementation")

    def test_retired_recipe_review_cannot_launch(self):
        self.request["digest"] = "retired-world"
        with self.assertRaisesRegex(LaunchError, "retired conditions"):
            self.service.validate_source(self.request)

    def test_sources_do_not_select_retained_job_worktrees(self):
        recipes = self.root / "agent_world/recipes"
        recipes.mkdir()
        (recipes / "participant-test.json").write_text("{}")
        old = self.root / "runs/jobs/old"
        old.mkdir(parents=True)
        (old / "job.json").write_text(json.dumps({"kind":"benchmark", "protocol":"participant-test", "recipe_fingerprint_sha256":"retired", "execution_root":str(self.root/"old-source"), "cells":[]}))
        info = {"digest":"current", "brains":["codex"], "recipe":{"defaults":{}, "replications":{"required_seeds":[11,41]}}}
        with patch.object(self.service, "launch_checkout", return_value=self.root), patch("agent_world.leaderboard_launch.git", side_effect=lambda root,*args: "a"*40 if args[0]=="rev-parse" else ""), patch("agent_world.leaderboard_launch.subprocess.check_output", return_value=json.dumps(info)) as query:
            sources = self.service.sources()
        self.assertEqual(list(sources), ["participant-test@current"])
        self.assertEqual(query.call_count, 1)
        self.assertEqual(query.call_args.kwargs["cwd"], self.root)

    def test_recovered_run_clears_stale_monitor_blocker(self):
        from datetime import datetime, timezone
        folder=self.root / "runs/jobs/web-test"
        folder.mkdir(parents=True)
        (folder / "job.json").write_text("{}")
        heartbeat={"checked_at_utc": datetime.now(timezone.utc).isoformat(),
                   "cells": [{"controller_state": "running", "tick": 21}]}
        (folder / "controller-heartbeat.json").write_text(json.dumps(heartbeat))
        self.service.update(self.identifier, state="needs_attention", assignment_ready=True,
                            supervisor_thread_id="shared-monitor", supervisor_state="watching",
                            monitor_reviewed=True, monitor_resolution="external_blocker")
        r=self.service.public_request(self.service.get(self.identifier))
        self.assertEqual(r["state"], "supervising")
        self.assertFalse(r["can_reconnect"])
        self.assertFalse(r["monitor_reviewed"])
        self.service.update(self.identifier, state="needs_attention", monitor_resolution="evidence_decision")
        r=self.service.public_request(self.service.get(self.identifier))
        self.assertEqual(r["state"], "needs_attention")
        self.assertEqual(r["supervisor_state"], "attention_required")
        self.assertFalse(r["can_reconnect"])

    def test_startup_card_excludes_experiments_and_existing_jobs(self):
        self.service.update(self.identifier, state="queued", run_kind="experiment")
        r=self.service.public_request(self.service.get(self.identifier))
        self.assertEqual(r["run_kind"], "experiment")
        self.service.update(self.identifier, run_kind="benchmark")
        self.assertTrue(self.service.public_request(self.service.get(self.identifier))["startup_pending"])
        folder=self.root / "runs/jobs/web-test"
        folder.mkdir(parents=True)
        (folder / "job.json").write_text(json.dumps({"kind":"benchmark"}))
        self.assertFalse(self.service.public_request(self.service.get(self.identifier))["startup_pending"])

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

    def test_sparse_monitor_records_do_not_break_portal_batch(self):
        other = "b" * 32
        with self.service.connection() as db:
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?)", (
                other, "monitored-experiment", "supervising", time.time(), time.time(),
                json.dumps({"run_id": "monitored-experiment", "run_kind": "experiment",
                            "brain": "codex", "model": "gpt-test"})))
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?)", (
                "c" * 32, "adopted-benchmark", "supervising", time.time(), time.time(),
                json.dumps({"run_id": "adopted-benchmark", "run_kind": "benchmark",
                            "brain": "claude", "model": "claude-test"})))
        with patch.object(self.service, "validate_source"), patch.object(self.service, "ensure_worker"):
            result = self.service.start_batch({"request_ids": [self.identifier]})
        self.assertEqual(result["results"][0]["request"]["state"], "queued")
        self.assertTrue(self.service.get(self.identifier)["dispatch_ready"])

    def test_legacy_recipe_id_still_blocks_duplicate_benchmark(self):
        with self.service.connection() as db:
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?,?)", (
                "b" * 32, "legacy-benchmark", "supervising", time.time(), time.time(),
                json.dumps({"run_id": "legacy-benchmark", "recipe_id": "participant-test",
                            "brain": "codex", "model": "gpt-test"})))
        with self.assertRaisesRegex(LaunchError, "already has an active"):
            self.service.start({"request_id": self.identifier})

    def test_experiment_job_does_not_block_same_model_benchmark(self):
        path = self.root / "runs/jobs/experiment/job.json"
        path.parent.mkdir(parents=True)
        job = {"run_id": "experiment", "kind": "experiment", "protocol": "participant-test",
               "config": {"model": {"brain": "codex", "id": "gpt-test"}},
               "controller": {"status": "running"}}
        path.write_text(json.dumps(job))
        with patch.object(self.service, "validate_source"), patch.object(self.service, "ensure_worker"):
            self.assertEqual(self.service.start({"request_id": self.identifier})["state"], "queued")

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

    def test_fable_preview_records_single_seed_without_changing_recipe(self):
        source = {"id": "test", "recipe_id": "participant-v8-revised", "digest": "hash",
                  "source": str(self.root), "commit": "abc", "brains": ["claude"],
                  "seeds": [11, 41], "defaults": {"reasoning_effort": "medium"}}
        checked = Mock(stdout=json.dumps({"launch_commit": "abc", "orchestrator_commit": "abc"}))
        with patch.object(self.service, "catalog", return_value={"blocker": None, "sources": {"test": source}}), \
             patch.object(self.service, "launch_checkout", return_value=self.root), \
             patch("agent_world.leaderboard_launch.subprocess.run", return_value=checked):
            result = self.service.preview({"recipe": "test", "brain": "claude", "model": "claude-fable-5-1"})
        self.assertEqual(result["seeds"], [41])
        saved = self.service.get(result["id"])
        self.assertEqual(json.loads(Path(saved["config_path"]).read_text())["seeds"], [41])
        self.assertEqual(source["seeds"], [11, 41])

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

    def test_cell_attention_can_record_external_blocker_with_running_controller(self):
        self.service.update(self.identifier, state="supervising")
        path = self.root / "runs/jobs/web-test/job.json"
        path.parent.mkdir(parents=True)
        job = {"controller": {"status": "running"}, "cells": [
            {"id": "seed-11", "controller_state": "needs_attention",
             "controller_attention": "decisions_unusable"},
            {"id": "seed-41", "controller_state": "waiting_startup_gate"},
        ]}
        path.write_text(json.dumps(job))
        with self.assertRaisesRegex(LaunchError, "Repairable faults"):
            self.service.monitoring_ack(self.identifier)
        self.service.monitoring_ack(
            self.identifier, "external_blocker", "Required provider interface unavailable")
        request = self.service.get(self.identifier)
        self.assertEqual(request["monitor_resolution"], "external_blocker")
        self.assertEqual(request["monitor_reviewed_incident"],
                         self.service.monitoring_incident(job))
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
