import unittest
from dataclasses import fields

from agent_world.agents import NullBrain, SurvivalBrain
from agent_world.hidden_world import SHOCK_EFFECTS, active_shock, crop_suitability, regrowth_factor, year_shocks
from agent_world.interface import build_observation, build_static_context
from agent_world.models import WorldConfig
from agent_world.protocols import get_recipe
from agent_world.rules import SEASONS
from agent_world.world import WorldEngine


def engine(seed=11, **overrides):
    defaults = get_recipe("participant-v9").defaults()
    names = {field.name for field in fields(WorldConfig)}
    # Older tests describe the first v9 world; newer ones pass their mode.
    settings = {key: value for key, value in defaults.items() if key in names} | {"hidden_world_mode": "seeded-v1"} | overrides
    return WorldEngine.create(WorldConfig(seed=seed, **settings), agent_names=["A", "B", "C"])


def play(world, brain, ticks):
    factors = []
    for _ in range(ticks):
        factors.append((world._hidden_regen_factor(), world._hidden_farm_factor(5, 5),
                        build_observation(world.state, "agent-1")["season"].get("shock")))
        world.tick({agent: brain.decide(build_observation(world.state, agent)) for agent in world.state.agents})
    return factors


class HiddenWorldTests(unittest.TestCase):
    def test_schedule_and_parameters_ignore_agent_actions(self):
        self.assertEqual(play(engine(), NullBrain(), 80), play(engine(), SurvivalBrain(), 80))

    def test_seeds_differ(self):
        self.assertNotEqual(regrowth_factor(11), regrowth_factor(41))
        self.assertNotEqual(year_shocks(11, 10, 0), year_shocks(41, 10, 0))
        area = [(x, y) for x in range(0, 16, 4) for y in range(0, 16, 4)]
        self.assertNotEqual([crop_suitability(11, *p) for p in area], [crop_suitability(41, *p) for p in area])

    def test_every_year_has_each_shock_inside_its_season_window(self):
        for seed in (11, 41, 73):
            for year in (0, 1):
                shocks = {shock.name: shock for shock in year_shocks(seed, 10, year)}
                self.assertEqual(set(shocks), {"drought", "blight", "cold_snap"})
                base = year * 40
                self.assertTrue(base <= shocks["drought"].start_tick and shocks["drought"].end_tick <= base + 20)
                self.assertTrue(base + 20 <= shocks["blight"].start_tick and shocks["blight"].end_tick <= base + 30)
                self.assertTrue(base + 30 <= shocks["cold_snap"].start_tick and shocks["cold_snap"].end_tick <= base + 40)

    def test_shock_is_visible_only_while_active(self):
        shock = year_shocks(11, 10, 0)[0]
        self.assertEqual(active_shock(11, 10, shock.start_tick), shock.name)
        self.assertIsNone(active_shock(11, 10, shock.start_tick - 1) if shock.start_tick else None)
        world = engine()
        world.state.tick = shock.start_tick
        self.assertEqual(build_observation(world.state, "agent-1")["season"]["shock"], shock.name)

    def test_rulebook_names_the_hidden_facts_but_not_their_values(self):
        world = engine()
        context = build_static_context(build_observation(world.state, "agent-1")["world"])
        self.assertIn("crop suitability varies by area", context)
        self.assertNotIn(f"{regrowth_factor(11):.2f}", context)

    def test_off_mode_changes_nothing(self):
        world = engine(hidden_world_mode="off")
        self.assertEqual((world._hidden_regen_factor(), world._hidden_farm_factor(1, 1)), (1.0, 1.0))
        observation = build_observation(world.state, "agent-1")
        self.assertNotIn("crop suitability", build_static_context(observation["world"]))
        world.state.tick = year_shocks(11, 10, 0)[0].start_tick
        self.assertNotIn("shock", build_observation(world.state, "agent-1")["season"])

    def test_ablation_modes_isolate_facts_and_shocks(self):
        shock = year_shocks(11, 10, 0)[0]
        facts, shocks = engine(hidden_world_mode="facts-v1"), engine(hidden_world_mode="shocks-v1")
        facts.state.tick = shocks.state.tick = shock.start_tick
        self.assertEqual(facts._hidden_regen_factor(), regrowth_factor(11))
        self.assertNotIn("shock", build_observation(facts.state, "agent-1")["season"])
        self.assertEqual(shocks._hidden_regen_factor(), SHOCK_EFFECTS[shock.name]["regen"])
        self.assertEqual(build_observation(shocks.state, "agent-1")["season"]["shock"], shock.name)
        facts_rules = build_static_context(build_observation(facts.state, "agent-1")["world"])
        shocks_rules = build_static_context(build_observation(shocks.state, "agent-1")["world"])
        self.assertIn("crop suitability", facts_rules)
        self.assertNotIn("droughts", facts_rules)
        self.assertIn("droughts", shocks_rules)
        self.assertNotIn("crop suitability", shocks_rules)

    def test_seeded_v2_strengthens_shocks_widens_crops_and_drops_the_facts_hint(self):
        from agent_world.hidden_world import V1, V2
        world = engine(hidden_world_mode="seeded-v2")
        rules = build_static_context(build_observation(world.state, "agent-1")["world"])
        self.assertNotIn("crop suitability", rules)
        self.assertNotIn("Learn them", rules)
        self.assertIn("droughts", rules)
        self.assertEqual(V2.crop_levels, (0.4, 1.0, 1.7))
        self.assertLess(V2.shock_effects["drought"]["farm"], V1.shock_effects["drought"]["farm"])
        drought = year_shocks(11, 10, 0, "seeded-v2")[0]
        self.assertGreater(drought.end_tick - drought.start_tick, year_shocks(11, 10, 0)[0].end_tick - year_shocks(11, 10, 0)[0].start_tick)
        world.state.tick = drought.start_tick
        self.assertEqual(world._active_shock_effects(), V2.shock_effects["drought"])
        self.assertEqual(build_observation(world.state, "agent-1")["season"]["shock"], "drought")

    def test_later_schedules_ignore_agent_actions(self):
        for mode in ("seeded-v2", "seeded-v3"):
            with self.subTest(mode=mode):
                self.assertEqual(play(engine(hidden_world_mode=mode), NullBrain(), 80),
                                 play(engine(hidden_world_mode=mode), SurvivalBrain(), 80))

    def test_seeded_v3_has_shocks_and_plain_seasons_but_no_production_differences(self):
        from agent_world.hidden_world import V2
        world = engine(hidden_world_mode="seeded-v3")
        rules = build_static_context(build_observation(world.state, "agent-1")["world"])
        self.assertIn("winter: wild regrowth is much lower", rules)
        self.assertNotIn("wild regrowth x", rules)
        self.assertNotIn("crop suitability", rules)
        self.assertIn("droughts", rules)
        self.assertIn("some land is better for farming than other land", rules)
        self.assertNotIn("x1.7", rules)
        self.assertEqual(world._hidden_regen_factor(), 1.0)
        drought = year_shocks(11, 10, 0, "seeded-v3")[0]
        world.state.tick = drought.start_tick
        self.assertEqual(world._active_shock_effects(), V2.shock_effects["drought"])
        self.assertEqual(build_observation(world.state, "agent-1")["season"]["shock"], "drought")

    def test_soil_follows_the_land_with_seeded_local_variation(self):
        from agent_world.hidden_world import soil_quality
        world = engine(hidden_world_mode="seeded-v3")
        terrains = [[tile.terrain for tile in row] for row in world.state.tiles]
        near = lambda x, y, kind, reach: any(
            terrains[ty][tx] == kind and abs(tx - x) + abs(ty - y) <= reach
            for ty in range(16) for tx in range(16))
        for seed in (11, 41):
            grid = soil_quality(seed, terrains)
            farmland = [(x, y) for y in range(16) for x in range(16) if terrains[y][x] in {"plains", "forest"}]
            wet = [grid[y][x] for x, y in farmland if near(x, y, "water", 2) and not near(x, y, "mountain", 1)]
            rocky = [grid[y][x] for x, y in farmland if near(x, y, "mountain", 1) and not near(x, y, "water", 2)]
            self.assertGreater(sum(wet) / len(wet), sum(rocky) / len(rocky))
            self.assertEqual({grid[y][x] for x, y in farmland}, {0.4, 1.0, 1.7})
        self.assertNotEqual(soil_quality(11, terrains), soil_quality(41, terrains))
        self.assertEqual(soil_quality(11, terrains), soil_quality(11, terrains))

    def test_soil_scales_farm_output_only_in_soil_modes(self):
        rich = engine(hidden_world_mode="seeded-v3")
        grid = [[rich._soil_factor(x, y) for x in range(16)] for y in range(16)]
        x, y = next((x, y) for y in range(16) for x in range(16) if grid[y][x] == 1.7)
        self.assertEqual(rich._hidden_farm_factor(x, y), 1.7)
        self.assertEqual(engine(hidden_world_mode="shocks-v1")._hidden_farm_factor(x, y), 1.0)

    def test_shocks_v3_matches_seeded_v3_shocks_without_soil_or_plain_seasons(self):
        shocks, full = engine(hidden_world_mode="shocks-v3"), engine(hidden_world_mode="seeded-v3")
        self.assertEqual(year_shocks(11, 10, 0, "shocks-v3"), year_shocks(11, 10, 0, "seeded-v3"))
        drought = year_shocks(11, 10, 0, "shocks-v3")[0]
        shocks.state.tick = full.state.tick = drought.start_tick
        self.assertEqual(shocks._active_shock_effects(), full._active_shock_effects())
        self.assertEqual({shocks._hidden_farm_factor(x, y) for x in range(16) for y in range(16)},
                         {full._active_shock_effects()["farm"]})
        rules = build_static_context(build_observation(shocks.state, "agent-1")["world"])
        self.assertIn("droughts", rules)
        self.assertIn("wild regrowth x", rules)
        self.assertNotIn("some land is better for farming", rules)

    def test_shocks_soil_v3_adds_soil_but_keeps_exact_season_numbers(self):
        world, full = engine(hidden_world_mode="shocks-soil-v3"), engine(hidden_world_mode="seeded-v3")
        grid = lambda w: [[w._soil_factor(x, y) for x in range(16)] for y in range(16)]
        self.assertEqual(grid(world), grid(full))
        self.assertEqual(year_shocks(11, 10, 0, "shocks-soil-v3"), year_shocks(11, 10, 0, "seeded-v3"))
        rules = build_static_context(build_observation(world.state, "agent-1")["world"])
        self.assertIn("wild regrowth x", rules)
        self.assertIn("some land is better for farming than other land", rules)
        self.assertIn("droughts", rules)
        x, y = next((x, y) for y in range(16) for x in range(16) if grid(world)[y][x] == 1.7)
        self.assertEqual(world._hidden_farm_factor(x, y), 1.7)

    def test_participant_v9_uses_the_simplified_world(self):
        self.assertEqual(get_recipe("participant-v9").defaults()["hidden_world_mode"], "seeded-v3")

    def test_exposure_damage_and_public_season_factors_are_unchanged(self):
        config = engine().state.config
        self.assertEqual((config.winter_exposure_damage, config.storm_exposure_damage), (3, 4))
        self.assertEqual(SEASONS["winter"]["regen"], 0.15)

    def test_recipe_is_two_winters_at_low_effort(self):
        recipe = get_recipe("participant-v9")
        defaults = recipe.defaults()
        self.assertEqual((defaults["ticks"], defaults["season_length_ticks"], recipe.reasoning_effort), (80, 10, "low"))
        self.assertEqual(defaults["specialization_mode"], "generalists")


if __name__ == "__main__":
    unittest.main()
