from __future__ import annotations

import os
import tempfile
import unittest
import unittest.mock
from argparse import Namespace
from pathlib import Path

import agent_world.benchmarks

from agent_world.benchmarks import (
    BENCHMARK_CORE_FINGERPRINT_FILES,
    BENCHMARK_PROVIDER_FINGERPRINT_FILES,
    BENCHMARK_EXTENDED_SEEDS,
    BENCHMARK_PROTOCOL_ID,
    BENCHMARK_ACCOUNTING_VALUES,
    BENCHMARK_SEEDS,
    BENCHMARK_SCORING_REVISION,
    BENCHMARK_SUITE_ID,
    BENCHMARK_ACCEPTED_ATTRIBUTION_OVERRIDES,
    BENCHMARK_ACCEPTED_PRIOR_TRIALS,
    NON_MATERIAL_FREE_ACTION_EVENTS,
    PURPOSEFUL_ACTION_EVENTS,
    _benchmark_trajectory,
    _cohort_raw_metrics,
    _enterprise_supply,
    accepted_attribution_override,
    accepted_prior_trial,
    aggregate_benchmark_reports,
    benchmark_code_fingerprint,
    benchmark_protocol,
    build_benchmark_results,
    format_benchmark_leaderboard,
    score_benchmark_counts,
)
from agent_world.cli import _apply_benchmark_protocol, _resolve_provider_max_workers
from agent_world.run_report import _render_benchmark_lines


def _protocol_report(
    seed: int,
    source: str,
    *,
    model_output_failure: bool = False,
    harness_failure: bool = False,
    unverified_failure: bool = False,
    workers: int = 40,
    reasoning_effort: str | None = None,
    protocol_id: str = BENCHMARK_PROTOCOL_ID,
) -> dict:
    from agent_world.protocols import get_recipe
    recipe = get_recipe(protocol_id)
    reasoning_effort = reasoning_effort or recipe.reasoning_effort
    agents = [f"agent-{index}" for index in range(1, 11)]
    cohort = {
        "brain": "codex",
        "model": "gpt-test",
        "reasoning_effort": reasoning_effort,
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
            "transfer_kind_mode": recipe.defaults()["transfer_kind_mode"],
            "economy_mode": "organic",
            "world_variant": "frontier",
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
            "benchmark_protocol": protocol_id,
            "benchmark_code_fingerprint": benchmark_code_fingerprint(["codex_cli"], protocol_id),
            "decision_mode": "raw",
            "turn_resolution": "simultaneous",
            "global_max_workers": workers,
            "provider_max_workers": {"codex_cli": workers},
            "agent_io_log": True,
            "action_feedback_mode": "baseline",
            "connector_profile": "connector-v3",
            "conversation_mode": "fresh-conversation",
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
    if unverified_failure:
        # Shape of a pre-validator failure: the production adapter's own parse
        # error, with nothing proving whether the model or the adapter erred.
        responses[0]["message"] = (
            "Codex decision failed: Codex action arguments_json is invalid: "
            "Expecting value: line 1 column 1 (char 0)"
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
            1
            if model_output_failure or harness_failure or unverified_failure
            else 0:
        ]
    ]
    report["benchmarks"] = build_benchmark_results(
        [start, *responses, *purposeful_events],
        snapshot,
        report,
    )
    return report


class BenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        # _apply_benchmark_protocol sets the Claude deliberation envelope in
        # process env; restore whatever was there so other tests see defaults.
        self._saved_thinking = os.environ.get("CLAUDE_MAX_THINKING_TOKENS")
        self.addCleanup(self._restore_thinking)

    def _restore_thinking(self) -> None:
        if self._saved_thinking is None:
            os.environ.pop("CLAUDE_MAX_THINKING_TOKENS", None)
        else:
            os.environ["CLAUDE_MAX_THINKING_TOKENS"] = self._saved_thinking

    def test_protocol_sets_claude_deliberation_envelope(self) -> None:
        args = Namespace(
            benchmark_protocol=BENCHMARK_PROTOCOL_ID,
            population=None,
            brain="claude",
            sequential_decisions=False,
            seed=None,
        )

        _apply_benchmark_protocol(args)

        # V5's one harness change: Claude gets the same opportunity to think
        # that Codex models have always had, inside a declared ceiling.
        self.assertEqual(os.environ.get("CLAUDE_MAX_THINKING_TOKENS"), self._saved_thinking)
        self.assertEqual(args.claude_thinking_budget_tokens, 2048)
        self.assertEqual(
            benchmark_protocol()["trial"]["claude_thinking_budget_tokens"], 2048
        )

    def test_pre_contract_synthetic_ledger_scores_are_unchanged(self) -> None:
        scores = _protocol_report(11, "pre-contract-score-regression")["benchmarks"]["cohorts"][
            "cohort-1"
        ]["scores"]
        self.assertEqual(
            {name: score["score"] for name, score in scores.items()},
            {
                "effective_execution": 100.0,
                "sustained_competence": 36.12,
                "entrepreneurial_agency": 0.0,
                "economic_productivity": 0.0,
            },
        )

    def test_settled_contract_matches_equivalent_trade_enterprise_flow(self) -> None:
        trade = self._trade("agent-1", "agent-2", {"food": 2}, {"coin": 3})
        contract = {
            "type": "contract_settled",
            "tick": 0,
            "actor_id": "agent-1",
            "data": {
                "contract": {"proposer_id": "agent-1", "buyer_id": "agent-2"},
                "transaction": {"give": {"food": 2}, "receive": {"coin": 3}},
            },
        }
        self.assertEqual(
            _enterprise_supply([contract], {"agent-1", "agent-2"}),
            _enterprise_supply([trade], {"agent-1", "agent-2"}),
        )

    def test_contract_default_collateral_is_not_enterprise_supply(self) -> None:
        event = {
            "type": "contract_defaulted",
            "tick": 2,
            "actor_id": "agent-1",
            "data": {
                "contract": {"proposer_id": "agent-1", "buyer_id": "agent-2"},
                "flow": {
                    "from": "agent-1",
                    "to": "agent-2",
                    "items": {"tool": 1},
                    "enterprise_supply_eligible": False,
                },
            },
        }
        self.assertEqual(_enterprise_supply([event], {"agent-1", "agent-2"})["total"], 0.0)

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
        self.assertEqual(args.preset, "frontier-generalists")
        self.assertEqual(args.world_variant, "frontier")
        self.assertEqual(args.reasoning_effort, "low")
        self.assertEqual(args.connector_profile, "connector-v3")
        self.assertEqual(args.max_workers, 40)
        self.assertEqual(args.codex_max_workers, 40)
        # Scoped to the adapter this trial will invoke, not every adapter.
        self.assertEqual(
            args.benchmark_code_fingerprint, benchmark_code_fingerprint(["codex_cli"])
        )
        self.assertNotEqual(
            args.benchmark_code_fingerprint, benchmark_code_fingerprint()
        )

    def test_claude_protocol_run_uses_twenty_workers(self) -> None:
        args = Namespace(
            benchmark_protocol=BENCHMARK_PROTOCOL_ID,
            population=None,
            brain="claude",
            sequential_decisions=False,
            seed=None,
        )

        _apply_benchmark_protocol(args)

        self.assertEqual(args.max_workers, 20)
        self.assertEqual(args.claude_max_workers, 20)
        self.assertEqual(args.grok_max_workers, 20)
        self.assertEqual(args.codex_max_workers, 40)

    def test_grok_protocol_run_uses_twenty_workers(self) -> None:
        args = Namespace(
            benchmark_protocol=BENCHMARK_PROTOCOL_ID,
            population=None,
            brain="grok",
            sequential_decisions=False,
            seed=None,
        )

        _apply_benchmark_protocol(args)

        self.assertEqual(args.max_workers, 20)
        self.assertEqual(args.grok_max_workers, 20)

    def test_zcode_protocol_uses_twenty_workers_and_low_effort(self) -> None:
        args = Namespace(
            benchmark_protocol=BENCHMARK_PROTOCOL_ID,
            population=None,
            brain="zcode",
            sequential_decisions=False,
            seed=None,
        )

        _apply_benchmark_protocol(args)

        self.assertEqual(args.max_workers, 20)
        self.assertEqual(args.zcode_max_workers, 20)
        self.assertEqual(args.reasoning_effort, "low")

    def test_protocol_preserves_explicit_worker_overrides(self) -> None:
        args = Namespace(
            benchmark_protocol=BENCHMARK_PROTOCOL_ID,
            population=None,
            brain="zcode",
            sequential_decisions=False,
            seed=None,
            max_workers=2,
            zcode_max_workers=2,
        )

        _apply_benchmark_protocol(args)

        self.assertEqual(args.max_workers, 2)
        self.assertEqual(args.zcode_max_workers, 2)

    def test_worker_count_is_operational_not_protocol_compliance(self) -> None:
        report = _protocol_report(11, "two-worker-run", workers=2)
        cohort = report["benchmarks"]["cohorts"]["cohort-1"]
        protocol = benchmark_protocol()

        self.assertTrue(cohort["protocol_compliant"])
        self.assertNotIn(
            "protocol_mismatch:global_max_workers",
            cohort["quality_flags"],
        )
        self.assertNotIn(
            "protocol_mismatch:provider_max_workers",
            cohort["quality_flags"],
        )
        self.assertFalse(
            protocol["execution_defaults"]["worker_count_is_protocol_setting"]
        )
        self.assertNotIn("global_max_workers", protocol["trial"])
        self.assertNotIn("provider_max_workers", protocol["trial"])

    def test_medium_effort_v7_attempt_is_not_protocol_compliant(self) -> None:
        report = _protocol_report(
            11,
            "pre-low-v7-medium-attempt",
            reasoning_effort="medium",
        )
        cohort = report["benchmarks"]["cohorts"]["cohort-1"]

        self.assertFalse(cohort["protocol_compliant"])
        self.assertIn(
            "protocol_mismatch:reasoning_effort",
            cohort["quality_flags"],
        )
        aggregate = aggregate_benchmark_reports([report])
        self.assertEqual(aggregate["results"], [])

    def test_provider_defaults_are_clamped_to_run_workers(self) -> None:
        limits = _resolve_provider_max_workers(Namespace(), 12)

        self.assertEqual(limits["codex_cli"], 12)
        self.assertEqual(limits["claude_cli"], 12)
        self.assertEqual(limits["grok_cli"], 12)
        self.assertEqual(limits["zcode_cli"], 12)
        self.assertEqual(limits["openrouter"], 4)

    def test_explicit_provider_workers_are_also_clamped_to_global_pool(self) -> None:
        limits = _resolve_provider_max_workers(
            Namespace(codex_max_workers=35, claude_max_workers=7), 30
        )

        self.assertEqual(limits["codex_cli"], 30)
        self.assertEqual(limits["claude_cli"], 7)

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

    def test_protocol_accepts_certification_and_optional_extended_seeds(self) -> None:
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
                "enterprise_supply_value": 40,
            }
        )

        self.assertEqual(scores["effective_execution"]["score"], 63.25)
        self.assertAlmostEqual(
            scores["sustained_competence"]["score"],
            (63.25 * ((90 * 60) ** 0.5) * 50) ** (1 / 3),
            places=2,
        )
        # supply 40/100 agent-ticks = 200; net value (120-80)=40/100 = 200.
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
        self.assertAlmostEqual(raw["initial_endowment_value"], 27.0)
        # The fixture's completed farm is worth exactly the materials it
        # consumed, so the only "growth" is the fixture handing the cohort a
        # structure. The 10,000-unit internal trade contributes nothing.
        self.assertAlmostEqual(raw["living_terminal_economic_value"], 28.25)
        self.assertEqual(raw["venture_initiatives"], 2)
        self.assertEqual(raw["enterprise_supply_value"], 0.0)
        self.assertEqual(
            entrepreneurship["components"]["enterprise_supply_score"],
            0.0,
        )
        self.assertEqual(entrepreneurship["score"], 0.0)

    def test_recipe_consistent_values_do_not_penalize_production_chains(self) -> None:
        self.assertAlmostEqual(BENCHMARK_ACCOUNTING_VALUES["ingot"], 19)
        self.assertAlmostEqual(BENCHMARK_ACCOUNTING_VALUES["advanced_tool"], 43)
        # Minting must be exactly value preserving. Rounding the per-unit coin
        # value up would multiply the error by the eight-coin output and let a
        # cohort print accounting value on every ore -> ingot -> coin cycle.
        self.assertAlmostEqual(BENCHMARK_ACCOUNTING_VALUES["coin"] * 8, 19)
        report = _protocol_report(11, "recipe-values")
        raw = report["benchmarks"]["cohorts"]["cohort-1"]["raw"]
        self.assertAlmostEqual(raw["initial_endowment_value"], 135.0)

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

    def _trade(self, offerer: str, acceptor: str, give: dict, receive: dict) -> dict:
        return {
            "type": "accept_trade",
            "tick": 0,
            "actor_id": acceptor,
            "data": {
                "trade": {"from_agent": offerer, "accepted_by": acceptor},
                "transaction": {"give": give, "receive": receive},
            },
        }

    def test_free_bookkeeping_actions_cannot_earn_purposeful_activity(self) -> None:
        """An all-`publish_rule` policy must be as worthless as an all-`wait` one."""

        from agent_world.rules import FREE_ACTION_TYPES

        self.assertFalse(PURPOSEFUL_ACTION_EVENTS & NON_MATERIAL_FREE_ACTION_EVENTS)
        # Every zero-action-point event that is still counted must move goods.
        self.assertEqual(
            PURPOSEFUL_ACTION_EVENTS & FREE_ACTION_TYPES,
            {
                "accept_trade",
                "accept_contract",
                "repay_contract",
                "claim_dividend",
            },
        )

        raw = _cohort_raw_metrics(
            events=[
                {
                    "type": "agent_response",
                    "tick": tick,
                    "actor_id": "agent-1",
                    "data": {"actions": [{"type": "publish_rule"}]},
                }
                for tick in range(4)
            ]
            + [
                {"type": event, "tick": tick, "actor_id": "agent-1", "data": {}}
                for tick, event in enumerate(
                    ["publish_rule", "create_group", "leave_group", "revoke_access"]
                )
            ],
            snapshot={"agents": {"agent-1": {"alive": True, "health": 100}}},
            config={"economy_mode": "organic"},
            member_ids=["agent-1"],
            final_tick=4,
            target_ticks=4,
        )

        self.assertEqual(raw["purposeful_agent_ticks"], 0)
        scores = score_benchmark_counts(raw)
        self.assertEqual(
            scores["effective_execution"]["components"]["action_feasibility_pct"],
            100.0,
        )
        self.assertEqual(scores["effective_execution"]["score"], 0.0)

    def test_minting_chain_cannot_manufacture_accounting_value(self) -> None:
        """ore -> ingot -> coins must conserve accounting units exactly."""

        values = BENCHMARK_ACCOUNTING_VALUES
        smelt_inputs = 2 * values["ore"] + values["wood"]
        self.assertAlmostEqual(smelt_inputs, values["ingot"])
        self.assertAlmostEqual(values["ingot"], 8 * values["coin"])
        self.assertAlmostEqual(smelt_inputs, 8 * values["coin"])

    def test_unclassified_gifts_never_score_as_supply(self) -> None:
        """Scoring revision 2: a raw gift is reported, not scored."""

        events = [
            {
                "type": "gift",
                "tick": 1,
                "actor_id": "agent-1",
                "data": {"to": "agent-2", "items": {"food": 3}},
            }
        ]
        supply = _enterprise_supply(events, {"agent-1", "agent-2"})
        self.assertEqual(supply["total"], 0.0)
        self.assertEqual(supply["informal_transfers"], 6.0)

    def test_payment_verdict_credits_the_recipient_as_vendor(self) -> None:
        """A classified bounty payment is service income earned by the scout,
        never goods supplied by the payer."""

        events = [
            {
                "type": "gift",
                "tick": 1,
                "actor_id": "agent-1",
                "data": {"to": "agent-2", "items": {"fiber": 3}},
            }
        ]
        supply = _enterprise_supply(
            events, {"agent-1", "agent-2"}, {0: "payment_for_service"}
        )
        self.assertEqual(supply["by_source"]["net_service_income"], 6.0)
        self.assertEqual(supply["by_source"]["net_goods_supplied_to_others"], 0.0)
        self.assertEqual(supply["total"], 6.0)
        self.assertEqual(supply["informal_transfers"], 0.0)

        # The payer's outlay nets against income they earn elsewhere, exactly
        # like access fees: paying for services is spending, not vending.
        both_ways = _enterprise_supply(
            events
            + [
                {
                    "type": "gift",
                    "tick": 2,
                    "actor_id": "agent-2",
                    "data": {"to": "agent-1", "items": {"fiber": 3}},
                }
            ],
            {"agent-1", "agent-2"},
            {0: "payment_for_service", 1: "payment_for_service"},
        )
        self.assertEqual(both_ways["total"], 0.0)

    def test_barter_verdict_keeps_goods_flow_semantics(self) -> None:
        events = [
            {
                "type": "gift",
                "tick": 1,
                "actor_id": "agent-1",
                "data": {"to": "agent-2", "items": {"wood": 2}},
            },
            {
                "type": "gift",
                "tick": 2,
                "actor_id": "agent-2",
                "data": {"to": "agent-1", "items": {"food": 3}},
            },
        ]
        verdicts = {0: "barter_settlement", 1: "barter_settlement"}
        supply = _enterprise_supply(events, {"agent-1", "agent-2"}, verdicts)
        # Two-way exchange of different goods: both directional flows are real
        # supply, same as an accepted trade of wood for food.
        self.assertEqual(supply["by_source"]["net_goods_supplied_to_others"], 12.0)
        # A barter wash of the SAME good still cancels via per-agent netting.
        wash = _enterprise_supply(
            [
                {
                    "type": "gift",
                    "tick": 1,
                    "actor_id": "agent-1",
                    "data": {"to": "agent-2", "items": {"wood": 2}},
                },
                {
                    "type": "gift",
                    "tick": 2,
                    "actor_id": "agent-2",
                    "data": {"to": "agent-1", "items": {"wood": 2}},
                },
            ],
            {"agent-1", "agent-2"},
            verdicts,
        )
        self.assertEqual(wash["total"], 0.0)

    def test_declared_payment_kind_scores_without_an_artifact(self) -> None:
        """V7: agents self-classify; scoring trusts the declaration."""

        events = [
            {
                "type": "gift",
                "tick": 1,
                "actor_id": "agent-1",
                "data": {"to": "agent-2", "items": {"fiber": 3}, "kind": "payment"},
            }
        ]
        supply = _enterprise_supply(events, {"agent-1", "agent-2"})
        self.assertEqual(supply["by_source"]["net_service_income"], 6.0)
        self.assertEqual(supply["total"], 6.0)

    def test_undeclared_or_gift_kind_forfeits_the_credit(self) -> None:
        """Strict liability: misfiling a payment as a gift is the model's loss."""

        for data in (
            {"to": "agent-2", "items": {"fiber": 3}},
            {"to": "agent-2", "items": {"fiber": 3}, "kind": "gift"},
        ):
            supply = _enterprise_supply(
                [{"type": "gift", "tick": 1, "actor_id": "agent-1", "data": data}],
                {"agent-1", "agent-2"},
            )
            self.assertEqual(supply["total"], 0.0)
            self.assertEqual(supply["informal_transfers"], 6.0)

    def test_artifact_verdict_overrides_declared_kind(self) -> None:
        """Frozen judge artifacts (v6 rescores) outrank self-declarations."""

        events = [
            {
                "type": "gift",
                "tick": 1,
                "actor_id": "agent-1",
                "data": {"to": "agent-2", "items": {"fiber": 3}, "kind": "payment"},
            }
        ]
        supply = _enterprise_supply(
            events, {"agent-1", "agent-2"}, {0: "unrequited_transfer"}
        )
        self.assertEqual(supply["total"], 0.0)

    def test_wash_trading_creates_no_enterprise_supply(self) -> None:
        """Value that returns to its origin must score nothing."""

        # Straight round trip between a pair.
        pairwise = _enterprise_supply(
            [
                self._trade("agent-1", "agent-2", {"wood": 5}, {"food": 5}),
                self._trade("agent-2", "agent-1", {"wood": 5}, {"food": 5}),
            ],
            {"agent-1", "agent-2"},
        )
        self.assertEqual(pairwise["total"], 0.0)

        # Circular flow, which per-pair netting would miss.
        circular = _enterprise_supply(
            [
                self._trade("agent-1", "agent-2", {"wood": 3}, {}),
                self._trade("agent-2", "agent-3", {"wood": 3}, {}),
                self._trade("agent-3", "agent-1", {"wood": 3}, {}),
            ],
            {"agent-1", "agent-2", "agent-3"},
        )
        self.assertEqual(circular["total"], 0.0)

    def test_producer_selling_to_same_model_peers_scores_enterprise_supply(self) -> None:
        """A cohort member with customers is an entrepreneur even when the
        customers run the same model and cohort net worth does not move."""

        supply = _enterprise_supply(
            [
                {
                    "type": "harvest",
                    "tick": 1,
                    "actor_id": "agent-1",
                    "data": {
                        "improved_land": True,
                        "resource": "food",
                        "quantity": 6,
                    },
                },
                self._trade("agent-1", "agent-2", {"food": 3}, {"coin": 8}),
                self._trade("agent-1", "agent-3", {"food": 2}, {"coin": 6}),
            ],
            {"agent-1", "agent-2", "agent-3"},
        )

        by_source = supply["by_source"]
        # Five food supplied outward at two units each; coin paid back is
        # excluded so buyers are not credited for supplying currency.
        self.assertEqual(by_source["net_goods_supplied_to_others"], 10.0)
        # Capital output is reported but not scored: those six harvested food
        # sit in cohort inventory, so net value creation already counts them.
        # Only the five that reached other agents are enterprise supply.
        self.assertEqual(supply["own_capital_output"], 12.0)
        self.assertEqual(supply["total"], 10.0)

    def test_access_fee_wash_between_members_nets_out(self) -> None:
        events = [
            {
                "type": "pay_access_fee",
                "tick": 0,
                "actor_id": "agent-1",
                "recipients": ["agent-2"],
                "data": {"fee": {"food": 2}},
            },
            {
                "type": "pay_access_fee",
                "tick": 1,
                "actor_id": "agent-2",
                "recipients": ["agent-1"],
                "data": {"fee": {"food": 2}},
            },
        ]
        self.assertEqual(
            _enterprise_supply(events, {"agent-1", "agent-2"})["total"], 0.0
        )
        # One-directional fee income is real service revenue.
        self.assertEqual(
            _enterprise_supply(events[:1], {"agent-1", "agent-2"})["by_source"][
                "net_service_income"
            ],
            4.0,
        )

    def test_entrepreneurship_is_not_a_restatement_of_terminal_wealth(self) -> None:
        """Two cohorts with identical wealth must separate on enterprise."""

        base = {
            "submitted_actions": 100,
            "submitted_actions_excluding_contention": 100,
            "possible_agent_ticks": 100,
            "initial_endowment_value": 80,
            "living_terminal_economic_value": 120,
        }
        forager = score_benchmark_counts({**base, "enterprise_supply_value": 0})
        trader = score_benchmark_counts({**base, "enterprise_supply_value": 20})

        self.assertEqual(
            forager["sustained_competence"]["components"]["material_outcome_pct"],
            trader["sustained_competence"]["components"]["material_outcome_pct"],
        )
        self.assertEqual(forager["entrepreneurial_agency"]["score"], 0.0)
        # geometric_mean(supply 100, value creation 200)
        self.assertEqual(trader["entrepreneurial_agency"]["score"], 141.42)

    def test_accepted_prior_trial_requires_an_exact_audited_match(self) -> None:
        """Promotion is a named allowlist, never an inferred rule."""

        fingerprint = next(iter(BENCHMARK_ACCEPTED_PRIOR_TRIALS))
        entry = BENCHMARK_ACCEPTED_PRIOR_TRIALS[fingerprint]

        # Matching fingerprint under its audited protocol is accepted.
        self.assertIsNotNone(accepted_prior_trial(entry["protocol"], fingerprint))
        # Every entry must carry both the deviation and the audit that
        # justified it, so no artifact can present a bare exemption.
        for record in BENCHMARK_ACCEPTED_PRIOR_TRIALS.values():
            self.assertTrue(record.get("deviation"))
            self.assertTrue(record.get("audited"))

        # A fingerprint is never promotable under a protocol it was not
        # audited against, and unknown fingerprints are never promotable.
        self.assertIsNone(accepted_prior_trial("participant-v1", fingerprint))
        self.assertIsNone(accepted_prior_trial(entry["protocol"], "deadbeef"))
        self.assertIsNone(accepted_prior_trial(None, None))

    def test_capital_output_is_reported_but_not_scored_as_supply(self) -> None:
        """Harvests from own land already count in net value creation."""

        supply = _enterprise_supply(
            [
                {
                    "type": "harvest",
                    "tick": 1,
                    "actor_id": "agent-1",
                    "data": {
                        "improved_land": True,
                        "resource": "food",
                        "quantity": 10,
                    },
                }
            ],
            {"agent-1"},
        )

        self.assertEqual(supply["own_capital_output"], 20.0)
        self.assertEqual(supply["total"], 0.0)

    def test_attribution_override_requires_every_field_to_match(self) -> None:
        """The one judgment call in the suite must not be able to widen."""

        entry = BENCHMARK_ACCEPTED_ATTRIBUTION_OVERRIDES[0]
        exact = {
            "model": entry["model"],
            "seed": entry["seed"],
            "source_fingerprint": entry["source_fingerprint"],
            "unverified_failures": entry["unverified_model_output_failures"],
        }
        self.assertIsNotNone(accepted_attribution_override(**exact))

        # One more unattributable failure than was audited must not be covered.
        self.assertIsNone(
            accepted_attribution_override(
                **{**exact, "unverified_failures": exact["unverified_failures"] + 1}
            )
        )
        self.assertIsNone(
            accepted_attribution_override(**{**exact, "model": "gpt-5.4"})
        )
        self.assertIsNone(accepted_attribution_override(**{**exact, "seed": 41}))
        self.assertIsNone(
            accepted_attribution_override(
                **{**exact, "source_fingerprint": "deadbeef"}
            )
        )

        # Every override must state its magnitude and who accepted it.
        for record in BENCHMARK_ACCEPTED_ATTRIBUTION_OVERRIDES:
            self.assertTrue(record.get("deviation"))
            self.assertTrue(record.get("sensitivity"))
            self.assertTrue(record.get("accepted_because"))

    def test_unaudited_model_output_failure_still_flags(self) -> None:
        """The override is an allowlist, not a relaxation of the rule."""

        report = _protocol_report(11, "unaudited", unverified_failure=True)
        cohort = report["benchmarks"]["cohorts"]["cohort-1"]

        self.assertIn(
            "unverified_model_output_attribution", cohort["quality_flags"]
        )
        self.assertFalse(cohort["protocol_compliant"])
        self.assertIsNone(cohort["attribution_override"])

    def test_entrepreneurship_score_has_no_upper_bound(self) -> None:
        scores = score_benchmark_counts(
            {
                "submitted_actions": 100,
                "submitted_actions_excluding_contention": 100,
                "possible_agent_ticks": 100,
                "initial_endowment_value": 80,
                "living_terminal_economic_value": 160,
                "venture_initiatives": 20,
                "enterprise_supply_value": 80,
            }
        )

        entrepreneurship = scores["entrepreneurial_agency"]
        self.assertEqual(
            entrepreneurship["components"]["enterprise_supply_score"], 400.0
        )
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

    def test_two_required_seeds_produce_certified_pooled_result(self) -> None:
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
        self.assertEqual(result["required_seeds"], sorted(BENCHMARK_SEEDS))
        self.assertEqual(result["extended_seeds"], [])
        self.assertEqual(result["raw"]["submitted_actions"], 20)
        self.assertEqual(result["status"], "certified")
        self.assertEqual(
            result["score_spread"]["effective_execution"]["n"],
            2,
        )
        self.assertIn(
            "absolute_difference",
            result["score_spread"]["sustained_competence"],
        )
        leaderboard = format_benchmark_leaderboard(aggregate)
        self.assertIn("gpt-test", leaderboard)
        self.assertIn("Per-replication scores", leaderboard)
        self.assertIn("absolute seed difference", leaderboard)
        self.assertNotIn("95%", leaderboard)

    def test_optional_extended_seed_does_not_change_official_score(self) -> None:
        required_reports = [
            _protocol_report(seed, f"seed-{seed}")
            for seed in sorted(BENCHMARK_SEEDS)
        ]
        official = aggregate_benchmark_reports(required_reports)["results"][0]
        extended_seed = min(BENCHMARK_EXTENDED_SEEDS)
        with_extended = aggregate_benchmark_reports(
            required_reports
            + [_protocol_report(extended_seed, f"seed-{extended_seed}")]
        )["results"][0]

        self.assertTrue(with_extended["certified"])
        self.assertEqual(with_extended["required_seeds"], sorted(BENCHMARK_SEEDS))
        self.assertEqual(with_extended["extended_seeds"], [extended_seed])
        self.assertEqual(with_extended["raw"], official["raw"])
        self.assertEqual(with_extended["scores"], official["scores"])
        self.assertEqual(with_extended["extended_raw"]["submitted_actions"], 30)
        leaderboard = format_benchmark_leaderboard(
            aggregate_benchmark_reports(
                required_reports
                + [_protocol_report(extended_seed, f"seed-{extended_seed}")]
            )
        )
        self.assertIn("(+1 extended)", leaderboard)
        self.assertIn("optional extended", leaderboard)

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





