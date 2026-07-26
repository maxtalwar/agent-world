from __future__ import annotations

import os
import tempfile
import time
import unittest
from unittest.mock import patch

from agent_world.env import load_dotenv
from agent_world.interface import build_static_context
from agent_world.openai_brain import OpenAIBrain, OpenAIQuotaError, extract_chat_text, extract_output_text


class CapturingBrain(OpenAIBrain):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_style = "responses"  # this mock returns a Responses-API shaped reply
        self.last_payload = None

    def _post_json_with_retries(self, path, payload):
        self.last_payload = payload
        return {"output_text": '{"intent":"wait","actions":[],"messages":[],"memory_updates":[]}'}


class QuotaBrain(OpenAIBrain):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = 0

    def _post_json(self, path, payload):
        self.calls += 1
        raise OpenAIQuotaError("OpenAI quota unavailable: insufficient_quota")


class CapturingChatBrain(OpenAIBrain):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_path = None
        self.last_payload = None

    def _post_json_with_retries(self, path, payload):
        self.last_path = path
        self.last_payload = payload
        return {
            "choices": [{"message": {"content": '{"intent":"ok","actions":[],"messages":[],"memory_updates":[]}'}}],
            "usage": {
                "prompt_tokens": 3000,
                "completion_tokens": 500,
                "cost": 0.0042,
                "prompt_tokens_details": {"cached_tokens": 1800},
                "completion_tokens_details": {"reasoning_tokens": 350},
            },
        }


class MalformedOpenAIBrain(OpenAIBrain):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_style = "responses"

    def _post_json_with_retries(self, path, payload):
        return {
            "output_text": '{"intent":"move"',
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
            },
        }


