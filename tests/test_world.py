from __future__ import annotations

from collections import Counter
import json
import unittest

from agent_world.interface import build_agent_prompt, build_observation
from agent_world.metrics import compute_metrics
from agent_world.models import AgentDecision, Position, WorldConfig
from agent_world.rules import ACTION_SCHEMA, RECIPES, RESOURCE_WEIGHTS
from agent_world.runner import SimulationRunner
from agent_world.world import WorldEngine


class WorldEngineTests(unittest.TestCase):
    def make_engine(self, agents: int = 2) -> WorldEngine:
        config = WorldConfig(seed=3)
        return WorldEngine.create(config=config, agent_names=[f"A{i + 1}" for i in range(agents)])

    def test_move_is_validated_and_updates_position(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        start = agent.position
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "move", "direction": "west"}])})
        self.assertNotEqual(start, agent.position)
        self.assertEqual(agent.position, Position(start.x - 1, start.y))
        self.assertTrue(any(event.type == "move" for event in engine.state.events))

    def test_water_tiles_are_not_occupiable(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        start = agent.position
        water_position = Position(start.x + 1, start.y)
        self.assertEqual(engine.state.tile_at(water_position).terrain, "water")
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "move", "direction": "east"}])})
        self.assertEqual(start, agent.position)
        self.assertTrue(any(event.type == "invalid_action" for event in engine.state.events))

    def test_agents_can_gather_water_from_adjacent_water(self) -> None:
        engine = WorldEngine.create(config=WorldConfig(seed=3, water_water_regen=0), agent_names=["A1"])
        agent = engine.state.agents["agent-1"]
        water_position = Position(agent.position.x + 1, agent.position.y)
        water_tile = engine.state.tile_at(water_position)
        before_inventory = agent.inventory["water"]
        before_source = water_tile.resources["water"]
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "gather", "resource": "water"}])})
        self.assertEqual(agent.position, Position(8, 8))
        self.assertEqual(agent.inventory["water"], before_inventory + 1)
        self.assertEqual(water_tile.resources["water"], before_source)

    def test_agents_can_fish_from_adjacent_water(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        water_position = Position(agent.position.x + 1, agent.position.y)
        water_tile = engine.state.tile_at(water_position)
        water_tile.resources["food"] = 1
        before_inventory = agent.inventory["food"]
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "fish"}])})
        self.assertEqual(agent.inventory["food"], before_inventory + 1)
        self.assertLessEqual(water_tile.resources["food"], 1)

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

    def test_harvest_requires_farm_plot_and_collects_more_from_improved_land(self) -> None:
        config = WorldConfig(seed=3, farm_passive_food_growth=0)
        engine = WorldEngine.create(config=config, agent_names=["A1"])
        agent = engine.state.agents["agent-1"]
        tile = engine.state.tile_at(agent.position)
        agent.inventory = Counter()
        tile.resources["food"] = 5

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "harvest", "resource": "food", "quantity": 3}])})
        self.assertEqual(agent.inventory["food"], 0)
        self.assertTrue(any("farm plot" in event.message for event in engine.state.events))

        agent.inventory = Counter({"fiber": 1})
        agent.needs.energy = 20
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "farm_plot"}])})
        agent.inventory = Counter()
        agent.needs.energy = 20
        tile.resources["food"] = 5
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "harvest", "resource": "food", "quantity": 3}])})

        self.assertEqual(agent.inventory["food"], 3)
        self.assertEqual(tile.resources["food"], 2)

    def test_default_carry_capacity_and_water_weight_are_tight(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]

        self.assertEqual(agent.carry_capacity, 10)
        self.assertEqual(agent.inventory_weight(), 5)

        agent.inventory["water"] += 2
        self.assertEqual(agent.inventory_weight(), 9)
        self.assertFalse(agent.can_carry("water", 1))
        self.assertTrue(agent.can_carry("food", 1))

    def test_world_config_controls_agent_limits_and_reserves(self) -> None:
        config = WorldConfig(
            seed=3,
            default_carry_capacity=18,
            food_reserve_start=4,
            food_reserve_max=8,
            water_reserve_start=5,
            water_reserve_max=9,
            energy_reserve_start=6,
            energy_reserve_max=12,
        )
        engine = WorldEngine.create(config=config, agent_names=["A1"])
        agent = engine.state.agents["agent-1"]

        self.assertEqual(agent.carry_capacity, 18)
        self.assertEqual(agent.needs.as_dict(), {"food": 4, "water": 5, "energy": 6})

        agent.needs.food = 7
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "consume", "item": "food"}])})
        self.assertLessEqual(agent.needs.food, 8)

    def test_world_config_scales_initial_resources(self) -> None:
        engine = WorldEngine.create(WorldConfig(resource_base_multiplier=2.0), agent_names=[])
        water_tile = engine.state.tiles[0][0]

        self.assertEqual(water_tile.resources["water"], 24)
        self.assertEqual(water_tile.resources["food"], 2)

    def test_world_config_controls_specific_regrowth_rates(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(plains_food_regen=1.0, plains_fiber_regen=0.0),
            agent_names=[],
        )
        plains_tile = next(tile for row in engine.state.tiles for tile in row if tile.terrain == "plains")
        plains_tile.resources["food"] = 0
        plains_tile.resources["fiber"] = 0

        engine.tick({})

        self.assertEqual(plains_tile.resources["food"], 1)
        self.assertEqual(plains_tile.resources["fiber"], 0)

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
        self.assertEqual(a1.inventory["food"], 2)
        self.assertFalse(engine.state.trades[trade_id].escrow_released)
        engine.tick({"agent-2": AgentDecision(actions=[{"type": "accept_trade", "trade_id": trade_id}])})
        self.assertEqual(a1.inventory["water"], 1)
        self.assertEqual(a2.inventory["food"], 1)
        self.assertEqual(engine.state.trades[trade_id].status, "accepted")
        self.assertTrue(engine.state.trades[trade_id].escrow_released)

    def test_public_trade_offer_can_be_accepted_by_visible_agent(self) -> None:
        engine = self.make_engine(2)
        a1 = engine.state.agents["agent-1"]
        a2 = engine.state.agents["agent-2"]
        a2.position = a1.position
        a1.inventory = Counter({"food": 2})
        a2.inventory = Counter({"water": 2})

        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {"type": "offer_trade", "to": "any", "give": {"food": 1}, "receive": {"water": 1}}
                    ]
                )
            }
        )
        trade_id = next(iter(engine.state.trades))
        self.assertTrue(engine.state.trades[trade_id].summary()["public"])
        self.assertEqual(a1.inventory["food"], 1)

        obs = build_observation(engine.state, "agent-2")
        self.assertEqual(obs["open_trades"][0]["id"], trade_id)

        engine.tick({"agent-2": AgentDecision(actions=[{"type": "accept_trade", "trade_id": trade_id}])})

        trade = engine.state.trades[trade_id]
        self.assertEqual(a1.inventory["water"], 1)
        self.assertEqual(a2.inventory["food"], 1)
        self.assertEqual(trade.status, "accepted")
        self.assertEqual(trade.accepted_by, "agent-2")
        self.assertEqual(compute_metrics(engine.state)["trade"]["public_accepted"], 1)

    def test_agent_cannot_accept_own_public_trade(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.inventory = Counter({"food": 2})

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "offer_trade", "give": {"food": 1}, "receive": {"water": 1}}])})
        trade_id = next(iter(engine.state.trades))
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "accept_trade", "trade_id": trade_id}])})

        self.assertEqual(engine.state.trades[trade_id].status, "open")
        self.assertTrue(any("own trade" in event.message for event in engine.state.events if event.type == "invalid_action"))

    def test_rejected_trade_returns_escrow_to_offerer(self) -> None:
        engine = self.make_engine(2)
        a1 = engine.state.agents["agent-1"]
        a2 = engine.state.agents["agent-2"]
        a2.position = a1.position
        a1.inventory = Counter({"food": 1})
        a2.inventory = Counter()

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "offer_trade", "to": "agent-2", "give": {"food": 1}, "receive": {"water": 1}}])})
        trade_id = next(iter(engine.state.trades))
        self.assertEqual(a1.inventory["food"], 0)

        engine.tick({"agent-2": AgentDecision(actions=[{"type": "reject_trade", "trade_id": trade_id}])})

        self.assertEqual(engine.state.trades[trade_id].status, "rejected")
        self.assertEqual(a1.inventory["food"], 1)
        self.assertTrue(engine.state.trades[trade_id].escrow_released)

    def test_expired_trade_returns_escrow_to_offerer(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.inventory = Counter({"food": 1})

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "offer_trade", "give": {"food": 1}, "receive": {"water": 1}, "expires_in": 1}])})
        trade_id = next(iter(engine.state.trades))
        self.assertEqual(agent.inventory["food"], 0)

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})

        self.assertEqual(engine.state.trades[trade_id].status, "expired")
        self.assertEqual(agent.inventory["food"], 1)
        self.assertTrue(engine.state.trades[trade_id].escrow_released)

    def test_claim_and_build_storage(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.inventory.update({"wood": 3, "fiber": 1})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "claim_tile"}])})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "storage"}])})
        tile = engine.state.tile_at(agent.position)
        self.assertEqual(tile.claimed_by, agent.id)
        self.assertEqual(len(tile.structure_ids), 1)
        structure = engine.state.structures[tile.structure_ids[0]]
        self.assertEqual(structure.type, "storage")

    def test_structure_recipe_costs_keep_storage_accessible_and_house_substantial(self) -> None:
        self.assertEqual(dict(RECIPES["farm_plot"].inputs), {"fiber": 1})
        self.assertEqual(RECIPES["farm_plot"].action_points, 1)
        self.assertEqual(RECIPES["farm_plot"].energy, 3)
        self.assertEqual(dict(RECIPES["storage"].inputs), {"wood": 2, "fiber": 1})
        self.assertEqual(RECIPES["storage"].action_points, 2)
        self.assertEqual(RECIPES["storage"].energy, 5)
        self.assertEqual(dict(RECIPES["well"].inputs), {"wood": 2, "fiber": 1})
        self.assertEqual(RECIPES["well"].action_points, 2)
        self.assertEqual(RECIPES["well"].energy, 6)
        self.assertEqual(dict(RECIPES["shelter"].inputs), {"wood": 6, "stone": 1, "fiber": 2})
        self.assertEqual(dict(RECIPES["house"].inputs), {"wood": 10, "stone": 3, "fiber": 3})
        self.assertEqual(RECIPES["house"].energy, 14)

    def test_well_provides_local_water_without_open_water(self) -> None:
        engine = WorldEngine.create(config=WorldConfig(seed=3, water_water_regen=0), agent_names=["A1"])
        agent = engine.state.agents["agent-1"]
        agent.inventory = Counter({"wood": 2, "fiber": 1})
        agent.needs.energy = 20
        for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
            pos = Position(agent.position.x + dx, agent.position.y + dy)
            if engine.in_bounds(pos):
                engine.state.tile_at(pos).resources["water"] = 0

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "well"}])})
        agent.inventory = Counter()
        agent.needs.energy = 20
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "gather", "resource": "water"}])})

        structure = next(iter(engine.state.structures.values()))
        gather_event = next(event for event in reversed(engine.state.events) if event.type == "gather")
        self.assertEqual(structure.type, "well")
        self.assertEqual(agent.inventory["water"], 1)
        self.assertEqual(gather_event.data["source"], "well")
        self.assertEqual(compute_metrics(engine.state)["infrastructure"]["wells"], 1)

    def test_farm_plot_is_persistent_and_improves_farming(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.inventory.update({"fiber": 1})
        tile = engine.state.tile_at(agent.position)
        tile.resources["food"] = 0
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "farm_plot"}])})
        self.assertEqual(engine.state.structures[tile.structure_ids[0]].type, "farm_plot")
        before = tile.resources["food"]
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "farm"}])})
        self.assertGreater(tile.resources["food"], before)

    def test_farming_requires_a_farm_plot(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        tile = engine.state.tile_at(agent.position)
        tile.resources["food"] = 0
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "farm"}])})
        self.assertEqual(tile.resources["food"], 0)
        self.assertTrue(
            any(event.type == "invalid_action" and "farm plot" in event.message for event in engine.state.events)
        )

    def test_house_improves_rest_and_can_store_goods(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.inventory.update({"wood": 10, "stone": 3, "fiber": 3})
        agent.carry_capacity = 40
        agent.needs.energy = 20
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "house"}])})
        structure_id = next(iter(engine.state.structures))
        structure = engine.state.structures[structure_id]
        self.assertEqual(structure.type, "house")
        agent.inventory["food"] += 1
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "store", "structure_id": structure_id, "item": "food"}])})
        self.assertGreaterEqual(structure.inventory["food"], 1)
        energy_before = agent.needs.energy
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        self.assertGreater(agent.needs.energy, energy_before + 6)

    def test_workshop_reduces_crafting_energy(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.inventory.update({"wood": 6, "stone": 3, "fiber": 2})
        agent.carry_capacity = 40
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "workshop"}])})
        agent.needs.energy = 5
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "craft", "recipe": "tool"}])})
        self.assertEqual(agent.inventory["tool"], 1)

    def test_heavy_structure_completes_via_staged_contributions(self) -> None:
        # A house weighs more than one agent can carry, so it must be funded across trips
        # by contributing materials to a construction site over several ticks.
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.needs.energy = 40
        agent.inventory.clear()
        house_inputs = RECIPES["house"].inputs
        self.assertGreater(
            sum(RESOURCE_WEIGHTS[item] * qty for item, qty in house_inputs.items()),
            agent.carry_capacity,
            "Test precondition: house inputs must exceed carry capacity.",
        )

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "house"}])})
        site = next(iter(engine.state.structures.values()))
        self.assertEqual(site.type, "house")
        self.assertEqual(site.status, "under_construction")
        self.assertFalse(site.is_complete)

        # An unfinished structure provides no effects: storing into it fails.
        agent.inventory.update({"food": 1})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "store", "structure_id": site.id, "item": "food"}])})
        self.assertTrue(any(event.type == "invalid_action" and "under construction" in event.message for event in engine.state.events))
        del agent.inventory["food"]

        for materials in ({"wood": 5}, {"wood": 5}, {"stone": 3}, {"fiber": 3}):
            agent.inventory.update(materials)
            agent.needs.energy = 40
            engine.tick({"agent-1": AgentDecision(actions=[{"type": "contribute", "structure": "house", "items": dict(materials)}])})

        self.assertTrue(site.is_complete)
        self.assertEqual(site.status, "complete")
        self.assertTrue(any(event.type == "build" and event.data.get("structure", {}).get("type") == "house" for event in engine.state.events))
        # Finished house now grants its rest bonus.
        agent.needs.energy = 10
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        self.assertGreater(agent.needs.energy, 10 + 6)

    def test_construction_site_supports_multi_agent_cooperation(self) -> None:
        engine = self.make_engine(2)
        owner = engine.state.agents["agent-1"]
        helper = engine.state.agents["agent-2"]
        helper.position = owner.position
        owner.needs.energy = 40
        owner.inventory.clear()
        helper.inventory.clear()

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "storage"}])})
        site = next(iter(engine.state.structures.values()))
        self.assertFalse(site.is_complete)

        owner.inventory.update({"wood": 2})
        helper.inventory.update({"fiber": 1})
        engine.tick(
            {
                "agent-1": AgentDecision(actions=[{"type": "contribute", "structure": "storage", "items": {"wood": 2}}]),
                "agent-2": AgentDecision(actions=[{"type": "contribute", "structure": "storage", "items": {"fiber": 1}}]),
            }
        )
        self.assertTrue(site.is_complete)
        self.assertGreaterEqual(len(site.contributors), 2)
        metrics = compute_metrics(engine.state)
        self.assertGreaterEqual(metrics["construction"]["cooperative_sites"], 1)
        self.assertGreaterEqual(metrics["construction"]["contributions"], 2)

    def test_metrics_report_lifespan_capacity_and_buildability(self) -> None:
        engine = self.make_engine(2)
        for _ in range(3):
            engine.tick({agent_id: AgentDecision(actions=[{"type": "wait"}]) for agent_id in engine.state.agents})
        metrics = compute_metrics(engine.state)
        self.assertIn("median_lifespan", metrics["agents"])
        self.assertIn("median_spare_action_points", metrics["capacity"])
        self.assertGreater(metrics["capacity"]["samples"], 0)
        self.assertIn("ever_buildable", metrics["infrastructure"])
        self.assertIn("never_buildable", metrics["infrastructure"])
        snapshot = engine.snapshot()
        self.assertIn("build_ready_ever", snapshot["diagnostics"])

    def test_storage_access_controls_retrieve(self) -> None:
        engine = self.make_engine(2)
        engine.state.config.carried_food_spoil_interval = 0
        owner = engine.state.agents["agent-1"]
        visitor = engine.state.agents["agent-2"]
        visitor.position = owner.position
        owner.inventory = Counter({"wood": 4, "fiber": 1, "food": 1})
        visitor.inventory = Counter()
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
        self.assertEqual(visitor.inventory["food"], 0)
        self.assertTrue(any(event.type == "invalid_action" for event in engine.state.events))
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "grant_access", "subject": structure_id, "target": "agent-2"}])})
        engine.tick({"agent-2": AgentDecision(actions=[{"type": "retrieve", "structure_id": structure_id, "item": "food"}])})
        self.assertEqual(visitor.inventory["food"], 1)

    def test_group_access_controls_shared_storage(self) -> None:
        engine = self.make_engine(2)
        engine.state.config.carried_food_spoil_interval = 0
        owner = engine.state.agents["agent-1"]
        member = engine.state.agents["agent-2"]
        member.position = owner.position
        owner.inventory = Counter({"wood": 4, "fiber": 1, "food": 1})
        member.inventory = Counter()

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "storage"}])})
        structure_id = next(iter(engine.state.structures))
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "store", "structure_id": structure_id, "item": "food"}])})
        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {"type": "wait"},
                        {"type": "wait"},
                        {"type": "wait"},
                        {"type": "create_group", "name": "Camp"},
                        {"type": "invite_member", "group_id": "group-1", "target": "agent-2"},
                        {"type": "grant_access", "subject": structure_id, "target": "group-1"},
                    ]
                ),
                "agent-2": AgentDecision(actions=[{"type": "join_group", "group_id": "group-1"}]),
            }
        )

        engine.tick({"agent-2": AgentDecision(actions=[{"type": "retrieve", "structure_id": structure_id, "item": "food"}])})

        self.assertIn("group-1", engine.state.structures[structure_id].access)
        self.assertIn("group-1", member.groups)
        self.assertEqual(member.inventory["food"], 1)

    def test_group_can_own_claimed_tile_and_storage(self) -> None:
        engine = self.make_engine(2)
        engine.state.config.carried_food_spoil_interval = 0
        founder = engine.state.agents["agent-1"]
        member = engine.state.agents["agent-2"]
        member.position = founder.position
        founder.inventory = Counter({"wood": 2, "fiber": 1, "food": 1})
        member.inventory = Counter()

        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {"type": "create_group", "name": "Camp"},
                        {"type": "invite_member", "group_id": "group-1", "target": "agent-2"},
                        {"type": "claim_tile", "group_id": "group-1"},
                        {"type": "build", "structure": "storage", "group_id": "group-1"},
                    ]
                ),
                "agent-2": AgentDecision(actions=[{"type": "join_group", "group_id": "group-1"}]),
            }
        )
        structure_id = next(iter(engine.state.structures))

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "store", "structure_id": structure_id, "item": "food"}])})
        engine.tick({"agent-2": AgentDecision(actions=[{"type": "retrieve", "structure_id": structure_id, "item": "food"}])})

        metrics = compute_metrics(engine.state)
        self.assertEqual(engine.state.tile_at(founder.position).claimed_by, "group-1")
        self.assertEqual(engine.state.structures[structure_id].owner_id, "group-1")
        self.assertEqual(member.inventory["food"], 1)
        self.assertEqual(metrics["groups"]["claimed_tiles"], 1)
        self.assertEqual(metrics["groups"]["owned_structures"], 1)

    def test_group_agreement_is_persisted_in_group_ledger(self) -> None:
        engine = self.make_engine(2)
        founder = engine.state.agents["agent-1"]
        member = engine.state.agents["agent-2"]
        member.position = founder.position

        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {"type": "create_group", "name": "Camp"},
                        {"type": "invite_member", "group_id": "group-1", "target": "agent-2"},
                        {
                            "type": "record_agreement",
                            "group_id": "group-1",
                            "parties": ["agent-1", "agent-2"],
                            "text": "Share stored food when hungry.",
                        },
                    ]
                ),
                "agent-2": AgentDecision(actions=[{"type": "join_group", "group_id": "group-1"}]),
            }
        )

        group = engine.state.groups["group-1"]
        obs = build_observation(engine.state, "agent-1")
        metrics = compute_metrics(engine.state)

        self.assertEqual(len(group.agreements), 1)
        self.assertEqual(group.agreements[0]["text"], "Share stored food when hungry.")
        self.assertEqual(group.agreements[0]["parties"], ["agent-1", "agent-2"])
        self.assertEqual(obs["known_groups"]["group-1"]["agreements"][0]["recorded_by"], "agent-1")
        self.assertEqual(metrics["groups"]["agreements"], 1)

    def test_non_member_cannot_record_group_agreement(self) -> None:
        engine = self.make_engine(2)
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "create_group", "name": "Camp"}])})

        engine.tick(
            {
                "agent-2": AgentDecision(
                    actions=[
                        {
                            "type": "record_agreement",
                            "group_id": "group-1",
                            "parties": ["agent-1", "agent-2"],
                            "text": "Use the storage.",
                        }
                    ]
                )
            }
        )

        self.assertEqual(engine.state.groups["group-1"].agreements, [])
        self.assertTrue(any("Only group members" in event.message for event in engine.state.events if event.type == "invalid_action"))

    def test_group_and_access_actions_are_agent_facing_free_actions(self) -> None:
        costs = {action["type"]: action["cost"]["action_points"] for action in ACTION_SCHEMA if "cost" in action}
        for action_type in [
            "grant_access",
            "revoke_access",
            "create_group",
            "invite_member",
            "join_group",
            "leave_group",
            "publish_rule",
            "record_agreement",
        ]:
            self.assertEqual(costs[action_type], 0)

    def test_carried_food_spoils_but_stored_food_is_protected(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.inventory = Counter({"food": 2, "wood": 4, "fiber": 1})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "storage"}])})
        structure_id = next(iter(engine.state.structures))
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "store", "structure_id": structure_id, "item": "food"}])})
        agent.inventory["food"] = 2
        while engine.state.tick <= engine.state.config.carried_food_spoil_interval:
            engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        storage = engine.state.structures[structure_id]
        self.assertLess(agent.inventory["food"], 2)
        self.assertEqual(storage.inventory["food"], 1)

    def test_food_consumption_restores_limited_food_reserve(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.inventory = Counter({"food": 1})
        agent.needs.food = 10
        agent.needs.energy = 10

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "consume", "item": "food"}])})

        self.assertEqual(agent.inventory["food"], 0)
        self.assertEqual(agent.needs.food, 14)
        self.assertEqual(agent.needs.energy, 13)

    def test_water_consumption_restores_more_than_food_because_thirst_decays_faster(self) -> None:
        config = WorldConfig(seed=3, survival_water_decay=0)
        engine = WorldEngine.create(config=config, agent_names=["A1"])
        agent = engine.state.agents["agent-1"]
        agent.inventory = Counter({"water": 1})
        agent.needs.water = 2

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "consume", "item": "water"}])})

        self.assertEqual(agent.inventory["water"], 0)
        self.assertEqual(agent.needs.water, 12)

    def test_reserves_start_below_hard_cap_and_clamp_to_max(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]

        self.assertEqual(agent.needs.as_dict(), {"food": 10, "water": 10, "energy": 25})
        agent.needs.food = 999
        agent.needs.water = 999
        agent.needs.energy = 999
        agent.needs.clamp()
        self.assertEqual(agent.needs.as_dict(), {"food": 20, "water": 20, "energy": 30})

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

    def test_top_level_messages_do_not_consume_action_points(self) -> None:
        engine = self.make_engine(1)
        decision = AgentDecision(
            messages=[{"mode": "say", "text": "hello"}],
            actions=[{"type": "wait"}, {"type": "wait"}, {"type": "wait"}],
        )

        engine.tick({"agent-1": decision})

        self.assertEqual(sum(event.type == "say" for event in engine.state.events), 1)
        self.assertEqual(sum(event.type == "wait" for event in engine.state.events), 3)
        self.assertFalse(any(event.type == "invalid_action" for event in engine.state.events))

    def test_speech_actions_are_free_after_action_points_are_spent(self) -> None:
        engine = self.make_engine(1)
        decision = AgentDecision(
            actions=[{"type": "wait"}, {"type": "wait"}, {"type": "wait"}, {"type": "say", "text": "still speaking"}]
        )

        engine.tick({"agent-1": decision})

        self.assertEqual(sum(event.type == "wait" for event in engine.state.events), 3)
        self.assertTrue(any(event.type == "say" and event.message == "still speaking" for event in engine.state.events))
        self.assertFalse(any(event.type == "invalid_action" for event in engine.state.events))

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

    def test_actor_resolution_priority_rotates_deterministically(self) -> None:
        engine = self.make_engine(3)
        observed_orders = []
        for tick in range(3):
            before = len(engine.state.events)
            engine.tick({agent_id: AgentDecision(actions=[{"type": "wait"}]) for agent_id in engine.state.agents})
            observed_orders.append(
                [event.actor_id for event in engine.state.events[before:] if event.type == "agent_response"]
            )

        self.assertEqual(observed_orders[0], ["agent-1", "agent-2", "agent-3"])
        self.assertEqual(observed_orders[1], ["agent-2", "agent-3", "agent-1"])
        self.assertEqual(observed_orders[2], ["agent-3", "agent-1", "agent-2"])

        second = self.make_engine(3)
        repeated = []
        for _ in range(3):
            before = len(second.state.events)
            second.tick({agent_id: AgentDecision(actions=[{"type": "wait"}]) for agent_id in second.state.agents})
            repeated.append([event.actor_id for event in second.state.events[before:] if event.type == "agent_response"])
        self.assertEqual(observed_orders, repeated)

    def test_trade_is_actionable_on_its_visible_expiration_tick(self) -> None:
        engine = self.make_engine(2)
        seller = engine.state.agents["agent-1"]
        buyer = engine.state.agents["agent-2"]
        buyer.position = seller.position
        seller.inventory = Counter({"food": 1})
        buyer.inventory = Counter({"water": 1})
        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {
                            "type": "offer_trade",
                            "to": "agent-2",
                            "give": {"food": 1},
                            "receive": {"water": 1},
                            "expires_in": 1,
                        }
                    ]
                )
            }
        )
        trade_id = next(iter(engine.state.trades))
        self.assertEqual(engine.state.tick, engine.state.trades[trade_id].expires_tick)

        engine.tick({"agent-2": AgentDecision(actions=[{"type": "accept_trade", "trade_id": trade_id}])})

        self.assertEqual(engine.state.trades[trade_id].status, "accepted")
        self.assertFalse(any(event.type == "expire_trade" for event in engine.state.events))

    def test_skill_and_equipped_tool_raise_output_reduce_energy_and_wear(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        tile = engine.state.tile_at(agent.position)
        tile.resources["wood"] = 10
        agent.inventory = Counter({"tool": 1})
        agent.equipped = {"tool"}
        agent.equipment_durability["tool"] = 1
        agent.skills["woodcraft"] = 4
        agent.needs.energy = 20

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "chop"}])})

        event = next(event for event in engine.state.events if event.type == "chop")
        self.assertEqual(event.data["quantity"], 3)
        self.assertEqual(event.data["skill_yield_bonus"], 1)
        self.assertEqual(event.data["tool_yield_bonus"], 1)
        self.assertEqual(event.data["energy_cost"], 4)
        self.assertEqual(agent.inventory["tool"], 0)
        self.assertNotIn("tool", agent.equipped)
        self.assertTrue(any(item.type == "tool_broken" for item in engine.state.events))

    def test_workshop_enables_ore_ingot_advanced_tool_chain(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.carry_capacity = 100
        agent.needs.energy = 100
        agent.inventory = Counter({"wood": 5, "stone": 2, "fiber": 1})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "workshop"}])})
        self.assertTrue(next(iter(engine.state.structures.values())).is_complete)

        agent.inventory = Counter({"ore": 4, "wood": 3, "fiber": 1})
        agent.needs.energy = 100
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "craft", "recipe": "ingot"}])})
        agent.needs.energy = 100
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "craft", "recipe": "ingot"}])})
        self.assertEqual(agent.inventory["ingot"], 2)

        agent.needs.energy = 100
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "craft", "recipe": "advanced_tool"}])})
        self.assertEqual(agent.inventory["advanced_tool"], 1)

    def test_commerce_public_offer_is_global_acceptance_is_free_and_price_is_recorded(self) -> None:
        config = WorldConfig(seed=3, economy_mode="commerce", geography_mode="dispersed")
        engine = WorldEngine.create(config=config, agent_names=["Seller", "Buyer"])
        seller = engine.state.agents["agent-1"]
        buyer = engine.state.agents["agent-2"]
        self.assertGreater(seller.position.distance_to(buyer.position), config.visible_radius)
        seller.inventory = Counter({"food": 2})
        buyer.inventory = Counter({"water": 2})
        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[{"type": "offer_trade", "to": "any", "give": {"food": 1}, "receive": {"water": 1}}]
                )
            }
        )
        trade_id = next(iter(engine.state.trades))
        self.assertEqual(engine.state.trades[trade_id].market_scope, "global")

        before = len(engine.state.events)
        engine.tick(
            {
                "agent-2": AgentDecision(
                    actions=[{"type": "accept_trade", "trade_id": trade_id}] + [{"type": "wait"}] * 4
                )
            }
        )
        new_events = engine.state.events[before:]
        self.assertEqual(sum(event.type == "wait" and event.actor_id == buyer.id for event in new_events), 4)
        self.assertEqual(engine.state.trades[trade_id].status, "accepted")
        self.assertEqual(engine.state.market_history[0]["trade_id"], trade_id)

    def test_commerce_standing_offer_fills_multiple_escrowed_lots(self) -> None:
        engine = WorldEngine.create(WorldConfig(seed=3, economy_mode="commerce"), agent_names=["Seller", "Buyer"])
        seller = engine.state.agents["agent-1"]
        buyer = engine.state.agents["agent-2"]
        buyer.position = seller.position
        seller.inventory = Counter({"food": 3})
        buyer.inventory = Counter({"water": 3})
        engine.tick(
            {
                seller.id: AgentDecision(
                    actions=[
                        {
                            "type": "offer_trade",
                            "to": "any",
                            "give": {"food": 1},
                            "receive": {"water": 1},
                            "lots": 2,
                        }
                    ]
                )
            }
        )
        trade_id = next(iter(engine.state.trades))
        trade = engine.state.trades[trade_id]
        self.assertEqual(seller.inventory["food"], 1)

        engine.tick({buyer.id: AgentDecision(actions=[{"type": "accept_trade", "trade_id": trade_id}])})
        self.assertEqual(trade.status, "open")
        self.assertEqual(trade.lots_remaining, 1)
        engine.tick({buyer.id: AgentDecision(actions=[{"type": "accept_trade", "trade_id": trade_id}])})

        self.assertEqual(trade.status, "accepted")
        self.assertEqual(trade.accepted_count, 2)
        self.assertEqual(len(engine.state.market_history), 2)
        self.assertEqual(seller.inventory["water"], 2)
        self.assertEqual(buyer.inventory["food"], 2)

    def test_commerce_structure_charges_fee_caps_use_and_credits_contributor(self) -> None:
        config = WorldConfig(seed=3, economy_mode="commerce", carried_food_spoil_interval=0)
        engine = WorldEngine.create(config=config, agent_names=["Owner", "Customer"])
        owner = engine.state.agents["agent-1"]
        customer = engine.state.agents["agent-2"]
        customer.position = owner.position
        owner.inventory = Counter({"fiber": 1})
        customer.inventory = Counter({"food": 3})
        owner.needs.energy = customer.needs.energy = 30
        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {"type": "build", "structure": "farm_plot"},
                        {
                            "type": "set_access_fee",
                            "structure_id": "structure-1",
                            "public": True,
                            "fee": {"food": 1},
                        },
                    ]
                )
            }
        )
        farm = engine.state.structures["structure-1"]
        farm.uses_per_tick = 1

        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[{"type": "claim_dividend", "structure_id": farm.id, "item": "food"}]
                ),
                "agent-2": AgentDecision(actions=[{"type": "farm"}, {"type": "farm"}]),
            }
        )

        self.assertEqual(farm.total_uses, 1)
        self.assertEqual(owner.inventory["food"], 1)
        self.assertEqual(customer.inventory["food"], 2)
        self.assertTrue(any("productive capacity" in event.message for event in engine.state.events if event.type == "invalid_action"))
        self.assertEqual(farm.contributor_shares(), {owner.id: 1.0})

    def test_commerce_structure_upkeep_can_deactivate_and_be_restored(self) -> None:
        config = WorldConfig(seed=3, economy_mode="commerce")
        engine = WorldEngine.create(config=config, agent_names=["Owner"])
        owner = engine.state.agents["agent-1"]
        owner.inventory = Counter({"fiber": 1})
        owner.needs.energy = 30
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "farm_plot"}])})
        farm = engine.state.structures["structure-1"]
        farm.upkeep_interval = 1

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        self.assertFalse(farm.active)

        owner.inventory["fiber"] = 1
        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[{"type": "maintain_structure", "structure_id": farm.id, "items": {"fiber": 1}}]
                )
            }
        )
        self.assertTrue(farm.active)

    def test_secured_credit_auto_repays_or_forfeits_collateral(self) -> None:
        def create_credit(borrower_has_repayment: bool) -> tuple[WorldEngine, str]:
            engine = WorldEngine.create(WorldConfig(seed=3, economy_mode="commerce"), agent_names=["Lender", "Borrower"])
            lender = engine.state.agents["agent-1"]
            borrower = engine.state.agents["agent-2"]
            borrower.position = lender.position
            lender.inventory = Counter({"food": 3})
            borrower.inventory = Counter({"tool": 1, **({"ore": 1} if borrower_has_repayment else {})})
            engine.tick(
                {
                    "agent-1": AgentDecision(
                        actions=[
                            {
                                "type": "offer_contract",
                                "to": borrower.id,
                                "advance": {"food": 2},
                                "repayment": {"ore": 1},
                                "collateral": {"tool": 1},
                                "due_in": 1,
                            }
                        ]
                    )
                }
            )
            contract_id = next(iter(engine.state.contracts))
            engine.tick({borrower.id: AgentDecision(actions=[{"type": "accept_contract", "contract_id": contract_id}])})
            engine.tick({})
            return engine, contract_id

        repaid, repaid_id = create_credit(True)
        self.assertEqual(repaid.state.contracts[repaid_id].status, "fulfilled")
        self.assertEqual(repaid.state.agents["agent-1"].inventory["ore"], 1)
        self.assertEqual(repaid.state.agents["agent-2"].inventory["tool"], 1)

        defaulted, defaulted_id = create_credit(False)
        self.assertEqual(defaulted.state.contracts[defaulted_id].status, "defaulted")
        self.assertEqual(defaulted.state.agents["agent-1"].inventory["tool"], 1)
        self.assertLess(defaulted.state.agents["agent-2"].reputation, 0)

    def test_commerce_coordination_actions_consume_configured_capacity(self) -> None:
        engine = WorldEngine.create(WorldConfig(seed=3, economy_mode="commerce"), agent_names=["A1"])
        engine.tick(
            {
                "agent-1": AgentDecision(
                    actions=[
                        {"type": "broadcast", "text": "hello"},
                        {"type": "create_group", "name": "Firm"},
                        {"type": "wait"},
                        {"type": "wait"},
                        {"type": "wait"},
                    ]
                )
            }
        )
        self.assertEqual(sum(event.type == "wait" for event in engine.state.events), 2)
        self.assertEqual(engine.state.config.communication_cost(), 1)
        self.assertEqual(engine.state.config.group_admin_cost(), 1)

    def test_snapshot_exposes_economic_treatment_state(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(seed=3, economy_mode="commerce", geography_mode="dispersed"),
            agent_names=["A1"],
        )
        snapshot = engine.snapshot()
        agent = snapshot["agents"]["agent-1"]
        self.assertEqual(snapshot["config"]["economy_mode"], "commerce")
        self.assertEqual(snapshot["market_history"], [])
        self.assertEqual(snapshot["contracts"], {})
        self.assertIsNotNone(agent["specialty"])
        self.assertIn("aptitudes", agent)
        self.assertIn("need_multipliers", agent)
        self.assertIn("equipment_durability", agent)

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

    def test_old_fields_wrapper_actions_are_normalized(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        start = agent.position
        engine.tick({"agent-1": {"actions": [{"type": "move", "fields": {"direction": "west"}}]}})
        self.assertEqual(agent.position, Position(start.x - 1, start.y))

    def test_observation_does_not_feed_agent_io_logs_back_to_agent(self) -> None:
        class WaitBrain:
            def decide(self, observation):
                return {"intent": "wait", "actions": [{"type": "wait"}], "messages": [], "memory_updates": []}

        engine = self.make_engine(1)
        runner = SimulationRunner(engine, {"agent-1": WaitBrain()})
        runner.step()
        obs = build_observation(engine.state, "agent-1")
        event_types = {event["type"] for event in obs["recent_events"]}
        self.assertNotIn("agent_observation", event_types)
        self.assertNotIn("agent_prompt", event_types)
        self.assertNotIn("agent_response", event_types)

    def test_observation_does_not_include_build_readiness_hint(self) -> None:
        engine = self.make_engine(1)
        agent = engine.state.agents["agent-1"]
        agent.inventory.update({"fiber": 1})
        obs = build_observation(engine.state, "agent-1")
        self.assertNotIn("current_affordances", obs)
        self.assertNotIn("buildable_structures_here", str(obs))

    def test_observation_includes_recipes_without_productivity_or_current_build_hint(self) -> None:
        engine = self.make_engine(1)
        obs = build_observation(engine.state, "agent-1")
        self.assertFalse(obs["world"]["terrain_rules"]["water"]["passable"])
        self.assertEqual(obs["world"]["reserve_scale"]["maximum"], {"food": 20, "water": 20, "energy": 30})
        self.assertIn("Higher is better", obs["world"]["reserve_scale"]["meaning"])
        self.assertIn("reserves", obs["self"])
        self.assertNotIn("needs", obs["self"])
        self.assertEqual(obs["action_format"]["shape"], "flat_object")
        self.assertEqual(obs["action_format"]["valid_example"], {"type": "move", "direction": "east"})
        move_action = next(action for action in obs["valid_actions"] if action["type"] == "move")
        self.assertEqual(move_action["example"], {"type": "move", "direction": "north"})
        self.assertEqual(move_action["cost"]["action_points"], "destination terrain move_cost")
        harvest_action = next(action for action in obs["valid_actions"] if action["type"] == "harvest")
        self.assertEqual(harvest_action["cost"], {"action_points": 2, "energy": 4})
        self.assertNotIn("fields", move_action)
        self.assertNotIn("base_resources", obs["world"]["terrain_rules"]["plains"])
        self.assertNotIn("regen", obs["world"]["terrain_rules"]["plains"])
        self.assertEqual(obs["world"]["recipes"]["farm_plot"]["required_terrain"], ["plains", "forest"])
        self.assertEqual(obs["world"]["recipes"]["well"]["required_terrain"], ["plains", "forest"])
        self.assertNotIn("structure_effects", obs["world"])
        self.assertNotIn("survival_rules", obs["world"])
        self.assertNotIn("farm_food_added", str(obs))
        self.assertNotIn("passive_food_growth_per_tick", str(obs))
        self.assertNotIn("buildable", str(obs))

    def test_visible_agents_show_coarse_carry_hints_not_exact_inventory(self) -> None:
        engine = self.make_engine(2)
        agent_1 = engine.state.agents["agent-1"]
        agent_2 = engine.state.agents["agent-2"]
        agent_2.position = agent_1.position
        agent_2.inventory.update({"wood": 1, "fiber": 1})

        obs = build_observation(engine.state, "agent-1")
        other = next(tile["agents"][0] for tile in obs["local_map"] if tile["agents"])
        nearby = obs["nearby_agents"][0]

        self.assertEqual(other["id"], "agent-2")
        self.assertEqual(other["visible_carry"]["load"], "heavy")
        self.assertEqual(other["visible_carry"]["resource_types"], ["fiber", "food", "water", "wood"])
        self.assertEqual(other["visible_condition"]["health"], "ok")
        self.assertEqual(other["visible_condition"]["hunger"], "strained")
        self.assertIn("thirst", other["visible_condition"])
        self.assertNotIn("inventory", other)
        self.assertEqual(nearby["id"], "agent-2")
        self.assertEqual(nearby["distance"], 0)
        self.assertEqual(nearby["visible_carry"]["resource_types"], other["visible_carry"]["resource_types"])
        self.assertNotIn("inventory", nearby)

    def test_gathering_food_from_farm_plot_produces_experiential_feedback(self) -> None:
        config = WorldConfig(seed=3, farm_passive_food_growth=0)
        engine = WorldEngine.create(config=config, agent_names=["A1"])
        agent = engine.state.agents["agent-1"]
        tile = engine.state.tile_at(agent.position)
        agent.inventory.update({"fiber": 1})
        agent.needs.energy = 20
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "farm_plot"}])})
        tile.resources["food"] = 2

        engine.tick({"agent-1": AgentDecision(actions=[{"type": "gather", "resource": "food"}])})

        gather_event = next(event for event in reversed(engine.state.events) if event.type == "gather")
        self.assertTrue(gather_event.data["improved_land"])
        self.assertIn("improved land", gather_event.message)

    def test_observation_includes_recent_action_feedback(self) -> None:
        engine = self.make_engine(1)
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "move", "direction": "sideways"}])})
        obs = build_observation(engine.state, "agent-1")
        self.assertEqual(len(obs["recent_action_feedback"]), 1)
        self.assertEqual(obs["recent_action_feedback"][0]["reason"], "Move requires direction north, south, east, or west.")
        self.assertEqual(obs["recent_action_feedback"][0]["attempted_action"]["direction"], "sideways")

    def test_compact_prompt_splits_static_rules_from_slim_dynamic_state(self) -> None:
        engine = self.make_engine(1)
        obs = build_observation(engine.state, "agent-1")
        obs["memory"] = [f"memory {index}" for index in range(30)]
        prompt = build_agent_prompt(obs, compact=True)
        prompt_observation = json.loads(prompt.split("The current observation follows as JSON:\n", 1)[1])

        # Static rulebook is rendered as terse text, not JSON, and carries costs/recipes.
        self.assertIn("ACTIONS (cost: action points, energy):", prompt)
        self.assertIn("RECIPES (inputs -> cost, terrain):", prompt)
        self.assertIn("cost:1ap,3en", prompt)  # gather
        self.assertIn("longer-term resilience", prompt)
        # Dynamic JSON no longer repeats the static sections.
        self.assertNotIn("valid_actions", prompt_observation)
        self.assertNotIn("world", prompt_observation)
        self.assertNotIn("action_format", prompt_observation)
        # Tiles omit empty/default fields but keep terrain and non-zero resources.
        for tile in prompt_observation["local_map"]:
            self.assertIn("terrain", tile)
            self.assertNotIn("passable", tile)
            self.assertNotIn("move_cost", tile)
            for value in tile.get("resources", {}).values():
                self.assertGreater(value, 0)
        self.assertEqual(prompt_observation["memory"], [f"memory {index}" for index in range(14, 30)])
        self.assertLess(len(prompt), len(build_agent_prompt(obs)))

    def test_parse_agent_response_salvages_fenced_and_noisy_json(self) -> None:
        from agent_world.interface import parse_agent_response

        fenced = '```json\n{"intent":"go","actions":[{"type":"wait"}],"messages":[],"memory_updates":[]}\n```'
        self.assertEqual(parse_agent_response(fenced).intent, "go")
        noisy = 'Here is my decision:\n{"intent":"noisy","actions":[],"messages":[],"memory_updates":[]}\nHope that helps!'
        self.assertEqual(parse_agent_response(noisy).intent, "noisy")
        nested = 'x {"intent":"nested","actions":[{"type":"say","text":"a {b} c"}],"messages":[],"memory_updates":[]}'
        self.assertEqual(parse_agent_response(nested).intent, "nested")
        truncated = '{"intent":"cut off, no closing brace'
        decision = parse_agent_response(truncated)
        self.assertTrue(decision.intent.startswith("Invalid JSON response"))
        self.assertEqual(decision.actions, [{"type": "wait"}])

    def test_denied_structure_access_notifies_owner(self) -> None:
        engine = self.make_engine(2)
        owner = engine.state.agents["agent-1"]
        visitor = engine.state.agents["agent-2"]
        visitor.position = owner.position
        owner.inventory = Counter({"wood": 2, "fiber": 1})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "storage"}])})
        structure_id = next(iter(engine.state.structures))

        visitor.inventory = Counter({"food": 1})
        engine.tick({"agent-2": AgentDecision(actions=[{"type": "store", "structure_id": structure_id, "item": "food"}])})

        denied = [event for event in engine.state.events if event.type == "access_denied"]
        self.assertEqual(len(denied), 1)
        self.assertEqual(denied[0].actor_id, "agent-2")
        self.assertIn("agent-1", denied[0].recipients)
        self.assertIn("denied access", denied[0].message)

    def test_observation_marks_structure_access(self) -> None:
        engine = self.make_engine(2)
        owner = engine.state.agents["agent-1"]
        visitor = engine.state.agents["agent-2"]
        visitor.position = owner.position
        owner.inventory = Counter({"wood": 2, "fiber": 1})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "storage"}])})

        obs_owner = build_observation(engine.state, "agent-1")
        obs_visitor = build_observation(engine.state, "agent-2")
        struct_owner = next(s for tile in obs_owner["local_map"] for s in tile["structures"])
        struct_visitor = next(s for tile in obs_visitor["local_map"] for s in tile["structures"])
        self.assertTrue(struct_owner["access_granted"])
        self.assertFalse(struct_visitor["access_granted"])

    def test_metrics_count_malformed_brain_responses_as_decision_failures(self) -> None:
        engine = self.make_engine(1)
        engine.log_event("agent_response", actor_id="agent-1", message="Invalid JSON response: Unterminated string")
        metrics = compute_metrics(engine.state)
        self.assertEqual(metrics["llm"]["decision_failures"], 1)

    def test_metrics_separate_hard_quota_from_retryable_rate_limits(self) -> None:
        engine = self.make_engine(1)
        engine.log_event("agent_response", actor_id="agent-1", message="OpenAI quota unavailable: insufficient_quota")
        metrics = compute_metrics(engine.state)
        self.assertEqual(metrics["llm"]["decision_failures"], 1)
        self.assertEqual(metrics["llm"]["quota_failures"], 1)
        self.assertEqual(metrics["llm"]["rate_limit_failures"], 0)


if __name__ == "__main__":
    unittest.main()
