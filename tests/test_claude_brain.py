from __future__ import annotations

import json
import os
import subprocess
import unittest
from unittest.mock import patch

from agent_world.claude_brain import (
    ClaudeBrain,
    build_claude_prompts,
    extract_claude_result,
)


def _successful_stdout(intent: str = "wait", actions: list[dict] | None = None) -> str:
    return json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": json.dumps(
                {
                    "intent": intent,
                    "actions": actions or [{"type": "wait"}],
                    "messages": [],
                    "memory_updates": [],
                }
            ),
            "structured_output": {
                "intent": intent,
                "actions": actions or [{"type": "wait"}],
                "messages": [],
                "memory_updates": [],
            },
            "usage": {
                "input_tokens": 200,
                "cache_creation_input_tokens": 300,
                "cache_read_input_tokens": 700,
                "output_tokens": 90,
            },
            "modelUsage": {"claude-sonnet-5-20250929": {"inputTokens": 1200, "outputTokens": 90}},
            "total_cost_usd": 0.01,
        }
    )


class ClaudeBrainTests(unittest.TestCase):
    def test_preflight_accepts_saved_plan_login(self) -> None:
        completed = subprocess.CompletedProcess(
            ["claude", "auth", "status"], 0, stdout=json.dumps({"loggedIn": True}), stderr=""
        )
        with patch("agent_world.claude_brain.subprocess.run", return_value=completed) as run:
            error = ClaudeBrain(executable="claude").preflight()

        self.assertIsNone(error)
        self.assertEqual(run.call_args.args[0], ["claude", "auth", "status"])
        self.assertNotIn("ANTHROPIC_API_KEY", run.call_args.kwargs["env"])

    def test_preflight_rejects_missing_plan_login(self) -> None:
        completed = subprocess.CompletedProcess(
            ["claude", "auth", "status"], 1, stdout=json.dumps({"loggedIn": False}), stderr=""
        )
        with patch("agent_world.claude_brain.subprocess.run", return_value=completed):
            error = ClaudeBrain(executable="claude").preflight()

        self.assertIn("Claude Code is not logged in", error or "")

    def test_extract_claude_result_prefers_structured_output(self) -> None:
        decision, usage, response_model = extract_claude_result(json.loads(_successful_stdout("observe")))
        self.assertEqual(decision["intent"], "observe")
        self.assertEqual(usage["cache_read_input_tokens"], 700)
        self.assertEqual(response_model, "claude-sonnet-5-20250929")

    def test_decide_uses_plan_auth_isolated_print_and_records_usage(self) -> None:
        completed = subprocess.CompletedProcess(
            ["claude"], 0, stdout=_successful_stdout(actions=[{"type": "move", "direction": "east"}]), stderr=""
        )
        old_api_key = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = "must-not-leak"
        try:
            with patch("agent_world.claude_brain.subprocess.run", return_value=completed) as run:
                brain = ClaudeBrain(executable="/usr/local/bin/claude", model="claude-sonnet-5", reasoning_effort="low")
                decision = brain.decide({"tick": 2, "self": {"id": "agent-1"}})
        finally:
            if old_api_key is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = old_api_key

        self.assertEqual(decision.actions, [{"type": "move", "direction": "east"}])
        command = run.call_args.args[0]
        self.assertIn("--print", command)
        self.assertIn("--json-schema", command)
        self.assertIn("claude-sonnet-5", command)
        self.assertEqual(command[command.index("--tools") + 1], "")
        self.assertEqual(run.call_args.kwargs["env"].get("ANTHROPIC_API_KEY"), None)
        self.assertEqual(run.call_args.kwargs["env"].get("MAX_THINKING_TOKENS"), "0")
        records = brain.runtime.usage_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["billing_mode"], "claude_plan")
        self.assertEqual(records[0]["prompt_tokens"], 1200)
        self.assertEqual(records[0]["cached_tokens"], 700)
        self.assertEqual(records[0]["tick"], 2)
        self.assertEqual(records[0]["cost"], 0)

    def test_minimal_effort_maps_to_low_for_the_cli(self) -> None:
        completed = subprocess.CompletedProcess(["claude"], 0, stdout=_successful_stdout(), stderr="")
        with patch("agent_world.claude_brain.subprocess.run", return_value=completed) as run:
            brain = ClaudeBrain(executable="claude", reasoning_effort="minimal")
            brain.decide({"tick": 0, "self": {"id": "agent-1"}})
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--effort") + 1], "low")

    def test_quota_failure_opens_circuit(self) -> None:
        completed = subprocess.CompletedProcess(
            ["claude"],
            1,
            stdout="",
            stderr="Claude usage limit reached. Your limit will reset at 3pm.",
        )
        with patch("agent_world.claude_brain.subprocess.run", return_value=completed) as run:
            brain = ClaudeBrain(executable="claude")
            first = brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            second = brain.decide({"tick": 1, "self": {"id": "agent-1"}})

        self.assertEqual(run.call_count, 1)
        self.assertTrue(first.intent.startswith("Claude quota unavailable:"))
        self.assertEqual(second.intent, first.intent)
        self.assertEqual(first.actions, [{"type": "wait"}])

    def test_session_limit_message_opens_circuit(self) -> None:
        completed = subprocess.CompletedProcess(
            ["claude"],
            1,
            stdout="",
            stderr="You've hit your session limit · resets 12:40am (America/New_York)",
        )
        with patch("agent_world.claude_brain.subprocess.run", return_value=completed) as run:
            brain = ClaudeBrain(executable="claude")
            first = brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            second = brain.decide({"tick": 1, "self": {"id": "agent-1"}})

        self.assertEqual(run.call_count, 1)
        self.assertTrue(first.intent.startswith("Claude quota unavailable:"))
        self.assertEqual(second.intent, first.intent)

    def test_auth_failure_opens_circuit(self) -> None:
        completed = subprocess.CompletedProcess(
            ["claude"], 1, stdout="", stderr="Not logged in. Please run /login."
        )
        with patch("agent_world.claude_brain.subprocess.run", return_value=completed) as run:
            brain = ClaudeBrain(executable="claude")
            first = brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            second = brain.decide({"tick": 1, "self": {"id": "agent-1"}})

        self.assertEqual(run.call_count, 1)
        self.assertTrue(first.intent.startswith("Claude provider unavailable:"))
        self.assertEqual(second.intent, first.intent)

    def test_error_result_json_is_reported(self) -> None:
        stdout = json.dumps(
            {
                "type": "result",
                "subtype": "error_during_execution",
                "is_error": True,
                "result": "Something exploded",
                "usage": {},
            }
        )
        completed = subprocess.CompletedProcess(["claude"], 0, stdout=stdout, stderr="")
        with patch("agent_world.claude_brain.subprocess.run", return_value=completed):
            decision = ClaudeBrain(executable="claude").decide({"tick": 0, "self": {"id": "agent-1"}})
        self.assertTrue(decision.intent.startswith("Claude decision failed:"))
        self.assertEqual(decision.actions, [{"type": "wait"}])

    def test_missing_decision_is_reported(self) -> None:
        with self.assertRaisesRegex(ValueError, "no decision"):
            extract_claude_result({"type": "result", "subtype": "success", "usage": {}})

    def test_result_text_fallback_when_structured_output_missing(self) -> None:
        result = {
            "type": "result",
            "subtype": "success",
            "result": json.dumps({"intent": "fallback", "actions": [{"type": "wait"}]}),
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        decision, usage, response_model = extract_claude_result(result)
        self.assertIn("fallback", decision)
        self.assertEqual(usage["output_tokens"], 5)
        self.assertIsNone(response_model)

    def test_system_prompt_is_stable_and_user_prompt_carries_dynamic_state(self) -> None:
        system_a, user_a = build_claude_prompts("RULEBOOK", '{"tick":1}')
        system_b, user_b = build_claude_prompts("RULEBOOK", '{"tick":2}')
        self.assertEqual(system_a, system_b)
        self.assertNotEqual(user_a, user_b)
        self.assertIn("RULEBOOK", system_a)
        self.assertIn('{"tick":2}', user_b)


if __name__ == "__main__":
    unittest.main()
