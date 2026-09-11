import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from agent_world.leaderboard_models import model_catalog, for_recipe, recipe_label, friendly
from agent_world.leaderboard import board_title
from agent_world.leaderboard_launch import LaunchService, LaunchError
from tests import test_leaderboard_launch


class CatalogTests(unittest.TestCase):
    def test_unsupported_kimi_devin_is_excluded_from_discovery(self):
        with patch("agent_world.leaderboard_models.command_models", return_value=[
            ("kimi-k2-7", "Kimi K2.7", None), ("kimi-k2-6", "Kimi K2.6", None)]):
            entries, _ = model_catalog({"x": {"brains": ["devin"]}})
        self.assertEqual(entries, [])  # The later user decision disconnects all Devin models.

    def test_live_catalog_defaults_and_recipe_effort(self):
        sources = {"x": {"brains": ["codex", "claude", "antigravity", "muse"],
            "models": [{"brain": "codex", "id": "gpt-5.6-luna-max"},
                       {"brain": "claude", "id": "claude-retired"}]}}
        client = Mock()
        client.rpc.return_value = {"data": [{"model": "gpt-6-astra",
            "supportedReasoningEfforts": [{"reasoningEffort": "medium"}]}]}
        def current(brain, environment):
            return {
                "claude": [("claude-opus-4-6", "Claude Opus 4.6", None),
                           ("claude-fable-5-1", "Claude Fable 5.1", ["medium"])],
                "muse": [("muse-spark-1.3", "Muse Spark 1.3", None)],
                "antigravity": [("gemini-3.7-flash-low", "Gemini 3.7 Flash (Low)", None),
                    ("gemini-3.7-flash-medium", "Gemini 3.7 Flash (Medium)", None),
                    ("gemini-3.1-pro-low", "Gemini 3.1 Pro (Low)", None)]}[brain]
        with patch("agent_world.leaderboard_models.command_models", side_effect=current):
            entries, warnings = model_catalog(sources, client)
        self.assertFalse(any(m["model"] == "claude-retired" for m in entries))
        self.assertFalse(warnings)
        recipe = {"brains": ["codex", "claude", "antigravity", "grok"],
                  "defaults": {"reasoning_effort": "medium"}}
        models = {m["name"]: m for m in for_recipe(entries, recipe)}
        self.assertEqual(models["GPT-6 Astra"]["brain"], "codex")
        self.assertEqual(models["Gemini 3.7 Flash"]["model"], "gemini-3.7-flash-medium")
        self.assertEqual(models["Gemini 3.7 Flash"]["lab"], "google")
        self.assertEqual(models["Claude Opus 4.6"]["brain"], "claude")
        self.assertEqual(models["Claude Fable 5.1"]["brain"], "claude")
        self.assertNotIn("Gemini 3.1 Pro", models)
        self.assertFalse(any("diagnostic" in m["model"] or "luna-max" in m["model"] for m in entries))
        recipe["brains"] = ["codex"]
        self.assertEqual([m["name"] for m in for_recipe(entries, recipe)], ["GPT-6 Astra"])

    def test_disabled_devin_is_not_discovered(self):
        with patch("agent_world.leaderboard_models.command_models") as discovery:
            entries, _ = model_catalog({"x": {"brains": ["devin"]}})
        discovery.assert_not_called()
        self.assertEqual(entries, [])

    def test_same_model_remains_available_per_harness(self):
        entries = [{"key": brain+":claude-opus-5", "model": "claude-opus-5",
                    "name": "Claude Opus 5", "brain": brain, "lab": "anthropic",
                    "efforts": None, "variants": None}
                   for brain in ["claude", "cursor", "devin"]]
        recipe = {"brains": ["claude", "cursor", "devin"],
                  "defaults": {"reasoning_effort": "medium"}}
        self.assertEqual({m["brain"] for m in for_recipe(entries, recipe)}, {"claude", "cursor"})

    def test_failed_connector_does_not_fall_back_to_run_history(self):
        sources = {"x": {"brains": ["claude"], "models": [{"brain": "claude", "id": "claude-fable-5"}]}}
        with patch("agent_world.leaderboard_models.command_models", side_effect=RuntimeError("offline")):
            entries, warnings = model_catalog(sources)
        self.assertEqual(entries, [])
        self.assertIn("catalog unavailable", warnings[0])

    def test_zcode_uses_current_connector_config(self):
        import tempfile
        from agent_world.leaderboard_models import command_models
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / "config.json"
            config.write_text(json.dumps({"provider": {"zai": {"options": {"apiKey": "secret"},
                "models": {"glm-5.3": {"name": "GLM-5.3"}}}}}))
            with patch("agent_world.leaderboard_models.shutil.which", return_value="/bin/zcode-cli"):
                self.assertEqual(command_models("zcode", {"ZCODE_CONFIG_PATH": str(config)}),
                                 [("glm-5.3", "GLM-5.3", ["max"])])

    def test_explicit_claude_versions_require_native_validation(self):
        def catalog(brain, env):
            return [("claude-opus-5", "Claude Opus 5", None)] if brain == "claude" else [
                ("anthropic/claude-opus-4.8", "Anthropic: Claude Opus 4.8", None),
                ("anthropic/claude-opus-9", "Anthropic: Claude Opus 9", None)]
        with patch("agent_world.leaderboard_models.command_models", side_effect=catalog), \
             patch("agent_world.leaderboard_models.claude_explicit_model", side_effect=lambda m,e:m=='claude-opus-4-8'):
            entries, _ = model_catalog({"x": {"brains": ["claude", "openrouter"]}})
        chosen=for_recipe(entries, {"brains": ["claude", "openrouter"], "defaults": {"reasoning_effort": "medium"}})
        self.assertEqual(next(m for m in chosen if m["name"]=='Claude Opus 4.8')["brain"], "claude")
        self.assertFalse(any(m["brain"]=='claude' and m["model"]=='claude-opus-9' for m in entries))

    def test_decision_catalog_rejects_media_and_requires_capabilities(self):
        from agent_world.leaderboard_models import openrouter_decision_model, decision_model_identity
        def model(identifier="google/gemini-2.5-pro", inputs=None, outputs=None):
            return {"id": identifier, "architecture": {"input_modalities": inputs or ["text", "image", "audio"],
                    "output_modalities": outputs or ["text"]}}
        self.assertTrue(openrouter_decision_model(model()))
        self.assertTrue(openrouter_decision_model(model("qwen/qwen-vl")))
        self.assertFalse(openrouter_decision_model(model(outputs=["text", "image"])))
        self.assertFalse(openrouter_decision_model(model(outputs=["text", "audio"])))
        self.assertFalse(openrouter_decision_model(model(inputs=["image"])))
        self.assertFalse(openrouter_decision_model({"id": "unknown"}))
        self.assertFalse(openrouter_decision_model(model("google/gemini-pro:batch")))
        for identifier in ["google/gemini-3-pro-image", "google/gemini-3.1-flash-lite-image",
                           "openai/gpt-image-1", "black-forest-labs/flux-2", "text-embedding-3"]:
            self.assertFalse(openrouter_decision_model(model(identifier)), identifier)
            self.assertFalse(decision_model_identity(identifier), identifier)
        self.assertFalse(decision_model_identity("opaque-id", "Google: Nano Banana Pro"))

    def test_muse_picker_exposes_only_standard_tier(self):
        entries = [{"key": "muse:"+model, "model": model, "name": friendly(model),
                    "brain": "muse", "lab": "meta", "efforts": None, "variants": None}
                   for model in ["muse-spark-1.3", "muse-spark-1.3-contributor"]]
        recipe = {"brains": ["muse"], "defaults": {"reasoning_effort": "medium"}}
        models = for_recipe(entries, recipe)
        self.assertEqual([m["name"] for m in models], ["Muse Spark 1.3"])
        self.assertEqual(models[0]["model"], "muse-spark-1.3")
        self.assertEqual(for_recipe(entries[1:], recipe), [])

    def test_zcode_requires_matching_recipe_effort(self):
        entry={"key":"zcode:glm-4.7","model":"glm-4.7","name":"GLM-4.7",
               "brain":"zcode","lab":"zai","efforts":["max"],"variants":None}
        recipe={"brains":["zcode"],"defaults":{"reasoning_effort":"medium"}}
        self.assertEqual(for_recipe([entry],recipe),[])
        recipe["defaults"]["reasoning_effort"]="max"
        self.assertEqual(for_recipe([entry],recipe)[0]["model"],"glm-4.7")

    def test_display_alias_preserves_recipe_identity(self):
        self.assertEqual(board_title("participant-v8-revised"), "v8.1")
        self.assertEqual(recipe_label("participant-v8-revised"), "Participant v8.1")
        self.assertEqual(friendly("claude-fable-5"), "Claude Fable 5")
        self.assertEqual(friendly("gpt-6-astra"), "GPT-6 Astra")


class CatalogLaunchTests(unittest.TestCase):
    setUp = test_leaderboard_launch.LaunchTests.setUp
    def test_forced_options_refresh_does_not_repeat_provider_discovery(self):
        with patch.object(self.service, "sources", return_value={}), \
             patch("agent_world.leaderboard_launch.model_catalog", return_value=([], [])) as discover:
            self.service.catalog()
            self.service.catalog(force=True)
            other = LaunchService(self.root, settings=self.service.settings)
            with patch.object(other, "sources", return_value={}):
                other.catalog()
        discover.assert_called_once()

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
