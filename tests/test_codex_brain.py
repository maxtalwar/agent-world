from __future__ import annotations

import json
import os
import subprocess
import unittest
from unittest.mock import patch

from agent_world.codex_brain import (
    CodexBrain,
    normalize_codex_response,
    parse_codex_jsonl,
    summarize_plan_usage,
)


def _successful_stdout(intent: str = "wait") -> str:
    decision = json.dumps(
        {
            "intent": intent,
            "actions": [{"type": "wait"}],
            "messages": [],
            "memory_updates": [],
        }
    )
    events = [
        {"type": "thread.started", "thread_id": "thread-1"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": decision}},
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1200,
                "cached_input_tokens": 800,
                "output_tokens": 90,
                "reasoning_output_tokens": 40,
            },
        },
    ]
    return "\n".join(json.dumps(event) for event in events)


class CodexBrainTests(unittest.TestCase):
    def test_parse_codex_jsonl_extracts_final_message_and_usage(self) -> None:
        message, usage = parse_codex_jsonl(_successful_stdout("observe"))
        self.assertIn('"intent": "observe"', message)
        self.assertEqual(usage["cached_input_tokens"], 800)

    def test_decide_uses_plan_auth_isolated_exec_and_records_usage(self) -> None:
        completed = subprocess.CompletedProcess(["codex"], 0, stdout=_successful_stdout(), stderr="")
        old_api_key = os.environ.get("CODEX_API_KEY")
        old_openai_key = os.environ.get("OPENAI_API_KEY")
        os.environ["CODEX_API_KEY"] = "must-not-leak"
        os.environ["OPENAI_API_KEY"] = "must-not-leak"
        try:
            with patch("agent_world.codex_brain.subprocess.run", return_value=completed) as run:
                brain = CodexBrain(executable="/usr/local/bin/codex", model="gpt-5.6-luna", reasoning_effort="low")
                decision = brain.decide({"tick": 2, "self": {"id": "agent-1"}})
        finally:
            if old_api_key is None:
                os.environ.pop("CODEX_API_KEY", None)
            else:
                os.environ["CODEX_API_KEY"] = old_api_key
            if old_openai_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_openai_key

        self.assertEqual(decision.actions, [{"type": "wait"}])
        command = run.call_args.args[0]
        self.assertIn("--ephemeral", command)
        self.assertIn("--output-schema", command)
        self.assertIn("gpt-5.6-luna", command)
        self.assertEqual(run.call_args.kwargs["env"].get("CODEX_API_KEY"), None)
        self.assertEqual(run.call_args.kwargs["env"].get("OPENAI_API_KEY"), None)
        records = brain.runtime.usage_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["billing_mode"], "chatgpt_plan")
        self.assertEqual(records[0]["prompt_tokens"], 1200)
        self.assertEqual(records[0]["tick"], 2)
        self.assertEqual(records[0]["cost"], 0)

    def test_quota_failure_opens_circuit(self) -> None:
        completed = subprocess.CompletedProcess(
            ["codex"],
            1,
            stdout="",
            stderr="You have hit your usage limit. Try again later.",
        )
        with patch("agent_world.codex_brain.subprocess.run", return_value=completed) as run:
            brain = CodexBrain(executable="codex")
            first = brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            second = brain.decide({"tick": 1, "self": {"id": "agent-1"}})

        self.assertEqual(run.call_count, 1)
        self.assertTrue(first.intent.startswith("Codex quota unavailable:"))
        self.assertEqual(second.intent, first.intent)
        self.assertEqual(first.actions, [{"type": "wait"}])

    def test_rate_limit_message_opens_circuit(self) -> None:
        completed = subprocess.CompletedProcess(
            ["codex"], 1, stdout="", stderr="Rate limit reached. Try again later."
        )
        with patch("agent_world.codex_brain.subprocess.run", return_value=completed) as run:
            brain = CodexBrain(executable="codex")
            first = brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            second = brain.decide({"tick": 1, "self": {"id": "agent-1"}})

        self.assertEqual(run.call_count, 1)
        self.assertTrue(first.intent.startswith("Codex quota unavailable:"))
        self.assertEqual(second.intent, first.intent)

    def test_stream_disconnect_opens_provider_circuit(self) -> None:
        completed = subprocess.CompletedProcess(
            ["codex"],
            1,
            stdout="",
            stderr="stream disconnected before completion: error sending request",
        )
        with patch("agent_world.codex_brain.subprocess.run", return_value=completed) as run:
            brain = CodexBrain(executable="codex")
            first = brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            second = brain.decide({"tick": 1, "self": {"id": "agent-1"}})

        self.assertEqual(run.call_count, 1)
        self.assertTrue(first.intent.startswith("Codex provider unavailable:"))
        self.assertEqual(second.intent, first.intent)

    def test_missing_final_message_is_reported(self) -> None:
        with self.assertRaisesRegex(ValueError, "no final agent message"):
            parse_codex_jsonl(json.dumps({"type": "turn.completed", "usage": {}}))

    def test_strict_action_wrapper_is_normalized_to_flat_actions(self) -> None:
        wrapped = json.dumps(
            {
                "intent": "move",
                "actions": [{"type": "move", "arguments_json": '{"direction":"east"}'}],
                "messages": [{"mode": "say", "text": "Going east", "to": ""}],
                "memory_updates": [],
            }
        )
        normalized = json.loads(normalize_codex_response(wrapped))
        self.assertEqual(normalized["actions"], [{"type": "move", "direction": "east"}])
        self.assertEqual(normalized["messages"], [{"mode": "say", "text": "Going east"}])

    def test_inner_action_json_salvages_trailing_model_text(self) -> None:
        wrapped = json.dumps(
            {
                "intent": "move",
                "actions": [
                    {
                        "type": "move",
                        "arguments_json": '{"direction":"east"} trailing explanation',
                    }
                ],
                "messages": [],
                "memory_updates": [],
            }
        )

        normalized = json.loads(normalize_codex_response(wrapped))

        self.assertEqual(normalized["actions"], [{"type": "move", "direction": "east"}])

    def test_capture_plan_usage_reads_account_rate_limit_snapshot(self) -> None:
        result = {
            "rateLimitsByLimitId": {
                "codex": {
                    "limitId": "codex",
                    "primary": {"usedPercent": 12, "resetsAt": 100},
                }
            }
        }
        with patch("agent_world.codex_brain._read_plan_usage_from_app_server", return_value=result) as read:
            snapshot = CodexBrain(executable="codex").capture_plan_usage()

        self.assertEqual(snapshot["result"]["rateLimitsByLimitId"]["codex"]["primary"]["usedPercent"], 12)
        self.assertEqual(read.call_args.args[0], "codex")
        self.assertEqual(read.call_args.args[1][1]["method"], "account/rateLimits/read")

    def test_plan_usage_summary_tracks_windows_and_credit_drawdown(self) -> None:
        def checkpoint(used: int, balance: str) -> dict:
            return {
                "captured_at_utc": f"t-{used}",
                "result": {
                    "rateLimitsByLimitId": {
                        "codex": {
                            "limitId": "codex",
                            "planType": "prolite",
                            "primary": {
                                "usedPercent": used,
                                "windowDurationMins": 300,
                                "resetsAt": 123,
                            },
                            "secondary": {
                                "usedPercent": 20,
                                "windowDurationMins": 10080,
                                "resetsAt": 456,
                            },
                            "credits": {
                                "hasCredits": True,
                                "unlimited": False,
                                "balance": balance,
                            },
                        }
                    }
                },
            }

        summary = summarize_plan_usage([checkpoint(12, "100.50"), checkpoint(17, "98.25")])
        bucket = summary["buckets"]["codex"]
        self.assertEqual(bucket["primary"]["used_percent_delta"], 5)
        self.assertEqual(bucket["secondary"]["used_percent_delta"], 0)
        self.assertEqual(bucket["credits"]["balance_delta"], "-2.25")


if __name__ == "__main__":
    unittest.main()
