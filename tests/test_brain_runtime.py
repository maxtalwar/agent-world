from __future__ import annotations

from pathlib import Path
import json
import os
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
    def test_model_backed_brains_default_to_four_workers(self) -> None:
        worker_env = {
            "openrouter": "OPENROUTER_MAX_PARALLEL_AGENTS",
            "codex": "CODEX_MAX_PARALLEL_AGENTS",
            "claude": "CLAUDE_MAX_PARALLEL_AGENTS",
            "cursor": "CURSOR_MAX_PARALLEL_AGENTS",
            "devin": "DEVIN_MAX_PARALLEL_AGENTS",
            "grok": "GROK_MAX_PARALLEL_AGENTS",
            "zcode": "ZCODE_MAX_PARALLEL_AGENTS",
        }
        with patch.dict(os.environ, {}, clear=True):
            for brain_type in worker_env:
                with self.subTest(brain_type=brain_type):
                    self.assertEqual(BrainSpec.resolve(brain_type).max_workers, 4)

    def test_model_worker_environment_override_is_honored(self) -> None:
        with patch.dict(os.environ, {"CODEX_MAX_PARALLEL_AGENTS": "7"}, clear=True):
            self.assertEqual(BrainSpec.resolve("codex").max_workers, 7)

    def test_brain_spec_rejects_invalid_concurrency(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_workers"):
            BrainSpec.resolve("codex", max_workers=0)

    def test_brain_spec_round_trips_versioned_boundaries(self) -> None:
        population = PopulationSpec.uniform(
            2,
            BrainSpec.resolve(
                "codex",
                connector_profile="stateless-v2",
                conversation_mode="bounded-session-v1",
                session_max_turns=7,
            ),
        )

        restored = PopulationSpec.from_dict(population.to_dict(["agent-1", "agent-2"]))

        brain = restored.groups[0].brain
        self.assertEqual(brain.connector_profile, "stateless-v2")
        self.assertEqual(brain.conversation_mode, "bounded-session-v1")
        self.assertEqual(brain.session_max_turns, 7)

    def test_bounded_sessions_reject_brains_without_cli_session_support(self) -> None:
        with self.assertRaisesRegex(ValueError, "supported only"):
            BrainSpec.resolve("openrouter", conversation_mode="bounded-session-v1")

    def test_openrouter_default_is_glm_and_ignores_openai_model_env(self) -> None:
        with patch.dict(
            os.environ,
            {"OPENAI_MODEL": "gpt-5.4-mini"},
            clear=True,
        ):
            spec = BrainSpec.resolve("openrouter")

        self.assertEqual(spec.type, "openrouter")
        self.assertEqual(spec.model, "z-ai/glm-5.2")
        self.assertEqual(spec.provider, "openrouter")

    def test_unqualified_glm_53_uses_zcode_native_harness(self) -> None:
        population = PopulationSpec.parse_many(["2@glm-5.3"])

        spec = population.groups[0].brain
        self.assertEqual(spec.type, "zcode")
        self.assertEqual(spec.provider, "zcode_cli")
        self.assertEqual(spec.model, "glm-5.3")
        self.assertEqual(spec.reasoning_effort, "max")

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

    def test_partial_tick_usage_is_moved_out_of_the_resumable_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            usage_path = Path(temp_dir) / "run-usage.jsonl"
            runtime = BrainRuntime(usage_path)
            runtime.record_usage({"call": 1, "tick": 0})
            checkpoint = runtime.usage_checkpoint()
            runtime.record_usage({"call": 2, "tick": 1})

            partial_path = runtime.rollback_usage(checkpoint, attempted_tick=1)

            self.assertEqual(runtime.usage_records(), [{"call": 1, "tick": 0}])
            self.assertEqual(
                [json.loads(line) for line in usage_path.read_text().splitlines()],
                [{"call": 1, "tick": 0}],
            )
            self.assertIsNotNone(partial_path)
            self.assertIn('"call": 2', partial_path.read_text())

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

    def test_population_parser_routes_openai_models_to_codex_by_default(self) -> None:
        population = PopulationSpec.parse_many(
            ["2@gpt-5.4-mini", "2@openai/gpt-5.4-mini"]
        )

        self.assertEqual(
            [group.brain.type for group in population.groups],
            ["codex", "codex"],
        )
        self.assertEqual(
            [group.brain.model for group in population.groups],
            ["gpt-5.4-mini", "gpt-5.4-mini"],
        )

    def test_population_parser_allows_explicit_openrouter_override(self) -> None:
        population = PopulationSpec.parse_many(
            ["2@openrouter:openai/gpt-5.4-mini"]
        )

        brain = population.groups[0].brain
        self.assertEqual(brain.type, "openrouter")
        self.assertEqual(brain.model, "openai/gpt-5.4-mini")

    def test_population_parser_accepts_explicit_future_claude_model(self) -> None:
        population = PopulationSpec.parse_many(["3@claude:claude-fable-future:high"])

        self.assertEqual(population.groups[0].brain.model, "claude-fable-future")
        self.assertEqual(population.groups[0].brain.reasoning_effort, "high")

    def test_population_parser_infers_grok_and_accepts_explicit_cursor_models(self) -> None:
        population = PopulationSpec.parse_many(
            ["2@cursor-grok-4.5", "3@cursor:gemini-3.1-pro:medium"]
        )

        self.assertEqual(population.total_agents, 5)
        self.assertEqual(population.groups[0].brain.type, "cursor")
        self.assertEqual(population.groups[0].brain.model, "cursor-grok-4.5")
        self.assertEqual(population.groups[1].brain.type, "cursor")
        self.assertEqual(population.groups[1].brain.model, "gemini-3.1-pro")
        self.assertEqual(population.groups[1].brain.reasoning_effort, "medium")

    def test_cursor_brain_spec_records_subscription_provenance(self) -> None:
        spec = BrainSpec.resolve("cursor", model="cursor-grok-4.5", reasoning_effort="low")

        self.assertEqual(spec.provider, "cursor_cli")
        self.assertEqual(spec.billing_mode, "cursor_subscription")
        self.assertTrue(spec.model_backed)

    def test_population_parser_and_spec_preserve_devin_provenance(self) -> None:
        population = PopulationSpec.parse_many(
            ["2@swe-1-6-fast", "1@devin:adaptive:high"]
        )

        self.assertEqual(population.total_agents, 3)
        self.assertEqual(
            [group.brain.type for group in population.groups],
            ["devin", "devin"],
        )
        self.assertEqual(population.groups[0].brain.model, "swe-1-6-fast")
        self.assertEqual(population.groups[1].brain.model, "adaptive")
        self.assertEqual(population.groups[1].brain.reasoning_effort, "high")
        self.assertEqual(population.groups[0].brain.provider, "devin_cli")
        self.assertEqual(
            population.groups[0].brain.billing_mode,
            "devin_subscription",
        )
        self.assertTrue(population.groups[0].brain.model_backed)

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

    def test_cursor_factory_shares_cursor_scope_without_leaking_to_codex(self) -> None:
        class FakeBrain:
            def __init__(self, model=None, reasoning_effort=None, runtime=None):
                self.model = model
                self.reasoning_effort = reasoning_effort
                self.runtime = runtime

        engine = WorldEngine.create(WorldConfig(seed=3), agent_names=["A1", "A2"])
        population = PopulationSpec.parse_many(
            ["1@cursor:cursor-grok-4.5:low", "1@codex:gpt-5.6-luna:low"]
        )
        runtime = BrainRuntime()
        with patch("agent_world.brain_factory.CursorBrain", FakeBrain), patch(
            "agent_world.brain_factory.CodexBrain", FakeBrain
        ):
            brains = create_population_brains(engine, population, runtime)

        self.assertEqual(brains["agent-1"].runtime.scope, "cursor_cli")
        self.assertEqual(brains["agent-2"].runtime.scope, "codex_cli")

    def test_devin_factory_scope_is_isolated_from_openrouter(self) -> None:
        class FakeBrain:
            def __init__(self, model=None, reasoning_effort=None, runtime=None):
                self.model = model
                self.reasoning_effort = reasoning_effort
                self.runtime = runtime

        engine = WorldEngine.create(WorldConfig(seed=3), agent_names=["A1", "A2"])
        population = PopulationSpec.parse_many(
            ["1@devin:swe-1-6-fast:low", "1@openrouter:z-ai/glm-5.2:medium"]
        )
        runtime = BrainRuntime()
        with patch("agent_world.brain_factory.DevinBrain", FakeBrain), patch(
            "agent_world.brain_factory.OpenRouterBrain", FakeBrain
        ):
            brains = create_population_brains(engine, population, runtime)

        self.assertEqual(brains["agent-1"].runtime.scope, "devin_cli")
        self.assertEqual(brains["agent-2"].runtime.scope, "openrouter")


if __name__ == "__main__":
    unittest.main()
