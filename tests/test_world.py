from __future__ import annotations

from collections import Counter
import json
import unittest

from agent_world.interface import build_observation
from agent_world.models import AgentDecision, Position, WorldConfig
from agent_world.runner import SimulationRunner
from agent_world.world import WorldEngine


class WorldEngineTests(unittest.TestCase):
    def make_engine(self, agents: int = 2) -> WorldEngine:
        config = WorldConfig(width=8, height=8, seed=3)
        return WorldEngine.create(config=config, agent_names=[f"A{i + 1}" for i in range(agents)])

    def test_move_is_validated_and_updates_position(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        start = agent.position
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "move", "direction": "east"}])})
        self.assertNotEqual(start, agent.position)
        self.assertEqual(agent.position, Position(start.x + 1, start.y))
        self.assertTrue(any(event.type == "move" for event in engine.state.events))

    def test_invalid_move_is_logged_without_mutating_position(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        start = agent.position
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "move", "direction": "sideways"}])})
        self.assertEqual(start, agent.position)
        self.assertTrue(any(event.type == "invalid_action" for event in engine.state.events))

    def test_gather_depletes_tile_and_adds_inventory(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        tile = engine.state.tile_at(agent.position)
        tile.resources["food"] = 3
        before = agent.inventory["food"]
        resource_before = tile.resources["food"]
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "gather", "resource": "food"}])})
        self.assertEqual(agent.inventory["food"], before + 1)
        self.assertLessEqual(tile.resources["food"], resource_before)

    def test_crafting_tool_consumes_inputs_and_creates_tool(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.inventory.update({"wood": 1, "stone": 1, "fiber": 1})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "craft", "recipe": "tool"}])})
        self.assertEqual(agent.inventory["tool"], 1)
        self.assertEqual(agent.inventory["wood"], 0)

    def test_trade_acceptance_transfers_goods(self) -> None:
        engine = self.make_engine(2)
        a1 = engine.state.agents["agent-1"]
        a2 = engine.state.agents["agent-2"]
        a2.position = a1.position
        a1.inventory = Counter({"food": 3})
        a2.inventory = Counter({"water": 3})
        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {
                            "type": "offer_trade",
                            "to": "agent-2",
                            "give": {"food": 1},
                            "receive": {"water": 1},
                        }
                    ]
                ),
                "agent-2": AgentDecision(actions=[{"type": "wait"}]),
            }
        )
        trade_id = next(iter(engine.state.trades))
        engine.tick({"agent-2": AgentDecision(actions=[{"type": "accept_trade", "trade_id": trade_id}])})
        self.assertEqual(a1.inventory["water"], 1)
        self.assertEqual(a2.inventory["food"], 1)
        self.assertEqual(engine.state.trades[trade_id].status, "accepted")

    def test_claim_and_build_storage(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.inventory.update({"wood": 4, "fiber": 1})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "claim_tile"}])})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "storage"}])})
        tile = engine.state.tile_at(agent.position)
        self.assertEqual(tile.claimed_by, agent.id)
        self.assertEqual(len(tile.structure_ids), 1)
        structure = engine.state.structures[tile.structure_ids[0]]
        self.assertEqual(structure.type, "storage")

    def test_storage_access_controls_retrieve(self) -> None:
        engine = self.make_engine(2)
        owner = engine.state.agents["agent-1"]
        visitor = engine.state.agents["agent-2"]
        visitor.position = owner.position
        owner.inventory.update({"wood": 4, "fiber": 1, "food": 1})
        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {"type": "build", "structure": "storage"},
                    ]
                )
            }
        )
        structure_id = next(iter(engine.state.structures))
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "store", "structure_id": structure_id, "item": "food"}])})
        engine.tick({"agent-2": AgentDecision(actions=[{"type": "retrieve", "structure_id": structure_id, "item": "food"}])})
        self.assertEqual(visitor.inventory["food"], 2)
        self.assertTrue(any(event.type == "invalid_action" for event in engine.state.events))
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "grant_access", "subject": structure_id, "target": "agent-2"}])})
        engine.tick({"agent-2": AgentDecision(actions=[{"type": "retrieve", "structure_id": structure_id, "item": "food"}])})
        self.assertEqual(visitor.inventory["food"], 3)

    def test_survival_damage_and_death(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.needs.food = 0
        agent.needs.water = 0
        agent.needs.energy = 0
        agent.health = 5
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        self.assertFalse(agent.alive)
        self.assertTrue(any(event.type == "death" for event in engine.state.events))

    def test_observation_filters_private_events(self) -> None:
        engine = self.make_engine(2)
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "consume", "item": "food"}])})
        obs_1 = build_observation(engine.state, "agent-1")
        obs_2 = build_observation(engine.state, "agent-2")
        self.assertTrue(any(event["type"] == "consume" for event in obs_1["recent_events"]))
        self.assertFalse(any(event["type"] == "consume" for event in obs_2["recent_events"]))

    def test_deterministic_runs_have_same_event_log(self) -> None:
        def run() -> list[dict[str, object]]:
            engine = self.make_engine(2)
            for _ in range(4):
                decisions = {
                    "agent-1": AgentDecision(actions=[{"type": "gather", "resource": "food"}]),
                    "agent-2": AgentDecision(actions=[{"type": "wait"}]),
                }
                engine.tick(decisions)
            return [json.loads(line) for line in engine.export_events_jsonl().splitlines()]

        self.assertEqual(run(), run())

    def test_runner_logs_private_observation_and_prompt(self) -> None:
        class WaitBrain:
            def decide(self, observation):
                return {"intent": "wait", "actions": [{"type": "wait"}], "messages": [], "memory_updates": []}

        engine = self.make_engine(1)
        runner = SimulationRunner(engine, {"agent-1": WaitBrain()})
        runner.step()
        event_types = [event.type for event in engine.state.events]
        self.assertIn("agent_observation", event_types)
        self.assertIn("agent_prompt", event_types)


if __name__ == "__main__":
    unittest.main()
