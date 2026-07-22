from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from agent_world.brain_factory import BrainSpec, PopulationGroup, PopulationSpec
from agent_world.brain_runtime import BrainRuntime
from agent_world.models import AgentDecision, WorldConfig
from agent_world.persistence import IncrementalRunWriter
from agent_world.session import SimulationSession
from agent_world.world import WorldEngine


class SimulationSessionTests(unittest.TestCase):
    def test_session_owns_lifecycle_persistence_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = WorldEngine.create(WorldConfig(seed=4), agent_names=["A1"])
            session = SimulationSession(
                engine=engine,
                brain_spec=BrainSpec.resolve("survival"),
                runtime=BrainRuntime(),
                writer=IncrementalRunWriter(
                    root / "run.jsonl",
                    root / "run-snapshot.json",
                    checkpoint_path=root / "run-checkpoint.pkl",
                    fsync=False,
                ),
                target_ticks=2,
                log_agent_io=False,
                report_stem=root / "run",
            )

            result = session.run()

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.final_tick, 2)
            self.assertIsNotNone(result.report)
            self.assertTrue((root / "run-report.json").exists())
            self.assertTrue((root / "run-report.md").exists())
            event_types = [event.type for event in engine.state.events]
            self.assertEqual(event_types.count("run_started"), 1)
            self.assertEqual(event_types.count("run_completed"), 1)

    def test_session_honors_external_stop_hook(self) -> None:
        engine = WorldEngine.create(WorldConfig(seed=5), agent_names=["A1"])
        session = SimulationSession(
            engine=engine,
            brain_spec=BrainSpec.resolve("survival"),
            runtime=BrainRuntime(),
            writer=IncrementalRunWriter(None, None, fsync=False),
            target_ticks=10,
            before_tick=lambda: engine.state.tick >= 2,
            log_agent_io=False,
        )

        result = session.run()

        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.stop_reason, "stop_requested")
        self.assertEqual(result.final_tick, 2)

    def test_session_stops_all_entry_points_on_quota_failure(self) -> None:
        class QuotaBrain:
            def decide(self, _observation):
                return AgentDecision(
                    intent="Codex quota unavailable: test limit",
                    actions=[{"type": "wait"}],
                )

        engine = WorldEngine.create(WorldConfig(seed=6), agent_names=["A1"])
        session = SimulationSession(
            engine=engine,
            brain_spec=BrainSpec(
                type="codex",
                model="gpt-5.6-luna",
                reasoning_effort="low",
                max_workers=1,
            ),
            runtime=BrainRuntime(),
            writer=IncrementalRunWriter(None, None, fsync=False),
            target_ticks=10,
            brains={"agent-1": QuotaBrain()},
            log_agent_io=False,
        )

        result = session.run()

        self.assertEqual(result.status, "paused_checkpoint")
        self.assertEqual(result.stop_reason, "insufficient_quota")
        self.assertEqual(result.final_tick, 0)
        self.assertEqual([event.type for event in engine.state.events].count("run_paused"), 1)
        self.assertNotIn("agent_response", [event.type for event in engine.state.events])

    def test_session_preflight_stops_before_any_provider_decision(self) -> None:
        class LoggedOutBrain:
            decisions = 0

            def preflight(self):
                return "Claude provider unavailable: Claude Code is not logged in"

            def decide(self, _observation):
                self.decisions += 1
                return AgentDecision(intent="wait", actions=[{"type": "wait"}])

        brain = LoggedOutBrain()
        engine = WorldEngine.create(WorldConfig(seed=7), agent_names=["A1"])
        session = SimulationSession(
            engine=engine,
            brain_spec=BrainSpec(type="claude", model="claude-sonnet-5"),
            runtime=BrainRuntime(),
            writer=IncrementalRunWriter(None, None, fsync=False),
            target_ticks=10,
            brains={"agent-1": brain},
            log_agent_io=False,
        )

        result = session.run()

        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.stop_reason, "provider_unavailable")
        self.assertEqual(result.final_tick, 0)
        self.assertEqual(brain.decisions, 0)
        self.assertEqual([event.type for event in engine.state.events].count("run_stopped"), 1)

    def test_session_shares_preflight_state_across_matching_brains(self) -> None:
        class ResolvingBrain:
            preflight_calls = 0

            def __init__(self):
                self.model = "cursor-grok-4.5"
                self.reasoning_effort = "medium"
                self.resolved_model = self.model
                self.runtime = BrainRuntime()

            def preflight(self):
                type(self).preflight_calls += 1
                self.resolved_model = "cursor-grok-4.5-medium"
                return None

            def copy_preflight_state_from(self, other):
                self.resolved_model = other.resolved_model

            def decide(self, _observation):
                return AgentDecision(intent=self.resolved_model, actions=[{"type": "wait"}])

        ResolvingBrain.preflight_calls = 0
        first = ResolvingBrain()
        second = ResolvingBrain()
        engine = WorldEngine.create(WorldConfig(seed=71), agent_names=["A1", "A2"])
        cursor = BrainSpec(type="cursor", model="cursor-grok-4.5", reasoning_effort="medium")
        session = SimulationSession(
            engine=engine,
            brain_spec=cursor,
            runtime=BrainRuntime(),
            writer=IncrementalRunWriter(None, None, fsync=False),
            target_ticks=1,
            brains={"agent-1": first, "agent-2": second},
            log_agent_io=False,
        )

        result = session.run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(ResolvingBrain.preflight_calls, 1)
        self.assertEqual(first.resolved_model, "cursor-grok-4.5-medium")
        self.assertEqual(second.resolved_model, "cursor-grok-4.5-medium")

    def test_session_stops_systematically_unhealthy_cohort_at_health_gate(self) -> None:
        class FailedBrain:
            def decide(self, _observation):
                return AgentDecision(
                    intent="Cursor decision failed: bad model alias",
                    actions=[{"type": "wait"}],
                )

        engine = WorldEngine.create(WorldConfig(seed=72), agent_names=["A1", "A2"])
        cursor = BrainSpec(type="cursor", model="cursor-grok-4.5", reasoning_effort="medium")
        session = SimulationSession(
            engine=engine,
            brain_spec=cursor,
            runtime=BrainRuntime(),
            writer=IncrementalRunWriter(None, None, fsync=False),
            target_ticks=10,
            brains={"agent-1": FailedBrain(), "agent-2": FailedBrain()},
            log_agent_io=False,
            startup_health_check_tick=2,
        )

        result = session.run()

        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.stop_reason, "startup_health_check_failed")
        self.assertEqual(result.final_tick, 2)
        health = next(event for event in engine.state.events if event.type == "run_health_check")
        self.assertEqual(health.data["status"], "failed")
        self.assertEqual(health.data["cohorts"][0]["decision_failures"], 4)

    def test_session_health_gate_ignores_isolated_response_failure(self) -> None:
        class OneFailureBrain:
            def __init__(self):
                self.calls = 0

            def decide(self, _observation):
                self.calls += 1
                intent = "Invalid JSON response: test" if self.calls == 1 else "wait"
                return AgentDecision(intent=intent, actions=[{"type": "wait"}])

        class HealthyBrain:
            def decide(self, _observation):
                return AgentDecision(intent="wait", actions=[{"type": "wait"}])

        engine = WorldEngine.create(WorldConfig(seed=73), agent_names=["A1", "A2"])
        cursor = BrainSpec(type="cursor", model="cursor-grok-4.5", reasoning_effort="medium")
        session = SimulationSession(
            engine=engine,
            brain_spec=cursor,
            runtime=BrainRuntime(),
            writer=IncrementalRunWriter(None, None, fsync=False),
            target_ticks=3,
            brains={"agent-1": OneFailureBrain(), "agent-2": HealthyBrain()},
            log_agent_io=False,
            startup_health_check_tick=2,
        )

        result = session.run()

        self.assertEqual(result.status, "completed")
        health = next(event for event in engine.state.events if event.type == "run_health_check")
        self.assertEqual(health.data["status"], "passed")

    def test_session_discards_tick_when_provider_becomes_unavailable(self) -> None:
        class ProviderFailureBrain:
            def decide(self, _observation):
                return AgentDecision(
                    intent="Codex provider unavailable: stream disconnected",
                    actions=[{"type": "wait"}],
                )

        engine = WorldEngine.create(WorldConfig(seed=9), agent_names=["A1"])
        session = SimulationSession(
            engine=engine,
            brain_spec=BrainSpec(
                type="codex",
                model="gpt-5.6-luna",
                reasoning_effort="low",
                max_workers=1,
            ),
            runtime=BrainRuntime(),
            writer=IncrementalRunWriter(None, None, fsync=False),
            target_ticks=10,
            brains={"agent-1": ProviderFailureBrain()},
            log_agent_io=False,
        )

        result = session.run()

        self.assertEqual(result.status, "paused_checkpoint")
        self.assertEqual(result.stop_reason, "provider_unavailable")
        self.assertEqual(result.final_tick, 0)
        self.assertEqual([event.type for event in engine.state.events].count("run_paused"), 1)
        self.assertNotIn("agent_response", [event.type for event in engine.state.events])

    def test_session_records_mixed_population_and_report_cohorts(self) -> None:
        class WaitBrain:
            def decide(self, _observation):
                return AgentDecision(intent="wait", actions=[{"type": "wait"}])

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = WorldEngine.create(WorldConfig(seed=8), agent_names=["A1", "A2"])
            luna = BrainSpec(type="codex", model="gpt-5.6-luna", reasoning_effort="low", max_workers=2)
            sonnet = BrainSpec(type="claude", model="claude-sonnet-5", reasoning_effort="low", max_workers=2)
            population = PopulationSpec(
                (
                    PopulationGroup(1, sonnet, "cohort-1"),
                    PopulationGroup(1, luna, "cohort-2"),
                )
            )
            session = SimulationSession(
                engine=engine,
                brain_spec=sonnet,
                population_spec=population,
                runtime=BrainRuntime(),
                writer=IncrementalRunWriter(None, None, fsync=False),
                target_ticks=1,
                brains={"agent-1": WaitBrain(), "agent-2": WaitBrain()},
                log_agent_io=False,
                report_stem=Path(temp_dir) / "mixed",
            )

            result = session.run()

            started = next(event for event in engine.state.events if event.type == "run_started")
            self.assertEqual(started.data["brain"], "mixed")
            self.assertEqual(started.data["population"]["assignments"]["agent-1"], "cohort-1")
            self.assertEqual(result.report["population"]["cohorts"]["cohort-1"]["model"], "claude-sonnet-5")


if __name__ == "__main__":
    unittest.main()
