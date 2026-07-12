from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_world.brain_factory import (
    BrainSpec,
    PopulationSpec,
    create_brains,
    create_population_brains,
)
from agent_world.brain_runtime import BrainRuntime
from agent_world.models import WorldConfig
from agent_world.world import WorldEngine


class BrainRuntimeTests(unittest.TestCase):
    def test_brain_spec_rejects_invalid_concurrency(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_workers"):
            BrainSpec.resolve("codex", max_workers=0)

    def test_usage_and_quota_are_isolated_between_runs(self) -> None:
        first = BrainRuntime()
        second = BrainRuntime()
        first.record_usage({"run": "first"})
        first.mark_quota_unavailable("first exhausted")

        self.assertEqual(first.usage_records(), [{"run": "first"}])
        self.assertEqual(second.usage_records(), [])
        self.assertEqual(first.quota_message(), "first exhausted")
        self.assertIsNone(second.quota_message())

    def test_usage_is_written_only_to_the_owning_runtime_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = Path(temp_dir) / "first.jsonl"
            second_path = Path(temp_dir) / "second.jsonl"
            first = BrainRuntime(first_path)
            second = BrainRuntime(second_path)
            first.record_usage({"call": 1})
            second.record_usage({"call": 2})

            self.assertIn('"call": 1', first_path.read_text())
            self.assertNotIn('"call": 2', first_path.read_text())
            self.assertIn('"call": 2', second_path.read_text())

    def test_factory_shares_one_provider_scoped_runtime_across_all_run_agents(self) -> None:
        class FakeCodexBrain:
            def __init__(self, model=None, reasoning_effort=None, runtime=None):
                self.model = model
                self.reasoning_effort = reasoning_effort
                self.runtime = runtime

        engine = WorldEngine.create(WorldConfig(seed=3), agent_names=["A1", "A2"])
        runtime = BrainRuntime()
        with patch("agent_world.brain_factory.CodexBrain", FakeCodexBrain):
            brains = create_brains(engine, BrainSpec.resolve("codex"), runtime)

        self.assertEqual(set(brains), {"agent-1", "agent-2"})
        self.assertTrue(all(brain.runtime.parent is runtime for brain in brains.values()))
        self.assertEqual({brain.runtime.scope for brain in brains.values()}, {"codex_cli"})

    def test_population_parser_infers_claude_and_codex_models(self) -> None:
        population = PopulationSpec.parse_many(
            ["10@claude-sonnet-5", "10@gpt-5.6-luna"]
        )

        self.assertEqual(population.total_agents, 20)
        self.assertTrue(population.mixed)
        self.assertEqual(population.groups[0].brain.type, "claude")
        self.assertEqual(population.groups[1].brain.type, "codex")
        self.assertEqual(population.groups[0].brain.model, "claude-sonnet-5")

    def test_population_parser_accepts_explicit_future_claude_model(self) -> None:
        population = PopulationSpec.parse_many(["3@claude:claude-fable-future:high"])

        self.assertEqual(population.groups[0].brain.model, "claude-fable-future")
        self.assertEqual(population.groups[0].brain.reasoning_effort, "high")

    def test_stratified_assignments_balance_each_specialty_and_survive_round_trip(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(
                seed=9,
                economy_mode="organic",
                geography_mode="dispersed",
                specialization_mode="specialists",
            ),
            agent_names=[f"A{index}" for index in range(1, 31)],
        )
        population = PopulationSpec.parse_many(
            [
                "5@claude-opus-4-8",
                "10@claude-sonnet-5",
                "10@gpt-5.6-luna",
                "5@gpt-5.6-terra",
            ]
        ).bind_assignments(engine, strategy="stratified", seed=77)

        assignments = population.assignments(engine.state.agents)
        by_specialty: dict[str, dict[str, int]] = {}
        for agent_id, agent in engine.state.agents.items():
            counts = by_specialty.setdefault(agent.specialty or "generalist", {})
            cohort = assignments[agent_id].id
            counts[cohort] = counts.get(cohort, 0) + 1
        expected = {group.id: group.count // 5 for group in population.groups}
        self.assertEqual(len(by_specialty), 5)
        self.assertTrue(all(counts == expected for counts in by_specialty.values()))
        restored = PopulationSpec.from_dict(population.to_dict(engine.state.agents))
        self.assertEqual(
            {key: value.id for key, value in assignments.items()},
            {key: value.id for key, value in restored.assignments(engine.state.agents).items()},
        )

    def test_mixed_factory_assigns_deterministic_cohorts_and_isolates_providers(self) -> None:
        class FakeBrain:
            def __init__(self, model=None, reasoning_effort=None, runtime=None):
                self.model = model
                self.reasoning_effort = reasoning_effort
                self.runtime = runtime

        engine = WorldEngine.create(
            WorldConfig(seed=3), agent_names=["A1", "A2", "A3", "A4"]
        )
        population = PopulationSpec.parse_many(
            ["2@claude-sonnet-5", "2@gpt-5.6-luna"]
        )
        runtime = BrainRuntime()
        with patch("agent_world.brain_factory.ClaudeBrain", FakeBrain), patch(
            "agent_world.brain_factory.CodexBrain", FakeBrain
        ):
            brains = create_population_brains(engine, population, runtime)

        self.assertEqual(
            [brains[f"agent-{index}"].model for index in range(1, 5)],
            ["claude-sonnet-5", "claude-sonnet-5", "gpt-5.6-luna", "gpt-5.6-luna"],
        )
        claude_runtime = brains["agent-1"].runtime
        codex_runtime = brains["agent-3"].runtime
        claude_runtime.mark_quota_unavailable("claude exhausted")
        self.assertEqual(brains["agent-2"].runtime.quota_message(), "claude exhausted")
        self.assertIsNone(codex_runtime.quota_message())


if __name__ == "__main__":
    unittest.main()
