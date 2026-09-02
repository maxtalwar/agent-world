from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_world.zcode_brain import (
    ZCodeBrain,
    _zcode_decision_working_directory,
    extract_zcode_result,
)


def _successful_stdout(intent: str = "wait") -> str:
    decision = {
        "intent": intent,
        "actions": [{"type": "wait"}],
        "messages": [],
        "memory_updates": [],
    }
    return json.dumps(
        {
            "sessionId": "zcode-session",
            "traceId": "zcode-trace",
            "turnId": "zcode-turn",
            "response": json.dumps(decision),
            "usage": {
                "inputTokens": 200,
                "cachedInputTokens": 70,
                "outputTokens": 90,
                "reasoningTokens": 40,
            },
            "eventCount": 4,
            "projection": {
                "status": "completed",
                "turnCount": 1,
                "totalTokenCount": 330,
                "contextWindow": 1_000_000,
            },
        }
    )


class ZCodeBrainTests(unittest.TestCase):
    def test_preflight_checks_cli_and_saved_coding_plan(self) -> None:
        completed = subprocess.CompletedProcess(
            ["zcode-cli", "doctor", "--json"],
            0,
            stdout=json.dumps({"status": "ok"}),
            stderr="",
        )
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / "config.json"
            config.write_text(
                json.dumps(
                    {"provider": {"zai": {"options": {"apiKey": "saved-plan-key", "baseURL": "https://coding.example"}, "models": {"glm-5.3": {"name": "GLM-5.3"}}}}}
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"ZCODE_CONFIG_PATH": str(config)}), patch(
                "agent_world.zcode_brain.subprocess.run", return_value=completed
            ) as run:
                brain = ZCodeBrain(executable="zcode-cli")
                error = brain.preflight()
        self.assertIsNone(error)
        self.assertEqual(run.call_args.args[0], ["zcode-cli", "doctor", "--json"])
        self.assertEqual(run.call_args.kwargs["env"]["ZCODE_MODEL"], "zai/glm-5.3")
        self.assertEqual(run.call_args.kwargs["env"]["ZCODE_API_KEY"], "saved-plan-key")
        self.assertEqual(run.call_args.kwargs["env"]["ZCODE_BASE_URL"], "https://coding.example")

    def test_preflight_explains_how_to_sign_in(self) -> None:
        completed = subprocess.CompletedProcess(
            ["zcode-cli"], 0, stdout=json.dumps({"status": "ok"}), stderr=""
        )
        with tempfile.TemporaryDirectory() as root, patch.dict(
            os.environ, {"ZCODE_CONFIG_PATH": str(Path(root) / "missing.json")}
        ), patch("agent_world.zcode_brain.subprocess.run", return_value=completed):
            error = ZCodeBrain(executable="zcode-cli").preflight()
        self.assertIn("zcode-cli login --no-browser", error or "")

    def test_preflight_rejects_stale_model_catalog(self) -> None:
        completed = subprocess.CompletedProcess(
            ["zcode-cli"], 0, stdout=json.dumps({"status": "ok"}), stderr=""
        )
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / "config.json"
            config.write_text(
                json.dumps({
                    "provider": {
                        "zai": {
                            "options": {"apiKey": "saved-plan-key"},
                            "models": {"glm-5.1": {"name": "GLM-5.1"}},
                        }
                    }
                }),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"ZCODE_CONFIG_PATH": str(config)}), patch(
                "agent_world.zcode_brain.subprocess.run", return_value=completed
            ):
                error = ZCodeBrain(executable="zcode-cli").preflight()
        self.assertIn("glm-5.3 is absent", error or "")

    def test_decide_uses_native_model_tool_fence_and_plan_usage(self) -> None:
        completed = subprocess.CompletedProcess(
            ["zcode-cli"], 0, stdout=_successful_stdout("hold position"), stderr=""
        )
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "must-not-leak",
                "ZAI_API_KEY": "must-not-leak",
                "ZCODE_CONFIG_PATH": str(Path(tempfile.gettempdir()) / "missing-zcode-config.json"),
            },
        ), patch(
            "agent_world.zcode_brain.subprocess.run", return_value=completed
        ) as run:
            brain = ZCodeBrain(executable="zcode-cli")
            decision = brain.decide({"tick": 2, "self": {"id": "agent-1"}})

        self.assertEqual(decision.actions, [{"type": "wait"}])
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--output-format") + 1], "json")
        self.assertEqual(command[command.index("--mode") + 1], "plan")
        self.assertIn("--disallowed-tools=", " ".join(command))
        deny_argument = next(
            item for item in command if item.startswith("--disallowed-tools=")
        )
        self.assertIn("WebSearch", deny_argument)
        self.assertNotIn("AskUserQuestion", deny_argument)
        self.assertNotIn("TodoWrite", deny_argument)
        self.assertNotIn("ANTHROPIC_API_KEY", run.call_args.kwargs["env"])
        self.assertNotIn("ZAI_API_KEY", run.call_args.kwargs["env"])
        self.assertNotIn("ZCODE_API_KEY", run.call_args.kwargs["env"])
        self.assertNotIn("ZCODE_BASE_URL", run.call_args.kwargs["env"])
        self.assertEqual(run.call_args.kwargs["env"]["ZCODE_MODEL"], "zai/glm-5.3")
        record = brain.runtime.usage_records()[0]
        self.assertEqual(record["provider"], "zcode_cli")
        self.assertEqual(record["billing_mode"], "zai_coding_plan")
        self.assertEqual(record["api_style"], "zcode_headless_json")
        self.assertEqual(record["prompt_tokens"], 200)
        self.assertEqual(record["cached_tokens"], 70)
        self.assertEqual(record["completion_tokens"], 90)
        self.assertEqual(record["reasoning_tokens"], 40)
        self.assertEqual(record["cost"], 0)
        self.assertEqual(record["zcode_trace_id"], "zcode-trace")

    def test_quota_error_opens_provider_circuit(self) -> None:
        completed = subprocess.CompletedProcess(
            ["zcode-cli"],
            1,
            stdout="",
            stderr="Error: usage limit reached; retry later",
        )
        with patch(
            "agent_world.zcode_brain.subprocess.run", return_value=completed
        ) as run:
            brain = ZCodeBrain(executable="zcode-cli")
            first = brain.decide({"tick": 20, "self": {"id": "agent-1"}})
            second = brain.decide({"tick": 20, "self": {"id": "agent-2"}})
        self.assertTrue(first.intent.startswith("ZCode quota unavailable:"))
        self.assertEqual(second.intent, first.intent)
        self.assertEqual(run.call_count, 1)

    def test_malformed_output_has_model_attribution(self) -> None:
        result = json.loads(_successful_stdout())
        result["response"] = '{"intent":"move"'
        completed = subprocess.CompletedProcess(
            ["zcode-cli"], 0, stdout=json.dumps(result), stderr=""
        )
        with patch("agent_world.zcode_brain.subprocess.run", return_value=completed):
            brain = ZCodeBrain(executable="zcode-cli")
            decision = brain.decide({"tick": 4, "self": {"id": "agent-1"}})
        self.assertTrue(decision.intent.startswith("ZCode model output contract failed:"))
        record = brain.runtime.usage_records()[0]
        self.assertEqual(record["decision_failure_origin"], "model_output")
        self.assertEqual(record["failed_raw_response"], '{"intent":"move"')

    def test_v7_low_effort_is_rejected_instead_of_silently_ignored(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires native max effort"):
            ZCodeBrain(executable="zcode-cli", reasoning_effort="low")

    def test_extract_result_and_stable_workspace(self) -> None:
        response, usage = extract_zcode_result(json.loads(_successful_stdout("observe")))
        self.assertIn('"intent": "observe"', response)
        self.assertEqual(usage["outputTokens"], 90)
        with tempfile.TemporaryDirectory() as root, patch.dict(
            os.environ, {"AGENT_WORLD_PROVIDER_WORKSPACE_ROOT": root}
        ):
            first = _zcode_decision_working_directory("stateless-v3")
            second = _zcode_decision_working_directory("stateless-v3")
        self.assertEqual(first, second)
        self.assertTrue(first.endswith("zcode-stateless-v3"))

    def test_bounded_sessions_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "only stateless"):
            ZCodeBrain(
                executable="zcode-cli", conversation_mode="bounded-session-v1"
            )


if __name__ == "__main__":
    unittest.main()
