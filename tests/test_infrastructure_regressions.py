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
