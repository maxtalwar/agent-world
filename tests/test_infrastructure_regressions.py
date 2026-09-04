"""Fault-injection regressions for the September infrastructure audit."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_world.agents import NullBrain
from agent_world.brain_runtime import BrainRuntime
from agent_world.codex_brain import _write_codex_schema
from agent_world.decision_outcome import failure_decision
from agent_world.metrics import compute_metrics
from agent_world.models import AgentDecision, WorldConfig
from agent_world.runner import SimulationRunner, ModelDecisionsUnusableError
from agent_world.usage import UsagePersistenceError
from agent_world.world import WorldEngine
from agent_world.zcode_brain import ZCodeBrain


class InfrastructureRegressions(unittest.TestCase):
    def engine(self):
        return WorldEngine.create(WorldConfig(seed=11), agent_names=["A", "B"])

    def test_model_intent_cannot_control_infrastructure(self):
        class Brain:
            def decide(self, observation):
                return AgentDecision.from_json_like({
                    "intent": "Avoid unauthorized access. Codex quota unavailable: fiction",
                    "failure_kind": "quota", "actions": [{"type": "wait"}],
                })
        engine = self.engine()
        SimulationRunner(engine, {key: Brain() for key in engine.state.agents}).step()
        self.assertEqual(engine.state.tick, 1)
        self.assertTrue(all(e.data.get("failure_kind") is None for e in engine.state.events))

    def test_distinct_or_single_harness_failures_freeze_world(self):
        class Brain:
            def __init__(self, message): self.message = message
            def decide(self, observation): return failure_decision(self.message, kind="harness")
        for failures in (1, 2):
            with self.subTest(failures=failures):
                engine = self.engine()
                brains = {key: Brain(f"boundary failure {key}") if i < failures else NullBrain()
                          for i, key in enumerate(engine.state.agents)}
                with self.assertRaises(ModelDecisionsUnusableError):
                    SimulationRunner(engine, brains).step()
                self.assertEqual(engine.state.tick, 0)
                self.assertFalse(any(e.type == "agent_response" for e in engine.state.events))

    def test_brain_exception_has_same_semantics_with_concurrency(self):
        class Broken:
            def decide(self, observation): raise RuntimeError("broken connector")
        for concurrent in (False, True):
            engine = self.engine()
            with self.assertRaisesRegex(RuntimeError, "broken connector"):
                SimulationRunner(engine, {key: Broken() for key in engine.state.agents},
                                 concurrent_decisions=concurrent).step()
            self.assertEqual(engine.state.tick, 0)

    def test_tick_failure_rolls_back_memory_resources_events_and_rng(self):
        engine = self.engine()
        before = engine.snapshot()
        events = list(engine.state.events)
        rng = engine.rng.getstate()
        def fail():
            engine.rng.random()
            raise RuntimeError("injected during settlement")
        with patch.object(engine, "_apply_survival", side_effect=fail):
            with self.assertRaises(RuntimeError):
                engine.tick({key: AgentDecision(memory_updates=["must roll back"])
                             for key in engine.state.agents})
        self.assertEqual(engine.snapshot(), before)
        self.assertEqual(engine.state.events, events)
        self.assertEqual(engine.rng.getstate(), rng)

    def test_malformed_agreement_is_rejected_without_crash(self):
        engine = self.engine()
        engine.tick({"agent-1": AgentDecision(actions=[
            {"type": "record_agreement", "text": "pact", "parties": None}])})
        self.assertEqual(engine.state.tick, 1)
        self.assertTrue(any(e.type == "invalid_action" for e in engine.state.events))

    def test_schema_paths_are_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            a = _write_codex_schema(path, {"maxItems": 4})
            b = _write_codex_schema(path, {"maxItems": 8})
            self.assertNotEqual(a, b)
            self.assertEqual(json.loads(a.read_text()), {"maxItems": 4})

    def test_usage_persistence_failure_is_fatal_and_not_acknowledged(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = BrainRuntime(usage_path=Path(tmp), provider_events_path=Path(tmp)/"events")
            with self.assertRaises(UsagePersistenceError):
                runtime.record_usage({"agent_id": "agent-1"})
            self.assertEqual(runtime.usage_records(), [])

    def test_zcode_accepts_canonical_and_legacy_boundary_names(self):
        for connector, conversation in (("connector-v1", "fresh-conversation"),
                                        ("stateless-v1", "stateless")):
            brain = ZCodeBrain(executable="/fake/zcode", connector_profile=connector,
                               conversation_mode=conversation)
            self.assertEqual(brain.connector_profile, "connector-v1")
            self.assertEqual(brain.conversation_mode, "fresh-conversation")

    def test_checkpoint_rejects_equal_length_corruption_and_prefers_relocated_ledger(self):
        from agent_world.persistence import IncrementalRunWriter, load_run_checkpoint
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original, moved = root/"original", root/"moved"
            original.mkdir()
            engine = self.engine()
            engine.tick({})
            writer = IncrementalRunWriter(original/"events.jsonl", original/"snapshot.json",
                                          checkpoint_path=original/"checkpoint.pkl")
            writer.flush(engine)
            shutil.copytree(original, moved)
            # Relocated evidence must not silently read the original absolute path.
            path = moved/"events.jsonl"
            data = path.read_bytes()
            self.assertIn(b'"tick": 0', data)
            path.write_bytes(data.replace(b'"tick": 0', b'"tick": 9', 1))
            with self.assertRaisesRegex(ValueError, "integrity"):
                load_run_checkpoint(moved/"checkpoint.pkl")
            loaded, _ = load_run_checkpoint(original/"checkpoint.pkl")
            self.assertEqual(loaded.state.tick, 1)

    def test_duplicate_usage_cannot_cover_a_missing_agent(self):
        from agent_world.run_report import build_report
        engine = self.engine()
        engine.tick({})
        report = build_report([e.to_dict() for e in engine.state.events], engine.snapshot(),
                              [{"tick": 0, "agent_id": "agent-1"}] * 2)
        self.assertEqual(report["reliability"]["usage_record_coverage_pct"], 50)
        self.assertEqual(report["reliability"]["benchmark_integrity_status"], "invalid")

    def test_process_transport_drains_stderr_and_bounds_output(self):
        import sys
        from agent_world.process_transport import run_process, ProcessOutputLimitError
        result = run_process([sys.executable, "-c",
                              "import sys; sys.stderr.write('x'*200000); print('ok')"],
                             text=True, timeout=2)
        self.assertEqual(result.stdout.strip(), "ok")
        self.assertEqual(len(result.stderr), 200000)
        with self.assertRaises(ProcessOutputLimitError):
            run_process([sys.executable, "-c", "print('x'*200000)"],
                        max_output_bytes=1024, timeout=2)

    def test_process_timeout_reaps_group_with_child_holding_pipes(self):
        import subprocess
        import sys
        import time
        from agent_world.process_transport import run_process
        script = "import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])"
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            run_process([sys.executable, "-c", script], timeout=0.1)
        self.assertLess(time.monotonic() - started, 2)

    def test_partial_line_cannot_defeat_app_server_deadline(self):
        import subprocess
        import sys
        import time
        from agent_world.codex_brain import _read_app_server_response
        process = subprocess.Popen([sys.executable, "-c",
                                    "import sys,time; sys.stdout.write('{'); sys.stdout.flush(); time.sleep(1)"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        started = time.monotonic()
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                _read_app_server_response(process, 1, started + 0.05)
            self.assertLess(time.monotonic() - started, 0.5)
        finally:
            process.kill()
            process.wait()
            process.stdout.close()
            process.stderr.close()

    def test_drip_http_body_obeys_wall_deadline(self):
        import threading
        import time
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from agent_world.openrouter_brain import OpenRouterBrain, OpenRouterHardDeadlineError
        class Slow(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(200)
                self.send_header("Content-Length", "100")
                self.end_headers()
                try:
                    for _ in range(100):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                        time.sleep(0.025)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        brain = OpenRouterBrain(api_key="synthetic",
                                base_url=f"http://127.0.0.1:{server.server_port}",
                                timeout_seconds=0.08, hard_deadline_grace_seconds=0.02,
                                min_request_interval_seconds=0)
        started = time.monotonic()
        try:
            with self.assertRaises(OpenRouterHardDeadlineError):
                brain._post_json("/test", {})
            self.assertLess(time.monotonic() - started, 0.5)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_provider_ready_scheduler_does_not_starve_another_provider(self):
        import threading
        from types import SimpleNamespace
        started = threading.Event()
        class Slow:
            runtime = SimpleNamespace(scope="slow")
            def decide(self, observation):
                if not started.wait(1):
                    raise RuntimeError("other provider was starved")
                return AgentDecision()
        class Fast:
            runtime = SimpleNamespace(scope="fast")
            def decide(self, observation):
                started.set()
                return AgentDecision()
        engine = WorldEngine.create(WorldConfig(seed=11), agent_names=["A", "B", "C"])
        SimulationRunner(engine, {"agent-1": Slow(), "agent-2": Slow(), "agent-3": Fast()},
                         concurrent_decisions=True, max_workers=2,
                         provider_max_workers={"slow": 1}).step()
        self.assertEqual(engine.state.tick, 1)

    def test_pending_journal_rejects_changed_execution_identity(self):
        from agent_world.runner import PendingTickJournal
        class Fixed:
            def __init__(self, intent): self.intent = intent
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"pending.json"
            first = PendingTickJournal(path, tick=0, observations={"a": {}}, brains={"a": Fixed("old")})
            first.record_decision("a", AgentDecision(intent="old"))
            second = PendingTickJournal(path, tick=0, observations={"a": {}}, brains={"a": Fixed("new")})
            self.assertEqual(second.decisions, {})

    def test_jsonl_tail_handles_append_partial_line_and_replacement(self):
        from agent_world.jsonl_tail import JsonlTail
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"events"
            path.write_text('{"type":"first"}\n{"type":')
            reader = JsonlTail(path)
            self.assertEqual(len(reader.read()), 1)
            with path.open("a") as handle:
                handle.write('"second"}\n')
            self.assertEqual([row["type"] for row in reader.read()], ["first", "second"])
            path.write_text('{"type":"third"}\n')
            self.assertEqual(reader.read(), [{"type": "third"}])

    def test_snapshot_ring_keeps_latest_ticks(self):
        from agent_world.observer import SnapshotHistory
        history = SnapshotHistory(Path("/unused"), max_ticks=2)
        for tick in range(4): history.record({"tick": tick})
        self.assertIsNone(history.get(0))
        self.assertEqual(history.tick_range(), {"min_tick": 2, "max_tick": 3, "count": 2})

    def test_history_policy_is_versioned_and_preserves_active_contracts(self):
        from agent_world.observation_policy import apply_history_policy
        import copy
        observation = {"known_contracts": [{"id": str(i), "status": "fulfilled"} for i in range(1000)] +
                       [{"id": "active", "status": "active"}],
                       "known_groups": {"g": {"rules": list(range(20)), "agreements": []}}}
        original = copy.deepcopy(observation)
        self.assertEqual(apply_history_policy(copy.deepcopy(observation), "full-v1"), original)
        bounded = apply_history_policy(observation, "bounded-v1")
        self.assertEqual(len(bounded["known_contracts"]), 13)
        self.assertEqual(bounded["known_contracts"][0]["id"], "active")
        self.assertEqual(bounded["history_policy"]["omitted"]["contracts"], 988)

    def test_world_config_rejects_boolean_integer_and_nonfinite_values(self):
        for values in ({"width": True}, {"resource_base_multiplier": float("nan")},
                       {"water_water_regen": float("inf")}, {"season_length_ticks": 0}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                WorldConfig(**values)

    def test_physical_request_budget_survives_failed_attempt_and_blocks_next(self):
        import sys
        from agent_world.process_transport import run_process
        from agent_world.request_context import request_context, RunBudgetExceeded
        runtime = BrainRuntime()
        runtime.configure_limits({"calls": 1})
        with request_context(runtime, "agent-1", 0):
            run_process([sys.executable, "-c", "print('ok')"], timeout=2)
            with self.assertRaises(RunBudgetExceeded):
                run_process([sys.executable, "-c", "print('must not start')"], timeout=2)
        self.assertEqual(runtime.provider_event_summary()["request_started"], 1)

    def test_exposed_tool_activity_is_rejected(self):
        from agent_world.tool_boundary import validate_tool_trace, ToolBoundaryError
        with self.assertRaises(ToolBoundaryError):
            validate_tool_trace('{"type":"item.completed","item":{"type":"command_execution","command":"whoami"}}')
        validate_tool_trace('{"type":"agent_message","text":"ordinary text mentioning tools"}')

    def test_poisoned_writer_cannot_publish_a_later_generation(self):
        from agent_world.persistence import IncrementalRunWriter
        writer = IncrementalRunWriter(None, None)
        with patch.object(writer, "_flush", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                writer.flush(self.engine())
        with self.assertRaisesRegex(RuntimeError, "previously failed"):
            writer.flush(self.engine())

    def test_every_connector_constructs_through_the_real_factory(self):
        import os
        from agent_world.brain_factory import BrainSpec, PopulationSpec, create_population_brains
        environment = {name + "_EXECUTABLE": "/bin/true" for name in
                       ("CODEX", "CLAUDE", "CURSOR", "DEVIN", "GROK", "ZCODE")}
        environment["OPENROUTER_API_KEY"] = "synthetic-no-network"
        with patch.dict(os.environ, environment):
            for provider in ("openrouter", "codex", "claude", "cursor", "devin", "grok", "zcode"):
                for profile, mode in (("connector-v1", "fresh-conversation"), ("stateless-v1", "stateless")):
                    with self.subTest(provider=provider, profile=profile):
                        engine = self.engine()
                        spec = BrainSpec.resolve(provider, connector_profile=profile, conversation_mode=mode)
                        brains = create_population_brains(engine, PopulationSpec.uniform(2, spec), BrainRuntime())
                        self.assertEqual(set(brains), set(engine.state.agents))

    def test_concurrent_exception_preserves_other_completed_decisions(self):
        from agent_world.runner import PendingTickJournal
        class Broken:
            def decide(self, observation): raise RuntimeError("injected")
        class Good:
            def decide(self, observation): return AgentDecision(intent="accepted")
        with tempfile.TemporaryDirectory() as tmp:
            engine = self.engine()
            runner = SimulationRunner(engine, {"agent-1": Broken(), "agent-2": Good()},
                                      concurrent_decisions=True, max_workers=2,
                                      pending_tick_path=Path(tmp)/"pending.json")
            with self.assertRaises(RuntimeError): runner.step()
            self.assertEqual(runner.cached_decision_count, 1)
            self.assertEqual(engine.state.tick, 0)

    def test_durable_ledger_reader_keeps_prefix_and_rejects_middle_corruption(self):
        from agent_world.io import read_jsonl_records
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"ledger"
            path.write_text('{"id":1}\n{"id":')
            self.assertEqual(read_jsonl_records(path), [{"id": 1}])
            path.write_text('{"id":1}\nbroken\n{"id":2}\n')
            with self.assertRaises(ValueError): read_jsonl_records(path)

    def test_managed_observer_selection_survives_client_restart(self):
        from agent_world.managed_observer import ManagedObserverClient
        from agent_world.observer import _parse_run_config
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cell = {"snapshot": str(root/"managed-snapshot.json"), "events": str(root/"managed.jsonl")}
            config = _parse_run_config({"brain": "codex", "model": "fixture-model"})
            fake_status = {"cells": [{"state": "running", "tick": 3}]}
            with patch("agent_world.managed_runs.launch_config", return_value={"cells": [cell]}) as launch, patch(
                    "agent_world.managed_runs.job_status", return_value=fake_status):
                first = ManagedObserverClient(root/"snapshot.json", root/"events.jsonl")
                status, response = first.start(config)
                self.assertEqual(status, 202)
                self.assertEqual(launch.call_count, 1)
                second = ManagedObserverClient(root/"snapshot.json", root/"events.jsonl")
                self.assertEqual(second.status()["current_tick"], 3)
                second.control("pause")
                self.assertTrue(second.status()["paused"])

    def test_export_inventory_uses_relative_paths_and_verifies_checksums(self):
        from agent_world.artifacts import export_job
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_dir, output = root/"job", root/"output"
            job_dir.mkdir()
            output.mkdir()
            (output/"run.jsonl").write_text('{"type":"test"}\n')
            (output/".env").write_text("SECRET=must-not-export")
            job = {"source_root": str(root), "job_dir": str(job_dir),
                   "cells": [{"output_dir": str(output)}]}
            with patch("agent_world.artifacts.load_job", return_value=job), patch(
                    "agent_world.artifacts._tmux_active", return_value=False):
                manifest = export_job("fixture", root/"export")
            self.assertEqual(len(manifest["files"]), 1)
            self.assertEqual(manifest["files"][0]["export_path"], "output/run.jsonl")
            self.assertFalse((root/"export/output/.env").exists())
            self.assertTrue((root/"export/export-manifest.json").is_file())

    def test_offline_report_preserves_plan_usage_summary(self):
        from agent_world.run_report import write_report
        with tempfile.TemporaryDirectory() as tmp:
            stem = Path(tmp)/"run"
            summary = {"available": True, "buckets": {}}
            (Path(tmp)/"run-plan-usage.json").write_text(json.dumps({
                "schema_version": 1, "checkpoints": [], "summary": summary,
            }))
            engine = self.engine()
            report = write_report([e.to_dict() for e in engine.state.events], engine.snapshot(), [], stem)
            self.assertEqual(report["usage"]["plan_limits"], summary)

    def test_report_reads_only_committed_prefix_after_torn_append(self):
        from agent_world.persistence import IncrementalRunWriter
        from agent_world.run_report import load_run_files
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = self.engine()
            writer = IncrementalRunWriter(root/"run.jsonl", root/"run-snapshot.json",
                                          checkpoint_path=root/"run-checkpoint.pkl")
            writer.flush(engine)
            with (root/"run.jsonl").open("ab") as handle:
                handle.write(b'{"tick":')
            events, snapshot, usage = load_run_files(root/"run")
            self.assertEqual(events, [e.to_dict() for e in engine.state.events])
            self.assertEqual(snapshot["tick"], 0)

    def test_request_admission_identity_and_limit_survive_restart_without_usage(self):
        from agent_world.request_context import request_context, admit_attempt, RunBudgetExceeded
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"provider-events.jsonl"
            first = BrainRuntime(provider_events_path=path)
            first.configure_limits({"calls": 1})
            with request_context(first, "agent-1", 0): admit_attempt()
            restarted = BrainRuntime(provider_events_path=path, truncate_provider_events=False)
            restarted.configure_limits({"calls": 1})
            self.assertEqual(restarted.run_identity, first.run_identity)
            with request_context(restarted, "agent-1", 0), self.assertRaises(RunBudgetExceeded):
                admit_attempt()

    def test_failed_pending_write_does_not_acknowledge_cached_decision(self):
        from agent_world.runner import PendingTickJournal
        from agent_world.interface import build_observation
        engine = self.engine()
        observations = {key: build_observation(engine.state, key) for key in engine.state.agents}
        with tempfile.TemporaryDirectory() as tmp:
            journal = PendingTickJournal(Path(tmp)/"pending.json", tick=0, observations=observations,
                                         brains={key: NullBrain() for key in observations})
            with patch("agent_world.runner.atomic_write_json", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    journal.record_decision("agent-1", AgentDecision(intent="accepted only after fsync"))
            self.assertEqual(journal.decisions, {})

    def test_pinned_worktree_resolves_the_canonical_job_store(self):
        import subprocess
        from agent_world.managed_runs import _canonical_root
        with tempfile.TemporaryDirectory() as tmp:
            root, linked = Path(tmp)/"repo", Path(tmp)/"linked"
            root.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
            git("init", "-q")
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "--allow-empty", "-qm", "Fixture")
            git("worktree", "add", "--detach", str(linked), "HEAD")
            with patch("agent_world.managed_runs.Path.cwd", return_value=linked):
                self.assertEqual(_canonical_root(), root)

    def test_historical_cells_pin_current_orchestration_separately(self):
        from agent_world.managed_runs import build_launch_plan
        config = {"run_id": "fixture", "kind": "benchmark", "protocol": "participant-v6",
                  "source": {"commit": "old"}, "seeds": [11], "model": {"brain": "codex", "id": "fixture"}}
        with patch("agent_world.managed_runs._git", side_effect=["a"*40, "b"*40]):
            plan = build_launch_plan(config, Path("/fixture"))
        self.assertEqual(plan["launch_commit"], "a"*40)
        self.assertEqual(plan["orchestrator_commit"], "b"*40)

    def test_append_after_torn_usage_write_retains_complete_prefix(self):
        from agent_world.usage import append_usage_record
        from agent_world.io import read_jsonl_records
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"usage.jsonl"
            for tail in (b'{"id":', b'{"id":2}'):
                path.write_bytes(b'{"id":1}\n' + tail)
                append_usage_record({"id": 3}, path)
                expected = [{"id": 1}, {"id": 3}] if tail.endswith(b":") else [{"id": 1}, {"id": 2}, {"id": 3}]
                self.assertEqual(read_jsonl_records(path), expected)
