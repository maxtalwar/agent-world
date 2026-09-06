import contextlib
import copy
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_world.benchmarks import (
    aggregate_benchmark_reports, benchmark_code_fingerprint, build_benchmark_results,
    format_benchmark_leaderboard, score_benchmark_counts,
)
from agent_world.benchmark_db import build_database, format_leaderboard
from agent_world.cli import main, build_parser, _apply_benchmark_protocol
from agent_world.managed_runs import load_run_config, build_launch_plan
from agent_world.protocols import get_recipe
from agent_world.run_report import build_report, _render_benchmark_lines
from agent_world.usage import summarize_decision_latency
from test_benchmarks import _protocol_report


def fixture(seed=11, health=80):
    recipe = get_recipe("participant-v8")
    report = _protocol_report(seed, f"fixture-{seed}", protocol_id=recipe.id)
    members = report["population"]["cohorts"]["cohort-1"]["agents"]
    start = {"type": "run_started", "tick": 0, "actor_id": None, "data": {
        "benchmark_protocol": recipe.id, "recipe": recipe.id,
        "recipe_fingerprint_sha256": recipe.digest,
        "benchmark_code_fingerprint": benchmark_code_fingerprint(["codex_cli"], recipe.id),
        "agent_io_log": True, "decision_mode": "raw", "turn_resolution": "simultaneous",
        "action_feedback_mode": "baseline", "connector_profile": "connector-v3",
        "conversation_mode": "fresh-conversation", "observation_history_policy": "full-v1",
        "codex_action_max_items": 4,
    }}
    events = [start]
    usage = []
    for tick in range(60):
        for agent in members:
            events.extend([
                {"type": "agent_observation", "tick": tick, "actor_id": agent,
                 "data": {"observation": {"self": {"health": health if tick else 100}}}},
                {"type": "agent_response", "tick": tick, "actor_id": agent, "message": "wait",
                 "data": {"actions": [{"type": "wait"}]}},
            ])
            usage.append({"tick": tick, "agent_id": agent, "duration_seconds": 2,
                          "model": "gpt-test", "provider": "codex_cli"})
    events += [{"type": "harvest", "tick": 59, "actor_id": members[0],
                "data": {"resource": "food", "quantity": 6, "improved_land": True}},
               {"type": "run_completed", "tick": 60}]
    snapshot = {"tick": 60, "agents": {
        agent: {"alive": True, "health": health, "inventory": {}} for agent in members
    }}
    report["usage"] = {"calls": len(usage), "decision_latency": summarize_decision_latency(usage),
                       "estimated_cost": {"available": True, "cost_usd": {"total": 3}}}
    report["benchmarks"] = build_benchmark_results(events, snapshot, report)
    return report, events, snapshot, usage


