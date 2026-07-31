from __future__ import annotations

import json
import os
import queue
import subprocess
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent_world.brain_boundary import ConversationInvocation
from agent_world.devin_brain import (
    AcpProtocolError,
    AcpTurnResult,
    DevinBrain,
    _AcpClient,
    _subscription_environment,
    build_devin_prompt,
    parse_devin_model_catalog,
    resolve_devin_model,
    run_devin_acp_turn,
)


def _decision_json(
    *,
    intent: str = "wait",
    actions: list[dict] | None = None,
) -> str:
    return json.dumps(
        {
            "intent": intent,
            "actions": actions or [{"type": "wait"}],
            "messages": [],
            "memory_updates": [],
        }
    )


def _turn(
    *,
    response_text: str | None = None,
    session_id: str = "devin-session",
    stop_reason: str = "end_turn",
) -> AcpTurnResult:
    return AcpTurnResult(
        session_id=session_id,
        response_text=response_text or _decision_json(),
        response_model="swe-1-6-fast",
        resolved_reasoning_effort="low",
        stop_reason=stop_reason,
        usage={
            "input_tokens": 120,
            "cache_read_tokens": 20,
            "output_tokens": 30,
            "reasoning_tokens": 8,
            "request_id": "req-1",
            "committed_acu_cost": 0.25,
        },
        agent_info={"name": "affogato", "version": "1.2.3"},
        tool_calls=[],
        transcript=[{"jsonrpc": "2.0", "id": 1, "result": {}}],
    )


