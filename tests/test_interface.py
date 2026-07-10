from __future__ import annotations

import unittest

from agent_world.interface import build_observation
from agent_world.models import AgentDecision, WorldConfig
from agent_world.world import WorldEngine


class EconomicInterfaceTests(unittest.TestCase):
    def test_global_public_offer_is_visible_to_distant_agent(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(
                economy_mode="commerce",
                geography_mode="dispersed",
                survival_food_decay=0,
                survival_water_decay=0,
                survival_energy_decay=0,
            ),
            agent_names=["Farmer", "Forester"],
        )
        engine.state.agents["agent-1"].inventory["food"] += 1
        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {
                            "type": "offer_trade",
                            "to": "any",
                            "scope": "global",
                            "give": {"food": 1},
                            "receive": {"wood": 1},
                        }
                    ]
                ),
                "agent-2": AgentDecision(actions=[{"type": "wait"}]),
            }
        )

        observation = build_observation(engine.state, "agent-2")
        self.assertEqual([trade["id"] for trade in observation["open_trades"]], ["trade-1"])
        self.assertEqual(observation["open_trades"][0]["market_scope"], "global")

    def test_commerce_prompt_state_exposes_treatment_costs_and_specialty(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(economy_mode="commerce", geography_mode="dispersed", objective_mode="individual"),
            agent_names=["A1"],
        )
        observation = build_observation(engine.state, "agent-1")
        self.assertEqual(observation["world"]["communication_action_cost"], 1)
        self.assertEqual(observation["world"]["group_admin_action_cost"], 1)
        self.assertEqual(observation["world"]["objective_mode"], "individual")
        self.assertIsNotNone(observation["self"]["specialty"])


if __name__ == "__main__":
    unittest.main()
