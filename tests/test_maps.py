from __future__ import annotations

from collections import Counter
import unittest

from agent_world.maps import (
    STANDARD_MAP_16,
    STANDARD_MAP_32,
    build_standard_tiles,
    render_tiles,
    specialist_profile,
)
from agent_world.models import Position, WorldConfig
from agent_world.world import WorldEngine


LEGACY_STANDARD_MAP_16_RENDER = """WWFFFFFFFMMMMMMM
WWFFFFFFMMMMMMMM
WFFFFFFFMMMMMMMM
WFFFFFF..MMMMMM.
WFFFFF....MMMM..
WFFFF.....WMMM..
WFFF.....WWWMM..
WFF......WWW....
WF....FF.WW.....
W......M.W......
W...............
W............FFF
WW..........FFFF
WWW.......FFFFFF
WWWW.....FFFFFFF
WWWWW...FFFFFFFF"""


class StandardMapTests(unittest.TestCase):
    def test_standard_world_uses_handcrafted_map(self) -> None:
        engine = WorldEngine.create(WorldConfig(), agent_names=[])
        self.assertEqual(render_tiles(engine.state.tiles), "\n".join(STANDARD_MAP_16))

    def test_standard_map_matches_config_dimensions(self) -> None:
        self.assertEqual(len(STANDARD_MAP_16), 16)
        self.assertTrue(all(len(row) == 16 for row in STANDARD_MAP_16))
        engine = WorldEngine.create(WorldConfig(), agent_names=[])
        self.assertEqual(len(engine.state.tiles), engine.state.config.height)
        self.assertTrue(all(len(row) == engine.state.config.width for row in engine.state.tiles))

    def test_standard_map_32_shape_and_glyphs(self) -> None:
        self.assertEqual(len(STANDARD_MAP_32), 32)
        self.assertTrue(all(len(row) == 32 for row in STANDARD_MAP_32))
        self.assertLessEqual(set("".join(STANDARD_MAP_32)), set(".FMW"))

    def test_standard_map_32_passable_region_is_connected(self) -> None:
        passable = {
            Position(x, y)
            for y, row in enumerate(STANDARD_MAP_32)
            for x, glyph in enumerate(row)
            if glyph != "W"
        }
        frontier = [next(iter(passable))]
        visited: set[Position] = set()
        while frontier:
            position = frontier.pop()
            if position in visited:
                continue
            visited.add(position)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor = position.shifted(dx, dy)
                if neighbor in passable and neighbor not in visited:
                    frontier.append(neighbor)
        self.assertEqual(visited, passable)

    def test_standard_map_32_fords_and_highpass_are_passable(self) -> None:
        landmarks = ((14, 10), (15, 10), (15, 21), (16, 21), (16, 0), (17, 0))
        for x, y in landmarks:
            with self.subTest(position=(x, y)):
                self.assertNotEqual(STANDARD_MAP_32[y][x], "W")

    def test_standard_map_32_barrens_are_marginal(self) -> None:
        for y in range(6, 20):
            for x in range(27, 32):
                with self.subTest(position=(x, y)):
                    self.assertEqual(STANDARD_MAP_32[y][x], ".")

        water = {
            Position(x, y)
            for y, row in enumerate(STANDARD_MAP_32)
            for x, glyph in enumerate(row)
            if glyph == "W"
        }
        barrens_center = Position(29, 12)
        self.assertGreater(min(barrens_center.distance_to(position) for position in water), 10)

    def test_standard_world_has_all_terrain_types(self) -> None:
        engine = WorldEngine.create(WorldConfig(), agent_names=[])
        counts = Counter(tile.terrain for row in engine.state.tiles for tile in row)
        self.assertGreater(counts["plains"], 0)
        self.assertGreater(counts["forest"], 0)
        self.assertGreater(counts["mountain"], 0)
        self.assertGreater(counts["water"], 0)

    def test_standard_world_makes_wild_food_patchy_but_preserves_starting_patch(self) -> None:
        patchy = WorldEngine.create(WorldConfig(seed=4), agent_names=[])
        dense = WorldEngine.create(WorldConfig(seed=4, wild_food_density=1.0), agent_names=[])

        patchy_food_tiles = sum(1 for row in patchy.state.tiles for tile in row if tile.resources.get("food", 0) > 0)
        dense_food_tiles = sum(1 for row in dense.state.tiles for tile in row if tile.resources.get("food", 0) > 0)

        self.assertLess(patchy_food_tiles, dense_food_tiles)
        self.assertGreater(patchy.state.tile_at(patchy._find_spawn_position(0)).resources.get("food", 0), 0)

    def test_non_standard_size_names_both_supported_sizes(self) -> None:
        with self.assertRaisesRegex(ValueError, r"16x16.*32x32"):
            build_standard_tiles(WorldConfig(width=24, height=24))

    def test_shared_oasis_is_rejected_for_32x32_world(self) -> None:
        with self.assertRaisesRegex(ValueError, r"32x32.*dispersed.*shared_oasis"):
            WorldEngine.create(WorldConfig(width=32, height=32, geography_mode="shared_oasis"), agent_names=[])

    def test_standard_map_build_is_deterministic_including_resources(self) -> None:
        config = WorldConfig(width=32, height=32, seed=41, geography_mode="dispersed")
        self.assertEqual(build_standard_tiles(config), build_standard_tiles(config))

    def test_standard_map_16_render_is_byte_identical_to_legacy_map(self) -> None:
        config = WorldConfig(width=16, height=16)
        self.assertEqual(render_tiles(build_standard_tiles(config)), LEGACY_STANDARD_MAP_16_RENDER)

    def test_dispersed_geography_spawns_heterogeneous_specialists(self) -> None:
        config = WorldConfig(seed=4, geography_mode="dispersed", specialization_mode="specialists")
        engine = WorldEngine.create(config, agent_names=["Farmer", "Forester", "Miner", "Fisher", "Artisan"])
        agents = list(engine.state.agents.values())

        self.assertEqual(
            [agent.specialty for agent in agents],
            ["farmer", "forester", "miner", "fisher", "artisan"],
        )
        self.assertEqual(len({agent.position for agent in agents}), 5)
        self.assertGreater(agents[0].position.distance_to(agents[2].position), config.visible_radius)
        self.assertEqual(engine.state.tile_at(agents[1].position).terrain, "forest")
        self.assertEqual(engine.state.tile_at(agents[2].position).terrain, "mountain")
        self.assertGreater(agents[0].aptitudes["farming"], agents[0].aptitudes["mining"])
        self.assertEqual(agents[2].inventory["ore"], 1)
        self.assertGreater(agents[2].need_multipliers["food"], 1.0)

    def test_32x32_specialists_resolve_40_role_appropriate_spawns(self) -> None:
        expected_anchors = (
            Position(20, 15),
            Position(26, 26),
            Position(10, 6),
            Position(4, 14),
            Position(13, 11),
        )
        self.assertEqual(
            tuple(specialist_profile(offset, 32, 32)["anchor"] for offset in range(5)),
            expected_anchors,
        )

        config = WorldConfig(
            width=32,
            height=32,
            seed=4,
            geography_mode="dispersed",
            specialization_mode="specialists",
        )
        engine = WorldEngine.create(config, agent_names=[f"Agent {index + 1}" for index in range(40)])
        agents = list(engine.state.agents.values())
        wanted_terrain = {
            "farmer": "plains",
            "forester": "forest",
            "miner": "mountain",
            "artisan": "plains",
        }

        self.assertEqual(len(agents), 40)
        self.assertEqual(len({agent.position for agent in agents}), 40)
        self.assertEqual(
            Counter(agent.specialty for agent in agents),
            Counter({role: 8 for role in (*wanted_terrain, "fisher")}),
        )
        for agent in agents:
            with self.subTest(agent=agent.id, specialty=agent.specialty):
                if agent.specialty == "fisher":
                    adjacent = (
                        agent.position.shifted(dx, dy)
                        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
                    )
                    self.assertTrue(
                        any(
                            0 <= position.x < config.width
                            and 0 <= position.y < config.height
                            and engine.state.tile_at(position).terrain == "water"
                            for position in adjacent
                        )
                    )
                else:
                    self.assertEqual(engine.state.tile_at(agent.position).terrain, wanted_terrain[agent.specialty])

    def test_dispersed_generalists_have_no_preset_economic_role(self) -> None:
        config = WorldConfig(seed=4, geography_mode="dispersed", specialization_mode="generalists")
        engine = WorldEngine.create(config, agent_names=["A1", "A2", "A3", "A4", "A5"])
        agents = list(engine.state.agents.values())

        self.assertTrue(all(agent.specialty is None for agent in agents))
        self.assertTrue(all(not agent.aptitudes for agent in agents))
        self.assertTrue(all(not agent.need_multipliers for agent in agents))
        self.assertEqual(len({agent.position for agent in agents}), 5)

    def test_world_config_validates_treatment_names(self) -> None:
        with self.assertRaises(ValueError):
            WorldConfig(geography_mode="everywhere")
        with self.assertRaises(ValueError):
            WorldConfig(economy_mode="magic")
        with self.assertRaises(ValueError):
            WorldConfig(objective_mode="undefined")


if __name__ == "__main__":
    unittest.main()
