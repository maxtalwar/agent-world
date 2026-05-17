"""OpenAI-backed agent brain.

This module uses the Responses API directly through the standard library so
the simulation has no required runtime dependencies beyond Python.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from agent_world.interface import build_agent_prompt, parse_agent_response
from agent_world.models import AgentDecision


AGENT_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["intent", "actions", "messages", "memory_updates"],
    "properties": {
        "intent": {
            "type": "string",
            "description": "A short reason for the choices this tick.",
        },
        "actions": {
            "type": "array",
            "description": "Ordered action objects using valid action schemas from the observation.",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "type": {"type": "string"},
                },
                "required": ["type"],
            },
        },
        "messages": {
            "type": "array",
            "description": "Optional speech objects. Use mode say, whisper, or broadcast.",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "mode": {"type": "string"},
                    "text": {"type": "string"},
                    "to": {"type": "string"},
                },
                "required": ["mode", "text"],
            },
        },
        "memory_updates": {
            "type": "array",
            "description": "Facts the agent chooses to remember.",
            "items": {"type": "string"},
        },
    },
}


class OpenAIBrain:
    """AgentBrain implementation that calls OpenAI for each decision."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
    ):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.timeout_seconds = timeout_seconds or int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "60"))
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIBrain. Put it in .env or export it.")

    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        prompt = build_agent_prompt(observation)
        payload = {
            "model": self.model,
            "instructions": (
                "You are choosing one tick of behavior for a simulated world agent. "
                "Use only valid actions from the observation. Return JSON only. "
                "Do not describe plans outside the JSON. Do not assume hidden abilities."
            ),
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "agent_decision",
                    "description": "A single simulation tick decision.",
                    "schema": AGENT_DECISION_SCHEMA,
                    "strict": False,
                }
            },
        }
        try:
            response = self._post_json("/responses", payload)
            output_text = extract_output_text(response)
            return parse_agent_response(output_text)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return AgentDecision(
                intent=f"OpenAI decision failed: {exc}",
                actions=[{"type": "wait"}],
                messages=[],
                memory_updates=[],
            )

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ValueError(f"OpenAI API error {exc.code}: {detail}") from exc


def extract_output_text(response: dict[str, Any]) -> str:
    """Extract text from a Responses API response."""

    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    chunks: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if isinstance(content.get("text"), str):
                chunks.append(content["text"])
    if chunks:
        return "".join(chunks)
    raise ValueError("No text output found in OpenAI response.")
