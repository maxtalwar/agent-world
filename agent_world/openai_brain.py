"""OpenAI-backed agent brain.

This module uses the Responses API directly through the standard library so
the simulation has no required runtime dependencies beyond Python.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import json
import os
from pathlib import Path
import re
import ssl
import threading
import time
from typing import Any
from urllib import error, request

from agent_world.interface import build_dynamic_observation, build_static_context, parse_agent_response
from agent_world.models import AgentDecision


AGENT_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["intent", "actions", "messages", "memory_updates"],
    "properties": {
        "intent": {
            "type": "string",
            "description": "A short reason for the choices this tick.",
            "maxLength": 180,
        },
        "actions": {
            "type": "array",
            "description": "Ordered action objects using valid action schemas from the observation.",
            "maxItems": 4,
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
                    "text": {"type": "string", "maxLength": 240},
                    "to": {"type": "string"},
                },
                "required": ["mode", "text"],
            },
        },
        "memory_updates": {
            "type": "array",
            "description": "Facts the agent chooses to remember.",
            "maxItems": 3,
            "items": {"type": "string", "maxLength": 180},
        },
    },
}


SYSTEM_INSTRUCTIONS = (
    "You are choosing one tick of behavior for a simulated world agent. "
    "Balance immediate survival with longer-term resilience. "
    "Use only valid actions from the observation. Return JSON only. "
    "Keep the JSON concise. Use short strings. "
    "Do not describe plans outside the JSON. Do not assume hidden abilities."
)


class OpenAIBrain:
    """AgentBrain implementation that calls an OpenAI-compatible API for each decision.

    Two request styles are supported:
      - "responses": OpenAI's Responses API (``/responses``), the default for api.openai.com.
      - "chat": the standard Chat Completions API (``/chat/completions``), used by OpenRouter
        and most other providers. Auto-selected when the base URL points at OpenRouter, or
        forced with the ``LLM_API_STYLE`` environment variable / ``api_style`` argument.
    """

    _rate_lock = threading.Lock()
    _next_allowed_at = 0.0
    _quota_unavailable_message: str | None = None
    _usage_records: list[dict[str, Any]] = []

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        max_retries: int | None = None,
        min_request_interval_seconds: float | None = None,
        api_style: str | None = None,
    ):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_style = (
            api_style
            or os.environ.get("LLM_API_STYLE")
            or ("chat" if "openrouter.ai" in self.base_url else "responses")
        ).strip().lower()
        self.timeout_seconds = timeout_seconds or int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "180"))
        self.max_output_tokens = max_output_tokens or int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "5000"))
        self.reasoning_effort = reasoning_effort or os.environ.get("OPENAI_REASONING_EFFORT", "medium")
        self.max_retries = max_retries if max_retries is not None else int(os.environ.get("OPENAI_MAX_RETRIES", "4"))
        self.min_request_interval_seconds = (
            min_request_interval_seconds
            if min_request_interval_seconds is not None
            else float(os.environ.get("OPENAI_MIN_REQUEST_INTERVAL_SECONDS", "0.75"))
        )
        self.ssl_context = _ssl_context()
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIBrain. Put it in .env or export it.")

    @classmethod
    def reset_runtime_state(cls) -> None:
        with cls._rate_lock:
            cls._next_allowed_at = 0.0
            cls._quota_unavailable_message = None
            cls._usage_records = []

    @classmethod
    def usage_records(cls) -> list[dict[str, Any]]:
        """Per-call usage/cost records (OpenRouter returns these when usage.include is set)."""
        with cls._rate_lock:
            return list(cls._usage_records)

    def _record_usage(self, response: dict[str, Any]) -> None:
        usage = response.get("usage")
        if not isinstance(usage, dict):
            return
        prompt_details = usage.get("prompt_tokens_details") or {}
        completion_details = usage.get("completion_tokens_details") or {}
        record = {
            "model": self.model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "cached_tokens": prompt_details.get("cached_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "reasoning_tokens": completion_details.get("reasoning_tokens", 0),
            "cost": usage.get("cost", 0),
            "time": time.time(),
        }
        with self._rate_lock:
            self.__class__._usage_records.append(record)
        # Persist incrementally so an interrupted run (crash, kill, laptop sleep) keeps
        # its cost data; the in-memory list is only summarized at normal run end.
        usage_log = os.environ.get("AGENT_WORLD_USAGE_LOG")
        if usage_log:
            try:
                with open(usage_log, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
            except OSError:
                pass

    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        quota_message = self._quota_message()
        if quota_message is not None:
            return _quota_decision(quota_message)

        # Static rulebook is byte-identical across all agents and ticks of a run, so it
        # rides in the system/instructions slot as a stable prefix (provider prompt caches
        # can reuse it); only the slim dynamic state varies per call.
        static_context = build_static_context(observation.get("world", {}))
        dynamic_json = json.dumps(build_dynamic_observation(observation), separators=(",", ":"), sort_keys=True)
        if self.api_style == "chat":
            endpoint, payload, extractor = "/chat/completions", self._chat_payload(static_context, dynamic_json), extract_chat_text
        else:
            endpoint, payload, extractor = "/responses", self._responses_payload(static_context, dynamic_json), extract_output_text
        try:
            response = self._post_json_with_retries(endpoint, payload)
            self._record_usage(response)
            return parse_agent_response(extractor(response))
        except OpenAIQuotaError as exc:
            self._mark_quota_unavailable(str(exc))
            return _quota_decision(str(exc))
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return AgentDecision(
                intent=f"OpenAI decision failed: {exc}",
                actions=[{"type": "wait"}],
                messages=[],
                memory_updates=[],
            )

    def _responses_payload(self, static_context: str, dynamic_json: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "instructions": f"{SYSTEM_INSTRUCTIONS}\n\n{static_context}",
            "input": f"The current observation follows as JSON:\n{dynamic_json}",
            "max_output_tokens": self.max_output_tokens,
            "reasoning": {"effort": self.reasoning_effort},
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

    def _chat_payload(self, static_context: str, dynamic_json: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"{SYSTEM_INSTRUCTIONS}\n\n{static_context}"},
                {"role": "user", "content": f"The current observation follows as JSON:\n{dynamic_json}"},
            ],
            "max_tokens": self.max_output_tokens,
            "response_format": {"type": "json_object"},
            "usage": {"include": True},
        }
        provider_order = [name.strip() for name in os.environ.get("OPENAI_PROVIDER_ORDER", "").split(",") if name.strip()]
        if provider_order and "openrouter.ai" in self.base_url:
            # Pin routing to reliable providers: OpenRouter otherwise load-balances across
            # dozens of hosts, and one degraded host means hung requests and cold caches.
            payload["provider"] = {"order": provider_order, "allow_fallbacks": True}
        if self.reasoning_effort:
            # OpenRouter normalizes this across providers; reasoning-capable models (GLM-5.2)
            # use it, and providers that ignore reasoning simply drop it.
            payload["reasoning"] = {"effort": self.reasoning_effort}
        return payload

    def _post_json_with_retries(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                return self._post_json(path, payload)
            except OpenAIQuotaError:
                raise
            except OpenAIRateLimitError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(exc.retry_after_seconds or min(30.0, 2.0 + attempt * 2.0))
            except ValueError as exc:
                last_error = exc
                break
        if last_error is not None:
            raise last_error
        raise ValueError("OpenAI request failed without an error.")

    def _throttle(self) -> None:
        if self.min_request_interval_seconds <= 0:
            return
        with self._rate_lock:
            now = time.monotonic()
            if now < self._next_allowed_at:
                time.sleep(self._next_allowed_at - now)
            self.__class__._next_allowed_at = time.monotonic() + self.min_request_interval_seconds

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        # urllib's timeout only bounds each socket read; providers that trickle keep-alive
        # bytes during slow generations reset it forever. Run the request in a worker and
        # enforce a hard wall-clock deadline so a stuck request cannot freeze the run.
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="openai-brain-request") as executor:
            future = executor.submit(self._post_json_blocking, path, payload)
            try:
                return future.result(timeout=self.timeout_seconds + 30)
            except FuturesTimeoutError as exc:
                future.cancel()
                raise OSError(
                    f"Request exceeded hard deadline of {self.timeout_seconds + 30}s (provider kept the connection alive without finishing)."
                ) from exc

    def _post_json_blocking(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter.ai" in self.base_url:
            headers["X-Title"] = "Agent World"
            headers["HTTP-Referer"] = "https://github.com/agent-world"
        req = request.Request(f"{self.base_url}{path}", data=body, method="POST", headers=headers)
        try:
            with request.urlopen(req, timeout=self.timeout_seconds, context=self.ssl_context) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 402:
                # OpenRouter returns 402 when the account is out of credits.
                raise OpenAIQuotaError("OpenAI quota unavailable: insufficient_credits") from exc
            if exc.code == 429:
                if _is_insufficient_quota(detail):
                    raise OpenAIQuotaError("OpenAI quota unavailable: insufficient_quota") from exc
                retry_after = _retry_after_seconds(exc, detail)
                raise OpenAIRateLimitError(f"OpenAI API error 429: {detail}", retry_after) from exc
            raise ValueError(f"OpenAI API error {exc.code}: {detail}") from exc

    def _quota_message(self) -> str | None:
        with self._rate_lock:
            return self.__class__._quota_unavailable_message

    def _mark_quota_unavailable(self, message: str) -> None:
        with self._rate_lock:
            self.__class__._quota_unavailable_message = message


class OpenAIRateLimitError(ValueError):
    def __init__(self, message: str, retry_after_seconds: float | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class OpenAIQuotaError(ValueError):
    pass


def _quota_decision(message: str) -> AgentDecision:
    return AgentDecision(
        intent=message,
        actions=[{"type": "wait"}],
        messages=[],
        memory_updates=[],
    )


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
    status = response.get("status")
    incomplete_details = response.get("incomplete_details")
    details = []
    if status:
        details.append(f"status={status}")
    if incomplete_details:
        details.append(f"incomplete_details={incomplete_details}")
    suffix = f" ({'; '.join(details)})" if details else ""
    raise ValueError(f"No text output found in OpenAI response{suffix}.")


def extract_chat_text(response: dict[str, Any]) -> str:
    """Extract the assistant message text from a Chat Completions response (OpenRouter/OpenAI)."""

    if isinstance(response.get("error"), dict):
        raise ValueError(f"API error: {response['error'].get('message', response['error'])}")
    choices = response.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            if text.strip():
                return text
        finish_reason = choices[0].get("finish_reason")
        raise ValueError(f"No content in chat response (finish_reason={finish_reason}).")
    raise ValueError("No choices in chat response.")


def _ssl_context() -> ssl.SSLContext:
    cafile = os.environ.get("SSL_CERT_FILE")
    if cafile and Path(cafile).exists():
        return ssl.create_default_context(cafile=cafile)
    fallback = Path("/etc/ssl/cert.pem")
    if fallback.exists():
        return ssl.create_default_context(cafile=str(fallback))
    return ssl.create_default_context()


def _retry_after_seconds(exc: error.HTTPError, detail: str) -> float | None:
    header = exc.headers.get("retry-after")
    if header:
        try:
            return max(0.0, float(header))
        except ValueError:
            pass
    match = re.search(r"try again in ([0-9.]+)s", detail)
    if match:
        return max(0.0, float(match.group(1)) + 0.25)
    return None


def _is_insufficient_quota(detail: str) -> bool:
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        return "insufficient_quota" in detail
    error_payload = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error_payload, dict):
        return "insufficient_quota" in detail
    return (
        error_payload.get("code") == "insufficient_quota"
        or error_payload.get("type") == "insufficient_quota"
    )
