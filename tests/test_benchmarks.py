from __future__ import annotations

import unittest
from argparse import Namespace

from agent_world.benchmarks import (
    BENCHMARK_PROTOCOL_ID,
    BENCHMARK_RESOURCE_VALUES,
    BENCHMARK_SEEDS,
    BENCHMARK_SCORING_REVISION,
    BENCHMARK_SUITE_ID,
    _benchmark_trajectory,
    _cohort_raw_metrics,
    aggregate_benchmark_reports,
    benchmark_code_fingerprint,
    benchmark_protocol,
    build_benchmark_results,
    format_benchmark_leaderboard,
    score_benchmark_counts,
)
from agent_world.cli import _apply_benchmark_protocol
from agent_world.run_report import _render_benchmark_lines


def _protocol_report(
    seed: int,
    source: str,
    *,
    model_output_failure: bool = False,
    harness_failure: bool = False,
) -> dict:
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
            "final_tick": 50,
            "target_ticks": 50,
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
            "quality_status": (
                "degraded"
                if model_output_failure or harness_failure
                else "clean"
            ),
            "benchmark_integrity_status": (
                "invalid" if harness_failure else "clean"
            ),
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
            "message": "move",
            "data": {"actions": [{"type": "move", "direction": "north"}]},
        }
        for agent_id in agents
    ]
    if model_output_failure:
        responses[0]["message"] = (
            "Codex model output contract failed: arguments_json is invalid: "
            "Expecting value: line 1 column 1 (char 0)"
        )
    if harness_failure:
        responses[0]["message"] = (
            "Codex harness failed: adapter rejected contract-valid output"
        )
    snapshot = {
        "tick": 50,
        "agents": {
            agent_id: {
                "alive": True,
                "health": 100,
                "inventory": {"food": 1, "water": 2, "coin": 4},
            }
            for agent_id in agents
        },
        "groups": {},
        "structures": {},
        "items": {},
        "trades": {},
    }
    purposeful_events = [
        {
            "type": "move",
            "tick": 0,
            "actor_id": agent_id,
            "message": "moved",
            "data": {},
        }
        for agent_id in agents[
            1 if model_output_failure or harness_failure else 0:
        ]
    ]
    report["benchmarks"] = build_benchmark_results(
        [start, *responses, *purposeful_events],
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
        self.assertEqual(args.ticks, 50)
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
            ticks=40,
        )

        with self.assertRaisesRegex(ValueError, "requires --ticks=50"):
            _apply_benchmark_protocol(args)

    def test_protocol_accepts_only_the_five_predeclared_seeds(self) -> None:
        allowed = Namespace(
            benchmark_protocol=BENCHMARK_PROTOCOL_ID,
            population=None,
            brain="codex",
            sequential_decisions=False,
            seed=137,
        )
        _apply_benchmark_protocol(allowed)
        self.assertEqual(allowed.seed, 137)

        rejected = Namespace(
            benchmark_protocol=BENCHMARK_PROTOCOL_ID,
            population=None,
            brain="codex",
            sequential_decisions=False,
            seed=12,
        )
        with self.assertRaisesRegex(ValueError, "11, 41, 73, 101, 137"):
            _apply_benchmark_protocol(rejected)

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
                "purposeful_agent_ticks": 45,
                "endpoint_health_points": 600,
                "endpoint_health_capacity": 1000,
                "initial_endowment_value": 80,
                "terminal_economic_value": 120,
                "living_terminal_economic_value": 120,
                "venture_initiatives": 10,
            }
        )

        self.assertEqual(scores["effective_execution"]["score"], 63.25)
        self.assertAlmostEqual(
            scores["sustained_competence"]["score"],
            (63.25 * ((90 * 60) ** 0.5) * 50) ** (1 / 3),
            places=2,
        )
        self.assertEqual(scores["entrepreneurial_agency"]["score"], 200.0)

    def test_wait_only_policy_cannot_earn_execution_credit(self) -> None:
        scores = score_benchmark_counts(
            {
                "submitted_actions": 100,
                "submitted_actions_excluding_contention": 100,
                "invalid_proposals": 0,
                "decisions": 100,
                "purposeful_agent_ticks": 0,
                "possible_agent_ticks": 100,
            }
        )

        execution = scores["effective_execution"]
        self.assertEqual(execution["components"]["action_feasibility_pct"], 100.0)
        self.assertEqual(execution["components"]["purposeful_agent_tick_pct"], 0.0)
        self.assertEqual(execution["score"], 0.0)

    def test_internal_turnover_cannot_create_entrepreneurial_value(self) -> None:
        raw = _cohort_raw_metrics(
            events=[
                {
                    "type": "offer_trade",
                    "tick": 0,
                    "actor_id": "agent-1",
                    "data": {},
                },
                {
                    "type": "accept_trade",
                    "tick": 0,
                    "actor_id": "agent-2",
                    "data": {
                        "value": {"give": 10_000, "receive": 10_000},
                    },
                },
                {
                    "type": "build",
                    "tick": 0,
                    "actor_id": "agent-2",
                    "data": {
                        "structure": {"type": "farm_plot"},
                        "contributed": {"wood": 2, "fiber": 2},
                    },
                },
            ],
            snapshot={
                "agents": {
                    "agent-1": {
                        "alive": True,
                        "health": 100,
                        "inventory": {"coin": 4, "food": 1, "water": 2},
                    },
                    "agent-2": {
                        "alive": True,
                        "health": 100,
                        "inventory": {"coin": 2},
                    },
                },
                "groups": {},
                "structures": {
                    "structure-1": {
                        "status": "complete",
                        "type": "farm_plot",
                        "owner_id": "agent-2",
                        "inventory": {},
                        "treasury": {},
                        "upkeep_reserve": {},
                    }
                },
                "items": {},
                "trades": {},
                "contracts": {},
            },
            config={"economy_mode": "organic"},
            member_ids=["agent-1", "agent-2"],
            final_tick=1,
            target_ticks=1,
        )

        scores = score_benchmark_counts(raw)
        entrepreneurship = scores["entrepreneurial_agency"]
        self.assertEqual(raw["initial_endowment_value"], 32)
        self.assertEqual(raw["living_terminal_economic_value"], 32.0)
        self.assertEqual(raw["venture_initiatives"], 2)
        self.assertEqual(
            entrepreneurship["components"]["value_creation_score"],
            0.0,
        )
        self.assertEqual(entrepreneurship["score"], 0.0)

    def test_recipe_consistent_values_do_not_penalize_production_chains(self) -> None:
        self.assertGreaterEqual(BENCHMARK_RESOURCE_VALUES["ingot"], 19)
        self.assertGreaterEqual(BENCHMARK_RESOURCE_VALUES["coin"] * 8, 19)
        self.assertGreaterEqual(BENCHMARK_RESOURCE_VALUES["advanced_tool"], 43)
        report = _protocol_report(11, "recipe-values")
        raw = report["benchmarks"]["cohorts"]["cohort-1"]["raw"]
        self.assertEqual(raw["initial_endowment_value"], 160)

    def test_single_action_completed_build_counts_as_an_initiative(self) -> None:
        raw = _cohort_raw_metrics(
            events=[
                {
                    "type": "agent_response",
                    "tick": 0,
                    "actor_id": "agent-1",
                    "data": {"actions": [{"type": "build"}]},
                },
                {
                    "type": "build",
                    "tick": 0,
                    "actor_id": "agent-1",
                    "data": {
                        "structure": {"type": "farm_plot"},
                        "contributed": {"wood": 2, "fiber": 2},
                    },
                },
            ],
            snapshot={
                "agents": {
                    "agent-1": {
                        "alive": True,
                        "health": 100,
                        "inventory": {},
                    }
                },
                "groups": {},
                "structures": {},
                "items": {},
                "trades": {},
                "contracts": {},
            },
            config={"economy_mode": "organic"},
            member_ids=["agent-1"],
            final_tick=1,
            target_ticks=1,
        )

        self.assertEqual(raw["venture_initiatives"], 1)
        self.assertEqual(raw["purposeful_agent_ticks"], 1)

    def test_entrepreneurship_score_has_no_upper_bound(self) -> None:
        scores = score_benchmark_counts(
            {
                "submitted_actions": 100,
                "submitted_actions_excluding_contention": 100,
                "possible_agent_ticks": 100,
                "initial_endowment_value": 80,
                "living_terminal_economic_value": 160,
                "venture_initiatives": 20,
            }
        )

        entrepreneurship = scores["entrepreneurial_agency"]
        self.assertEqual(entrepreneurship["components"]["initiative_score"], 400.0)
        self.assertEqual(
            entrepreneurship["components"]["value_creation_score"],
            400.0,
        )
        self.assertEqual(entrepreneurship["score"], 400.0)
        self.assertIsNone(entrepreneurship["scale"]["maximum"])

    def test_protocol_declares_unbounded_entrepreneurship_scale(self) -> None:
        protocol = benchmark_protocol()

        self.assertEqual(protocol["scoring_revision"], BENCHMARK_SCORING_REVISION)
        self.assertEqual(BENCHMARK_SCORING_REVISION, 1)
        self.assertTrue(protocol["score_scale"]["metric_specific"])
        self.assertIsNone(protocol["score_scale"]["maximum"])
        self.assertEqual(
            protocol["score_scales"]["effective_execution"]["maximum"],
            100.0,
        )
        self.assertIsNone(
            protocol["score_scales"]["entrepreneurial_agency"]["maximum"]
        )
        self.assertEqual(
            protocol["score_scales"]["entrepreneurial_agency"]["reference_target"],
            100.0,
        )
        self.assertTrue(
            protocol["score_scales"]["economic_productivity"]["diagnostic"]
        )

    def test_v4_does_not_rescore_incompatible_historical_reports(self) -> None:
        report = _protocol_report(11, "historical-v3")
        report["benchmarks"]["suite_id"] = "agent-world-participant-v3"

        aggregate = aggregate_benchmark_reports([report])

        self.assertEqual(aggregate["results"], [])
        self.assertEqual(
            aggregate["rejected"][0]["reason"],
            "missing_or_incompatible_benchmark_suite",
        )

    def test_competence_penalizes_dead_estates_and_endpoint_collapse(self) -> None:
        scores = score_benchmark_counts(
            {
                "submitted_actions": 100,
                "contention_failures": 0,
                "submitted_actions_excluding_contention": 100,
                "invalid_proposals": 30,
                "action_point_overruns": 0,
                "possible_agent_ticks": 100,
                "decisions": 100,
                "purposeful_agent_ticks": 70,
                "initial_agents": 10,
                "living_agents": 2,
                "endpoint_health_points": 100,
                "endpoint_health_capacity": 1000,
                "initial_endowment_value": 80,
                "terminal_economic_value": 800,
                "living_terminal_economic_value": 40,
                "venture_initiatives": 0,
            }
        )

        competence = scores["sustained_competence"]
        self.assertAlmostEqual(
            competence["score"],
            (70 * (100 * 10) ** 0.5 * (100 * 40 / 240)) ** (1 / 3),
            places=2,
        )
        self.assertEqual(
            competence["components"]["total_terminal_economic_value"],
            800,
        )
        self.assertEqual(
            competence["components"]["living_terminal_economic_value"],
            40.0,
        )

    def test_spark_collapse_regression_is_not_scored_as_high_competence(self) -> None:
        scores = score_benchmark_counts(
            {
                "submitted_actions": 1959,
                "contention_failures": 11,
                "submitted_actions_excluding_contention": 1948,
                "invalid_proposals": 646,
                "action_point_overruns": 76,
                "possible_agent_ticks": 800,
                "observed_agent_ticks": 660,
                "decisions": 629,
                "purposeful_agent_ticks": 400,
                "initial_agents": 20,
                "living_agents": 12,
                "endpoint_health_points": 368,
                "endpoint_health_capacity": 2000,
                "initial_endowment_value": 160,
                "terminal_economic_value": 419,
                "living_terminal_economic_value": 251,
                "venture_initiatives": 10,
            }
        )

        competence = scores["sustained_competence"]
        self.assertLess(competence["score"], 55.0)
        self.assertEqual(
            competence["components"]["survival_exposure_pct"],
            78.62,
        )
        self.assertEqual(
            competence["components"]["endpoint_population_health_pct"],
            18.4,
        )

    def test_incomplete_run_uses_target_horizon_for_survival_exposure(self) -> None:
        report = _protocol_report(11, "seed-11")
        report["run"]["completed"] = False
        report["run"]["final_tick"] = 20
        report["population"]["cohorts"]["cohort-1"]["agents"] = [
            f"agent-{index}" for index in range(1, 11)
        ]
        snapshot = {
            "tick": 20,
            "agents": {
                f"agent-{index}": {
                    "alive": True,
                    "health": 100,
                    "inventory": {"coin": 4},
                }
                for index in range(1, 11)
            },
            "groups": {},
            "structures": {},
            "items": {},
            "trades": {},
            "contracts": {},
        }
        events = [
            {
                "type": "run_started",
                "tick": 0,
                "actor_id": None,
                "message": "started",
                "data": {},
            },
            *[
                {
                    "type": "agent_response",
                    "tick": tick,
                    "actor_id": f"agent-{index}",
                    "message": "wait",
                    "data": {"actions": [{"type": "wait"}]},
                }
                for tick in range(20)
                for index in range(1, 11)
            ],
        ]

        benchmark = build_benchmark_results(events, snapshot, report)
        components = benchmark["cohorts"]["cohort-1"]["scores"][
            "sustained_competence"
        ]["components"]

        self.assertEqual(components["survival_exposure_pct"], 40.0)

    def test_declared_standard_trial_is_protocol_compliant(self) -> None:
        report = _protocol_report(11, "seed-11")
        benchmark = report["benchmarks"]

        self.assertTrue(benchmark["trial"]["protocol_compliant"])
        self.assertTrue(
            benchmark["cohorts"]["cohort-1"]["protocol_compliant"]
        )
        self.assertEqual(
            benchmark["cohorts"]["cohort-1"]["scores"]["effective_execution"]["score"],
            100.0,
        )

    def test_model_output_failure_is_scored_without_invalidating_trial(self) -> None:
        report = _protocol_report(
            11,
            "seed-11-model-failure",
            model_output_failure=True,
        )
        benchmark = report["benchmarks"]
        cohort = benchmark["cohorts"]["cohort-1"]

        self.assertTrue(benchmark["trial"]["protocol_compliant"])
        self.assertTrue(cohort["protocol_compliant"])
        self.assertEqual(cohort["raw"]["engine_invalid_proposals"], 0)
        self.assertEqual(cohort["raw"]["model_output_failures"], 1)
        self.assertEqual(cohort["raw"]["invalid_proposals"], 1)
        self.assertEqual(
            cohort["scores"]["effective_execution"]["score"],
            90.0,
        )

        aggregate = aggregate_benchmark_reports([report])
        self.assertEqual(aggregate["results"][0]["status"], "provisional")

    def test_harness_failure_invalidates_trial_instead_of_scoring_model(self) -> None:
        report = _protocol_report(
            11,
            "seed-11-harness-failure",
            harness_failure=True,
        )
        benchmark = report["benchmarks"]
        cohort = benchmark["cohorts"]["cohort-1"]

        self.assertFalse(benchmark["trial"]["protocol_compliant"])
        self.assertFalse(cohort["protocol_compliant"])
        self.assertEqual(cohort["raw"]["model_output_failures"], 0)
        self.assertEqual(cohort["raw"]["external_decision_failures"], 1)

        aggregate = aggregate_benchmark_reports([report])
        self.assertEqual(aggregate["results"], [])
        self.assertEqual(aggregate["rejected"][0]["reason"], "diagnostic_only")

    def test_revision_one_checkpoint_uses_event_ledger_failure_classification(self) -> None:
        trajectory = _benchmark_trajectory(
            [
                {
                    "type": "agent_response",
                    "tick": 7,
                    "actor_id": "agent-1",
                    "message": (
                        "Codex decision failed: Codex action arguments_json "
                        "is invalid: Expecting value"
                    ),
                    "data": {"actions": [{"type": "wait"}]},
                },
                {
                    "type": "benchmark_checkpoint",
                    "tick": 30,
                    "actor_id": None,
                    "message": "checkpoint",
                    "data": {
                        "suite_id": BENCHMARK_SUITE_ID,
                        "protocol_id": BENCHMARK_PROTOCOL_ID,
                        "tick": 30,
                        "cohorts": {
                            "cohort-1": {
                                "raw": {
                                    "submitted_actions": 10,
                                    "submitted_actions_excluding_contention": 10,
                                    "invalid_proposals": 2,
                                    "decision_failures": 1,
                                },
                            },
                        },
                    },
                },
            ]
        )

        raw = trajectory[0]["cohorts"]["cohort-1"]["raw"]
        self.assertEqual(raw["engine_invalid_proposals"], 2)
        self.assertEqual(raw["model_output_failures"], 1)
        self.assertEqual(raw["invalid_proposals"], 3)

    def test_five_required_seeds_produce_certified_pooled_result(self) -> None:
        aggregate = aggregate_benchmark_reports(
            [
                _protocol_report(seed, f"seed-{seed}")
                for seed in sorted(BENCHMARK_SEEDS)
            ]
        )

        self.assertEqual(len(aggregate["results"]), 1)
        result = aggregate["results"][0]
        self.assertTrue(result["certified"])
        self.assertEqual(result["seeds"], sorted(BENCHMARK_SEEDS))
        self.assertEqual(result["raw"]["submitted_actions"], 50)
        self.assertEqual(result["status"], "certified")
        self.assertEqual(
            result["score_spread"]["effective_execution"]["n"],
            5,
        )
        self.assertIn(
            "mean_95pct_t_interval",
            result["score_spread"]["sustained_competence"],
        )
        leaderboard = format_benchmark_leaderboard(aggregate)
        self.assertIn("gpt-test", leaderboard)
        self.assertIn("Per-replication scores", leaderboard)
        self.assertIn("descriptive mean 95% t interval", leaderboard)

    def test_duplicate_seed_does_not_enter_certified_pool(self) -> None:
        reports = [
            _protocol_report(seed, f"seed-{seed}")
            for seed in sorted(BENCHMARK_SEEDS)
        ]
        reports.append(_protocol_report(11, "seed-11-repeat"))

        result = aggregate_benchmark_reports(reports)["results"][0]

        self.assertFalse(result["certified"])
        self.assertIn(
            "duplicate_seed_replication",
            result["certification_flags"],
        )

    def test_seed_11_alone_produces_provisional_result(self) -> None:
        aggregate = aggregate_benchmark_reports(
            [_protocol_report(11, "seed-11")]
        )

        self.assertEqual(len(aggregate["results"]), 1)
        result = aggregate["results"][0]
        self.assertFalse(result["certified"])
        self.assertTrue(result["provisional"])
        self.assertEqual(result["status"], "provisional")
        self.assertEqual(result["seeds"], [11])
        self.assertIn(
            "| gpt-test | 11 ",
            format_benchmark_leaderboard(aggregate),
        )
        self.assertIn(
            "| provisional |",
            format_benchmark_leaderboard(aggregate),
        )

    def test_seed_41_alone_is_not_provisional(self) -> None:
        aggregate = aggregate_benchmark_reports(
            [_protocol_report(41, "seed-41")]
        )

        self.assertEqual(len(aggregate["results"]), 1)
        result = aggregate["results"][0]
        self.assertFalse(result["certified"])
        self.assertFalse(result["provisional"])
        self.assertEqual(result["status"], "incomplete_replication")

    def test_report_presents_primary_scores_before_invalid_rate(self) -> None:
        report = _protocol_report(11, "seed-11")
        markdown = "\n".join(_render_benchmark_lines(report["benchmarks"]))

        self.assertLess(
            markdown.index("Primary benchmark scorecard"),
            markdown.index("Supporting execution diagnostics"),
        )
        self.assertIn("**Effective execution**", markdown)
        self.assertIn("**Sustained competence**", markdown)
        self.assertIn("**Entrepreneurial agency**", markdown)
        self.assertIn("Invalid proposals", markdown)
        self.assertIn("Supporting economic diagnostics", markdown)
        self.assertIn("Net value created", markdown)
        self.assertIn("(0.0%)", markdown)

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
