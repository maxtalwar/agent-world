from __future__ import annotations

import unittest
from collections import Counter

from agent_world.metrics import (
    compute_metrics,
    is_ambiguous_boundary_failure_message,
    is_confirmed_model_contract_failure_message,
    is_model_output_failure_message,
)
from agent_world.models import AgentDecision, WorldConfig
from agent_world.world import WorldEngine


LEGACY_EXHAUSTION_MESSAGE = (
    "Claude boundary failed: claude -p exited 1: error_max_structured_output_retries"
)


class DecisionFailureClassificationTests(unittest.TestCase):
    def test_structured_output_exhaustion_counts_as_model_output(self) -> None:
        # Scoring revision 2: preserved ledgers logged this under the generic
        # boundary prefix, which invalidated the trial instead of charging the
        # model. Reclassifying reproduces the correct score from raw evidence.
        self.assertTrue(
            is_model_output_failure_message("agent_response", LEGACY_EXHAUSTION_MESSAGE)
        )
        self.assertFalse(
            is_ambiguous_boundary_failure_message(
                "agent_response", LEGACY_EXHAUSTION_MESSAGE
            )
        )

    def test_structured_output_exhaustion_is_not_independently_confirmed(self) -> None:
        # The CLI consumes the failed payloads, so nothing is left for the
        # independent contract validator to re-check.
        self.assertFalse(
            is_confirmed_model_contract_failure_message(
                "agent_response", LEGACY_EXHAUSTION_MESSAGE
            )
        )

    def test_other_boundary_failures_stay_ambiguous(self) -> None:
        other = "Claude boundary failed: claude -p exited 1: something else entirely"
        self.assertTrue(is_ambiguous_boundary_failure_message("agent_response", other))
        self.assertFalse(is_model_output_failure_message("agent_response", other))


class EconomicMetricsTests(unittest.TestCase):
    def test_settled_contract_has_equivalent_trade_volume(self) -> None:
        config = dict(
            seed=1,
            economy_mode="organic",
            survival_food_decay=0,
            survival_water_decay=0,
            survival_energy_decay=0,
            carried_food_spoil_interval=0,
        )
        trade = WorldEngine.create(WorldConfig(**config), agent_names=["Seller", "Buyer"])
        seller, buyer = trade.state.agents.values()
        buyer.position = seller.position
        seller.inventory = Counter({"food": 2})
        buyer.inventory = Counter({"coin": 3})
        trade.tick({seller.id: AgentDecision(actions=[{"type": "offer_trade", "to": buyer.id, "give": {"food": 2}, "receive": {"coin": 3}}])})
        trade.tick({buyer.id: AgentDecision(actions=[{"type": "accept_trade", "trade_id": "trade-1"}])})

        contract = WorldEngine.create(WorldConfig(**config), agent_names=["Seller", "Buyer"])
        seller, buyer = contract.state.agents.values()
        seller.inventory = Counter({"food": 2})
        buyer.inventory = Counter({"coin": 3})
        contract.tick({seller.id: AgentDecision(actions=[{"type": "propose_contract", "counterparty": buyer.id, "give": {"food": 2}, "receive": {"coin": 3}, "deadline_tick": 3}])})
        contract.tick({buyer.id: AgentDecision(actions=[{"type": "accept_contract", "contract_id": "contract-1"}])})
        contract.tick({seller.id: AgentDecision(actions=[{"type": "deliver_contract", "contract_id": "contract-1"}])})

        trade_metrics = compute_metrics(trade.state)
        contract_metrics = compute_metrics(contract.state)
        self.assertEqual(contract_metrics["trade"]["volume"], trade_metrics["trade"]["volume"])
        self.assertEqual(
            contract_metrics["economic_flows"]["market"]["transfer_value"],
            trade_metrics["economic_flows"]["market"]["transfer_value"],
        )

    def test_transfer_market_specialization_and_asset_sections_are_reported(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(survival_food_decay=0, survival_water_decay=0, survival_energy_decay=0),
            agent_names=["A1", "A2"],
        )
        engine.state.agents["agent-1"].inventory["fiber"] = 1
        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {"type": "gift", "to": "agent-2", "items": {"food": 1}},
                        {
                            "type": "offer_trade",
                            "to": "agent-2",
                            "give": {"fiber": 1},
                            "receive": {"water": 1},
                            "expires_in": 5,
                        },
                    ]
                ),
                "agent-2": AgentDecision(actions=[{"type": "wait"}]),
            }
        )
        engine.tick(
            {
                "agent-1": AgentDecision(actions=[{"type": "wait"}]),
                "agent-2": AgentDecision(actions=[{"type": "accept_trade", "trade_id": "trade-1"}]),
            }
        )

        metrics = compute_metrics(engine.state)
        self.assertEqual(metrics["economic_flows"]["gifts"]["by_item"], {"food": 1})
        self.assertEqual(metrics["economic_flows"]["market"]["accepted"], 1)
        self.assertEqual(metrics["economic_flows"]["market"]["conversion_pct"], 100.0)
        self.assertIn("division_of_labor_index", metrics["specialization"])
        self.assertIn("agent_wealth_including_asset_shares", metrics["productive_assets"])


if __name__ == "__main__":
    unittest.main()
