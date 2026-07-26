from __future__ import annotations

import json
import unittest

from agent_world.interface import build_dynamic_observation, build_observation, build_static_context
from agent_world.models import AgentDecision, Position, WorldConfig
from agent_world.world import WorldEngine


class EconomicInterfaceTests(unittest.TestCase):
    def test_no_feedback_treatment_removes_failure_payload_and_prompt_instruction(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(action_feedback_mode="none"),
            agent_names=["A1"],
        )
        engine.tick(
            {"agent-1": AgentDecision(actions=[{"type": "move", "direction": "sideways"}])}
        )

        observation = build_observation(engine.state, "agent-1")
        dynamic = build_dynamic_observation(observation)
        static = build_static_context(observation["world"])

        self.assertEqual(observation["recent_action_feedback"], [])
        self.assertNotIn("recent_action_feedback", dynamic)
        self.assertFalse(
            any(event["type"] in {"invalid_action", "contention_failure"} for event in observation["recent_events"])
        )
        self.assertNotIn("Use recent_action_feedback", static)

    def test_baseline_feedback_treatment_preserves_current_payload_and_instruction(self) -> None:
        engine = WorldEngine.create(WorldConfig(), agent_names=["A1"])
        engine.tick(
            {"agent-1": AgentDecision(actions=[{"type": "move", "direction": "sideways"}])}
        )

        observation = build_observation(engine.state, "agent-1")
        static = build_static_context(observation["world"])

        self.assertEqual(
            observation["recent_action_feedback"][0]["reason"],
            "Move requires direction north, south, east, or west.",
        )
        self.assertIn("Use recent_action_feedback", static)

    def test_minimal_feedback_names_only_last_ticks_failed_action(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(action_feedback_mode="minimal"),
            agent_names=["A1"],
        )
        engine.tick(
            {"agent-1": AgentDecision(actions=[{"type": "move", "direction": "sideways"}])}
        )

        observation = build_observation(engine.state, "agent-1")
        dynamic = build_dynamic_observation(observation)
        static = build_static_context(observation["world"])

        self.assertEqual(
            dynamic["recent_action_feedback"],
            [{"tick": 0, "failed_action": "move"}],
        )
        self.assertFalse(
            any(
                event["type"] in {"invalid_action", "contention_failure"}
                for event in dynamic.get("recent_events", [])
            )
        )
        self.assertIn("names actions that failed last tick", static)
        self.assertNotIn("avoid repeating invalid actions", static)

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        next_dynamic = build_dynamic_observation(build_observation(engine.state, "agent-1"))
        self.assertNotIn("recent_action_feedback", next_dynamic)

    def test_causal_feedback_explains_proven_contention_without_identifying_agent(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(
                action_feedback_mode="causal",
                plains_food_regen=0,
                forest_food_regen=0,
            ),
            agent_names=["A1", "A2"],
        )
        first = engine.state.agents["agent-1"]
        second = engine.state.agents["agent-2"]
        second.position = first.position
        engine.state.tile_at(first.position).resources["food"] = 1
        engine.tick(
            {
                first.id: AgentDecision(
                    actions=[{"type": "gather", "resource": "food"}]
                ),
                second.id: AgentDecision(
                    actions=[{"type": "gather", "resource": "food"}]
                ),
            }
        )

        dynamic = build_dynamic_observation(build_observation(engine.state, second.id))
        feedback = dynamic["recent_action_feedback"][0]

        self.assertEqual(
            feedback["cause"],
            "Another agent obtained the remaining resource before this action resolved.",
        )
        self.assertNotIn(first.id, json.dumps(feedback))
        self.assertIn("error", feedback)
        self.assertIn("action", feedback)

    def test_causal_feedback_leaves_invalid_proposal_payload_at_baseline(self) -> None:
        baseline = WorldEngine.create(WorldConfig(), agent_names=["A1"])
        causal = WorldEngine.create(
            WorldConfig(action_feedback_mode="causal"), agent_names=["A1"]
        )
        decision = {
            "agent-1": AgentDecision(
                actions=[{"type": "move", "direction": "sideways"}]
            )
        }
        baseline.tick(decision)
        causal.tick(decision)

        baseline_feedback = build_dynamic_observation(
            build_observation(baseline.state, "agent-1")
        )["recent_action_feedback"]
        causal_feedback = build_dynamic_observation(
            build_observation(causal.state, "agent-1")
        )["recent_action_feedback"]

        self.assertEqual(causal_feedback, baseline_feedback)

    def test_twenty_agent_organic_prompt_stays_within_infrastructure_budgets(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(economy_mode="organic", geography_mode="dispersed"),
            agent_names=[f"A{index}" for index in range(20)],
        )
        dynamic_sizes = []
        static_context = None
        for agent_id in engine.state.agents:
            observation = build_observation(engine.state, agent_id)
            static_context = static_context or build_static_context(observation["world"])
            dynamic_sizes.append(
                len(
                    json.dumps(
                        build_dynamic_observation(observation),
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                )
            )

        assert static_context is not None
        self.assertLessEqual(len(static_context), 6_500)
        self.assertLessEqual(sum(dynamic_sizes) / len(dynamic_sizes), 2_200)
        self.assertLessEqual(max(dynamic_sizes), 2_300)

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

    def test_distant_global_traffic_does_not_crowd_out_recent_local_event(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(economy_mode="organic", geography_mode="dispersed"),
            agent_names=["A1"],
        )
        agent = engine.state.agents["agent-1"]
        agent.position = Position(8, 8)
        engine.log_event(
            "say",
            actor_id=agent.id,
            position=agent.position,
            message="locally relevant",
            scope="public",
        )
        for index in range(engine.state.config.recent_event_limit * 6):
            engine.log_event(
                "say",
                actor_id=None,
                position=Position(0, 0),
                message=f"distant {index}",
                scope="public",
            )

        observation = build_observation(engine.state, agent.id)

        self.assertIn("locally relevant", [event["message"] for event in observation["recent_events"]])

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
            WorldConfig(
                economy_mode="commerce",
                geography_mode="dispersed",
                objective_mode="individual",
                specialization_mode="specialists",
            ),
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
        static_context = build_static_context(near["world"])
        self.assertIn("zero carry weight", static_context)
        self.assertNotIn("high-value", static_context)


if __name__ == "__main__":
    unittest.main()
