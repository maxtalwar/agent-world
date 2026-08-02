import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent_world.benchmark_db import _latency_summary, build_database, verify_database
from agent_world.benchmarks import score_benchmark_counts


class BenchmarkDatabaseTests(unittest.TestCase):
    def test_latency_summary_uses_interpolated_percentiles(self) -> None:
        summary = _latency_summary([1, 3])

        self.assertEqual(summary["samples"], 2)
        self.assertEqual(summary["mean"], 2)
        self.assertEqual(summary["median"], 2)
        self.assertAlmostEqual(summary["p95"], 2.9)
        self.assertEqual(summary["max"], 3)

    def test_builds_queryable_run_decision_tick_and_model_layers(self) -> None:
        raw = {
            "initial_agents": 1,
            "possible_agent_ticks": 10,
            "observed_agent_ticks": 10,
            "decisions": 2,
            "decision_failures": 0,
            "model_output_failures": 0,
            "external_decision_failures": 0,
            "submitted_actions": 4,
            "contention_failures": 0,
            "submitted_actions_excluding_contention": 4,
            "engine_invalid_proposals": 0,
            "invalid_proposals": 0,
            "action_point_overruns": 0,
            "initial_endowment_value": 13.5,
            "terminal_economic_value": 20,
            "living_agents": 1,
            "endpoint_health_points": 80,
            "endpoint_health_capacity": 100,
            "living_terminal_economic_value": 20,
            "purposeful_agent_ticks": 8,
            "venture_initiatives": 1,
            "venture_initiatives_by_type": {"offer_trade": 1},
            "enterprise_supply_value": 2,
            "enterprise_supply_by_source": {
                "net_goods_supplied_to_others": 2,
                "net_service_income": 0,
            },
            "own_capital_output_value": 0,
            "informal_transfer_value": 0,
        }
        scores = score_benchmark_counts(raw)
        report = {
            "run": {"completed": True, "final_tick": 50, "target_ticks": 50},
            "benchmarks": {
                "cohorts": {
                    "cohort-1": {
                        "model": "test-model",
                        "provider": "test-provider",
                        "brain": "test-brain",
                        "reasoning_effort": "medium",
                        "scores": scores,
                        "raw": raw,
                        "diagnostics": {"communications": 3, "groups_created": 0},
                    }
                },
                "trial": {"declared_protocol": "participant-v6"},
            },
            "usage": {"reasoning_tokens_estimated": False, "cache_hit_rate_pct": 25},
            "reliability": {
                "benchmark_integrity_status": "valid",
                "quality_status": "clean",
                "quality_flags": [],
                "usage_record_coverage_pct": 100,
                "decision_attempts": 2,
                "decision_failure_rate_pct": 0,
                "invalid_action_rate_pct": 0,
                "contention_failure_rate_pct": 0,
            },
            "survival": {"dead": 0},
            "structures": {
                "complete": {"farm_plot": 1},
                "in_progress": {},
                "coop_builds": [],
            },
            "economy": {
                "access_grants": 0,
                "trades": {"offered": 1, "accepted": 0, "conversion_rate_pct": 0},
                "gifts": 0,
                "construction": {"contributions": {"events": 1}},
                "institutions": {},
            },
            "actions": {"counts": {"gather": 4}},
        }
        usage = [
            {
                "tick": 0,
                "agent_id": "agent-1",
                "time": 10,
                "duration_seconds": 1,
                "provider": "test-provider",
                "model": "test-model",
                "prompt_tokens": 100,
                "cached_tokens": 25,
                "completion_tokens": 5,
                "reasoning_tokens": 10,
            },
            {
                "tick": 0,
                "agent_id": "agent-2",
                "time": 12,
                "duration_seconds": 3,
                "provider": "test-provider",
                "model": "test-model",
                "prompt_tokens": 100,
                "cached_tokens": 25,
                "completion_tokens": 5,
                "reasoning_tokens": 20,
            },
        ]
        manifest = {
            "started_at_utc": "2026-08-02T00:00:00+00:00",
            "ended_at_utc": "2026-08-02T00:00:10+00:00",
        }
        catalog = {
            "schema_version": 1,
            "suite": "participant-v6",
            "scoring_revision": 2,
            "models": [
                {
                    "model_key": "test-model",
                    "label": "Test Model",
                    "runs": [{"seed": 11, "report_path": "run-report.json"}],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "run-report.json").write_text(json.dumps(report), encoding="utf-8")
            (root / "run-usage.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in usage), encoding="utf-8"
            )
            (root / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
            database = root / "benchmarks.sqlite"

            build_database(root / "catalog.json", database, repo_root=root)

            verification = verify_database(database)
            self.assertEqual(verification["integrity"], "ok")
            self.assertEqual(verification["decisions"], 2)
            self.assertEqual(verification["latency_coverage_pct"], 100)
            connection = sqlite3.connect(database)
            run = connection.execute(
                "SELECT latency_mean_seconds, latency_p95_seconds, wall_clock_seconds, "
                "usage_observed_span_seconds "
                "FROM benchmark_runs"
            ).fetchone()
            tick = connection.execute(
                "SELECT concurrent_wall_span_seconds FROM tick_metrics"
            ).fetchone()
            model = connection.execute(
                "SELECT reasoning_tokens_per_decision, net_living_value_created "
                "FROM model_results"
            ).fetchone()
            connection.close()

            self.assertEqual(run[0], 2)
            self.assertAlmostEqual(run[1], 2.9)
            self.assertEqual(run[2], 10)
            self.assertEqual(run[3], 3)
            self.assertEqual(tick[0], 3)
            self.assertEqual(model[0], 15)
            self.assertEqual(model[1], 6.5)


if __name__ == "__main__":
    unittest.main()