class BenchmarkFingerprintScopeTests(unittest.TestCase):
    """The fingerprint must catch real changes without firing on unrelated ones."""

    def test_provider_scope_excludes_adapters_a_trial_never_invoked(self) -> None:
        claude = benchmark_code_fingerprint(["claude_cli"])
        codex = benchmark_code_fingerprint(["codex_cli"])
        self.assertNotEqual(claude, codex)
        # Neither equals the all-adapter fingerprint, so scoping is in effect.
        self.assertNotEqual(claude, benchmark_code_fingerprint())
        # Asking twice is stable.
        self.assertEqual(claude, benchmark_code_fingerprint(["claude_cli"]))

    def test_every_provider_maps_to_a_real_source_file(self) -> None:
        package_dir = Path(agent_world.benchmarks.__file__).resolve().parent
        for provider, names in BENCHMARK_PROVIDER_FINGERPRINT_FILES.items():
            for name in names:
                self.assertTrue(
                    (package_dir / name).exists(),
                    f"{provider} maps to missing source {name}",
                )
        for name in BENCHMARK_CORE_FINGERPRINT_FILES:
            self.assertTrue((package_dir / name).exists(), f"missing core source {name}")

    def test_comments_and_docstrings_do_not_change_the_fingerprint(self) -> None:
        source = b'"""Doc."""\n# a comment\nX = 1\n'
        same_behavior = b'"""Different doc."""\n# an entirely different comment\nX = 1\n'
        different_behavior = b'"""Doc."""\n# a comment\nX = 2\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_bytes(source)
            baseline = agent_world.benchmarks._behavior_source_uncached(path)
            path.write_bytes(same_behavior)
            self.assertEqual(
                baseline, agent_world.benchmarks._behavior_source_uncached(path)
            )
            path.write_bytes(different_behavior)
            self.assertNotEqual(
                baseline, agent_world.benchmarks._behavior_source_uncached(path)
            )

    def test_unparsable_source_fails_closed_on_raw_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.py"
            path.write_bytes(b"def (:\n")
            self.assertEqual(
                agent_world.benchmarks._behavior_source_uncached(path), b"def (:\n"
            )


