from __future__ import annotations

import unittest

from agent_world.interface import build_observation, build_static_context
from agent_world.models import AgentDecision, Position, WorldConfig
from agent_world.world import WorldEngine


class EconomicInterfaceTests(unittest.TestCase):
    def test_organic_broadcast_uses_its_audible_radius_not_visual_radius(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(
                economy_mode="organic",
                survival_food_decay=0,
                survival_water_decay=0,
                survival_energy_decay=0,
            ),
            agent_names=["A1", "A2"],
        )
        speaker = engine.state.agents["agent-1"]
        listener = engine.state.agents["agent-2"]
        speaker.position = Position(8, 8)
        listener.position = Position(8, 11)
        engine.tick({speaker.id: AgentDecision(actions=[{"type": "broadcast", "text": "market at eight eight"}])})
        observation = build_observation(engine.state, listener.id)
        self.assertIn("market at eight eight", [event["message"] for event in observation["recent_events"]])

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

    def test_organic_market_information_is_local_and_prompt_requires_physical_exchange(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(
                economy_mode="organic",
                geography_mode="dispersed",
                objective_mode="neutral",
                survival_food_decay=0,
                survival_water_decay=0,
                survival_energy_decay=0,
            ),
            agent_names=["Farmer", "Forester", "Miner"],
        )
        farmer = engine.state.agents["agent-1"]
        forester = engine.state.agents["agent-2"]
        miner = engine.state.agents["agent-3"]
        farmer.position = Position(6, 10)
        forester.position = Position(6, 11)
        miner.position = Position(12, 2)
        farmer.inventory["food"] += 1
        engine.tick(
            {
                farmer.id: AgentDecision(
                    actions=[
                        {
                            "type": "offer_trade",
                            "to": "any",
                            "scope": "global",
                            "give": {"food": 1},
                            "receive": {"coin": 1},
                        }
                    ]
                )
            }
        )

        near = build_observation(engine.state, forester.id)
        far = build_observation(engine.state, miner.id)
        self.assertEqual([trade["id"] for trade in near["open_trades"]], ["trade-1"])
        self.assertEqual(far["open_trades"], [])
        self.assertEqual(near["world"]["trade_settlement"], "physical_meeting_at_escrow_position")
        self.assertEqual(near["world"]["recipes"]["well"]["inputs"], {"wood": 6, "stone": 2, "fiber": 2})
        self.assertNotIn("offer_contract", [action["type"] for action in near["valid_actions"]])
        self.assertIn("zero carry weight", build_static_context(near["world"]))


if __name__ == "__main__":
    unittest.main()
