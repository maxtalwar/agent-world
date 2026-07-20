from __future__ import annotations

import json
import os
import subprocess
import unittest
from unittest.mock import patch

from agent_world.cursor_brain import (
    CursorBrain,
    build_cursor_prompt,
    cursor_model_candidates,
    extract_cursor_result,
    parse_cursor_model_list,
    resolve_cursor_model,
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
            "session_id": "cursor-session",
            "request_id": "cursor-request",
            "usage": {
                "inputTokens": 200,
                "cacheReadTokens": 700,
                "cacheWriteTokens": 300,
                "outputTokens": 90,
            },
        }
    )


class CursorBrainTests(unittest.TestCase):
    def test_preflight_accepts_login_and_resolves_effort_variant(self) -> None:
        status = subprocess.CompletedProcess(["cursor-agent", "status"], 0, stdout="Logged in", stderr="")
        models = subprocess.CompletedProcess(
            ["cursor-agent", "--list-models"],
            0,
            stdout="Available models\ncursor-grok-4.5-low - Cursor Grok 4.5 Low\n",
            stderr="",
        )
        with patch("agent_world.cursor_brain.subprocess.run", side_effect=[status, models]) as run:
            brain = CursorBrain(executable="cursor-agent", model="cursor-grok-4.5", reasoning_effort="low")
            error = brain.preflight()

        self.assertIsNone(error)
        self.assertEqual(brain.resolved_model, "cursor-grok-4.5-low")
        self.assertEqual(run.call_args_list[0].args[0], ["cursor-agent", "status"])
        self.assertEqual(run.call_args_list[1].args[0], ["cursor-agent", "--list-models"])

    def test_preflight_rejects_missing_login(self) -> None:
        completed = subprocess.CompletedProcess(
            ["cursor-agent", "status"], 1, stdout="Not logged in", stderr=""
        )
        with patch("agent_world.cursor_brain.subprocess.run", return_value=completed):
            error = CursorBrain(executable="cursor-agent").preflight()
        self.assertIn("Cursor Agent is not logged in", error or "")

    def test_preflight_rejects_unavailable_model(self) -> None:
        status = subprocess.CompletedProcess(["cursor-agent", "status"], 0, stdout="Logged in", stderr="")
        models = subprocess.CompletedProcess(
            ["cursor-agent", "--list-models"], 0, stdout="auto - Auto\n", stderr=""
        )
        with patch("agent_world.cursor_brain.subprocess.run", side_effect=[status, models]):
            error = CursorBrain(
                executable="cursor-agent", model="cursor-grok-4.5", reasoning_effort="medium"
            ).preflight()
        self.assertIn("not available on this account", error or "")

    def test_model_list_and_resolution_are_account_driven(self) -> None:
        available = parse_cursor_model_list(
            "Available models\ncursor-grok-4.5-low - Grok Low\ncomposer-2.5 - Composer\n"
        )
        self.assertEqual(available, {"cursor-grok-4.5-low", "composer-2.5"})
        self.assertEqual(resolve_cursor_model("cursor-grok-4.5", "low", available), "cursor-grok-4.5-low")
        self.assertEqual(resolve_cursor_model("composer-2.5", "high", available), "composer-2.5")
        self.assertEqual(cursor_model_candidates("gpt-5.6-luna", "minimal")[0], "gpt-5.6-luna-none")

    def test_decide_uses_subscription_auth_read_only_workspace_and_records_usage(self) -> None:
        completed = subprocess.CompletedProcess(
            ["cursor-agent"],
            0,
            stdout=_successful_stdout(actions=[{"type": "move", "direction": "east"}]),
            stderr="",
        )
        old_key = os.environ.get("CURSOR_API_KEY")
        os.environ["CURSOR_API_KEY"] = "must-not-leak"
        try:
            with patch("agent_world.cursor_brain.subprocess.run", return_value=completed) as run:
                brain = CursorBrain(
                    executable="/usr/local/bin/cursor-agent",
                    model="cursor-grok-4.5-low",
                    reasoning_effort="low",
                )
                decision = brain.decide({"tick": 2, "self": {"id": "agent-1"}})
        finally:
            if old_key is None:
                os.environ.pop("CURSOR_API_KEY", None)
            else:
                os.environ["CURSOR_API_KEY"] = old_key

        self.assertEqual(decision.actions, [{"type": "move", "direction": "east"}])
        command = run.call_args.args[0]
        self.assertIn("--print", command)
        self.assertEqual(command[command.index("--mode") + 1], "ask")
        self.assertEqual(command[command.index("--sandbox") + 1], "enabled")
        self.assertEqual(command[command.index("--model") + 1], "cursor-grok-4.5-low")
        self.assertNotIn("CURSOR_API_KEY", run.call_args.kwargs["env"])
        self.assertIn("Output JSON schema", run.call_args.kwargs["input"])
        records = brain.runtime.usage_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["provider"], "cursor_cli")
        self.assertEqual(records[0]["billing_mode"], "cursor_subscription")
        self.assertEqual(records[0]["prompt_tokens"], 1200)
        self.assertEqual(records[0]["cached_tokens"], 700)
        self.assertEqual(records[0]["cursor_session_id"], "cursor-session")
        self.assertEqual(records[0]["cost"], 0)

    def test_extract_cursor_result(self) -> None:
        decision, usage, model = extract_cursor_result(json.loads(_successful_stdout("observe")))
        self.assertIn("observe", decision)
        self.assertEqual(usage["outputTokens"], 90)
        self.assertIsNone(model)

    def test_quota_failure_opens_provider_scope_circuit(self) -> None:
        completed = subprocess.CompletedProcess(
            ["cursor-agent"], 1, stdout="", stderr="Usage limit reached; try again later"
        )
        with patch("agent_world.cursor_brain.subprocess.run", return_value=completed) as run:
            brain = CursorBrain(executable="cursor-agent")
            first = brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            second = brain.decide({"tick": 1, "self": {"id": "agent-1"}})
        self.assertEqual(run.call_count, 1)
        self.assertTrue(first.intent.startswith("Cursor quota unavailable:"))
        self.assertEqual(first.intent, second.intent)

    def test_connection_failure_opens_provider_scope_circuit(self) -> None:
        completed = subprocess.CompletedProcess(
            ["cursor-agent"], 1, stdout="", stderr="Service unavailable: network error"
        )
        with patch("agent_world.cursor_brain.subprocess.run", return_value=completed):
            decision = CursorBrain(executable="cursor-agent").decide(
                {"tick": 0, "self": {"id": "agent-1"}}
            )
        self.assertTrue(decision.intent.startswith("Cursor provider unavailable:"))

    def test_prompt_keeps_dynamic_observation_at_the_boundary(self) -> None:
        first = build_cursor_prompt("RULEBOOK", '{"tick":1}')
        second = build_cursor_prompt("RULEBOOK", '{"tick":2}')
        self.assertNotEqual(first, second)
        self.assertIn("RULEBOOK", first)
        self.assertTrue(second.endswith('{"tick":2}'))


if __name__ == "__main__":
    unittest.main()
