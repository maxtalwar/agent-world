import unittest
from collections import Counter
from dataclasses import fields

from agent_world.hidden_world import year_shocks
from agent_world.interface import build_observation, build_static_context
from agent_world.models import Position, WorldConfig
from agent_world.protocols import get_recipe
from agent_world.rules import (
    CLOTHING_DURABILITY,
    INVEST_SHOCK_FARM_FLOOR,
    INVEST_TOOL_DURABILITY,
    TOOL_MAX_DURABILITY,
)
from agent_world.world import WorldEngine


def engine(investment_mode="invest-v1", **overrides):
    defaults = get_recipe("participant-v9").defaults()
    names = {field.name for field in fields(WorldConfig)}
    settings = {key: value for key, value in defaults.items() if key in names}
    settings |= {"investment_mode": investment_mode} | overrides
    return WorldEngine.create(WorldConfig(seed=11, **settings), agent_names=["A", "B"])


def first_agent(world):
    return next(iter(world.state.agents.values()))


class InvestmentWorldTests(unittest.TestCase):
    def test_tools_are_proportional_and_durable(self):
        world = engine()
        self.assertEqual(world._invest_tool_bonus("tool", 1), 1)
        self.assertEqual(world._invest_tool_bonus("tool", 6), 3)
        self.assertEqual(world._invest_tool_bonus("advanced_tool", 6), 6)
        self.assertEqual(world._invest_tool_bonus(None, 6), 0)
        self.assertEqual(world._max_durability("tool"), INVEST_TOOL_DURABILITY["tool"])
        self.assertEqual(engine("off")._max_durability("tool"), TOOL_MAX_DURABILITY["tool"])

    def test_farm_fertility_grows_with_use_and_caps(self):
        world = engine()
        plot = type("Plot", (), {"total_uses": 0})()
        self.assertEqual(world._farm_fertility(plot), 0)
        plot.total_uses = 8
        self.assertEqual(world._farm_fertility(plot), 2)
        plot.total_uses = 1000
        self.assertEqual(world._farm_fertility(plot), 4)

    def test_shocks_spare_farms_but_not_wild_food(self):
        drought = year_shocks(11, 10, 0, "seeded-v3")[0]
        invest, plain = engine(), engine("off")
        invest.state.tick = plain.state.tick = drought.start_tick
        self.assertEqual(invest._active_shock_effects()["regen"], plain._active_shock_effects()["regen"])
        self.assertEqual(invest._active_shock_effects()["farm"], INVEST_SHOCK_FARM_FLOOR["drought"])
        self.assertLess(plain._active_shock_effects()["farm"], INVEST_SHOCK_FARM_FLOOR["drought"])

    def test_preserved_food_is_consumable_and_never_spoils(self):
        world = engine()
        agent = first_agent(world)
        agent.inventory = Counter({"preserved_food": 2})
        agent.needs.food = 5
        world._action_consume(agent, {"type": "consume", "item": "preserved_food"}, 3)
        self.assertEqual((agent.inventory["preserved_food"], agent.needs.food), (1, 10))
        world.state.tick = world.state.config.carried_food_spoil_interval
        world._apply_food_spoilage()
        self.assertEqual(agent.inventory["preserved_food"], 1)
        off = engine("off")
        self.assertIsNone(off._consumable_effects("preserved_food"))

    def test_clothing_cuts_exposure_and_wears_out(self):
        world = engine()
        agent = first_agent(world)
        world.state.tick = 31  # first winter tick with 10-tick seasons
        agent.position = Position(8, 10)
        health = agent.health
        agent.inventory = Counter({"clothing": 1, "food": 5, "water": 5})
        agent.needs.food = agent.needs.water = agent.needs.energy = 15
        world._action_equip(agent, {"type": "equip", "item": "clothing"}, 3)
        self.assertEqual(agent.equipment_durability["clothing"], CLOTHING_DURABILITY)
        world._apply_survival()
        winter = world.state.config.winter_exposure_damage
        storm = world.state.config.storm_exposure_damage if world._is_storm() else 0
        expected = max(0, winter + storm - 2 * (1 + bool(storm)))
        self.assertEqual(health - agent.health, expected)
        self.assertEqual(agent.equipment_durability["clothing"], CLOTHING_DURABILITY - 1)

    def test_new_recipes_and_rules_appear_only_when_investing(self):
        invest = build_observation(engine().state, "agent-1")
        off = build_observation(engine("off").state, "agent-1")
        self.assertTrue({"preserved_food", "cloth", "clothing"} <= set(invest["world"]["recipes"]))
        self.assertFalse({"preserved_food", "cloth", "clothing"} & set(off["world"]["recipes"]))
        rules = build_static_context(invest["world"])
        self.assertIn("INVESTMENT:", rules)
        self.assertIn("consume {item=food|water|preserved_food", rules)
        self.assertIn("equip {item=tool|advanced_tool|clothing}", rules)
        self.assertNotIn("INVESTMENT:", build_static_context(off["world"]))

    def test_published_recipes_and_accounting_are_unchanged(self):
        from agent_world.rules import ACCOUNTING_VALUES, RECIPES
        self.assertFalse({"preserved_food", "cloth", "clothing"} & set(RECIPES))
        self.assertFalse({"preserved_food", "cloth", "clothing"} & set(ACCOUNTING_VALUES))


