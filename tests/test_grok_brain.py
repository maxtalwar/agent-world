from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_world.grok_brain import (
    GrokBrain,
    _grok_decision_working_directory,
    extract_grok_result,
    parse_grok_model_list,
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
            "text": json.dumps(decision),
            "stopReason": "end_turn",
            "sessionId": "grok-session",
            "requestId": "grok-request",
            "usage": {
                "input_tokens": 200,
                "cache_read_input_tokens": 70,
                "cache_creation_input_tokens": 30,
                "output_tokens": 90,
                "reasoning_tokens": 40,
            },
            "total_cost_usd": 0.005,
            "modelUsage": {"grok-4.6-build": {}},
            "structuredOutput": decision,
        }
    )


class GrokBrainTests(unittest.TestCase):
    def test_preflight_uses_saved_login_and_exact_account_model(self) -> None:
        completed = subprocess.CompletedProcess(
            ["grok", "models"],
            0,
            stdout="Logged in with grok.com\n* grok-4.6 (default)\n- grok-4.5\n",
            stderr="",
        )
        with patch("agent_world.grok_brain.subprocess.run", return_value=completed) as run:
            brain = GrokBrain(executable="grok", model="grok-4.6")
            error = brain.preflight()
        self.assertIsNone(error)
        self.assertEqual(brain.resolved_model, "grok-4.6")
        self.assertEqual(run.call_args.args[0], ["grok", "models"])

    def test_model_list_parser(self) -> None:
        self.assertEqual(
            parse_grok_model_list("* grok-4.6 (default)\n- grok-4.5\n"),
            {"grok-4.6", "grok-4.5"},
        )

    def test_decide_uses_native_schema_and_records_subscription_usage(self) -> None:
        completed = subprocess.CompletedProcess(
            ["grok"], 0, stdout=_successful_stdout("hold position"), stderr=""
        )
        with patch.dict(os.environ, {"XAI_API_KEY": "must-not-leak"}), patch(
            "agent_world.grok_brain.subprocess.run", return_value=completed
        ) as run:
            brain = GrokBrain(
                executable="grok",
                model="grok-4.6",
                reasoning_effort="medium",
            )
            decision = brain.decide({"tick": 2, "self": {"id": "agent-1"}})

        self.assertEqual(decision.actions, [{"type": "wait"}])
        command = run.call_args.args[0]
        self.assertIn("--json-schema", command)
        self.assertEqual(command[command.index("--model") + 1], "grok-4.6")
        self.assertEqual(command[command.index("--reasoning-effort") + 1], "medium")
        self.assertEqual(command[command.index("--max-turns") + 1], "1")
        self.assertIn("--disable-web-search", command)
        self.assertIn("--no-subagents", command)
        self.assertNotIn("XAI_API_KEY", run.call_args.kwargs["env"])
        record = brain.runtime.usage_records()[0]
        self.assertEqual(record["provider"], "grok_cli")
        self.assertEqual(record["response_model"], "grok-4.6-build")
        self.assertEqual(record["billing_mode"], "grok_subscription")
        self.assertEqual(record["api_style"], "grok_single_json_schema")
        self.assertEqual(record["prompt_tokens"], 200)
        self.assertEqual(record["cached_tokens"], 70)
        self.assertEqual(record["reasoning_tokens"], 40)
        self.assertEqual(record["cost"], 0)
        self.assertEqual(record["provider_reported_cost_usd"], 0.005)

    def test_backend_response_label_is_not_reused_as_request_model(self) -> None:
        completed = subprocess.CompletedProcess(
            ["grok"], 0, stdout=_successful_stdout("continue"), stderr=""
        )
        with patch(
            "agent_world.grok_brain.subprocess.run", return_value=completed
        ) as run:
            brain = GrokBrain(executable="grok", model="grok-4.6")
            brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            brain.decide({"tick": 1, "self": {"id": "agent-1"}})

        self.assertEqual(brain.resolved_model, "grok-4.6-build")
        self.assertEqual(len(run.call_args_list), 2)
        for call in run.call_args_list:
            command = call.args[0]
            self.assertEqual(command[command.index("--model") + 1], "grok-4.6")

    def test_usage_balance_exhaustion_opens_quota_circuit(self) -> None:
        detail = (
            'Internal error: { "message": "API error (status 402 Payment Required): '
            'Grok Build usage balance exhausted", "http_status": 402 }'
        )
        completed = subprocess.CompletedProcess(
            ["grok"],
            0,
            stdout=json.dumps({"type": "error", "message": detail}),
            stderr="",
        )
        with patch(
            "agent_world.grok_brain.subprocess.run", return_value=completed
        ) as run:
            brain = GrokBrain(executable="grok", model="grok-4.6")
            first = brain.decide({"tick": 20, "self": {"id": "agent-1"}})
            second = brain.decide({"tick": 20, "self": {"id": "agent-2"}})

        self.assertTrue(first.intent.startswith("Grok quota unavailable:"))
        self.assertEqual(second.intent, first.intent)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(brain.runtime.quota_message(), first.intent)

    def test_malformed_model_output_has_model_attribution(self) -> None:
        result = json.loads(_successful_stdout())
        result.pop("structuredOutput")
        result["text"] = '{"intent":"move"'
        completed = subprocess.CompletedProcess(
            ["grok"], 0, stdout=json.dumps(result), stderr=""
        )
        with patch("agent_world.grok_brain.subprocess.run", return_value=completed):
            brain = GrokBrain(executable="grok")
            decision = brain.decide({"tick": 4, "self": {"id": "agent-1"}})
        self.assertTrue(decision.intent.startswith("Grok model output contract failed:"))
        record = brain.runtime.usage_records()[0]
        self.assertEqual(record["decision_failure_origin"], "model_output")
        self.assertEqual(record["failed_raw_response"], '{"intent":"move"')

    def test_extracts_structured_output_and_resolved_build(self) -> None:
        decision, usage, model = extract_grok_result(
            json.loads(_successful_stdout("observe"))
        )
        self.assertEqual(decision["intent"], "observe")
        self.assertEqual(usage["output_tokens"], 90)
        self.assertEqual(model, "grok-4.6-build")

    def test_stateless_v3_workspace_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as root, patch.dict(
            os.environ, {"AGENT_WORLD_PROVIDER_WORKSPACE_ROOT": root}
        ):
            first = _grok_decision_working_directory("stateless-v3")
            second = _grok_decision_working_directory("stateless-v3")
        self.assertEqual(first, second)
        self.assertTrue(first.endswith("grok-stateless-v3"))

    def test_bounded_sessions_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "only stateless"):
            GrokBrain(executable="grok", conversation_mode="bounded-session-v1")


if __name__ == "__main__":
    unittest.main()
