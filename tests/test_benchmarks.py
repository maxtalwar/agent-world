from __future__ import annotations

import unittest
from argparse import Namespace

from agent_world.benchmarks import (
    BENCHMARK_PROTOCOL_ID,
    aggregate_benchmark_reports,
    benchmark_code_fingerprint,
    build_benchmark_results,
    format_benchmark_leaderboard,
    score_benchmark_counts,
)
from agent_world.cli import _apply_benchmark_protocol


def _protocol_report(seed: int, source: str) -> dict:
    agents = [f"agent-{index}" for index in range(1, 11)]
    cohort = {
        "brain": "codex",
        "model": "gpt-test",
        "reasoning_effort": "medium",
        "provider": "codex_cli",
        "agents": agents,
        "initial_agents": 10,
    }
    report = {
        "source": source,
        "run": {
            "completed": True,
            "final_tick": 40,
            "target_ticks": 40,
        },
        "config": {
            "seed": seed,
            "economy_mode": "organic",
            "geography_mode": "dispersed",
            "specialization_mode": "generalists",
            "objective_mode": "neutral",
        },
        "population": {
            "type": "codex",
            "total_agents": 10,
            "cohorts": {"cohort-1": cohort},
        },
        "reliability": {
            "quality_status": "clean",
            "usage_record_coverage_pct": 100.0,
        },
    }
    start = {
        "type": "run_started",
        "tick": 0,
        "actor_id": None,
        "message": "started",
        "data": {
            "benchmark_protocol": BENCHMARK_PROTOCOL_ID,
            "benchmark_code_fingerprint": benchmark_code_fingerprint(),
            "decision_mode": "raw",
            "turn_resolution": "simultaneous",
            "global_max_workers": 4,
            "provider_max_workers": {"codex_cli": 4},
            "agent_io_log": True,
            "action_feedback_mode": "baseline",
            "connector_profile": "stateless-v3",
            "conversation_mode": "stateless",
        },
    }
    responses = [
        {
            "type": "agent_response",
            "tick": 0,
            "actor_id": agent_id,
            "message": "wait",
            "data": {"actions": [{"type": "wait"}]},
        }
        for agent_id in agents
    ]
    snapshot = {
        "tick": 40,
        "agents": {
            agent_id: {
                "alive": True,
                "inventory": {"food": 1, "water": 2, "coin": 4},
            }
            for agent_id in agents
        },
        "groups": {},
        "structures": {},
        "items": {},
        "trades": {},
    }
    report["benchmarks"] = build_benchmark_results(
        [start, *responses],
        snapshot,
        report,
    )
    return report


class BenchmarkTests(unittest.TestCase):
    def test_protocol_flag_locks_comparable_run_settings(self) -> None:
        args = Namespace(
            benchmark_protocol=BENCHMARK_PROTOCOL_ID,
            population=None,
            brain="codex",
            sequential_decisions=False,
            seed=None,
        )

        _apply_benchmark_protocol(args)

        self.assertEqual(args.seed, 11)
        self.assertEqual(args.ticks, 40)
        self.assertEqual(args.agents, 10)
        self.assertEqual(args.preset, "organic-generalists")
        self.assertEqual(args.reasoning_effort, "medium")
        self.assertEqual(args.connector_profile, "stateless-v3")
        self.assertEqual(args.benchmark_code_fingerprint, benchmark_code_fingerprint())

    def test_protocol_flag_rejects_conflicting_settings(self) -> None:
        args = Namespace(
            benchmark_protocol=BENCHMARK_PROTOCOL_ID,
            population=None,
            brain="codex",
            sequential_decisions=False,
            seed=11,
            ticks=50,
        )

        with self.assertRaisesRegex(ValueError, "requires --ticks=40"):
            _apply_benchmark_protocol(args)

    def test_scores_use_frozen_formulas(self) -> None:
        scores = score_benchmark_counts(
            {
                "submitted_actions": 100,
                "contention_failures": 10,
                "submitted_actions_excluding_contention": 90,
                "invalid_proposals": 18,
                "action_point_overruns": 3,
                "possible_agent_ticks": 100,
                "decisions": 90,
                "initial_endowment_value": 80,
                "terminal_economic_value": 120,
                "venture_initiatives": 10,
                "realized_venture_value": 20,
            }
        )

        self.assertEqual(scores["planning_execution"]["score"], 80.0)
        self.assertAlmostEqual(
            scores["sustained_competence"]["score"],
            (80 * 90 * 50) ** (1 / 3),
            places=2,
        )
        self.assertEqual(scores["entrepreneurial_agency"]["score"], 50.0)

    def test_declared_standard_trial_is_protocol_compliant(self) -> None:
        report = _protocol_report(11, "seed-11")
        benchmark = report["benchmarks"]

        self.assertTrue(benchmark["trial"]["protocol_compliant"])
        self.assertTrue(
            benchmark["cohorts"]["cohort-1"]["protocol_compliant"]
        )
        self.assertEqual(
            benchmark["cohorts"]["cohort-1"]["scores"]["planning_execution"]["score"],
            100.0,
        )

    def test_two_required_seeds_produce_certified_pooled_result(self) -> None:
        aggregate = aggregate_benchmark_reports(
            [_protocol_report(11, "seed-11"), _protocol_report(41, "seed-41")]
        )

        self.assertEqual(len(aggregate["results"]), 1)
        result = aggregate["results"][0]
        self.assertTrue(result["certified"])
        self.assertEqual(result["seeds"], [11, 41])
        self.assertEqual(result["raw"]["submitted_actions"], 20)
        self.assertIn("gpt-test", format_benchmark_leaderboard(aggregate))

    def test_undeclared_run_remains_diagnostic(self) -> None:
        report = _protocol_report(11, "seed-11")
        report["benchmarks"]["trial"]["protocol_compliant"] = False
        report["benchmarks"]["cohorts"]["cohort-1"]["protocol_compliant"] = False
        report["benchmarks"]["cohorts"]["cohort-1"]["quality_flags"] = [
            "benchmark_protocol_not_declared"
        ]

        aggregate = aggregate_benchmark_reports([report])

        self.assertEqual(aggregate["results"], [])
        self.assertEqual(aggregate["rejected"][0]["reason"], "diagnostic_only")


if __name__ == "__main__":
    unittest.main()
