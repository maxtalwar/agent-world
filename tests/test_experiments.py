from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_world.cli import _experiment, _run
from agent_world.experiments import (
    _configured_world,
    run_factorial_experiment,
    selected_conditions,
)
from agent_world.models import AgentDecision


class FactorialExperimentTests(unittest.TestCase):
    def test_condition_selection_supports_full_design_and_one_cell(self) -> None:
        full = selected_conditions()
        self.assertEqual(
            [condition["id"] for condition in full],
            [
                "baseline-collective",
                "baseline-individual",
                "commerce-collective",
                "commerce-individual",
            ],
        )
        single = selected_conditions(["commerce"], ["individual"])
        self.assertEqual(single[0]["config_overrides"], {
            "geography_mode": "dispersed",
            "economy_mode": "commerce",
            "objective_mode": "individual",
        })
        organic = selected_conditions(["organic"], ["neutral"])
        self.assertEqual(
            organic[0]["config_overrides"],
            {
                "geography_mode": "dispersed",
                "economy_mode": "organic",
                "objective_mode": "neutral",
            },
        )

    def test_world_config_treatments_are_applied_through_dataclass_fields(self) -> None:
        config, applied, unsupported = _configured_world(
            width=16,
            height=16,
            seed=7,
            overrides={
                "geography_mode": "dispersed",
                "economy_mode": "commerce",
                "objective_mode": "collective",
                "future_field": "not-yet-supported",
            },
        )
        self.assertEqual(config.seed, 7)
        self.assertEqual(config.geography_mode, "dispersed")
        self.assertEqual(config.economy_mode, "commerce")
        self.assertEqual(config.objective_mode, "collective")
        self.assertNotIn("future_field", applied)
        self.assertEqual(unsupported, {"future_field": "not-yet-supported"})

    def test_survival_run_writes_auditable_manifests_and_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "experiment"
            manifest = run_factorial_experiment(
                out_dir=output,
                seeds=[19],
                ticks=1,
                agents=1,
                environments=["commerce"],
                objectives=["individual"],
                brain="survival",
                log_agent_io=False,
            )

            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["aggregate_summary"]["valid_run_count"], 1)
            self.assertEqual(manifest["aggregate_summary"]["total_llm_cost_usd"], 0)
            run = manifest["runs"][0]
            self.assertEqual(run["final_ticks"], 1)
            self.assertTrue(run["valid_for_analysis"])

            run_manifest_path = Path(run["manifest"])
            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(run_manifest["condition"]["applied_config_overrides"]["economy_mode"], "commerce")
            self.assertEqual(run_manifest["config"]["objective_mode"], "individual")
            self.assertEqual(run_manifest["brain"]["type"], "survival")
            self.assertEqual(len(run_manifest["provenance"]["git_sha"]), 40)
            for hash_name in (
                "rules_source_sha256",
                "initial_api_system_prompt_sha256",
                "initial_api_user_prompt_sha256",
            ):
                self.assertEqual(len(run_manifest["hashes"][hash_name]), 64)
            for output_name in ("events", "snapshot", "report_json", "report_markdown", "manifest"):
                self.assertTrue(Path(run_manifest["outputs"][output_name]).exists())
            self.assertIsNone(run_manifest["outputs"]["usage"])

            events = Path(run_manifest["outputs"]["events"]).read_text(encoding="utf-8")
            self.assertIn('"type": "run_started"', events)
            self.assertIn('"type": "run_completed"', events)
            self.assertTrue((output / "summary.json").exists())
            self.assertTrue((output / "summary.md").exists())

    def test_openrouter_cells_use_isolated_run_scoped_usage(self) -> None:
        class FakeOpenRouterBrain:
            instances = 0

            def __init__(self, model=None, reasoning_effort=None, runtime=None):
                self.__class__.instances += 1
                self.model = model or "fake-model"
                self.reasoning_effort = reasoning_effort or "low"
                self.runtime = runtime
                self.base_url = "https://fake.provider.test/v1"
                self.api_style = "chat"
                self.max_output_tokens = 100
                self.timeout_seconds = 5
                self.max_retries = 0
                self.min_request_interval_seconds = 0

            def decide(self, _observation):
                self.runtime.record_usage(
                    {
                        "model": self.model,
                        "prompt_tokens": 10,
                        "cached_tokens": 0,
                        "completion_tokens": 2,
                        "reasoning_tokens": 0,
                        "cost": 0.01,
                    }
                )
                return AgentDecision(intent="wait", actions=[{"type": "wait"}], messages=[], memory_updates=[])

        old_usage_log = os.environ.get("AGENT_WORLD_USAGE_LOG")
        os.environ["AGENT_WORLD_USAGE_LOG"] = "/tmp/original-agent-world-usage.jsonl"
        try:
            with tempfile.TemporaryDirectory() as temp_dir, patch(
                "agent_world.brain_factory.OpenRouterBrain", FakeOpenRouterBrain
            ):
                manifest = run_factorial_experiment(
                    out_dir=Path(temp_dir) / "experiment",
                    seeds=[3],
                    ticks=1,
                    agents=1,
                    environments=["baseline", "commerce"],
                    objectives=["individual"],
                    brain="openrouter",
                    model="fake-model",
                )
                self.assertEqual(FakeOpenRouterBrain.instances, 2)
                self.assertEqual(manifest["aggregate_summary"]["total_llm_cost_usd"], 0.02)
                for run in manifest["runs"]:
                    usage_path = Path(json.loads(Path(run["manifest"]).read_text())["outputs"]["usage"])
                    records = [json.loads(line) for line in usage_path.read_text().splitlines() if line]
                    self.assertEqual(len(records), 1)
                self.assertEqual(
                    os.environ.get("AGENT_WORLD_USAGE_LOG"),
                    "/tmp/original-agent-world-usage.jsonl",
                )
        finally:
            if old_usage_log is None:
                os.environ.pop("AGENT_WORLD_USAGE_LOG", None)
            else:
                os.environ["AGENT_WORLD_USAGE_LOG"] = old_usage_log

    def test_cli_experiment_defaults_to_survival_and_can_select_one_cell(self) -> None:
        aggregate = {"valid_run_count": 1, "run_count": 1, "total_llm_cost_usd": 0.0}
        fake_manifest = {
            "status": "completed",
            "aggregate_summary": aggregate,
            "outputs": {"manifest": "/tmp/manifest.json", "summary_json": "/tmp/summary.json"},
        }
        args = argparse.Namespace(
            agents=1,
            ticks=1,
            seeds=[2],
            brain="survival",
            model=None,
            reasoning_effort=None,
            environment="commerce",
            objective="individual",
            width=16,
            height=16,
            out_dir=Path("/tmp/test-experiment"),
            no_agent_io_log=True,
            max_workers=None,
            overwrite=False,
            progress=False,
        )
        with patch("agent_world.cli.run_factorial_experiment", return_value=fake_manifest) as runner, patch(
            "builtins.print"
        ):
            _experiment(args)
        kwargs = runner.call_args.kwargs
        self.assertEqual(kwargs["brain"], "survival")
        self.assertEqual(kwargs["environments"], ["commerce"])
        self.assertEqual(kwargs["objectives"], ["individual"])

    def test_ordinary_cli_run_records_lifecycle_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = argparse.Namespace(
                ticks=1,
                agents=1,
                seed=5,
                width=16,
                height=16,
                brain="survival",
                model=None,
                reasoning_effort=None,
                out=root / "ordinary.jsonl",
                snapshot=root / "ordinary-snapshot.json",
                no_agent_io_log=True,
                sequential_decisions=True,
                max_workers=1,
                progress=False,
            )
            with patch("builtins.print"):
                _run(args)
            events = [json.loads(line) for line in args.out.read_text().splitlines() if line]
            event_types = [event["type"] for event in events]
            self.assertIn("run_started", event_types)
            self.assertIn("run_completed", event_types)
            self.assertLess(event_types.index("run_started"), event_types.index("run_completed"))

    def test_ordinary_cli_run_resumes_from_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            out = root / "resumable.jsonl"
            snapshot = root / "resumable-snapshot.json"
            first = argparse.Namespace(
                ticks=1,
                agents=1,
                seed=5,
                width=16,
                height=16,
                objective_mode="neutral",
                economy_mode="baseline",
                geography_mode="shared_oasis",
                brain="survival",
                model=None,
                reasoning_effort=None,
                out=out,
                snapshot=snapshot,
                checkpoint=None,
                resume_checkpoint=None,
                no_agent_io_log=True,
                sequential_decisions=True,
                max_workers=1,
                progress=False,
            )
            with patch("builtins.print"):
                _run(first)

            checkpoint = root / "resumable-checkpoint.pkl"
            resumed = argparse.Namespace(
                ticks=2,
                agents=99,
                seed=999,
                width=8,
                height=8,
                objective_mode="individual",
                economy_mode="commerce",
                geography_mode="dispersed",
                brain=None,
                model=None,
                reasoning_effort=None,
                out=None,
                snapshot=None,
                checkpoint=None,
                resume_checkpoint=checkpoint,
                no_agent_io_log=False,
                sequential_decisions=False,
                max_workers=None,
                progress=False,
            )
            with patch("builtins.print"):
                _run(resumed)

            self.assertEqual(json.loads(snapshot.read_text())["tick"], 2)
            event_types = [json.loads(line)["type"] for line in out.read_text().splitlines()]
            self.assertEqual(event_types.count("run_started"), 1)
            self.assertEqual(event_types.count("run_resumed"), 1)
            self.assertEqual(event_types.count("run_completed"), 2)

    def test_ordinary_openrouter_run_uses_run_scoped_usage_state(self) -> None:
        class FakeOpenRouterBrain:
            instances = 0

            def __init__(self, model=None, reasoning_effort=None, runtime=None):
                self.__class__.instances += 1
                self.model = model or "fake"
                self.runtime = runtime

            def decide(self, _observation):
                self.runtime.record_usage(
                    {
                        "prompt_tokens": 2,
                        "cached_tokens": 0,
                        "completion_tokens": 1,
                        "reasoning_tokens": 0,
                        "cost": 0.001,
                    }
                )
                return AgentDecision(intent="wait", actions=[{"type": "wait"}], messages=[], memory_updates=[])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = argparse.Namespace(
                ticks=1,
                agents=1,
                seed=5,
                width=16,
                height=16,
                brain="openrouter",
                model="fake",
                reasoning_effort="low",
                out=root / "ordinary-openrouter.jsonl",
                snapshot=root / "ordinary-openrouter-snapshot.json",
                no_agent_io_log=True,
                sequential_decisions=True,
                max_workers=1,
                progress=False,
            )
            with patch(
                "agent_world.brain_factory.OpenRouterBrain",
                FakeOpenRouterBrain,
            ), patch("builtins.print"):
                _run(args)
            self.assertEqual(FakeOpenRouterBrain.instances, 1)
            usage = [
                json.loads(line)
                for line in (
                    root / "ordinary-openrouter-usage.jsonl"
                ).read_text().splitlines()
                if line
            ]
            self.assertEqual(len(usage), 1)

    def test_ordinary_codex_run_uses_codex_usage_records(self) -> None:
        class FakeCodexBrain:
            instances = 0

            def __init__(self, model=None, reasoning_effort=None, runtime=None):
                self.__class__.instances += 1
                self.model = model or "gpt-5.6-luna"
                self.runtime = runtime

            def decide(self, _observation):
                self.runtime.record_usage(
                    {
                        "provider": "codex_cli",
                        "model": self.model,
                        "billing_mode": "chatgpt_plan",
                        "prompt_tokens": 2,
                        "cached_tokens": 0,
                        "completion_tokens": 1,
                        "reasoning_tokens": 0,
                        "cost": 0,
                    }
                )
                return AgentDecision(intent="wait", actions=[{"type": "wait"}], messages=[], memory_updates=[])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = argparse.Namespace(
                ticks=1,
                agents=1,
                seed=5,
                width=16,
                height=16,
                brain="codex",
                model="gpt-5.6-luna",
                reasoning_effort="low",
                out=root / "ordinary-codex.jsonl",
                snapshot=root / "ordinary-codex-snapshot.json",
                no_agent_io_log=True,
                sequential_decisions=True,
                max_workers=1,
                progress=False,
            )
            with patch("agent_world.brain_factory.CodexBrain", FakeCodexBrain), patch("builtins.print"):
                _run(args)
            self.assertEqual(FakeCodexBrain.instances, 1)
            usage = [
                json.loads(line)
                for line in (root / "ordinary-codex-usage.jsonl").read_text().splitlines()
                if line
            ]
            self.assertEqual(len(usage), 1)
            self.assertEqual(usage[0]["billing_mode"], "chatgpt_plan")


if __name__ == "__main__":
    unittest.main()
