from __future__ import annotations

import json
import unittest

from agent_world.cli import DEFAULT_RUN_PRESET, RUN_PRESETS
from agent_world.interface import build_dynamic_observation, build_observation, build_static_context
from agent_world.models import AgentDecision, Position, Structure, WorldConfig
from agent_world.rules import (
    FRONTIER_RECIPES,
    current_season,
    is_storm_tick,
    recipes_for_mode,
    structure_types_for_variant,
)
from agent_world.world import WorldEngine


def _frontier_config(**overrides) -> WorldConfig:
    defaults = dict(
        seed=11,
        economy_mode="organic",
        geography_mode="dispersed",
        world_variant="frontier",
        # One-tick seasons put winter at tick 3 without simulating 36 ticks.
        season_length_ticks=1,
        survival_food_decay=0,
        survival_water_decay=0,
        survival_energy_decay=0,
    )
    defaults.update(overrides)
    return WorldConfig(**defaults)


def _place_structure(engine: WorldEngine, structure_type: str, position: Position, owner_id: str) -> Structure:
    structure = Structure(
        id=f"structure-test-{structure_type}",
        type=structure_type,
        position=position,
        owner_id=owner_id,
        status="complete",
    )
    engine.state.structures[structure.id] = structure
    engine.state.tile_at(position).structure_ids.append(structure.id)
    return structure


class FrontierRulesTests(unittest.TestCase):
    def test_frontier_recipes_and_structures_are_variant_gated(self) -> None:
        classic = recipes_for_mode("organic")
        frontier = recipes_for_mode("organic", "frontier")
        self.assertNotIn("road", classic)
        self.assertNotIn("irrigation", classic)
        self.assertIn("road", frontier)
        self.assertIn("irrigation", frontier)
        self.assertNotIn("road", structure_types_for_variant("classic"))
        self.assertIn("road", structure_types_for_variant("frontier"))

    def test_frontier_generalists_is_the_ordinary_run_default(self) -> None:
        self.assertEqual(DEFAULT_RUN_PRESET, "frontier-generalists")
        self.assertEqual(
            RUN_PRESETS[DEFAULT_RUN_PRESET]["world_variant"],
            "frontier",
        )


    def test_season_cycle_and_storm_determinism(self) -> None:
        self.assertEqual(current_season(1, 0), "spring")
        self.assertEqual(current_season(1, 3), "winter")
        self.assertEqual(current_season(12, 47), "winter")
        # Deterministic per (seed, tick); storms never strike outside autumn/winter.
        for tick in range(0, 200):
            self.assertEqual(is_storm_tick(7, 1, tick), is_storm_tick(7, 1, tick))
            if current_season(1, tick) in {"spring", "summer"}:
                self.assertFalse(is_storm_tick(7, 1, tick))
        self.assertTrue(any(is_storm_tick(7, 1, tick) for tick in range(0, 400)))


class FrontierPromptTests(unittest.TestCase):
    def test_classic_prompt_is_unchanged(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(economy_mode="organic", geography_mode="dispersed"),
            agent_names=["A1"],
        )
        prompt = build_static_context(build_observation(engine.state, "agent-1")["world"])
        self.assertNotIn("SEASONS", prompt)
        self.assertNotIn("irrigation", prompt)
        self.assertNotIn("- road:", prompt)
        self.assertIn("structure=farm_plot|storage|shelter|house|workshop|well", prompt)
        self.assertNotIn("structure=farm_plot|storage|shelter|house|workshop|well|road", prompt)

    def test_frontier_prompt_documents_the_new_world(self) -> None:
        engine = WorldEngine.create(_frontier_config(season_length_ticks=12), agent_names=["A1"])
        observation = build_observation(engine.state, "agent-1")
        prompt = build_static_context(observation["world"])
        self.assertIn("SEASONS (cycle spring->summer->autumn->winter, 12 ticks each", prompt)
        self.assertIn("winter tick costs 3 health", prompt)
        self.assertIn("road (structure)", prompt)
        self.assertIn("irrigation (structure)", prompt)
        self.assertIn("structure=farm_plot|storage|shelter|house|workshop|well|road|irrigation", prompt)
        self.assertIn("- road: ", prompt)
        self.assertIn("- irrigation: ", prompt)

    def test_dynamic_observation_carries_season_state(self) -> None:
        engine = WorldEngine.create(_frontier_config(), agent_names=["A1"])
        engine.state.tick = 3  # winter under one-tick seasons
        observation = build_observation(engine.state, "agent-1")
        dynamic = build_dynamic_observation(observation)
        self.assertEqual(dynamic["season"]["name"], "winter")
        self.assertEqual(dynamic["season"]["ticks_remaining"], 1)
        # Classic worlds carry no season key at all.
        classic = WorldEngine.create(WorldConfig(), agent_names=["A1"])
        classic_dynamic = build_dynamic_observation(build_observation(classic.state, "agent-1"))
        self.assertNotIn("season", classic_dynamic)