class OpenAIBrainTests(unittest.TestCase):
    def test_extract_output_text_from_output_text(self) -> None:
        response = {"output_text": '{"intent":"wait","actions":[],"messages":[],"memory_updates":[]}'}
        self.assertIn('"intent"', extract_output_text(response))

    def test_hard_deadline_does_not_wait_for_stuck_worker_shutdown(self) -> None:
        brain = OpenAIBrain(
            api_key="test",
            timeout_seconds=0.01,
            hard_deadline_grace_seconds=0.01,
            min_request_interval_seconds=0,
        )

        with patch.object(brain, "_post_json_blocking", side_effect=lambda *_: time.sleep(0.25)):
            started = time.monotonic()
            with self.assertRaisesRegex(OSError, "hard deadline"):
                brain._post_json("/responses", {})
            elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.15)

    def test_extract_output_text_from_nested_response_content(self) -> None:
        response = {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"intent":"wait","actions":[],"messages":[],"memory_updates":[]}',
                        }
                    ]
                }
            ]
        }
        self.assertIn('"actions"', extract_output_text(response))

    def test_extract_output_text_reports_incomplete_response_details(self) -> None:
        response = {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [],
        }
        with self.assertRaisesRegex(ValueError, "max_output_tokens"):
            extract_output_text(response)

    def test_dotenv_loader_sets_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("AGENT_WORLD_TEST_ENV=loaded\n")
            os.environ.pop("AGENT_WORLD_TEST_ENV", None)
            load_dotenv(path)
            self.assertEqual(os.environ["AGENT_WORLD_TEST_ENV"], "loaded")

    def test_openai_brain_requires_key(self) -> None:
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with self.assertRaises(ValueError):
                OpenAIBrain()
        finally:
            if old_key is not None:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_reasoning_effort_is_sent_in_response_payload(self) -> None:
        brain = CapturingBrain(
            api_key="test-key",
            reasoning_effort="high",
            min_request_interval_seconds=0,
        )
        decision = brain.decide({"tick": 0, "valid_actions": []})

        self.assertEqual(decision.intent, "wait")
        self.assertEqual(brain.last_payload["reasoning"], {"effort": "high"})

    def test_malformed_model_output_is_preserved_with_failure_metadata(self) -> None:
        brain = MalformedOpenAIBrain(
            api_key="test-key",
            min_request_interval_seconds=0,
        )
        decision = brain.decide({"tick": 4, "self": {"id": "agent-1"}})

        self.assertEqual(decision.actions, [{"type": "wait"}])
        self.assertTrue(decision.intent.startswith("OpenAI model output failed:"))
        record = brain.runtime.usage_records()[0]
        self.assertEqual(record["decision_failure_origin"], "model_output")
        self.assertEqual(record["failed_raw_response"], '{"intent":"move"')
        self.assertEqual(len(record["failed_raw_response_sha256"]), 64)

    def test_default_max_output_tokens_allow_medium_reasoning_headroom(self) -> None:
        old_value = os.environ.pop("OPENAI_MAX_OUTPUT_TOKENS", None)
        try:
            brain = CapturingBrain(api_key="test-key", min_request_interval_seconds=0)
            brain.decide({"tick": 0, "valid_actions": []})
            self.assertEqual(brain.last_payload["max_output_tokens"], 5000)
        finally:
            if old_value is not None:
                os.environ["OPENAI_MAX_OUTPUT_TOKENS"] = old_value

    def test_openrouter_base_url_uses_chat_completions(self) -> None:
        brain = CapturingChatBrain(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="z-ai/glm-5.2",
            reasoning_effort="high",
            min_request_interval_seconds=0,
        )
        decision = brain.decide({"tick": 0, "valid_actions": []})

        self.assertEqual(brain.api_style, "chat")
        self.assertEqual(brain.last_path, "/chat/completions")
        self.assertEqual(brain.last_payload["model"], "z-ai/glm-5.2")
        self.assertEqual(brain.last_payload["messages"][0]["role"], "system")
        self.assertEqual(brain.last_payload["messages"][1]["role"], "user")
        self.assertEqual(brain.last_payload["response_format"], {"type": "json_object"})
        self.assertEqual(brain.last_payload["reasoning"], {"effort": "high"})
        self.assertIn("max_tokens", brain.last_payload)
        self.assertNotIn("input", brain.last_payload)
        self.assertEqual(decision.intent, "ok")

    def test_chat_payload_requests_usage_and_records_costs(self) -> None:
        brain = CapturingChatBrain(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="z-ai/glm-5.2",
            min_request_interval_seconds=0,
        )
        brain.decide({"tick": 0, "valid_actions": []})

        self.assertEqual(brain.last_payload["usage"], {"include": True})
        records = brain.runtime.usage_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["prompt_tokens"], 3000)
        self.assertEqual(records[0]["cached_tokens"], 1800)
        self.assertEqual(records[0]["reasoning_tokens"], 350)
        self.assertAlmostEqual(records[0]["cost"], 0.0042)
        self.assertEqual(records[0]["api_style"], "chat")
        self.assertEqual(records[0]["tick"], 0)
        self.assertEqual(len(records[0]["static_prompt_sha256"]), 64)
        self.assertEqual(len(records[0]["request_sha256"]), 64)

    def test_objective_treatments_are_explicit_and_distinct(self) -> None:
        neutral = build_static_context({"objective_mode": "neutral"})
        collective = build_static_context({"objective_mode": "collective"})
        individual = build_static_context({"objective_mode": "individual"})

        self.assertIn("No external score is specified", neutral)
        self.assertIn("all living agents", collective)
        self.assertIn("retained resources", individual)
        self.assertEqual(len({neutral, collective, individual}), 3)

    def test_chat_payload_pins_openrouter_providers_when_configured(self) -> None:
        os.environ["OPENAI_PROVIDER_ORDER"] = "Z.AI, Alibaba"
        try:
            brain = CapturingChatBrain(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1",
                min_request_interval_seconds=0,
            )
            brain.decide({"tick": 0, "valid_actions": []})
            self.assertEqual(brain.last_payload["provider"], {"order": ["Z.AI", "Alibaba"], "allow_fallbacks": True})
        finally:
            del os.environ["OPENAI_PROVIDER_ORDER"]

    def test_extract_chat_text_reads_message_content(self) -> None:
        text = extract_chat_text({"choices": [{"message": {"content": '{"intent":"x"}'}}]})
        self.assertIn('"intent"', text)

    def test_default_base_url_uses_responses_style(self) -> None:
        saved = {key: os.environ.pop(key, None) for key in ("OPENAI_BASE_URL", "LLM_API_STYLE")}
        try:
            brain = OpenAIBrain(api_key="test-key", min_request_interval_seconds=0)
            self.assertEqual(brain.api_style, "responses")
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[key] = value

    def test_insufficient_quota_is_not_retried_and_opens_circuit(self) -> None:
        brain = QuotaBrain(
            api_key="test-key",
            max_retries=4,
            min_request_interval_seconds=0,
        )

        first_decision = brain.decide({"tick": 0, "valid_actions": []})
        second_decision = brain.decide({"tick": 1, "valid_actions": []})

        self.assertEqual(brain.calls, 1)
        self.assertEqual(first_decision.intent, "OpenAI quota unavailable: insufficient_quota")
        self.assertEqual(second_decision.intent, "OpenAI quota unavailable: insufficient_quota")
        self.assertEqual(first_decision.actions, [{"type": "wait"}])


if __name__ == "__main__":
    unittest.main()
