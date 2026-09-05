from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent_world.agents import SurvivalBrain
from agent_world.models import WorldConfig
from agent_world.run_report import (
    _normalize_loaded_usage_record,
    build_report,
    format_comparison,
    render_markdown,
    write_report,
)
from agent_world.runner import SimulationRunner
from agent_world.world import WorldEngine


def _run_short_sim(ticks: int = 4) -> tuple[list[dict], dict]:
    config = WorldConfig(seed=5)
    engine = WorldEngine.create(config=config, agent_names=["A1", "A2"])
    brains = {agent_id: SurvivalBrain() for agent_id in engine.state.agents}
    runner = SimulationRunner(engine, brains, log_agent_io=False)
    for _ in range(ticks):
        runner.step()
    events = [json.loads(line) for line in engine.export_events_jsonl().splitlines() if line.strip()]
    return events, engine.snapshot()


class RunReportTests(unittest.TestCase):
    def test_historical_grok_usage_is_upgraded_to_inclusive_prompt_tokens(self) -> None:
        record = _normalize_loaded_usage_record(
            {
                "provider": "grok_cli",
                "prompt_tokens": 1002,
                "cached_tokens": 14848,
                "grok_model_usage": {
                    "grok-4.6-build": {
                        "inputTokens": 1002,
                        "cacheReadInputTokens": 14848,
                        "cacheCreationInputTokens": 0,
                    }
                },
            }
        )

        self.assertEqual(record["prompt_tokens"], 15850)
        self.assertEqual(record["cached_tokens"], 14848)

    def test_contract_and_ledger_diagnostics(self) -> None:
        snapshot = {
            "tick": 4,
            "config": {"seed": 1, "economy_mode": "organic"},
            "agents": {
                "agent-1": {"alive": True, "health": 100, "inventory": {}},
                "agent-2": {"alive": True, "health": 100, "inventory": {}},
            },
            "groups": {},
            "structures": {},
            "trades": {},
            "contracts": {},
            "market_history": [],
        }
        contract = {
            "id": "contract-1",
            "proposer_id": "agent-1",
            "counterparty": "agent-2",
            "buyer_id": "agent-2",
            "give": {"food": 1},
            "receive": {"coin": 1},
            "created_tick": 0,
        }
        events = [
            {"type": "contract_proposed", "tick": 0, "actor_id": "agent-1", "message": "p", "data": {"contract": contract}},
            {"type": "contract_settled", "tick": 1, "actor_id": "agent-1", "message": "s", "data": {"contract": contract}},
            {"type": "contract_proposed", "tick": 1, "actor_id": "agent-1", "message": "p", "data": {"contract": {**contract, "id": "contract-2"}}},
            {"type": "contract_defaulted", "tick": 3, "actor_id": "agent-1", "message": "d", "data": {"contract": {**contract, "id": "contract-2"}}},
            {"type": "ledger_note", "tick": 3, "actor_id": "agent-2", "message": "n", "data": {"author": "agent-2", "title": "T", "body": "B"}},
        ]

        report = build_report(events, snapshot, target_ticks=4)

        self.assertEqual(
            report["diagnostics"],
            {
                "contracts_proposed": 2,
                "contracts_settled": 1,
                "contracts_defaulted": 1,
                "contract_default_rate_pct": 50.0,
                "ledger_note_count": 1,
            },
        )
        self.assertEqual(report["economy"]["institutions"]["delivery_contracts"]["default_rate_pct"], 50.0)

    def test_build_report_covers_core_sections(self) -> None:
        events, snapshot = _run_short_sim()
        report = build_report(events, snapshot, source="unit-test")

        self.assertEqual(report["source"], "unit-test")
        self.assertEqual(report["run"]["final_tick"], snapshot["tick"])
        self.assertTrue(report["run"]["completed"])
        self.assertEqual(report["config"]["seed"], 5)
        self.assertEqual(report["survival"]["living"], 2)
        self.assertIn("agent-1", report["survival"]["agents"])
        self.assertNotIn("agent_observation", report["actions"]["counts"])
        self.assertGreaterEqual(report["communication"]["says_total"], 0)
        self.assertIsInstance(report["milestone_first_ticks"], dict)
        self.assertEqual(report["usage"]["calls"], 0)

    def test_build_report_marks_stopped_runs(self) -> None:
        events, snapshot = _run_short_sim()
        events.append(
            {
                "type": "run_stopped",
                "tick": snapshot["tick"],
                "actor_id": None,
                "message": "stopped",
                "data": {"reason": "insufficient_quota", "target_ticks": 40},
            }
        )
        report = build_report(events, snapshot)
        self.assertFalse(report["run"]["completed"])
        self.assertEqual(report["run"]["stop_reason"], "insufficient_quota")
        self.assertEqual(report["run"]["target_ticks"], 40)

    def test_build_report_marks_started_run_without_terminal_event_interrupted(self) -> None:
        events, snapshot = _run_short_sim()
        events.insert(
            0,
            {
                "type": "run_started",
                "tick": 0,
                "actor_id": None,
                "message": "started",
                "data": {"config": {"ticks": 40, "brain": "llm"}},
            },
        )

        report = build_report(events, snapshot)

        self.assertFalse(report["run"]["completed"])
        self.assertEqual(report["run"]["status"], "interrupted")
        self.assertEqual(report["run"]["stop_reason"], "interrupted")
        self.assertEqual(report["run"]["target_ticks"], 40)
        self.assertEqual(report["run"]["completion_evidence"], "missing_terminal_event")

    def test_build_report_prefers_explicit_completed_terminal_evidence(self) -> None:
        events, snapshot = _run_short_sim()
        events.extend(
            [
                {
                    "type": "run_started",
                    "tick": 0,
                    "actor_id": None,
                    "message": "started",
                    "data": {"config": {"ticks": 4}},
                },
                {
                    "type": "run_completed",
                    "tick": snapshot["tick"],
                    "actor_id": None,
                    "message": "completed",
                    "data": {"target_ticks": 4},
                },
            ]
        )

        report = build_report(events, snapshot)

        self.assertTrue(report["run"]["completed"])
        self.assertEqual(report["run"]["status"], "completed")
        self.assertEqual(report["run"]["completion_evidence"], "run_completed")

    def test_missing_provider_charge_is_rendered_as_unavailable(self):
        events, snapshot = _run_short_sim()
        report = build_report(events, snapshot, [{"model": "muse-spark-1.3", "cost": None,
                                                "prompt_tokens": 100, "completion_tokens": 20}])
        self.assertIsNone(report["usage"]["total_cost_usd"])
        self.assertIsNone(report["usage"]["attempted_provider_cost_usd"])
        self.assertIn("provider cost unavailable", render_markdown(report))
        self.assertNotIn("1 calls, $0", render_markdown(report))

    def test_usage_records_are_aggregated(self) -> None:
        events, snapshot = _run_short_sim()
        usage = [
            {"cost": 0.01, "prompt_tokens": 1000, "cached_tokens": 500, "completion_tokens": 200, "reasoning_tokens": 100, "agent_dynamic_observation_chars": 2000},
            {"cost": 0.02, "prompt_tokens": 1000, "cached_tokens": 900, "completion_tokens": 300, "reasoning_tokens": 150, "agent_dynamic_observation_chars": 3000},
        ]
        report = build_report(events, snapshot, usage)
        self.assertEqual(report["usage"]["calls"], 2)
        self.assertAlmostEqual(report["usage"]["total_cost_usd"], 0.03)
        self.assertEqual(report["usage"]["cache_hit_rate_pct"], 70.0)
        self.assertEqual(report["usage"]["efficiency"]["mean_uncached_input_tokens_per_call"], 300.0)
        self.assertEqual(report["usage"]["efficiency"]["mean_reasoning_tokens_per_call"], 125.0)
        self.assertEqual(report["usage"]["efficiency"]["mean_agent_dynamic_observation_chars"], 2500.0)

    def test_codex_simulation_credits_are_run_scoped_and_exact(self) -> None:
        events, snapshot = _run_short_sim()
        usage = [
            {
                "provider": "codex_cli",
                "model": "gpt-5.6-luna",
                "prompt_tokens": 1_000_000,
                "cached_tokens": 400_000,
                "completion_tokens": 100_000,
                "reasoning_tokens": 60_000,
                "cost": 0,
            }
        ]
        report = build_report(events, snapshot, usage)
        credits = report["usage"]["simulation_credits"]

        self.assertEqual(credits["credits"]["total"], 31.0)
        self.assertEqual(credits["reasoning_output_tokens"], 60_000)
        self.assertIn("simulation run only", credits["attribution"])
        self.assertIn("Simulation plan credits: 31.0 exact run-scoped credits", render_markdown(report))

    def test_codex_plan_drawdown_is_in_report_and_markdown(self) -> None:
        events, snapshot = _run_short_sim()
        plan_usage = {
            "available": True,
            "buckets": {
                "codex": {
                    "limit_name": None,
                    "primary": {
                        "before_used_percent": 10,
                        "after_used_percent": 13,
                        "used_percent_delta": 3,
                    },
                    "secondary": {
                        "before_used_percent": 20,
                        "after_used_percent": 20,
                        "used_percent_delta": 0,
                    },
                    "credits": {
                        "before_balance": "100.0",
                        "after_balance": "99.5",
                        "balance_delta": "-0.5",
                    },
                }
            },
        }
        report = build_report(events, snapshot, plan_usage=plan_usage)

        self.assertEqual(report["usage"]["plan_limits"], plan_usage)
        markdown = render_markdown(report)
        self.assertIn("Codex plan [codex]", markdown)
        self.assertIn("delta +3pp", markdown)

    def test_llm_failures_use_agent_response_semantics(self) -> None:
        events, snapshot = _run_short_sim()
        events.extend(
            [
                {
                    "type": "agent_response",
                    "tick": 2,
                    "actor_id": "agent-1",
                    "message": "Invalid JSON response: Unterminated string",
                    "data": {},
                },
                {
                    "type": "agent_response",
                    "tick": 2,
                    "actor_id": "agent-2",
                    "message": (
                        "Codex model output contract failed: arguments_json "
                        "is invalid: Expecting value"
                    ),
                    "data": {"actions": [{"type": "wait"}]},
                },
                {
                    "type": "agent_response",
                    "tick": 2,
                    "actor_id": "agent-1",
                    "message": (
                        "Codex harness failed: adapter rejected "
                        "contract-valid output"
                    ),
                    "data": {"actions": [{"type": "wait"}]},
                },
                {
                    "type": "agent_response",
                    "tick": 2,
                    "actor_id": "agent-2",
                    "message": "Codex boundary failed: no decision payload",
                    "data": {"actions": [{"type": "wait"}]},
                },
                {
                    "type": "some_error_event",
                    "tick": 2,
                    "actor_id": None,
                    "message": "not an LLM decision failure",
                    "data": {},
                },
            ]
        )

        report = build_report(events, snapshot)

        self.assertEqual(report["reliability"]["llm_failure_events"], 4)
        self.assertEqual(report["reliability"]["model_output_failure_events"], 2)
        self.assertEqual(report["reliability"]["harness_failure_events"], 1)
        self.assertEqual(
            report["reliability"]["ambiguous_boundary_failure_events"],
            1,
        )
        self.assertEqual(
            report["reliability"]["benchmark_integrity_status"],
            "invalid",
        )
        self.assertEqual(report["reliability"]["quality_status"], "degraded")
        self.assertEqual(
            report["reliability"]["llm_failures_by_agent"],
            {"agent-1": 2, "agent-2": 2},
        )
        self.assertNotIn("agent_response", report["actions"]["counts"])

    def test_economy_reports_transfer_trade_and_asset_flows(self) -> None:
        snapshot = {
            "tick": 5,
            "config": {"seed": 3, "action_points_per_tick": 4},
            "agents": {
                "agent-1": {"alive": True, "health": 100, "inventory": {}, "groups": ["group-1"]},
                "agent-2": {"alive": True, "health": 100, "inventory": {}, "groups": ["group-1"]},
            },
            "groups": {
                "group-1": {"id": "group-1", "name": "Builders", "members": ["agent-1", "agent-2"]}
            },
            "structures": {
                "structure-1": {
                    "id": "structure-1",
                    "type": "storage",
                    "owner_id": "group-1",
                    "status": "complete",
                    "contributors": ["agent-1", "agent-2"],
                    "inventory": {"food": 2},
                }
            },
            "trades": {
                "trade-1": {"status": "accepted"},
                "trade-2": {"status": "expired"},
            },
        }
        trade_1 = {
            "id": "trade-1",
            "from_agent": "agent-1",
            "to_agent": "agent-2",
            "accepted_by": "agent-2",
            "give": {"stone": 1},
            "receive": {"food": 1},
            "created_tick": 2,
            "public": False,
            "status": "accepted",
        }
        trade_2 = {
            "id": "trade-2",
            "from_agent": "agent-2",
            "to_agent": "agent-1",
            "give": {"food": 1},
            "receive": {"wood": 1},
            "created_tick": 2,
            "public": False,
            "status": "expired",
        }
        events = [
            {"type": "world_created", "tick": 0, "actor_id": None, "message": "created", "data": {}},
            {
                "type": "create_group",
                "tick": 0,
                "actor_id": "agent-1",
                "message": "created group",
                "data": {"group": {"id": "group-1", "members": ["agent-1"]}},
            },
            {
                "type": "build_started",
                "tick": 1,
                "actor_id": "agent-1",
                "message": "started storage",
                "data": {
                    "structure": {"id": "structure-1", "type": "storage", "owner_id": "group-1"},
                    "contributed": {"wood": 2},
                },
            },
            {
                "type": "join_group",
                "tick": 1,
                "actor_id": "agent-2",
                "message": "joined group",
                "data": {"group": {"id": "group-1", "members": ["agent-1", "agent-2"]}},
            },
            {
                "type": "contribute",
                "tick": 2,
                "actor_id": "agent-2",
                "message": "contributed",
                "data": {"structure_id": "structure-1", "contributed": {"fiber": 1}},
            },
            {
                "type": "gift",
                "tick": 2,
                "actor_id": "agent-1",
                "message": "gifted",
                "data": {"to": "agent-2", "items": {"food": 2, "wood": 1}},
            },
            {
                "type": "offer_trade",
                "tick": 2,
                "actor_id": "agent-1",
                "message": "offered",
                "data": {"trade": trade_1},
            },
            {
                "type": "offer_trade",
                "tick": 2,
                "actor_id": "agent-2",
                "message": "offered",
                "data": {"trade": trade_2},
            },
            {
                "type": "accept_trade",
                "tick": 4,
                "actor_id": "agent-2",
                "message": "accepted",
                "data": {"trade": trade_1, "value": {"give": 4, "receive": 2}},
            },
            {
                "type": "expire_trade",
                "tick": 4,
                "actor_id": "agent-2",
                "message": "expired",
                "data": {"trade": trade_2},
            },
            {
                "type": "invalid_action",
                "tick": 4,
                "actor_id": "agent-2",
                "message": "Trade is not open.",
                "data": {"action": {"type": "accept_trade", "trade_id": "trade-2"}},
            },
            {
                "type": "run_completed",
                "tick": 5,
                "actor_id": None,
                "message": "completed",
                "data": {"target_ticks": 5},
            },
        ]

        report = build_report(events, snapshot)
        economy = report["economy"]

        self.assertEqual(economy["gifts"], 1)
        self.assertEqual(economy["gift_quantity"], 3)
        self.assertEqual(economy["gift_value"], 7)
        self.assertEqual(economy["gift_by_item"], {"food": 2, "wood": 1})
        self.assertEqual(economy["gift_categories"]["subsistence"]["quantity"], 2)
        self.assertEqual(economy["gift_categories"]["materials"]["quantity"], 1)
        self.assertEqual(economy["gift_group_status"]["in_group"], 1)

        trades = economy["trades"]
        self.assertEqual(trades["conversion_rate_pct"], 50.0)
        self.assertEqual(trades["accepted_value"], 6)
        self.assertEqual(trades["acceptance_latency_ticks"]["median"], 2.0)
        self.assertEqual(trades["accept_success_rate_pct"], 50.0)
        self.assertEqual(trades["invalid_accepts"], 1)
        self.assertEqual(trades["invalid_accept_reasons"], {"Trade is not open.": 1})
        self.assertEqual(trades["offered_group_status"]["in_group"], 2)
        self.assertEqual(trades["accepted_group_status"]["in_group"], 1)

        construction = economy["construction"]
        self.assertEqual(construction["contributions"]["quantity"], 3)
        self.assertEqual(construction["contributions"]["value"], 8)
        self.assertEqual(construction["assets"]["count"], 1)
        self.assertEqual(construction["assets"]["replacement_cost_value"], 8)
        self.assertEqual(construction["assets"]["stored_inventory_value"], 4)
        self.assertEqual(
            construction["contributor_ownership"]["agent-1"]["contribution_value_to_group_owned_assets"],
            6,
        )

    def test_write_report_creates_json_and_markdown(self) -> None:
        events, snapshot = _run_short_sim()
        with tempfile.TemporaryDirectory() as tmp:
            stem = Path(tmp) / "sample"
            report = write_report(events, snapshot, [], stem)
            loaded = json.loads((Path(tmp) / "sample-report.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["run"], report["run"])
            markdown = (Path(tmp) / "sample-report.md").read_text(encoding="utf-8")
            self.assertIn("# Run report: sample", markdown)
            self.assertIn("agent-1", markdown)

    def test_render_markdown_mentions_early_stop(self) -> None:
        events, snapshot = _run_short_sim()
        events.append(
            {
                "type": "run_stopped",
                "tick": snapshot["tick"],
                "actor_id": None,
                "message": "stopped",
                "data": {"reason": "insufficient_quota", "target_ticks": 40},
            }
        )
        markdown = render_markdown(build_report(events, snapshot))
        self.assertIn("stopped early: insufficient_quota", markdown)

    def test_render_and_compare_accept_legacy_report_shape(self) -> None:
        events, snapshot = _run_short_sim()
        report = build_report(events, snapshot, source="legacy")
        report["run"].pop("status")
        report["run"].pop("completion_evidence")
        for key in list(report["economy"]):
            if key.startswith("gift_") and key != "gift_network":
                report["economy"].pop(key)
        report["economy"].pop("construction")
        for key in list(report["economy"]["trades"]):
            if key not in {"offered", "accepted", "rejected", "expired", "cancelled", "accepted_detail"}:
                report["economy"]["trades"].pop(key)

        self.assertIn("# Run report: legacy", render_markdown(report))
        self.assertIn("legacy", format_comparison([report]).splitlines()[0])

    def test_format_comparison_lines_up_runs(self) -> None:
        events, snapshot = _run_short_sim()
        first = build_report(events, snapshot, source="run-a")
        second = build_report(events, snapshot, source="run-b")
        table = format_comparison([first, second])
        self.assertIn("run-a", table.splitlines()[0])
        self.assertIn("run-b", table.splitlines()[0])
        self.assertIn("trades accepted", table)


if __name__ == "__main__":
    unittest.main()
