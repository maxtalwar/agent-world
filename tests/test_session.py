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

        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.stop_reason, "insufficient_quota")
        self.assertEqual(result.final_tick, 1)
        self.assertEqual([event.type for event in engine.state.events].count("run_stopped"), 1)

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