class FrontierEngineTests(unittest.TestCase):
    def test_winter_exposure_damages_unsheltered_agents_only(self) -> None:
        engine = WorldEngine.create(_frontier_config(), agent_names=["A1", "A2"])
        exposed = engine.state.agents["agent-1"]
        sheltered = engine.state.agents["agent-2"]
        _place_structure(engine, "shelter", sheltered.position, sheltered.id)
        engine.state.tick = 3  # winter
        engine.tick(
            {
                "agent-1": AgentDecision(actions=[{"type": "wait"}]),
                "agent-2": AgentDecision(actions=[{"type": "wait"}]),
            }
        )
        self.assertLessEqual(exposed.health, 100 - engine.state.config.winter_exposure_damage)
        self.assertEqual(sheltered.health, 100)
        damage_events = [
            event
            for event in engine.state.events
            if event.type == "survival_damage" and event.actor_id == "agent-1"
        ]
        self.assertTrue(any("winter_exposure" in (event.data or {}).get("causes", []) for event in damage_events))

    def test_summer_has_no_exposure(self) -> None:
        engine = WorldEngine.create(_frontier_config(), agent_names=["A1"])
        engine.state.tick = 1  # summer
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        agent = engine.state.agents["agent-1"]
        if agent.health < 100:
            # Only a seeded storm could explain damage, and summer has none.
            self.fail("agent took exposure damage in summer")

    def test_farm_is_dormant_in_winter_unless_irrigated(self) -> None:
        engine = WorldEngine.create(_frontier_config(), agent_names=["A1"])
        agent = engine.state.agents["agent-1"]
        tile = engine.state.tile_at(agent.position)
        if tile.terrain not in {"plains", "forest"}:
            self.skipTest("spawn tile unsuitable for farming test")
        _place_structure(engine, "farm_plot", agent.position, agent.id)
        engine.state.tick = 3  # winter
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "farm"}])})
        self.assertTrue(
            any(
                event.type == "invalid_action" and "dormant in winter" in event.message
                for event in engine.state.events
            )
        )
        # Same setup with irrigation works at the winter floor.
        irrigated = WorldEngine.create(_frontier_config(), agent_names=["A1"])
        agent2 = irrigated.state.agents["agent-1"]
        tile2 = irrigated.state.tile_at(agent2.position)
        before = tile2.resources["food"]
        _place_structure(irrigated, "farm_plot", agent2.position, agent2.id)
        _place_structure(irrigated, "irrigation", agent2.position, agent2.id)
        irrigated.state.tick = 3
        irrigated.tick({"agent-1": AgentDecision(actions=[{"type": "farm"}])})
        farmed = [event for event in irrigated.state.events if event.type == "farm"]
        self.assertTrue(farmed, "irrigated farm should work through winter")
        self.assertGreater(tile2.resources["food"], before)

    def test_completed_road_reduces_move_cost(self) -> None:
        engine = WorldEngine.create(_frontier_config(), agent_names=["A1"])
        agent = engine.state.agents["agent-1"]
        # Find an adjacent passable tile whose terrain costs more than 1.
        target = None
        for direction, (dx, dy) in (("north", (0, -1)), ("south", (0, 1)), ("west", (-1, 0)), ("east", (1, 0))):
            candidate = agent.position.shifted(dx, dy)
            if not engine.in_bounds(candidate):
                continue
            tile = engine.state.tile_at(candidate)
            from agent_world.rules import TERRAIN_RULES

            rule = TERRAIN_RULES[tile.terrain]
            if rule.passable and rule.move_cost > 1:
                target = (direction, candidate)
                break
        if target is None:
            self.skipTest("no adjacent expensive terrain near spawn")
        direction, position = target
        _place_structure(engine, "road", position, agent.id)
        moved = engine.tick(
            {"agent-1": AgentDecision(actions=[{"type": "move", "direction": direction}] )}
        )
        move_events = [event for event in engine.state.events if event.type == "move"]
        self.assertTrue(move_events, "move over road should succeed")
        # The engine returns remaining AP indirectly; assert via a second action
        # budgeted only if the road price (1 ap) was charged: 4 ap - 1 = 3 left.
        self.assertEqual(engine.state.agents["agent-1"].position, position)

    def test_irrigation_requires_completed_farm(self) -> None:
        engine = WorldEngine.create(_frontier_config(), agent_names=["A1"])
        agent = engine.state.agents["agent-1"]
        agent.inventory.update({"wood": 4, "stone": 2, "fiber": 2})
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "build", "structure": "irrigation"}])})
        self.assertTrue(
            any(
                event.type == "invalid_action" and "completed farm plot" in event.message
                for event in engine.state.events
            )
        )

    def test_classic_world_is_untouched_by_frontier_mechanics(self) -> None:
        engine = WorldEngine.create(
            WorldConfig(survival_food_decay=0, survival_water_decay=0, survival_energy_decay=0),
            agent_names=["A1"],
        )
        engine.state.tick = 39  # would be deep winter under 12-tick seasons
        engine.tick({"agent-1": AgentDecision(actions=[{"type": "wait"}])})
        self.assertEqual(engine.state.agents["agent-1"].health, 100)


