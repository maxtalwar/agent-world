from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_world.codex_brain import (
    CodexBrain,
    _codex_decision_working_directory,
    normalize_codex_response,
    parse_codex_jsonl,
    summarize_plan_usage,
)


def _successful_stdout(intent: str = "wait") -> str:
    decision = json.dumps(
        {
            "intent": intent,
            "actions": [{"type": "wait", "arguments_json": "{}"}],
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


def _stdout_with_response(response: str) -> str:
    events = [
        {"type": "thread.started", "thread_id": "thread-1"},
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": response},
        },
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
        old_openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        os.environ["CODEX_API_KEY"] = "must-not-leak"
        os.environ["OPENAI_API_KEY"] = "must-not-leak"
        os.environ["OPENROUTER_API_KEY"] = "must-not-leak"
        try:
            with patch("agent_world.codex_brain.run_process", return_value=completed) as run:
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
            if old_openrouter_key is None:
                os.environ.pop("OPENROUTER_API_KEY", None)
            else:
                os.environ["OPENROUTER_API_KEY"] = old_openrouter_key

        self.assertEqual(decision.actions, [{"type": "wait"}])
        command = run.call_args.args[0]
        self.assertIn("--ephemeral", command)
        self.assertIn("--output-schema", command)
        self.assertIn("gpt-5.6-luna", command)
        self.assertEqual(run.call_args.kwargs["env"].get("CODEX_API_KEY"), None)
        self.assertEqual(run.call_args.kwargs["env"].get("OPENAI_API_KEY"), None)
        self.assertEqual(run.call_args.kwargs["env"].get("OPENROUTER_API_KEY"), None)
        records = brain.runtime.usage_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["billing_mode"], "chatgpt_plan")
        self.assertEqual(records[0]["prompt_tokens"], 1200)
        self.assertEqual(records[0]["tick"], 2)
        self.assertEqual(records[0]["cost"], 0)

    def test_malformed_model_output_is_preserved_with_failure_metadata(self) -> None:
        raw_response = json.dumps(
            {
                "intent": "move east",
                "actions": [
                    {"type": "move", "arguments_json": '{"direction":"east"'}
                ],
                "messages": [],
                "memory_updates": [],
            }
        )
        completed = subprocess.CompletedProcess(
            ["codex"],
            0,
            stdout=_stdout_with_response(raw_response),
            stderr="",
        )
        with patch(
            "agent_world.codex_brain.run_process",
            return_value=completed,
        ):
            brain = CodexBrain(executable="codex")
            decision = brain.decide({"tick": 7, "self": {"id": "agent-1"}})

        self.assertEqual(decision.actions, [{"type": "wait"}])
        self.assertTrue(
            decision.intent.startswith("Codex model output contract failed:")
        )
        records = brain.runtime.usage_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["decision_failure_origin"], "model_output")
        self.assertEqual(records[0]["failed_raw_response"], raw_response)
        self.assertEqual(
            records[0]["failed_raw_response_sha256"],
            hashlib.sha256(raw_response.encode("utf-8")).hexdigest(),
        )
        self.assertIn(
            "arguments_json is not valid JSON",
            records[0]["decision_failure_detail"],
        )

    def test_contract_valid_output_rejected_by_adapter_is_harness_failure(self) -> None:
        raw_response = json.dumps(
            {
                "intent": "move east",
                "actions": [
                    {
                        "type": "move",
                        "arguments_json": '{"direction":"east"}',
                    }
                ],
                "messages": [],
                "memory_updates": [],
            }
        )
        completed = subprocess.CompletedProcess(
            ["codex"],
            0,
            stdout=_stdout_with_response(raw_response),
            stderr="",
        )
        with patch(
            "agent_world.codex_brain.run_process",
            return_value=completed,
        ), patch(
            "agent_world.codex_brain.parse_agent_response",
            side_effect=ValueError("adapter regression"),
        ):
            brain = CodexBrain(executable="codex")
            decision = brain.decide({"tick": 7, "self": {"id": "agent-1"}})

        self.assertTrue(decision.intent.startswith("Codex harness failed:"))
        record = brain.runtime.usage_records()[0]
        self.assertEqual(record["decision_failure_origin"], "harness")
        self.assertEqual(record["decision_contract_validation"], "valid")
        self.assertEqual(
            record["decision_failure_class"],
            "adapter_rejected_contract_valid_output",
        )

    def test_payload_extraction_failure_preserves_provider_envelope(self) -> None:
        envelope = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 10,
                        },
                    }
                ),
            ]
        )
        completed = subprocess.CompletedProcess(
            ["codex"],
            0,
            stdout=envelope,
            stderr="",
        )
        with patch(
            "agent_world.codex_brain.run_process",
            return_value=completed,
        ):
            brain = CodexBrain(executable="codex")
            decision = brain.decide({"tick": 7, "self": {"id": "agent-1"}})

        self.assertTrue(decision.intent.startswith("Codex boundary failed:"))
        record = brain.runtime.usage_records()[0]
        self.assertEqual(record["decision_failure_origin"], "ambiguous_boundary")
        self.assertEqual(record["decision_contract_validation"], "not_tested")
        self.assertEqual(record["failed_raw_provider_envelope"], envelope)
        self.assertEqual(record["prompt_tokens"], 100)

    def test_stateless_v2_reuses_workspace_and_disables_irrelevant_skills(self) -> None:
        completed = subprocess.CompletedProcess(
            ["codex"], 0, stdout=_successful_stdout(), stderr=""
        )
        with patch("agent_world.codex_brain._codex_version_text", return_value="codex-cli 0.142.5"), patch(
            "agent_world.codex_brain.run_process", return_value=completed
        ) as run:
            brain = CodexBrain(executable="codex", connector_profile="connector-v2")
            brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            brain.decide({"tick": 1, "self": {"id": "agent-1"}})

        first_command = run.call_args_list[0].args[0]
        self.assertIn("--ephemeral", first_command)
        self.assertTrue(
            any("skills.config=" in value for value in first_command)
        )
        self.assertEqual(
            run.call_args_list[0].kwargs["cwd"],
            run.call_args_list[1].kwargs["cwd"],
        )

    def test_stateless_v2_uses_the_newest_model_compatible_cli(self) -> None:
        with patch(
            "agent_world.codex_brain._resolve_codex_executable",
            return_value="/Applications/ChatGPT.app/Contents/Resources/codex",
        ) as resolve, patch(
            "agent_world.codex_brain._codex_version_text",
            return_value="codex-cli 0.145.0-alpha.30",
        ):
            brain = CodexBrain(connector_profile="connector-v2")

        resolve.assert_called_once_with()
        self.assertEqual(
            brain.executable,
            "/Applications/ChatGPT.app/Contents/Resources/codex",
        )

    def test_stateless_v3_disables_all_irrelevant_harness_features(self) -> None:
        completed = subprocess.CompletedProcess(
            ["codex"], 0, stdout=_successful_stdout(), stderr=""
        )
        with patch(
            "agent_world.codex_brain._codex_version_text",
            return_value="codex-cli 0.145.0-alpha.30",
        ), patch("agent_world.codex_brain.run_process", return_value=completed) as run:
            brain = CodexBrain(executable="codex", connector_profile="connector-v3")
            brain.decide({"tick": 0, "self": {"id": "agent-1"}})

        command = run.call_args.args[0]
        disabled = {
            command[index + 1]
            for index, value in enumerate(command[:-1])
            if value == "--disable"
        }
        self.assertEqual(
            disabled,
            {
                "multi_agent",
                "multi_agent_v2",
                "shell_tool",
                "apps",
                "plugins",
                "plugin_sharing",
                "skill_search",
                "skill_mcp_dependency_install",
                "remote_plugin",
            },
        )
        self.assertTrue(any("skills.config=" in value for value in command))

    def test_stateless_v3_workspace_survives_process_local_cache_reset(self) -> None:
        with tempfile.TemporaryDirectory() as root, patch.dict(
            os.environ,
            {"AGENT_WORLD_PROVIDER_WORKSPACE_ROOT": root},
        ):
            _codex_decision_working_directory.cache_clear()
            first = _codex_decision_working_directory("connector-v3")
            _codex_decision_working_directory.cache_clear()
            second = _codex_decision_working_directory("connector-v3")

        self.assertEqual(first, second)
        self.assertTrue(first.endswith("codex-connector-v3"))

    def test_bounded_session_resumes_with_only_dynamic_context(self) -> None:
        completed = subprocess.CompletedProcess(
            ["codex"], 0, stdout=_successful_stdout(), stderr=""
        )
        with patch("agent_world.codex_brain._codex_version_text", return_value="codex-cli 0.142.5"), patch(
            "agent_world.codex_brain.run_process", return_value=completed
        ) as run:
            brain = CodexBrain(
                executable="codex",
                connector_profile="connector-v2",
                conversation_mode="persistent-conversation-v1",
            )
            brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            brain.decide({"tick": 1, "self": {"id": "agent-1"}})

        first_command = run.call_args_list[0].args[0]
        second_command = run.call_args_list[1].args[0]
        self.assertNotIn("--ephemeral", first_command)
        self.assertNotIn("resume", first_command)
        self.assertIn("resume", second_command)
        self.assertIn("thread-1", second_command)
        self.assertIn("Continue the same simulated agent", run.call_args_list[1].kwargs["input"])
        records = brain.runtime.usage_records()
        self.assertFalse(records[0]["conversation_resumed"])
        self.assertTrue(records[1]["conversation_resumed"])

    def test_quota_failure_opens_circuit(self) -> None:
        completed = subprocess.CompletedProcess(
            ["codex"],
            1,
            stdout="",
            stderr="You have hit your usage limit. Try again later.",
        )
        with patch("agent_world.codex_brain.run_process", return_value=completed) as run:
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
        with patch("agent_world.codex_brain.run_process", return_value=completed) as run:
            brain = CodexBrain(executable="codex")
            first = brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            second = brain.decide({"tick": 1, "self": {"id": "agent-1"}})

        self.assertEqual(run.call_count, 1)
        self.assertTrue(first.intent.startswith("Codex quota unavailable:"))
        self.assertEqual(second.intent, first.intent)

    def test_stream_disconnect_is_retryable_and_does_not_open_circuit(self) -> None:
        completed = subprocess.CompletedProcess(
            ["codex"],
            1,
            stdout="",
            stderr="stream disconnected before completion: error sending request",
        )
        with patch("agent_world.codex_brain.run_process", return_value=completed) as run:
            brain = CodexBrain(executable="codex")
            first = brain.decide({"tick": 0, "self": {"id": "agent-1"}})
            second = brain.decide({"tick": 1, "self": {"id": "agent-1"}})

        self.assertEqual(run.call_count, 2)
        self.assertTrue(first.intent.startswith("Codex provider unavailable:"))
        self.assertEqual(second.intent, first.intent)
        self.assertEqual(
            brain.runtime.provider_event_summary(), {"provider_error": 2}
        )

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