if __name__ == "__main__":
    unittest.main()


class InvestV2Tests(unittest.TestCase):
    def irrigate(self, world, x, y):
        from agent_world.models import Structure
        sid = f"structure-test-{x}-{y}"
        world.state.structures[sid] = Structure(sid, "irrigation", Position(x, y), "agent-1")
        world.state.tiles[y][x].structure_ids.append(sid)

    def test_no_farm_sparing_except_irrigated_drought(self):
        from agent_world.hidden_world import V2
        from agent_world.rules import IRRIGATED_DROUGHT_FARM_FLOOR
        world = engine("invest-v2")
        drought = year_shocks(11, 10, 0, "seeded-v3")[0]
        world.state.tick = drought.start_tick
        self.assertEqual(world._active_shock_effects()["farm"], V2.shock_effects["drought"]["farm"])
        dry = world._hidden_farm_factor(8, 10) / world._soil_factor(8, 10)
        self.irrigate(world, 8, 10)
        wet = world._hidden_farm_factor(8, 10) / world._soil_factor(8, 10)
        self.assertAlmostEqual(dry, V2.shock_effects["drought"]["farm"])
        self.assertAlmostEqual(wet, IRRIGATED_DROUGHT_FARM_FLOOR)
        blight = year_shocks(11, 10, 0, "seeded-v3")[1]
        world.state.tick = blight.start_tick
        self.assertAlmostEqual(world._hidden_farm_factor(8, 10) / world._soil_factor(8, 10),
                               V2.shock_effects["blight"]["farm"])

    def test_irrigation_no_longer_keeps_winter_farms(self):
        self.assertFalse(engine("invest-v2")._irrigation_keeps_winter_farms())
        self.assertTrue(engine("invest-v1")._irrigation_keeps_winter_farms())
        self.assertTrue(engine("off")._irrigation_keeps_winter_farms())

    def test_rules_are_folded_into_existing_lines(self):
        rules = build_static_context(build_observation(engine("invest-v2").state, "agent-1")["world"])
        self.assertNotIn("INVESTMENT:", rules)
        self.assertNotIn("hurt wild plants", rules)
        self.assertNotIn("unless irrigated", rules)
        self.assertNotIn("half rate through winter", rules)
        for text in (
            "winter: wild regrowth is much lower and farms produce nothing",
            "irrigated farms hold up better in droughts",
            "tool: craft from wood+stone+fiber; equip; raises work output by about half",
            "farm_plot: improved plains/forest for reliable food; grows more productive the more it is worked",
            "preserved_food: made from food+wood; never spoils",
            "clothing: made at a workshop from cloth+fiber; equip to cut winter and storm exposure",
        ):
            self.assertIn(text, rules)
