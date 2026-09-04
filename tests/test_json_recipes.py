from __future__ import annotations

from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_world import benchmarks, cli, managed_runs, protocols
from agent_world.benchmarks import aggregate_benchmark_reports, benchmark_protocol, _benchmark_trajectory, score_benchmark_counts
from agent_world.protocols import get_recipe, load_recipes, recipe_from_dict
from agent_world.run_finalization import finalize_job
from test_benchmarks import _protocol_report


def custom_definition():
    path = Path(__file__).resolve().parents[1] / "configs/recipe-examples/small-society.json"
    return json.loads(path.read_text())


@contextmanager
def registered(value):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / (value["id"] + ".json")
        path.write_text(json.dumps(value))
        loaded = load_recipes(Path(directory))
        registry = {**protocols.RECIPES, **loaded}
        with patch.object(protocols, "RECIPES", registry), patch.object(cli, "RECIPES", registry), \
             patch.object(benchmarks, "RECIPES", registry), patch.object(managed_runs, "RECIPES", registry):
            yield loaded[value["id"]]


class JsonRecipeTests(unittest.TestCase):
    def test_third_recipe_controls_launch_world_scoring_and_replication(self):
        with registered(custom_definition()) as recipe, tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            config_path.write_text(json.dumps({
                "schema_version": 1, "run_id": "custom-test", "kind": "benchmark",
                "protocol": recipe.id, "model": {"brain": "codex", "id": "gpt-test"},
            }))
            config = managed_runs.load_run_config(config_path)
            self.assertEqual(config["seeds"], [5, 9])
            with patch.object(managed_runs, "_git", side_effect=["a" * 40, "", ""]):
                plan = managed_runs.build_launch_plan(config, root)
            self.assertEqual([cell["target_ticks"] for cell in plan["cells"]], [6, 6])
            args = cli.build_parser().parse_args(plan["cells"][0]["command"][3:])
            cli._apply_benchmark_protocol(args)
            self.assertEqual((args.agents, args.width, args.height), (3, 32, 32))
            self.assertEqual(args.season_length_ticks, 3)
            self.assertEqual(args.observation_history_policy, "bounded-v1")

            # Real local simulation: no model or provider process is involved.
            output = root / "local.jsonl"
            snapshot = root / "local-snapshot.json"
            with redirect_stdout(io.StringIO()):
                cli.main(["run", "--recipe", recipe.id, "--brain", "survival",
                          "--out", str(output), "--snapshot", str(snapshot)])
            world = json.loads(snapshot.read_text())
            self.assertEqual((world["tick"], len(world["agents"])), (6, 3))
            self.assertEqual(world["config"]["season_length_ticks"], 3)
            self.assertEqual((world["config"]["width"], world["config"]["height"]), (32, 32))

            from agent_world.persistence import load_run_checkpoint
            checkpoint = root / "local-checkpoint.pkl"
            with redirect_stdout(io.StringIO()):
                cli.main(["run", "--resume-checkpoint", str(checkpoint), "--ticks", "7"])
            resumed_engine, extra = load_run_checkpoint(checkpoint)
            self.assertEqual(resumed_engine._codex_action_max_items, 6)
            self.assertEqual(resumed_engine._observation_history_policy, "bounded-v1")
            self.assertEqual(extra["run"]["startup_health_check_tick"], 1)

            reports = [_protocol_report(seed, f"seed-{seed}", protocol_id=recipe.id) for seed in [5, 9, 17]]
            self.assertTrue(all(report["benchmarks"]["trial"]["protocol_compliant"] for report in reports))
            aggregate = aggregate_benchmark_reports(reports)
            result = aggregate["results"][0]
            self.assertTrue(result["certified"])
            self.assertEqual(result["required_seeds"], [5, 9])
            self.assertEqual(result["extended_seeds"], [17])
            self.assertTrue(aggregate_benchmark_reports(reports[:1])["results"][0]["provisional"])
            self.assertEqual(benchmark_protocol(recipe.id)["trial"]["official_score_tick"], 6)
            raw = reports[0]["benchmarks"]["cohorts"]["cohort-1"]["raw"]
            self.assertNotEqual(score_benchmark_counts(raw, recipe.id), score_benchmark_counts(raw, "participant-v7"))
            from agent_world.benchmark_db import _pool_recipe_counts
            record = {"recipe_id": recipe.id, "recipe_digest": recipe.digest, "raw_metrics_json": json.dumps(raw)}
            pooled, scores = _pool_recipe_counts([record])
            self.assertEqual(scores, score_benchmark_counts(raw, recipe.id))
            with self.assertRaisesRegex(ValueError, "different benchmark recipes"):
                _pool_recipe_counts([record, {**record, "recipe_id": "participant-v7"}])
            with self.assertRaisesRegex(ValueError, "differs"):
                _pool_recipe_counts([{**record, "recipe_digest": "changed"}])
            events = [{"type": "benchmark_checkpoint", "data": {
                "suite_id": recipe.suite_id, "protocol_id": recipe.id, "tick": tick,
                "cohorts": {"cohort-1": {"raw": raw}},
            }} for tick in [2, 4, 6, 50]]
            trajectory = _benchmark_trajectory(events, recipe.id)
            self.assertEqual([row["tick"] for row in trajectory], [2, 4, 6])
            self.assertEqual(trajectory[-1]["role"], "official_endpoint")

    def test_third_recipe_finalizes_with_its_own_seeds_and_transfer_policy(self):
        for accounting, mode in (("self_declared", "self_declared"), ("frozen_classifier", "external")):
            value = custom_definition()
            value["transfer_accounting"] = accounting
            value["defaults"]["transfer_kind_mode"] = mode
            with self.subTest(accounting=accounting), registered(value) as recipe, tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cells = []
                reports = []
                for seed in recipe.required_seeds:
                    folder = root / str(seed)
                    folder.mkdir()
                    events = folder / "run.jsonl"
                    events.write_text(json.dumps({"type": "gift", "tick": 1, "actor_id": "agent-1",
                                                 "data": {"to": "agent-2", "items": {"water": 1}, "kind": "gift"}}) + "\n")
                    snapshot = folder / "run-snapshot.json"
                    snapshot.write_text("{}")
                    manifest = folder / "run-manifest.json"
                    manifest.write_text(json.dumps({"resolved_models": {"gpt-test": 18}}))
                    cells.append({"seed": seed, "target_ticks": 6, "events": str(events),
                                  "snapshot": str(snapshot), "run_manifest": str(manifest)})
                    reports.append(_protocol_report(seed, str(events), protocol_id=recipe.id))
                job = {"schema_version": 1, "run_id": "custom", "kind": "benchmark",
                       "protocol": recipe.id, "recipe_fingerprint_sha256": recipe.digest,
                       "job_dir": str(root), "source_root": str(root), "launch_commit": "a" * 40,
                       "config": {"model": {"id": "gpt-test"}}, "cells": cells}

                def frozen(cell, root):
                    artifact = Path(cell["events"]).parent / "gift-classifications.json"
                    artifact.write_text("{}")
                    return artifact

                with patch("agent_world.run_finalization.load_job", return_value=job), \
                     patch("agent_world.run_finalization.cell_status", return_value={"state": "completed", "supervisor_active": False}), \
                     patch("agent_world.run_finalization.load_run_files", return_value=([], {}, [])), \
                     patch("agent_world.run_finalization.write_report", side_effect=reports), \
                     patch("agent_world.run_finalization._classify_v6_gifts", side_effect=frozen) as classify:
                    result = finalize_job("custom", root=root)
                self.assertEqual(result["analysis_readiness"]["status"], "ready")
                self.assertEqual(result["analysis_readiness"]["completed_seeds"], [5, 9])
                self.assertEqual(classify.call_count, 2 if accounting == "frozen_classifier" else 0)

    def test_missing_recipe_is_not_relabelled_as_the_default(self):
        from agent_world.benchmarks import build_benchmark_results
        events = [{"type": "run_started", "data": {
            "recipe": "missing-society", "recipe_fingerprint_sha256": "recorded",
        }}]
        with self.assertRaisesRegex(ValueError, "Unsupported recipe"):
            build_benchmark_results(events, {}, {})

    def test_legacy_renderer_header_does_not_change_the_declared_trial(self):
        from agent_world.benchmark_db import _pool_recipe_counts
        report = _protocol_report(11, "legacy", protocol_id="participant-v6")
        raw = report["benchmarks"]["cohorts"]["cohort-1"]["raw"]
        record = {"recipe_id": "participant-v6", "report_recipe_id": "participant-v7",
                  "raw_metrics_json": json.dumps(raw)}
        _, scores = _pool_recipe_counts([record])
        self.assertEqual(scores, score_benchmark_counts(raw, "participant-v6"))
        with self.assertRaisesRegex(ValueError, "conflicts"):
            _pool_recipe_counts([{**record, "recipe_digest": get_recipe("participant-v6").digest}])

    def test_validation_command_does_not_register_or_launch_an_example(self):
        path = Path(__file__).resolve().parents[1] / "configs/recipe-examples/small-society.json"
        output = io.StringIO()
        with redirect_stdout(output):
            cli.main(["recipes", "--validate", str(path)])
        self.assertEqual(json.loads(output.getvalue())[0]["id"], "small-society")
        self.assertNotIn("small-society", protocols.RECIPES)

    def test_malformed_recipes_fail_before_launch(self):
        mutations = [
            lambda v: v.update(unknown=True),
            lambda v: v["defaults"].update(ticks=True),
            lambda v: v["defaults"].update(width="12"),
            lambda v: v["defaults"].update(unsupported_setting=1),
            lambda v: v["replications"].update(required_seeds=[]),
            lambda v: v["replications"].update(extended_seeds=[5]),
            lambda v: v["replications"].update(provisional_seed=11),
            lambda v: v.update(checkpoints=[2, 4]),
            lambda v: v.update(transfer_accounting="unknown"),
            lambda v: v["scoring"].update(policy="unimplemented"),
            lambda v: v["scoring"]["parameters"].update(material_endowment_multiple=0),
            lambda v: v["scoring"]["parameters"].update(material_endowment_multiple=float("nan")),
        ]
        for mutation in mutations:
            value = custom_definition()
            mutation(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                recipe_from_dict(value)

    def test_discovery_validates_filenames_duplicate_keys_and_immutable_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong-name.json"
            path.write_text(json.dumps(custom_definition()))
            with self.assertRaisesRegex(ValueError, "filename"):
                load_recipes(Path(directory))
            path.write_text('{"id": "a", "id": "b"}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                load_recipes(Path(directory))
        recipe = recipe_from_dict(custom_definition())
        original = recipe.digest
        copy = recipe.defaults()
        copy["ticks"] = 999
        self.assertEqual(recipe.digest, original)
        other = custom_definition()
        other["scoring"]["parameters"]["material_endowment_multiple"] = 8
        self.assertNotEqual(recipe_from_dict(other).digest, original)

    def test_explicit_source_commit_must_contain_the_same_recipe(self):
        with registered(custom_definition()) as recipe:
            config = {"run_id": "custom", "kind": "benchmark", "protocol": recipe.id,
                      "model": {"brain": "codex", "id": "gpt-test"}, "seeds": [5],
                      "source": {"commit": "older"}}
            with patch.object(managed_runs, "_git", side_effect=["a" * 40, json.dumps(recipe.to_dict()), "b" * 40]):
                plan = managed_runs.build_launch_plan(config, Path("/repo"))
            self.assertEqual(plan["recipe_fingerprint_sha256"], recipe.digest)
            changed = recipe.to_dict()
            changed["defaults"]["agents"] = 4
            with patch.object(managed_runs, "_git", side_effect=["a" * 40, json.dumps(changed)]), \
                 self.assertRaisesRegex(ValueError, "differs in source.commit"):
                managed_runs.build_launch_plan(config, Path("/repo"))

    def test_uncommitted_recipe_cannot_enter_a_pinned_launch(self):
        with registered(custom_definition()) as recipe:
            config = {"run_id": "custom", "kind": "benchmark", "protocol": recipe.id,
                      "model": {"brain": "codex", "id": "gpt-test"}, "seeds": [5]}
            with patch.object(managed_runs, "_git", side_effect=["a" * 40, "", "?? agent_world/recipes/small-society.json"]), \
                 self.assertRaisesRegex(ValueError, "Commit recipe files"):
                managed_runs.build_launch_plan(config, Path("/repo"))


if __name__ == "__main__":
    unittest.main()
