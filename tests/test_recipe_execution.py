import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from agent_world.models import WorldConfig
from agent_world.world import WorldEngine
from agent_world.interface import build_observation, build_static_context, build_dynamic_observation
from agent_world.protocols import get_recipe
from agent_world.recipe_execution import verify_recipe_execution

ROOT = Path(__file__).resolve().parents[1]

class RecipeExecutionTests(unittest.TestCase):
    def test_historical_v6_replays_original_fifty_tick_outcomes(self):
        fixture = json.loads((ROOT / "tests/fixtures/historical-v6-sol-seed11.json").read_text())
        engine = WorldEngine.create(WorldConfig(**fixture["config"], world_revision="frontier-v6"), agent_names=fixture["names"])
        obs = build_observation(engine.state, "agent-1")
        self.assertNotIn("town_ledger", obs)
        self.assertFalse({"propose_contract", "post_ledger_note", "deliver_contract"} & {a["type"] for a in obs["valid_actions"]})
        self.assertEqual(hashlib.sha256(build_static_context(obs["world"]).encode()).hexdigest(), fixture["static_prompt_sha256"])
        self.assertEqual(hashlib.sha256(json.dumps(build_dynamic_observation(obs), sort_keys=True).encode()).hexdigest(), fixture["initial_dynamic_sha256"])
        for decisions in fixture["decisions"]:
            engine.tick(decisions)
        self.assertEqual(engine.state.tick, 50)
        for id, expected in fixture["expected_agents"].items():
            agent = engine.state.agents[id]
            self.assertEqual({"health": agent.health, "alive": agent.alive, "inventory": dict(agent.inventory), "position": asdict(agent.position)}, expected)

    def test_v61_keeps_the_board_and_delivery_contracts(self):
        defaults = get_recipe("participant-v6-1").defaults()
        config = WorldConfig(**{k: v for k,v in defaults.items() if k in WorldConfig.__dataclass_fields__})
        engine = WorldEngine.create(config, agent_names=["A"])
        obs = build_observation(engine.state, "agent-1")
        self.assertIn("town_ledger", obs)
        self.assertTrue({"propose_contract", "post_ledger_note", "deliver_contract"} <= {a["type"] for a in obs["valid_actions"]})

    def test_execution_lock_rejects_changed_implementation_and_definition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/"agent_world").mkdir()
            source = root/"agent_world/world.py"; source.write_text("original")
            lock = {"files": {"agent_world/world.py": hashlib.sha256(b"original").hexdigest()}, "recipes": {"participant-v6": {"recipe_digest": get_recipe("participant-v6").digest}}}
            path = root/"agent_world/recipe-execution-locks.json"; path.write_text(json.dumps(lock))
            verify_recipe_execution("participant-v6", root)
            source.write_text("added new world feature")
            with self.assertRaisesRegex(ValueError, "implementation changed"):
                verify_recipe_execution("participant-v6", root)
            source.write_text("original"); lock["recipes"]["participant-v6"]["recipe_digest"]="other"
            path.write_text(json.dumps(lock))
            with self.assertRaisesRegex(ValueError, "definition changed"):
                verify_recipe_execution("participant-v6", root)

    def test_registered_recipes_match_reviewed_locks(self):
        from agent_world.protocols import RECIPES
        for recipe in RECIPES:
            verify_recipe_execution(recipe)
