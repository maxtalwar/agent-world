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
