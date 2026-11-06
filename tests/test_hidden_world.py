import unittest
from dataclasses import fields

from agent_world.agents import NullBrain, SurvivalBrain
from agent_world.hidden_world import active_shock, crop_suitability, regrowth_factor, year_shocks
from agent_world.interface import build_observation, build_static_context
from agent_world.models import WorldConfig
from agent_world.protocols import get_recipe
from agent_world.rules import SEASONS
from agent_world.world import WorldEngine


def engine(seed=11, **overrides):
    defaults = get_recipe("participant-v9").defaults()
    names = {field.name for field in fields(WorldConfig)}
    settings = {key: value for key, value in defaults.items() if key in names} | overrides
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
