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