class V8PipelineTests(unittest.TestCase):
    def test_full_evidence_scores_and_pools_under_new_names(self):
        reports = [fixture(11, 80)[0], fixture(41, 60)[0]]
        for report in reports:
            cohort = report["benchmarks"]["cohorts"]["cohort-1"]
            self.assertTrue(cohort["protocol_compliant"], cohort["quality_flags"])
            self.assertEqual(set(cohort["scores"]), {"execution", "capability", "production"})
            self.assertEqual(cohort["scores"]["execution"]["score"], 100)
        aggregate = aggregate_benchmark_reports(reports, "participant-v8")
        row = aggregate["results"][0]
        self.assertTrue(row["certified"])
        self.assertEqual(row["scores"]["capability"]["score"], 70)
        self.assertEqual(row["scores"]["production"]["score"], 2)
        self.assertEqual(row["score_spread"]["capability"]["absolute_difference"], 20)
        text = format_benchmark_leaderboard(aggregate)
        self.assertIn("| Model | Capability | Execution | Production | Cost/run | Mean time/decision |", text)
        self.assertIn("$3.00 | 2.00s", text)
        self.assertNotIn("Competence", text)
        rendered = "\n".join(_render_benchmark_lines(reports[0]["benchmarks"]))
        self.assertIn("| Cohort | Capability | Execution | Production |", rendered)

    def test_missing_observations_and_external_failure_are_unavailable_not_zero(self):
        for defect in ("missing", "external"):
            report, events, snapshot, usage = fixture()
            if defect == "missing":
                events = [e for e in events if not (e["type"] == "agent_observation" and e["tick"] == 30)]
            else:
                next(e for e in events if e["type"] == "agent_response")["message"] = (
                    "Grok quota unavailable: usage balance exhausted")
            report["benchmarks"] = build_benchmark_results(events, snapshot, report)
            cohort = report["benchmarks"]["cohorts"]["cohort-1"]
            self.assertFalse(cohort["protocol_compliant"])
            self.assertTrue(all(s["score"] is None for s in cohort["scores"].values()))
            self.assertEqual(aggregate_benchmark_reports([report])["results"], [])

    def test_valid_noop_can_execute_perfectly(self):
        report, events, snapshot, _ = fixture()
        for e in events:
            if e["type"] == "agent_response":
                e["data"]["actions"] = []
        report["benchmarks"] = build_benchmark_results(events, snapshot, report)
        cohort = report["benchmarks"]["cohorts"]["cohort-1"]
        self.assertTrue(cohort["protocol_compliant"], cohort["quality_flags"])
        self.assertEqual(cohort["scores"]["execution"]["score"], 100)

    def test_live_checkpoint_scores_without_claiming_completion(self):
        report, events, snapshot, _ = fixture()
        events = [e for e in events if e.get("tick", 0) < 12]
        snapshot["tick"] = 12
        report["run"].update(final_tick=12, target_ticks=12, completed=False)
        report["benchmarks"] = build_benchmark_results(events, snapshot, report)
        cohort = report["benchmarks"]["cohorts"]["cohort-1"]
        self.assertEqual(cohort["scores"]["capability"]["score"], 80)
        self.assertFalse(cohort["protocol_compliant"])
        self.assertIn("run_not_completed", cohort["quality_flags"])

    def test_managed_recipe_owns_horizon_board_and_effort(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"schema_version": 1, "run_id": "fixture", "kind": "benchmark",
                                        "protocol": "participant-v8", "model": {"brain": "codex", "id": "gpt-test"}}))
            config = load_run_config(path)
            with patch("agent_world.managed_runs._git", side_effect=["a" * 40, "", ""]):
                plan = build_launch_plan(config, Path(directory))
            self.assertEqual([c["target_ticks"] for c in plan["cells"]], [60, 60])
            self.assertEqual([c["seed"] for c in plan["cells"]], [11, 41])
            args = build_parser().parse_args(plan["cells"][0]["command"][3:])
            _apply_benchmark_protocol(args)
            self.assertEqual(args.reasoning_effort, "medium")
            self.assertEqual(args.town_ledger_output_mode, "disabled")
            self.assertEqual(args.season_length_ticks, 12)
            self.assertEqual(args.transfer_kind_mode, "self_declared")

    def test_real_local_world_report_and_checkpoint_resume(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            output, snapshot = root / "run.jsonl", root / "run-snapshot.json"
            main(["run", "--recipe", "participant-v8", "--brain", "survival",
                  "--ticks", "12", "--out", str(output), "--snapshot", str(snapshot)])
            main(["run", "--resume-checkpoint", str(root / "run-checkpoint.pkl"), "--ticks", "60"])
            from agent_world.persistence import load_run_checkpoint
            engine, _ = load_run_checkpoint(root / "run-checkpoint.pkl")
            self.assertEqual(engine.state.tick, 60)
            self.assertEqual(engine.state.config.town_ledger_output_mode, "disabled")
            report = build_report([e.to_dict() for e in engine.state.events], engine.snapshot(), target_ticks=60)
            cohort = next(iter(report["benchmarks"]["cohorts"].values()))
            self.assertIsNotNone(cohort["scores"]["capability"]["score"])
            self.assertIsNotNone(cohort["scores"]["production"]["score"])
            self.assertFalse(cohort["protocol_compliant"])

    def test_catalog_preserves_new_names_and_retry_latency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = []
            for seed in (11, 41):
                report, _, _, usage = fixture(seed)
                # Two attempts at the first decision: 2 seconds + a 4-second retry.
                usage.append({**usage[0], "duration_seconds": 4, "committed": False})
                folder = root / str(seed)
                folder.mkdir()
                (folder / "run-report.json").write_text(json.dumps(report))
                (folder / "run-usage.jsonl").write_text("".join(json.dumps(u) + "\n" for u in usage))
                runs.append({"seed": seed, "report_path": f"{seed}/run-report.json"})
            catalog = {"schema_version": 2, "models": [{
                "model_key": "fixture", "label": "Fixture", "suite": "participant-v8",
                "kind": "benchmark_trial", "runs": runs,
            }]}
            (root / "catalog.json").write_text(json.dumps(catalog))
            db = root / "test.sqlite"
            build_database(root / "catalog.json", db, repo_root=root)
            with sqlite3.connect(db) as connection:
                row = connection.execute("SELECT capability, execution, production, competence, entrepreneurship, "
                                         "latency_mean_seconds FROM model_results").fetchone()
            self.assertEqual(row[:5], (80, 100, 2, None, None))
            self.assertAlmostEqual(row[5], 1204 / 600)
            text = format_leaderboard(db, "participant-v8")
            self.assertIn("Capability | Execution | Production", text)
            self.assertNotIn("Entrepreneurship", text)

    def test_managed_finalizer_produces_ready_v8_artifacts(self):
        from agent_world.run_finalization import finalize_job
        recipe = get_recipe("participant-v8")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cells, reports = [], []
            for seed in recipe.required_seeds:
                folder = root / str(seed)
                folder.mkdir()
                report, events, snapshot, usage = fixture(seed)
                (folder / "run.jsonl").write_text("\n".join(json.dumps(e) for e in events))
                (folder / "run-snapshot.json").write_text(json.dumps(snapshot))
                (folder / "run-manifest.json").write_text(json.dumps({"resolved_models": {"gpt-test": 600}}))
                cells.append({"seed": seed, "target_ticks": 60,
                              "events": str(folder / "run.jsonl"), "snapshot": str(folder / "run-snapshot.json"),
                              "run_manifest": str(folder / "run-manifest.json")})
                reports.append(report)
            job = {"schema_version": 1, "run_id": "fixture", "kind": "benchmark",
                   "protocol": recipe.id, "recipe_fingerprint_sha256": recipe.digest,
                   "job_dir": str(root), "source_root": str(root), "launch_commit": "a" * 40,
                   "config": {"model": {"id": "gpt-test"}}, "cells": cells}
            with patch("agent_world.run_finalization.load_job", return_value=job), \
                 patch("agent_world.run_finalization.cell_status", return_value={"state": "completed", "supervisor_active": False}), \
                 patch("agent_world.run_finalization.load_run_files", return_value=([], {}, [])), \
                 patch("agent_world.run_finalization.write_report", side_effect=reports), \
                 patch("agent_world.run_finalization._classify_v6_gifts") as classify:
                result = finalize_job("fixture", root=root)
            self.assertEqual(result["analysis_readiness"]["status"], "ready")
            self.assertEqual(result["analysis_readiness"]["completed_seeds"], [11, 41])
            self.assertFalse(classify.called)

    def test_old_recipes_and_scores_remain_distinct(self):
        self.assertEqual(get_recipe("participant-v6").defaults()["ticks"], 50)
        self.assertEqual(get_recipe("participant-v7").defaults()["ticks"], 50)
        self.assertEqual(get_recipe("participant-v6").reasoning_effort, "medium")
        self.assertEqual(get_recipe("participant-v7").reasoning_effort, "low")
        self.assertTrue(aggregate_benchmark_reports([fixture()[0]], "participant-v7")["rejected"])
        with self.assertRaises(ValueError):
            aggregate_benchmark_reports([fixture()[0], _protocol_report(11, "legacy")])


if __name__ == "__main__":
    unittest.main()
