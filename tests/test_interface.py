from __future__ import annotations

import json
import unittest

from agent_world.interface import (
    build_dynamic_observation,
    build_observation,
    build_static_context,
    game_context_format,
)
from agent_world.models import AgentDecision, Position, WorldConfig
from agent_world.world import WorldEngine


class EconomicInterfaceTests(unittest.TestCase):
    def test_grounded_v3_adds_literal_embodiment_without_action_advice(self) -> None:
        engine = WorldEngine.create(WorldConfig(seed=11), agent_names=["A1"])
        agent = engine.state.agents["agent-1"]
        agent.position = Position(8, 8)
        agent.inventory["wood"] = 2
        observation = build_observation(
            engine.state, agent.id, observation_mode="grounded-v3"
        )

        dynamic = build_dynamic_observation(observation)

        self.assertEqual(dynamic["here"]["position"], [8, 8])
        self.assertEqual(set(dynamic["adjacent"]), {"north", "east", "south", "west"})
        self.assertEqual(dynamic["adjacent"]["north"]["position"], [8, 7])
        self.assertIn("move_cost", dynamic["adjacent"]["north"])
        self.assertEqual(dynamic["body"]["action_points"], 4)
        self.assertEqual(dynamic["body"]["energy"], agent.needs.energy)
        self.assertEqual(
            dynamic["body"]["carry_remaining"],
            agent.carry_capacity - agent.inventory_weight(),
        )
        rendered = json.dumps(dynamic, sort_keys=True).lower()
        for advisory_term in ("recommended", "opportunity", "profitable", "legal_actions"):
            self.assertNotIn(advisory_term, rendered)
        self.assertEqual(
            game_context_format(observation),
            "static_context_v2+grounded_dynamic_v3",
        )

    def test_compact_v2_shape_remains_the_default_control(self) -> None:
        engine = WorldEngine.create(WorldConfig(seed=11), agent_names=["A1"])
        observation = build_observation(engine.state, "agent-1")

        dynamic = build_dynamic_observation(observation)

        self.assertNotIn("body", dynamic)
        self.assertNotIn("here", dynamic)
        self.assertNotIn("adjacent", dynamic)
        self.assertEqual(
            game_context_format(observation),
            "static_context_v2+compact_dynamic_v2",
        )

    def test_body_only_v3_adds_only_compact_body_summary(self) -> None:
        engine = WorldEngine.create(WorldConfig(seed=11), agent_names=["A1"])
        control = build_dynamic_observation(
            build_observation(engine.state, "agent-1")
        )
        body_only_observation = build_observation(
            engine.state, "agent-1", observation_mode="body-only-v3"
        )

        body_only = build_dynamic_observation(body_only_observation)

        agent = engine.state.agents["agent-1"]
        self.assertEqual(
            body_only["body"],
            {
                "ap": 4,
                "en": 25,
                "free": agent.carry_capacity - agent.inventory_weight(),
            },
        )
        self.assertEqual(
            {key: value for key, value in body_only.items() if key != "body"},
            control,
        )
        self.assertNotIn("here", body_only)
        self.assertNotIn("adjacent", body_only)
        self.assertEqual(
            game_context_format(body_only_observation),
            "static_context_v2+body_only_dynamic_v3",
        )

    def test_indexed_v3_labels_existing_tiles_without_duplication(self) -> None:
        engine = WorldEngine.create(WorldConfig(seed=11), agent_names=["A1"])
        engine.state.agents["agent-1"].position = Position(8, 8)
        control_observation = build_observation(engine.state, "agent-1")
        indexed_observation = build_observation(
            engine.state, "agent-1", observation_mode="indexed-v3"
        )

        control = build_dynamic_observation(control_observation)
        indexed = build_dynamic_observation(indexed_observation)
        labels = {
            tuple(tile["p"]): tile["rel"]
            for tile in indexed["local_map"]
            if "rel" in tile
        }

        self.assertEqual(
            labels,
            {
                (8, 8): "here",
                (8, 7): "north",
                (9, 8): "east",
                (8, 9): "south",
                (7, 8): "west",
            },
        )
        stripped_map = [
            {key: value for key, value in tile.items() if key != "rel"}
            for tile in indexed["local_map"]
        ]
        self.assertEqual(stripped_map, control["local_map"])
        agent = engine.state.agents["agent-1"]
        self.assertEqual(
            indexed["body"],
            {
                "ap": 4,
                "en": 25,
                "free": agent.carry_capacity - agent.inventory_weight(),
            },
        )
        self.assertNotIn("here", indexed)
        self.assertNotIn("adjacent", indexed)
        self.assertNotIn("passable", json.dumps(indexed["local_map"]))
        self.assertEqual(
            game_context_format(indexed_observation),
            "static_context_v2+indexed_dynamic_v3",
        )

    def test_indexed_v3_is_materially_smaller_than_grounded_v3(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(economy_mode="organic", geography_mode="dispersed"),
            agent_names=[f"A{index}" for index in range(20)],
        )
        indexed_sizes = []
        grounded_sizes = []
        for agent_id in engine.state.agents:
            for mode, sizes in (
                ("indexed-v3", indexed_sizes),
                ("grounded-v3", grounded_sizes),
            ):
                observation = build_observation(
                    engine.state, agent_id, observation_mode=mode
                )
                sizes.append(
                    len(
                        json.dumps(
                            build_dynamic_observation(observation),
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                    )
                )

        self.assertLess(
            sum(indexed_sizes) / len(indexed_sizes),
            (sum(grounded_sizes) / len(grounded_sizes)) * 0.75,
        )

    def test_grounded_v3_marks_off_map_neighbors_explicitly(self) -> None:
        engine = WorldEngine.create(WorldConfig(seed=11), agent_names=["A1"])
        engine.state.agents["agent-1"].position = Position(0, 0)

        dynamic = build_dynamic_observation(
            build_observation(engine.state, "agent-1", observation_mode="grounded-v3")
        )

        self.assertEqual(
            dynamic["adjacent"]["north"],
            {"position": [0, -1], "in_world": False, "passable": False},
        )
        self.assertFalse(dynamic["adjacent"]["west"]["in_world"])

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
        self.assertIn("zero carry weight", build_static_context(near["world"]))


if __name__ == "__main__":
    unittest.main()
