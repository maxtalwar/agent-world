import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from agent_world.leaderboard_models import model_catalog, for_recipe, recipe_label, friendly
from agent_world.leaderboard import board_title
from agent_world.leaderboard_launch import LaunchService, LaunchError
from tests import test_leaderboard_launch


class CatalogTests(unittest.TestCase):
    def test_live_catalog_defaults_and_recipe_effort(self):
        sources = {"x": {"models": [{"brain": "codex", "id": "gpt-5.6-luna-max"},
            {"brain": "claude", "id": "claude-opus-4-6"},
            {"brain": "grok", "id": "grok-4.6"},
            {"brain": "cursor", "id": "gpt-diagnostic"}]}}
        client = Mock()
        client.rpc.return_value = {"data": [{"model": "gpt-6-astra",
            "supportedReasoningEfforts": [{"reasoningEffort": "medium"}]}]}
        response = Mock(stdout="gemini-3.7-flash-low\tGemini 3.7 Flash (Low)\n"
                        "gemini-3.7-flash-medium\tGemini 3.7 Flash (Medium)\n"
                        "gemini-3.1-pro-low\tGemini 3.1 Pro (Low)\n"
                        "claude-opus-4-6-thinking\tClaude Opus 4.6 (Thinking)\n")
        with patch("agent_world.leaderboard_models.shutil.which", return_value="/agy"), \
             patch("agent_world.leaderboard_models.subprocess.run", return_value=response):
            entries, warnings = model_catalog(sources, client)
        self.assertFalse(warnings)
        recipe = {"brains": ["codex", "claude", "antigravity", "grok"],
                  "defaults": {"reasoning_effort": "medium"}}
        models = {m["name"]: m for m in for_recipe(entries, recipe)}
        self.assertEqual(models["GPT-6 Astra"]["brain"], "codex")
        self.assertEqual(models["Gemini 3.7 Flash"]["model"], "gemini-3.7-flash-medium")
        self.assertEqual(models["Gemini 3.7 Flash"]["lab"], "google")
        self.assertEqual(models["Claude Opus 4.6"]["brain"], "claude")
        self.assertNotIn("Gemini 3.1 Pro", models)
        self.assertFalse(any("diagnostic" in m["model"] or "luna-max" in m["model"] for m in entries))
        recipe["brains"] = ["codex"]
        self.assertEqual([m["name"] for m in for_recipe(entries, recipe)], ["GPT-6 Astra"])

    def test_display_alias_preserves_recipe_identity(self):
        self.assertEqual(board_title("participant-v8-revised"), "v8.1")
        self.assertEqual(recipe_label("participant-v8-revised"), "Participant v8.1")
        self.assertEqual(friendly("claude-fable-5"), "Claude Fable 5")
        self.assertEqual(friendly("gpt-6-astra"), "GPT-6 Astra")


class CatalogLaunchTests(unittest.TestCase):
    setUp = test_leaderboard_launch.LaunchTests.setUp
    def test_catalog_selection_resolves_exact_id_on_server(self):
        source = {"id": "recipe@hash", "recipe_id": "participant-v8-revised",
                  "digest": "hash", "source": str(self.root), "commit": "a" * 40,
                  "brains": ["antigravity"], "seeds": [11, 41],
                  "defaults": {"ticks": 60, "agents": 10, "reasoning_effort": "medium"}}
        model = {"key": "antigravity:gemini-3.7-flash", "name": "Gemini 3.7 Flash",
                 "brain": "antigravity", "model": "gemini-3.7-flash",
                 "lab": "google", "efforts": ["medium"],
                 "variants": {"medium": "gemini-3.7-flash-medium"}}
        catalog = {"sources": {source["id"]: source}, "blocker": None, "models": [model]}
        plan = {"launch_commit": source["commit"], "orchestrator_commit": source["commit"]}
        with patch.object(self.service, "catalog", return_value=catalog), \
             patch.object(self.service, "launch_checkout", return_value=self.root), \
             patch("agent_world.leaderboard_launch.subprocess.run", return_value=Mock(stdout=json.dumps(plan))):
            result = self.service.preview({"recipe": source["id"], "model_key": model["key"]})
            self.assertEqual(result["model"], "gemini-3.7-flash-medium")
            self.assertEqual(result["model_name"], "Gemini 3.7 Flash")
            self.assertEqual(result["recipe_title"], "Participant v8.1")
            saved = self.service.get(result["id"])
            config = json.loads(Path(saved["config_path"]).read_text())
            self.assertEqual(config["protocol"], "participant-v8-revised")
            self.assertEqual(config["model"]["brain"], "antigravity")
            self.assertEqual(config["model"]["reasoning_effort"], "medium")
            with self.assertRaises(LaunchError):
                self.service.preview({"recipe": source["id"], "model_key": "made-up"})
            with self.assertRaises(LaunchError):
                self.service.preview({"recipe": source["id"], "model_key": model["key"], "brain": "codex"})


if __name__ == "__main__":
    unittest.main()
