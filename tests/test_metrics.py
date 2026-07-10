from __future__ import annotations

import unittest

from agent_world.metrics import compute_metrics
from agent_world.models import AgentDecision, WorldConfig
from agent_world.world import WorldEngine


class EconomicMetricsTests(unittest.TestCase):
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
