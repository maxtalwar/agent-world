from __future__ import annotations

from collections import Counter
import unittest

from agent_world.maps import STANDARD_MAP_16, render_tiles
from agent_world.models import WorldConfig
from agent_world.world import WorldEngine


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

    def test_non_standard_size_is_rejected_for_now(self) -> None:
        with self.assertRaises(ValueError):
            WorldEngine.create(WorldConfig(width=8, height=8), agent_names=[])


if __name__ == "__main__":
    unittest.main()