class ResumeFingerprintGuardTests(unittest.TestCase):
    """The resume guard must use the same provider scoping launch records.

    Regression: the guard originally compared a checkpoint's provider-scoped
    fingerprint against the unscoped hash, so every benchmark resume was
    rejected even at the exact launch commit — which would have broken every
    rate-limit pause/resume mid-campaign.
    """

    def test_resume_accepts_the_scoped_launch_fingerprint(self) -> None:
        from agent_world.cli import _check_resume_fingerprint

        scoped = benchmark_code_fingerprint(["codex_cli"])
        self.assertNotEqual(scoped, benchmark_code_fingerprint())
        # Must not raise: same code, same provider scope as launch recorded.
        _check_resume_fingerprint(BENCHMARK_PROTOCOL_ID, scoped, ["codex_cli"])

    def test_resume_rejects_a_changed_fingerprint(self) -> None:
        from agent_world.cli import _check_resume_fingerprint

        with self.assertRaises(ValueError):
            _check_resume_fingerprint(
                BENCHMARK_PROTOCOL_ID, "not-a-real-hash", ["codex_cli"]
            )

    def test_resume_accepts_an_audited_compatible_fingerprint(self) -> None:
        from agent_world.cli import _check_resume_fingerprint

        import agent_world.cli as cli_module

        with unittest.mock.patch.object(
            cli_module,
            "BENCHMARK_COMPATIBLE_SOURCE_FINGERPRINTS",
            frozenset({"audited-old-hash"}),
        ):
            _check_resume_fingerprint(
                BENCHMARK_PROTOCOL_ID, "audited-old-hash", ["codex_cli"]
            )

    def test_fable_launch_fingerprint_is_registered_for_its_own_suite(self) -> None:
        # The Fable v6 checkpoints resume from a v6-pinned worktree, where this
        # entry suppresses the fingerprint mismatch the quota fix introduced.
        self.assertIn(
            "7dff4cecc0b56951c1a5bf504a1dfc5f0446ef8d6e7cefc6dbddcebdbe2addb6",
            agent_world.benchmarks.BENCHMARK_COMPATIBLE_SOURCE_FINGERPRINTS,
        )

    def test_resume_refuses_a_checkpoint_from_an_earlier_protocol(self) -> None:
        # A historical source fingerprint cannot be accepted merely because
        # its recipe is now selectable in the current checkout.
        from agent_world.cli import _check_resume_fingerprint

        with self.assertRaises(ValueError) as caught:
            _check_resume_fingerprint(
                "participant-v6",
                "7dff4cecc0b56951c1a5bf504a1dfc5f0446ef8d6e7cefc6dbddcebdbe2addb6",
                ["claude_cli"],
            )
        self.assertIn("pinned to its own launch commit", str(caught.exception))

    def test_non_benchmark_resume_is_unguarded(self) -> None:
        from agent_world.cli import _check_resume_fingerprint

        _check_resume_fingerprint(None, "anything", ["codex_cli"])


