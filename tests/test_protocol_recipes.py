from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_world.cli import _apply_benchmark_protocol, build_parser, main
from agent_world.interface import build_observation, build_static_context
from agent_world.managed_runs import build_cell_command, build_launch_plan, load_run_config
from agent_world.models import AgentDecision, WorldConfig
from agent_world.protocols import get_recipe
from agent_world.world import WorldEngine


class ProtocolRecipeTests(unittest.TestCase):
    def load(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"schema_version": 1, "run_id": "recipe-test", **value}))
            return load_run_config(path)

    def test_managed_v6_and_v7_use_current_checkout_with_separate_defaults(self):
        with patch.dict("os.environ", {}, clear=False):
            for protocol, effort in (("participant-v6", "medium"), ("participant-v7", "low")):
                config = self.load({
                    "kind": "benchmark", "protocol": protocol,
                    "model": {"brain": "codex", "id": "fixture-model"},
                })
                command = build_cell_command(config, 11, Path("/tmp/unused"))
                args = build_parser().parse_args(command[3:])
                _apply_benchmark_protocol(args)
                self.assertEqual(args.reasoning_effort, effort)
                self.assertEqual(args.recipe, protocol)
                self.assertEqual(args.ticks, 50)
                self.assertNotIn("commit", config.get("source", {}))

    def test_recipe_experiment_allows_glm_max_custom_world_and_arbitrary_seed(self):
        config = self.load({
            "kind": "experiment", "recipe": "participant-v6",
            "question": "How does a small GLM society behave?",
            "model": {"brain": "zcode", "id": "glm-5.3", "reasoning_effort": "max"},
            "seeds": [123], "runtime": {"ticks": 7, "agents": 3},
            "world": {"width": 12, "height": 12, "objective_mode": "individual"},
        })
        command = build_cell_command(config, 123, Path("/tmp/unused"))
        args = build_parser().parse_args(command[3:])
        _apply_benchmark_protocol(args)
        self.assertIsNone(args.benchmark_protocol)
        self.assertEqual((args.reasoning_effort, args.ticks, args.agents, args.seed), ("max", 7, 3, 123))
        self.assertEqual((args.width, args.height, args.objective_mode), (12, 12, "individual"))
        self.assertEqual(args.transfer_kind_mode, "external")
        benchmark = {**config, "kind": "benchmark", "protocol": "participant-v6",
                     "runtime": {}, "world": {}, "seeds": [11]}
        with self.assertRaisesRegex(ValueError, "requires model.reasoning_effort"):
            self.load(benchmark)

    def test_world_transfer_mode_does_not_mutate_other_worlds(self):
        for mode in ("external", "self_declared", "external"):
            engine = WorldEngine.create(WorldConfig(transfer_kind_mode=mode), agent_names=["A", "B"])
            a, b = engine.state.agents.values()
            b.position = a.position
            a.inventory["water"] = 10
            observation = build_observation(engine.state, a.id)
            gift = next(action for action in observation["valid_actions"] if action["type"] == "gift")
            self.assertEqual("kind" in gift["parameters"], mode == "self_declared")
            static = build_static_context(observation["world"])
            self.assertEqual("gift|payment|barter" in static, mode == "self_declared")
            engine.tick({a.id: AgentDecision(actions=[{
                "type": "gift", "to": b.id, "items": {"water": 1}, "kind": "payment",
            }])})
            event = next(event for event in engine.state.events if event.type == "gift")
            self.assertEqual("kind" in event.data, mode == "self_declared")

    def test_local_recipe_run_and_resume_preserve_identity_without_certification(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            output = Path(directory) / "run.jsonl"
            checkpoint = Path(directory) / "run-checkpoint.pkl"
            main(["run", "--recipe", "participant-v6", "--brain", "survival",
                  "--ticks", "1", "--agents", "2", "--out", str(output)])
            main(["run", "--resume-checkpoint", str(checkpoint), "--ticks", "2"])
            manifest = json.loads((Path(directory) / "run-manifest.json").read_text())
            self.assertEqual(manifest["recipe"], "participant-v6")
            self.assertEqual(manifest["recipe_fingerprint_sha256"], get_recipe("participant-v6").digest)
            self.assertIsNone(manifest["benchmark_protocol"])
            events = [json.loads(line) for line in output.read_text().splitlines()]
            resumed = next(event for event in events if event["type"] == "run_resumed")
            self.assertEqual(resumed["data"]["recipe"], "participant-v6")
            with self.assertRaisesRegex(ValueError, "Cannot change recipe"):
                main(["run", "--resume-checkpoint", str(checkpoint), "--recipe", "participant-v7", "--ticks", "3"])

    def test_explicit_population_and_preset_override_recipe_defaults(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            output = Path(directory) / "run.jsonl"
            main(["run", "--recipe", "participant-v6", "--population", "1@survival",
                  "--population", "2@survival", "--preset", "baseline",
                  "--ticks", "1", "--out", str(output),
                  "--snapshot", str(Path(directory) / "run-snapshot.json")])
            snapshot = json.loads((Path(directory) / "run-snapshot.json").read_text())
            self.assertEqual(len(snapshot["agents"]), 3)
            self.assertEqual(snapshot["config"]["economy_mode"], "baseline")
            self.assertEqual(snapshot["config"]["world_variant"], "classic")

    def test_claude_thinking_budget_is_local_to_each_instance(self):
        from agent_world.claude_brain import ClaudeBrain, _plan_auth_environment
        with patch.dict("os.environ", {"CLAUDE_MAX_THINKING_TOKENS": "77"}):
            recipe_brain = ClaudeBrain(executable="unused", thinking_budget_tokens=2048)
            experiment_brain = ClaudeBrain(executable="unused", thinking_budget_tokens=0)
            self.assertEqual(_plan_auth_environment(recipe_brain.thinking_budget_tokens)["MAX_THINKING_TOKENS"], "2048")
            self.assertEqual(_plan_auth_environment(experiment_brain.thinking_budget_tokens)["MAX_THINKING_TOKENS"], "0")
            self.assertEqual(_plan_auth_environment()["MAX_THINKING_TOKENS"], "77")

    def test_unrelated_recipe_edits_leave_selected_fingerprint_unchanged(self):
        from dataclasses import replace
        import agent_world.protocols as protocols
        from agent_world.benchmarks import benchmark_code_fingerprint, _behavior_source_uncached
        before_v6 = benchmark_code_fingerprint(["codex_cli"], "participant-v6")
        before_v7 = benchmark_code_fingerprint(["codex_cli"], "participant-v7")
        changed = {**protocols.RECIPES,
                   "participant-v7": replace(protocols.get_recipe("participant-v7"), reasoning_effort="high")}
        with patch.object(protocols, "RECIPES", changed):
            self.assertEqual(benchmark_code_fingerprint(["codex_cli"], "participant-v6"), before_v6)
            self.assertNotEqual(benchmark_code_fingerprint(["codex_cli"], "participant-v7"), before_v7)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "protocols.py"
            source.write_text("RECIPES = {'participant-v6': 1}\n")
            before = _behavior_source_uncached(source)
            source.write_text("RECIPES = {'participant-v6': 1, 'participant-v8': 2}\n")
            self.assertEqual(_behavior_source_uncached(source), before)


if __name__ == "__main__":
    unittest.main()