class DevinBrainTests(unittest.TestCase):
    def test_preflight_accepts_saved_login_and_account_model(self) -> None:
        status = subprocess.CompletedProcess(
            ["devin", "auth", "status"],
            0,
            stdout="Logged in",
            stderr="",
        )
        models = subprocess.CompletedProcess(
            ["devin", "models", "list", "--format", "json"],
            0,
            stdout=json.dumps(
                {"models": [{"id": "swe-1-6-fast"}, {"alias": "adaptive"}]}
            ),
            stderr="",
        )
        with patch(
            "agent_world.devin_brain.subprocess.run",
            side_effect=[status, models],
        ) as run:
            brain = DevinBrain(executable="devin", model="swe-1-6-fast")
            error = brain.preflight()

        self.assertIsNone(error)
        self.assertEqual(brain.resolved_model, "swe-1-6-fast")
        self.assertEqual(run.call_args_list[0].args[0], ["devin", "auth", "status"])
        self.assertEqual(
            run.call_args_list[1].args[0],
            ["devin", "models", "list", "--format", "json"],
        )

    def test_preflight_rejects_missing_login(self) -> None:
        status = subprocess.CompletedProcess(
            ["devin", "auth", "status"],
            1,
            stdout="Not logged in",
            stderr="",
        )
        with patch("agent_world.devin_brain.subprocess.run", return_value=status):
            error = DevinBrain(executable="devin").preflight()
        self.assertIn("run `devin auth login`", error or "")

    def test_model_catalog_and_resolution_are_account_scoped(self) -> None:
        available = parse_devin_model_catalog(
            {
                "models": [
                    {"model_id": "swe-1-6-fast", "aliases": ["swe"]},
                    {"id": "claude-sonnet-5"},
                ]
            }
        )
        self.assertEqual(
            available,
            {"swe-1-6-fast", "swe", "claude-sonnet-5"},
        )
        self.assertEqual(
            resolve_devin_model("swe-1-6-fast", available),
            "swe-1-6-fast",
        )
        self.assertEqual(resolve_devin_model("adaptive", available), "adaptive")
        self.assertIsNone(resolve_devin_model("not-on-account", available))

    def test_decide_records_acp_provenance_usage_and_strips_provider_keys(self) -> None:
        old_values = {
            key: os.environ.get(key)
            for key in (
                "OPENAI_API_KEY",
                "OPENROUTER_API_KEY",
                "WINDSURF_API_KEY",
                "DEVIN_API_KEY",
            )
        }
        os.environ.update({key: "must-not-leak" for key in old_values})
        expected_response = _decision_json(
            intent="move east",
            actions=[{"type": "move", "direction": "east"}],
        )
        try:
            with patch(
                "agent_world.devin_brain.run_devin_acp_turn",
                return_value=_turn(response_text=expected_response),
            ) as run:
                brain = DevinBrain(
                    executable="/usr/local/bin/devin",
                    model="swe-1-6-fast",
                    reasoning_effort="low",
                )
                decision = brain.decide(
                    {"tick": 2, "self": {"id": "agent-1"}, "world": {}}
                )
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(decision.actions, [{"type": "move", "direction": "east"}])
        command = run.call_args.kwargs["command"]
        self.assertEqual(command[-3:], ["acp", "--model", "swe-1-6-fast"])
        self.assertIn("--agent-config", command)
        for key in old_values:
            self.assertNotIn(key, run.call_args.kwargs["env"])
        self.assertIn("Output JSON schema", run.call_args.kwargs["prompt"])
        record = brain.runtime.usage_records()[0]
        self.assertEqual(record["provider"], "devin_cli")
        self.assertEqual(record["connector_runtime"], "devin_cli")
        self.assertEqual(record["api_style"], "agent_client_protocol")
        self.assertEqual(
            record["billing_mode"], "devin_subscription"
        )
        self.assertEqual(record["response_model"], "swe-1-6-fast")
        self.assertEqual(record["prompt_tokens"], 120)
        self.assertEqual(record["cached_tokens"], 20)
        self.assertEqual(record["reasoning_tokens"], 8)
        self.assertEqual(record["devin_session_id"], "devin-session")
        self.assertEqual(record["raw_response"], expected_response)
        self.assertEqual(record["cost"], 0)

    def test_malformed_model_output_is_preserved_with_failure_metadata(self) -> None:
        raw_response = '{"intent":"move"'
        with patch(
            "agent_world.devin_brain.run_devin_acp_turn",
            return_value=_turn(response_text=raw_response),
        ):
            brain = DevinBrain(executable="devin")
            decision = brain.decide(
                {"tick": 4, "self": {"id": "agent-1"}, "world": {}}
            )

        self.assertEqual(decision.actions, [{"type": "wait"}])
        self.assertTrue(
            decision.intent.startswith("Devin model output contract failed:")
        )
        record = brain.runtime.usage_records()[0]
        self.assertEqual(record["decision_failure_origin"], "model_output")
        self.assertEqual(record["failed_raw_response"], raw_response)
        self.assertEqual(len(record["failed_raw_response_sha256"]), 64)

    def test_timeout_records_failure_and_opens_provider_scope_circuit(self) -> None:
        with patch(
            "agent_world.devin_brain.run_devin_acp_turn",
            side_effect=subprocess.TimeoutExpired(["devin", "acp"], 3),
        ) as run:
            brain = DevinBrain(executable="devin", timeout_seconds=3)
            brain.timeout_retries = 0
            first = brain.decide(
                {"tick": 0, "self": {"id": "agent-1"}, "world": {}}
            )
            second = brain.decide(
                {"tick": 1, "self": {"id": "agent-1"}, "world": {}}
            )

        self.assertEqual(run.call_count, 1)
        self.assertTrue(first.intent.startswith("Devin provider unavailable:"))
        self.assertEqual(first.intent, second.intent)
        record = brain.runtime.usage_records()[0]
        self.assertEqual(record["decision_failure_origin"], "ambiguous_boundary")
        self.assertEqual(record["devin_stop_reason"], "error")

    def test_non_json_acp_stdout_is_a_safe_protocol_failure(self) -> None:
        client = _AcpClient.__new__(_AcpClient)
        client.timeout_seconds = 1
        client.process = SimpleNamespace(args=["devin", "acp"], poll=lambda: None)
        client._events = queue.Queue()
        client._events.put(("stdout", "not-json"))
        client.transcript = []
        client._stderr_lines = []
        client._closed_streams = set()

        with self.assertRaisesRegex(AcpProtocolError, "non-JSON stdout"):
            client._next_message(time.monotonic() + 1)

    def test_tool_call_update_is_rejected_as_a_boundary_failure(self) -> None:
        turn = _turn()
        turn.tool_calls.append(
            {"sessionUpdate": "tool_call", "toolCallId": "forbidden"}
        )
        with patch(
            "agent_world.devin_brain.run_devin_acp_turn",
            return_value=turn,
        ):
            brain = DevinBrain(executable="devin")
            decision = brain.decide(
                {"tick": 0, "self": {"id": "agent-1"}, "world": {}}
            )

        self.assertTrue(decision.intent.startswith("Devin boundary failed:"))
        self.assertEqual(
            brain.runtime.usage_records()[0]["devin_tool_call_count"],
            1,
        )

    def test_quota_and_auth_errors_fail_safely(self) -> None:
        for detail, prefix in (
            ("Usage limit reached", "Devin quota unavailable:"),
            ("Not logged in", "Devin provider unavailable:"),
        ):
            with self.subTest(detail=detail), patch(
                "agent_world.devin_brain.run_devin_acp_turn",
                side_effect=AcpProtocolError(
                    detail,
                    transcript=[{"jsonrpc": "2.0", "error": detail}],
                ),
            ) as run:
                brain = DevinBrain(executable="devin")
                first = brain.decide(
                    {"tick": 0, "self": {"id": "agent-1"}, "world": {}}
                )
                second = brain.decide(
                    {"tick": 1, "self": {"id": "agent-1"}, "world": {}}
                )
                self.assertEqual(run.call_count, 1)
                self.assertTrue(first.intent.startswith(prefix))
                self.assertEqual(first.intent, second.intent)
                self.assertEqual(
                    brain.runtime.usage_records()[0]["decision_failure_origin"],
                    "ambiguous_boundary",
                )

    def test_bounded_session_resumes_with_compact_continuation(self) -> None:
        with patch(
            "agent_world.devin_brain.run_devin_acp_turn",
            side_effect=[_turn(session_id="session-1"), _turn(session_id="session-1")],
        ) as run:
            brain = DevinBrain(
                executable="devin",
                connector_profile="stateless-v2",
                conversation_mode="bounded-session-v1",
            )
            brain.decide({"tick": 0, "self": {"id": "agent-1"}, "world": {}})
            brain.decide({"tick": 1, "self": {"id": "agent-1"}, "world": {}})

        first_invocation = run.call_args_list[0].kwargs["invocation"]
        second_invocation = run.call_args_list[1].kwargs["invocation"]
        self.assertIsNone(first_invocation.resume_session_id)
        self.assertEqual(second_invocation.resume_session_id, "session-1")
        self.assertIn(
            "Continue the same simulated agent",
            run.call_args_list[1].kwargs["prompt"],
        )

    def test_acp_turn_negotiates_session_and_collects_streamed_usage(self) -> None:
        class FakeClient:
            instance: "FakeClient | None" = None

            def __init__(self, **_kwargs):
                self.calls: list[tuple[str, dict]] = []
                self.transcript: list[dict] = []
                self.stderr_text = ""
                FakeClient.instance = self

            def request(self, method: str, params: dict) -> dict:
                self.calls.append((method, params))
                if method == "initialize":
                    return {"agentInfo": {"name": "affogato", "version": "1"}}
                if method == "session/new":
                    return {
                        "sessionId": "session-1",
                        "configOptions": [
                            {"id": "mode", "currentValue": "accept-edits"},
                            {
                                "id": "reasoning_effort",
                                "currentValue": "medium",
                                "options": [
                                    {"value": "low"},
                                    {"value": "high"},
                                ],
                            },
                            {"id": "model", "currentValue": "swe-1-6-fast"},
                        ],
                    }
                if method == "session/set_config_option":
                    return {}
                if method == "session/prompt":
                    self.transcript.extend(
                        [
                            {
                                "method": "session/update",
                                "params": {
                                    "update": {
                                        "sessionUpdate": "agent_message_chunk",
                                        "content": {
                                            "type": "text",
                                            "text": _decision_json(),
                                        },
                                    }
                                },
                            },
                            {
                                "method": "session/update",
                                "params": {
                                    "update": {
                                        "sessionUpdate": "usage_update",
                                        "used": 200,
                                        "size": 1000,
                                        "token_usage": {
                                            "input_tokens": 80,
                                            "output_tokens": 20,
                                        },
                                    }
                                },
                            },
                        ]
                    )
                    return {"stopReason": "end_turn"}
                raise AssertionError(method)

            def close(self) -> None:
                return None

        with patch("agent_world.devin_brain._AcpClient", FakeClient):
            result = run_devin_acp_turn(
                command=["devin", "acp"],
                cwd="/tmp",
                prompt="choose",
                invocation=ConversationInvocation(None, True, 0, 1),
                reasoning_effort="low",
                timeout_seconds=3,
                env={},
            )

        assert FakeClient.instance is not None
        methods = [method for method, _params in FakeClient.instance.calls]
        self.assertEqual(
            methods,
            [
                "initialize",
                "session/new",
                "session/set_config_option",
                "session/set_config_option",
                "session/prompt",
            ],
        )
        mode_call = FakeClient.instance.calls[2][1]
        self.assertEqual(mode_call["value"], "ask")
        effort_call = FakeClient.instance.calls[3][1]
        self.assertEqual(effort_call["value"], "low")
        self.assertEqual(result.response_model, "swe-1-6-fast")
        self.assertEqual(result.usage["input_tokens"], 80)
        self.assertEqual(result.usage["output_tokens"], 20)
        self.assertEqual(result.usage["context_used"], 200)

    def test_environment_and_prompt_are_isolated(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "secret",
                "OPENROUTER_API_KEY": "secret",
                "DEVIN_API_KEY": "secret",
                "PATH": "/usr/bin",
            },
            clear=True,
        ):
            env = _subscription_environment()
        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertEqual(env["NO_COLOR"], "1")
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("OPENROUTER_API_KEY", env)
        self.assertNotIn("DEVIN_API_KEY", env)
        prompt = build_devin_prompt("RULEBOOK", '{"tick":1}')
        self.assertIn("RULEBOOK", prompt)
        self.assertTrue(prompt.endswith('{"tick":1}'))


if __name__ == "__main__":
    unittest.main()