class FingerprintRegistryExemptionTests(unittest.TestCase):
    def test_registry_edits_do_not_move_the_fingerprint(self) -> None:
        # Accepting an old report must not orphan current ones: registry
        # constants are metadata about history, not behavior.
        base = 'BENCHMARK_COMPATIBLE_REPORT_FINGERPRINTS: frozenset[str] = frozenset({"a"})\nX = 1\n'
        edited = 'BENCHMARK_COMPATIBLE_REPORT_FINGERPRINTS: frozenset[str] = frozenset({"a", "b"})\nX = 1\n'
        behavior_change = 'BENCHMARK_COMPATIBLE_REPORT_FINGERPRINTS: frozenset[str] = frozenset({"a"})\nX = 2\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text(base)
            baseline = agent_world.benchmarks._behavior_source_uncached(path)
            path.write_text(edited)
            self.assertEqual(baseline, agent_world.benchmarks._behavior_source_uncached(path))
            path.write_text(behavior_change)
            self.assertNotEqual(baseline, agent_world.benchmarks._behavior_source_uncached(path))


class PriorSuiteAcceptanceTests(unittest.TestCase):
    """The prior-suite registry mechanism, exercised with a patched entry.

    The registry itself is empty for v6 - the world changed, so no earlier
    trial can carry over - but the acceptance machinery stays tested so a
    future suite that CAN carry results forward has a proven path.
    """

    V4_SUITE = "agent-world-participant-v4"
    V4_FINGERPRINT = "2563b8f7166f071bbc6b48e372c96793252cc4d188317d0f6f724ef1708617bc"

    def setUp(self) -> None:
        patcher = unittest.mock.patch.dict(
            agent_world.benchmarks.BENCHMARK_ACCEPTED_PRIOR_SUITE_REPORTS,
            {
                (self.V4_SUITE, self.V4_FINGERPRINT): {
                    "providers": frozenset({"codex_cli"}),
                    "deviation": "scored_under_participant_v4: test entry.",
                    "audited": "test audit note.",
                }
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _v4_report(self, seed: int, source: str, provider: str = "codex_cli") -> dict:
        report = _protocol_report(seed, source)
        report["benchmarks"]["suite_id"] = self.V4_SUITE
        report["benchmarks"]["protocol"]["id"] = "participant-v4"
        report["benchmarks"]["protocol"]["code_fingerprint_sha256"] = self.V4_FINGERPRINT
        report["benchmarks"]["cohorts"]["cohort-1"]["provider"] = provider
        report["usage"] = {"calls": 500, "reasoning_tokens": 400_000}
        return report

    def test_audited_v4_codex_pair_certifies_with_declared_deviation(self) -> None:
        aggregate = aggregate_benchmark_reports(
            [self._v4_report(11, "v4-seed11"), self._v4_report(41, "v4-seed41")]
        )
        self.assertEqual(aggregate["rejected"], [])
        result = aggregate["results"][0]
        self.assertTrue(result["certified"])
        self.assertEqual(result["status"], "certified_with_declared_deviation")
        self.assertTrue(
            any(
                "scored_under_participant_v4" in d.get("deviation", "")
                for d in result["declared_deviations"]
            )
        )
        # Deliberation spend pools across the pair: 800k tokens / 1000 calls.
        self.assertEqual(result["mean_reasoning_tokens_per_call"], 800.0)
        board = format_benchmark_leaderboard(aggregate)
        self.assertIn("Reasoning/decision", board)
        self.assertIn("800 tok", board)

    def test_prior_suite_claude_cohorts_are_not_carried_over(self) -> None:
        # V5 exists to give Claude the deliberation opportunity v4 denied it,
        # so v4 claude results must re-run rather than carry over - even when
        # the report fingerprint itself is in the audited registry.
        aggregate = aggregate_benchmark_reports(
            [self._v4_report(11, "v4-claude", provider="claude_cli")]
        )
        self.assertEqual(aggregate["results"], [])
        self.assertEqual(
            aggregate["rejected"][0]["reason"], "prior_suite_provider_not_audited"
        )

    def test_unknown_prior_suite_fingerprint_is_rejected(self) -> None:
        report = self._v4_report(11, "v4-unknown")
        report["benchmarks"]["protocol"]["code_fingerprint_sha256"] = "f" * 64
        aggregate = aggregate_benchmark_reports([report])
        self.assertEqual(
            aggregate["rejected"][0]["reason"],
            "missing_or_incompatible_benchmark_suite",
        )


class VersionedRecipeScoringTests(unittest.TestCase):
    def test_both_recipes_score_and_aggregate_independently_in_one_process(self):
        for protocol_id in ("participant-v6", "participant-v7", "participant-v6"):
            report = _protocol_report(11, protocol_id, protocol_id=protocol_id)
            self.assertTrue(report["benchmarks"]["trial"]["protocol_compliant"])
            self.assertEqual(report["benchmarks"]["protocol"]["id"], protocol_id)
            aggregate = aggregate_benchmark_reports([report])
            self.assertEqual(aggregate["protocol"]["id"], protocol_id)
            self.assertEqual(aggregate["rejected"], [])
            self.assertEqual(len(aggregate["results"]), 1)
            self.assertEqual(aggregate["results"][0]["scoring_revision"], 2 if protocol_id == "participant-v6" else 1)

    def test_mixed_recipes_require_selection_and_never_pool_counts(self):
        v6 = _protocol_report(11, "v6", protocol_id="participant-v6")
        v7 = _protocol_report(41, "v7", protocol_id="participant-v7")
        with self.assertRaisesRegex(ValueError, "Mixed benchmark recipes"):
            aggregate_benchmark_reports([v6, v7])
        selected = aggregate_benchmark_reports([v6, v7], "participant-v6")
        self.assertEqual(len(selected["results"]), 1)
        self.assertFalse(selected["results"][0]["certified"])
        self.assertEqual(selected["rejected"][0]["source"], "v7")

    def test_each_recipe_resumes_only_with_its_own_source_fingerprint(self):
        from agent_world.cli import _check_resume_fingerprint
        for protocol_id in ("participant-v6", "participant-v7"):
            fingerprint = benchmark_code_fingerprint(["codex_cli"], protocol_id)
            _check_resume_fingerprint(protocol_id, fingerprint, ["codex_cli"])
            other = "participant-v7" if protocol_id == "participant-v6" else "participant-v6"
            with self.assertRaises(ValueError):
                _check_resume_fingerprint(other, fingerprint, ["codex_cli"])

    def test_v6_does_not_trust_a_v7_self_declared_payment(self):
        events = [{"type": "gift", "actor_id": "a", "data": {
            "to": "b", "items": {"coin": 7}, "kind": "payment",
        }}]
        v6 = _enterprise_supply(events, {"a", "b"}, transfer_accounting="frozen_classifier")
        v7 = _enterprise_supply(events, {"a", "b"}, transfer_accounting="self_declared")
        self.assertNotEqual(v6, v7)
        classified = _enterprise_supply(events, {"a", "b"}, {0: "payment_for_service"}, "frozen_classifier")
        self.assertEqual(classified, v7)


if __name__ == "__main__":
    unittest.main()