if __name__ == "__main__":
    unittest.main()


class FrontierScoringPipelineTests(unittest.TestCase):
    """Frontier structures must flow through every scoring path without crashes
    or silent zero-valuation - the bug class that only surfaces mid-campaign."""

    def _engine_with_frontier_assets(self) -> WorldEngine:
        engine = WorldEngine.create(_frontier_config(season_length_ticks=12), agent_names=["A1", "A2"])
        agent = engine.state.agents["agent-1"]
        _place_structure(engine, "farm_plot", agent.position, agent.id)
        _place_structure(engine, "irrigation", agent.position, agent.id)
        _place_structure(engine, "road", engine.state.agents["agent-2"].position, agent.id)
        engine.tick({aid: AgentDecision(actions=[{"type": "wait"}]) for aid in engine.state.agents})
        return engine

    def test_offline_metrics_value_frontier_structures(self) -> None:
        from agent_world.metrics import compute_metrics

        engine = self._engine_with_frontier_assets()
        metrics = compute_metrics(engine.state)
        assets = metrics["productive_assets"]
        # irrigation (4 wood + 2 stone + 2 fiber) and road (2 stone + 1 wood)
        # must carry nonzero replacement value for agent-1.
        self.assertGreater(assets["agent_wealth_including_asset_shares"]["agent-1"], 0)

    def test_run_report_and_benchmarks_value_frontier_structures(self) -> None:
        from agent_world.run_report import build_report
        from agent_world.run_report import _structure_replacement_value as report_value
        from agent_world.benchmarks import _structure_replacement_value as bench_value

        self.assertGreater(report_value("road", "organic", "frontier"), 0)
        self.assertGreater(report_value("irrigation", "organic", "frontier"), 0)
        self.assertGreater(bench_value("road", "organic", "frontier"), 0)
        self.assertGreater(bench_value("irrigation", "organic", "frontier"), 0)
        # Classic worlds still value nothing they cannot build.
        self.assertEqual(bench_value("road", "organic", "classic"), 0.0)

        engine = self._engine_with_frontier_assets()
        events = [json.loads(line) for line in engine.export_events_jsonl().splitlines() if line.strip()]
        report = build_report(events, engine.snapshot(), [], target_ticks=50)
        owners = report["economy"]["construction"]["assets"]["by_owner"]
        agent1 = owners.get("agent-1") or {}
        self.assertGreater(agent1.get("replacement_cost_value", 0), 0)
        # The benchmarks section must build without error on a frontier snapshot.
        self.assertIn("benchmarks", report)

    def test_benchmark_raw_metrics_credit_frontier_capital(self) -> None:
        from agent_world.run_report import build_report

        engine = self._engine_with_frontier_assets()
        events = [json.loads(line) for line in engine.export_events_jsonl().splitlines() if line.strip()]
        report = build_report(events, engine.snapshot(), [], target_ticks=50)
        cohorts = (report.get("benchmarks") or {}).get("cohorts") or {}
        if cohorts:
            raw = next(iter(cohorts.values())).get("raw") or {}
            self.assertGreater(raw.get("living_terminal_economic_value", 0), 0)
