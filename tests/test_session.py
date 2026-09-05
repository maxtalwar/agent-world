from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from agent_world.benchmarks import (
    BENCHMARK_DIAGNOSTIC_TICKS,
    BENCHMARK_PROTOCOL_ID,
    benchmark_code_fingerprint,
)
from agent_world.brain_factory import BrainSpec, PopulationGroup, PopulationSpec
from agent_world.brain_runtime import BrainRuntime
from agent_world.decision_outcome import failure_decision
from agent_world.models import AgentDecision, WorldConfig
from agent_world.persistence import IncrementalRunWriter, load_run_checkpoint
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

    def test_session_persists_benchmark_score_trajectory_in_event_log(self) -> None:
        class WaitBrain:
            def decide(self, _observation):
                return AgentDecision(intent="wait", actions=[{"type": "wait"}])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = WorldEngine.create(WorldConfig(seed=51), agent_names=["A1"])
            session = SimulationSession(
                engine=engine,
                brain_spec=BrainSpec.resolve("survival"),
                runtime=BrainRuntime(),
                writer=IncrementalRunWriter(
                    root / "run.jsonl",
                    root / "run-snapshot.json",
                    fsync=False,
                ),
                target_ticks=50,
                brains={"agent-1": WaitBrain()},
                lifecycle_metadata={
                    "benchmark_protocol": BENCHMARK_PROTOCOL_ID,
                    "benchmark_code_fingerprint": benchmark_code_fingerprint(["codex_cli"]),
                },
                benchmark_checkpoint_ticks=BENCHMARK_DIAGNOSTIC_TICKS,
                report_stem=root / "run",
            )

            result = session.run()

            checkpoints = [
                event
                for event in engine.state.events
                if event.type == "benchmark_checkpoint"
            ]
            self.assertEqual(
                [event.data["tick"] for event in checkpoints],
                [30, 40, 50],
            )
            self.assertTrue(all(event.scope == "private" for event in checkpoints))
            self.assertEqual(
                [row["tick"] for row in result.report["benchmarks"]["trajectory"]],
                [30, 40, 50],
            )
            self.assertEqual(
                [
                    row["role"]
                    for row in result.report["benchmarks"]["trajectory"]
                ],
                [
                    "diagnostic_checkpoint",
                    "diagnostic_checkpoint",
                    "official_endpoint",
                ],
            )
            self.assertEqual(
                [
                    row["cohorts"]["cohort-1"]["raw"]["possible_agent_ticks"]
                    for row in result.report["benchmarks"]["trajectory"]
                ],
                [30, 40, 50],
            )
            self.assertIn(
                "Benchmark score trajectory",
                (root / "run-report.md").read_text(encoding="utf-8"),
            )

    def test_session_stops_all_entry_points_on_quota_failure(self) -> None:
        class QuotaBrain:
            def decide(self, _observation):
                return AgentDecision(
                    failure_kind="quota", intent="Codex quota unavailable: test limit",
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
        self.assertEqual(result.stop_reason, "authentication_required")
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
                    failure_kind="model_output", intent="Cursor model output failed: invalid JSON",
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
                return AgentDecision(failure_kind="model_output" if self.calls == 1 else None, intent=intent, actions=[{"type": "wait"}])

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

    def test_resumed_session_before_gate_still_checks_health(self) -> None:
        class HealthyBrain:
            def decide(self, _observation):
                return AgentDecision(intent="wait", actions=[{"type": "wait"}])

        engine = WorldEngine.create(WorldConfig(seed=11), agent_names=["A1"])
        brain = BrainSpec(type="cursor", model="cursor-grok-4.5", reasoning_effort="low")
        def make_session(target, resumed):
            return SimulationSession(
                engine=engine, brain_spec=brain, runtime=BrainRuntime(),
                writer=IncrementalRunWriter(None, None, fsync=False),
                target_ticks=target, brains={"agent-1": HealthyBrain()},
                log_agent_io=False, startup_health_check_tick=2, resumed=resumed,
            )
        make_session(1, False).run()
        make_session(3, True).run()
        checks = [e for e in engine.state.events if e.type == "run_health_check"]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].tick, 2)
        self.assertEqual(checks[0].data["status"], "passed")
        self.assertEqual(checks[0].data["cohorts"][0]["attempts"], 2)
        make_session(4, True).run()
        self.assertEqual(sum(e.type == "run_health_check" for e in engine.state.events), 1)

    def test_session_discards_tick_when_provider_becomes_unavailable(self) -> None:
        class ProviderFailureBrain:
            def decide(self, _observation):
                return AgentDecision(
                    failure_kind="provider", intent="Codex provider unavailable: stream disconnected",
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

    def test_authentication_pauses_without_provider_retries(self) -> None:
        class AuthenticationBrain:
            def decide(self, _observation):
                return AgentDecision(
                    failure_kind="authentication", intent="Claude authentication required: not logged in",
                    actions=[{"type": "wait"}],
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = WorldEngine.create(WorldConfig(seed=90), agent_names=["A1"])
            result = SimulationSession(
                engine=engine,
                brain_spec=BrainSpec.resolve("survival"),
                runtime=BrainRuntime(),
                writer=IncrementalRunWriter(
                    Path(temp_dir) / "run.jsonl",
                    Path(temp_dir) / "run-snapshot.json",
                    checkpoint_path=Path(temp_dir) / "run-checkpoint.pkl",
                    fsync=False,
                ),
                target_ticks=1,
                brains={"agent-1": AuthenticationBrain()},
                log_agent_io=False,
                startup_health_check_tick=None,
                provider_retry_rounds=2,
            ).run()

        self.assertEqual(result.status, "paused_checkpoint")
        self.assertEqual(result.stop_reason, "authentication_required")
        self.assertEqual(result.final_tick, 0)
        paused = next(
            event for event in engine.state.events if event.type == "run_paused"
        )
        self.assertEqual(paused.data["affected_agent_ids"], ["agent-1"])

    def test_resume_reuses_accepted_decisions_and_calls_only_unresolved_agent(self) -> None:
        class CountingHealthyBrain:
            def __init__(self):
                self.calls = 0

            def decide(self, _observation):
                self.calls += 1
                return AgentDecision(intent="healthy", actions=[{"type": "wait"}])

        class ProviderFailureBrain:
            def __init__(self):
                self.calls = 0

            def decide(self, _observation):
                self.calls += 1
                return AgentDecision(
                    failure_kind="provider", intent="ZCode provider unavailable: exceeded 300s timeout",
                    actions=[{"type": "wait"}],
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            events_path = root / "run.jsonl"
            snapshot_path = root / "run-snapshot.json"
            checkpoint_path = root / "run-checkpoint.pkl"
            first_engine = WorldEngine.create(
                WorldConfig(seed=91), agent_names=["A1", "A2"]
            )
            healthy = CountingHealthyBrain()
            failed = ProviderFailureBrain()
            first = SimulationSession(
                engine=first_engine,
                brain_spec=BrainSpec.resolve("survival"),
                runtime=BrainRuntime(),
                writer=IncrementalRunWriter(
                    events_path,
                    snapshot_path,
                    checkpoint_path=checkpoint_path,
                    fsync=False,
                ),
                target_ticks=1,
                brains={"agent-1": healthy, "agent-2": failed},
                max_workers=2,
                concurrent_decisions=True,
                log_agent_io=False,
                startup_health_check_tick=None,
                provider_retry_rounds=0,
            )

            first_result = first.run()

            pending_path = root / "run-pending-tick.json"
            self.assertEqual(first_result.status, "paused_checkpoint")
            self.assertEqual(first_result.final_tick, 0)
            self.assertEqual(healthy.calls, 1)
            self.assertEqual(failed.calls, 1)
            self.assertTrue(pending_path.exists())
            self.assertLess(pending_path.stat().st_size, 1_000_000)
            pending = json.loads(pending_path.read_text(encoding="utf-8"))
            self.assertEqual(set(pending["decisions"]), {"agent-1"})
            paused = next(
                event for event in first_engine.state.events if event.type == "run_paused"
            )
            self.assertEqual(paused.data["affected_agent_ids"], ["agent-2"])
            self.assertEqual(paused.data["affected_agent_count"], 1)
            self.assertEqual(paused.data["cached_agent_ids"], ["agent-1"])

            resumed_engine, _extra = load_run_checkpoint(checkpoint_path)
            recovered = CountingHealthyBrain()
            should_not_be_called = CountingHealthyBrain()
            resumed_writer = IncrementalRunWriter(
                events_path,
                snapshot_path,
                checkpoint_path=checkpoint_path,
                fsync=False,
                truncate_events=False,
            )
            resumed_writer.rebase(resumed_engine)
            second = SimulationSession(
                engine=resumed_engine,
                brain_spec=BrainSpec.resolve("survival"),
                runtime=BrainRuntime(),
                writer=resumed_writer,
                target_ticks=1,
                brains={"agent-1": should_not_be_called, "agent-2": recovered},
                max_workers=2,
                concurrent_decisions=True,
                log_agent_io=False,
                startup_health_check_tick=None,
                provider_retry_rounds=0,
                resumed=True,
            )

            second_result = second.run()

            self.assertEqual(second_result.status, "completed")
            self.assertEqual(second_result.final_tick, 1)
            self.assertEqual(should_not_be_called.calls, 0)
            self.assertEqual(recovered.calls, 1)
            self.assertFalse(pending_path.exists())

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
                max_workers=28,
                provider_max_workers={"codex_cli": 24, "claude_cli": 4},
                report_stem=Path(temp_dir) / "mixed",
            )

            result = session.run()

            started = next(event for event in engine.state.events if event.type == "run_started")
            self.assertEqual(session.max_workers, 28)
            self.assertEqual(session.runner.max_workers, 28)
            self.assertEqual(
                session.runner.provider_max_workers,
                {"codex_cli": 24, "claude_cli": 4},
            )
            self.assertEqual(started.data["brain"], "mixed")
            self.assertEqual(started.data["population"]["assignments"]["agent-1"], "cohort-1")
            self.assertEqual(result.report["population"]["cohorts"]["cohort-1"]["model"], "claude-sonnet-5")


if __name__ == "__main__":
    unittest.main()


class QuotaWaitAndResumeTests(unittest.TestCase):
    """A rate limit must suspend a run, never damage or abandon it.

    Regression for the Fable seed-41 trial: the Claude weekly-limit message was
    not recognized as quota, so every agent's failure became a fabricated wait
    action and the world advanced eighteen ticks against a provider refusing
    every call.
    """

    WEEKLY_LIMIT = (
        "Claude quota unavailable: claude -p exited 1: You've hit your weekly "
        "limit · resets 2pm (America/Los_Angeles)"
    )

    def _session(self, brains, *, target_ticks, quota_wait_max_seconds, slept):
        engine = WorldEngine.create(
            WorldConfig(seed=7), agent_names=list(brains)
        )
        return engine, SimulationSession(
            engine=engine,
            brain_spec=BrainSpec.resolve("survival"),
            runtime=BrainRuntime(),
            writer=IncrementalRunWriter(None, None, fsync=False),
            target_ticks=target_ticks,
            brains={f"agent-{index + 1}": brain for index, brain in enumerate(brains.values())},
            log_agent_io=False,
            startup_health_check_tick=None,
            quota_wait_max_seconds=quota_wait_max_seconds,
            sleep=slept.append,
        )

    def test_run_waits_out_the_limit_and_finishes_without_advancing_the_world(self) -> None:
        class LimitedBrain:
            def __init__(self) -> None:
                self.calls = 0

            def decide(self, _observation):
                self.calls += 1
                # Exhausted for the first tick's attempt, healthy afterwards.
                if self.calls <= 1:
                    return AgentDecision(
                        failure_kind="quota", intent=QuotaWaitAndResumeTests.WEEKLY_LIMIT, actions=[]
                    )
                return AgentDecision(intent="wait", actions=[{"type": "wait"}])

        slept: list[float] = []
        brains = {"A1": LimitedBrain(), "A2": LimitedBrain()}
        engine, session = self._session(
            brains, target_ticks=2, quota_wait_max_seconds=86400, slept=slept
        )

        result = session.run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.final_tick, 2)
        self.assertTrue(slept, "the run should have waited for the cap to reset")
        waits = [e for e in engine.state.events if e.type == "run_quota_wait"]
        retries = [e for e in engine.state.events if e.type == "run_quota_retry"]
        self.assertEqual(len(waits), 1)
        self.assertEqual(len(retries), 1)
        # The wait is logged at the completed-tick boundary: the discarded tick
        # never reached the world.
        self.assertEqual(waits[0].data["completed_tick"], 0)
        self.assertEqual(waits[0].data["wait_source"], "provider_reset_time")

    def test_exhausting_the_wait_budget_pauses_to_a_resumable_checkpoint(self) -> None:
        class AlwaysLimitedBrain:
            def decide(self, _observation):
                return AgentDecision(
                    failure_kind="quota", intent=QuotaWaitAndResumeTests.WEEKLY_LIMIT, actions=[]
                )

        slept: list[float] = []
        brains = {"A1": AlwaysLimitedBrain(), "A2": AlwaysLimitedBrain()}
        engine, session = self._session(
            brains, target_ticks=5, quota_wait_max_seconds=3600, slept=slept
        )

        result = session.run()

        self.assertEqual(result.status, "paused_checkpoint")
        self.assertEqual(result.stop_reason, "insufficient_quota")
        self.assertEqual(result.final_tick, 0)
        # Interruptible slices can accumulate sub-nanosecond floating-point error.
        self.assertAlmostEqual(sum(slept), 3600, places=6)
        self.assertLessEqual(engine._session_quota_state["reserved_seconds"], 3600)

    def test_waiting_disabled_keeps_the_original_pause_behavior(self) -> None:
        class AlwaysLimitedBrain:
            def decide(self, _observation):
                return AgentDecision(
                    failure_kind="quota", intent=QuotaWaitAndResumeTests.WEEKLY_LIMIT, actions=[]
                )

        slept: list[float] = []
        brains = {"A1": AlwaysLimitedBrain(), "A2": AlwaysLimitedBrain()}
        _engine, session = self._session(
            brains, target_ticks=5, quota_wait_max_seconds=0, slept=slept
        )

        result = session.run()

        self.assertEqual(result.status, "paused_checkpoint")
        self.assertEqual(result.stop_reason, "insufficient_quota")
        self.assertEqual(slept, [])

    def test_unrecognized_systemic_boundary_failure_pauses_instead_of_waiting(self) -> None:
        # The catch-all: a provider phrasing no classifier knows must still
        # never be laundered into wait actions.
        class UnknownFailureBrain:
            def decide(self, _observation):
                return AgentDecision(
                    failure_kind="harness", intent="Claude boundary failed: claude -p exited 1: novel outage text",
                    actions=[],
                )

        slept: list[float] = []
        brains = {"A1": UnknownFailureBrain(), "A2": UnknownFailureBrain()}
        engine, session = self._session(
            brains, target_ticks=5, quota_wait_max_seconds=0, slept=slept
        )

        result = session.run()

        self.assertEqual(result.status, "paused_checkpoint")
        self.assertEqual(result.stop_reason, "decisions_unusable")
        self.assertEqual(result.final_tick, 0)
        paused = [e for e in engine.state.events if e.type == "run_paused"]
        self.assertEqual(paused[0].data["affected_agents"], 2)

    def test_one_infrastructure_failure_freezes_the_tick(self) -> None:
        # Any confirmed infrastructure failure freezes the tick.
        class FlakyBrain:
            def decide(self, _observation):
                return AgentDecision(
                    failure_kind="harness", intent="Claude boundary failed: claude -p exited 1: novel outage text",
                    actions=[],
                )

        class HealthyBrain:
            def decide(self, _observation):
                return AgentDecision(intent="wait", actions=[{"type": "wait"}])

        slept: list[float] = []
        brains = {"A1": FlakyBrain(), "A2": HealthyBrain()}
        _engine, session = self._session(
            brains, target_ticks=2, quota_wait_max_seconds=0, slept=slept
        )

        result = session.run()

        self.assertEqual(result.status, "paused_checkpoint")
        self.assertEqual(result.final_tick, 0)
