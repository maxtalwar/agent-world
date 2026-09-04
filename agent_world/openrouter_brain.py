"""OpenRouter-backed agent brain.

This module uses the Responses API directly through the standard library so
the simulation has no required runtime dependencies beyond Python.
"""

from __future__ import annotations

import json
import hashlib
from http import client as http_client
import os
from pathlib import Path
import re
import ssl
import threading
import socket
import time
from typing import Any
from urllib.parse import urlsplit

from agent_world.brain_runtime import BrainRuntime
from agent_world.decision_failure import (
    ambiguous_boundary_metadata,
    attribute_decision_failure,
    attributed_failure_message,
    serialize_raw,
)
from agent_world.interface import build_dynamic_observation, build_static_context, parse_agent_response
from agent_world.models import AgentDecision
from agent_world.decision_outcome import failure_decision
from agent_world.provider_telemetry import record_provider_attempt


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
    "Pursue the objective stated in the world rulebook while respecting the simulated constraints. "
    "Use only valid actions from the observation. Return JSON only. "
    "Keep the JSON concise. Use short strings. "
    "Do not describe plans outside the JSON. Do not assume hidden abilities."
)


class OpenRouterBrain:
    """AgentBrain implementation that calls OpenRouter for each decision.

    OpenRouter uses the OpenAI-compatible Chat Completions API, but this
    connector is not the route for OpenAI models. GPT models default to
    ``CodexBrain``; callers may still explicitly select OpenRouter.
    """

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
        hard_deadline_grace_seconds: float | None = None,
        runtime: BrainRuntime | None = None,
    ):
        self.runtime = runtime or BrainRuntime()
        self.model = model or os.environ.get("OPENROUTER_MODEL", "z-ai/glm-5.2")
        self.api_key = (
            api_key
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENAI_API_KEY", "")
        )
        self.base_url = (
            base_url
            or os.environ.get("OPENROUTER_BASE_URL")
            or "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.api_style = (api_style or "chat").strip().lower()
        if self.api_style != "chat":
            raise ValueError("OpenRouterBrain supports only the chat API style.")
        self.timeout_seconds = timeout_seconds or int(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "180"))
        self.max_output_tokens = max_output_tokens or int(os.environ.get("OPENROUTER_MAX_OUTPUT_TOKENS", "5000"))
        self.reasoning_effort = reasoning_effort or os.environ.get("OPENROUTER_REASONING_EFFORT", "medium")
        self.max_retries = max_retries if max_retries is not None else int(os.environ.get("OPENROUTER_MAX_RETRIES", "4"))
        self.min_request_interval_seconds = (
            min_request_interval_seconds
            if min_request_interval_seconds is not None
            else float(os.environ.get("OPENROUTER_MIN_REQUEST_INTERVAL_SECONDS", "0.5"))
        )
        self.hard_deadline_grace_seconds = (
            hard_deadline_grace_seconds
            if hard_deadline_grace_seconds is not None
            else float(os.environ.get("OPENROUTER_HARD_DEADLINE_GRACE_SECONDS", "30"))
        )
        self.ssl_context = _ssl_context()
        self._active_request_meta: dict[str, Any] = {}
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required for OpenRouterBrain. "
                "Put it in .env or export it."
            )

    def _record_usage(self, response: dict[str, Any], request_meta: dict[str, Any] | None = None) -> None:
        usage = response.get("usage")
        if not isinstance(usage, dict):
            return
        prompt_details = usage.get("prompt_tokens_details") or {}
        completion_details = usage.get("completion_tokens_details") or {}
        record = {
            "model": self.model,
            "response_model": response.get("model"),
            "provider": response.get("provider"),
            "api_style": self.api_style,
            "base_url": self.base_url,
            "reasoning_effort": self.reasoning_effort,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "cached_tokens": prompt_details.get("cached_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "reasoning_tokens": completion_details.get("reasoning_tokens", 0),
            "cost": usage.get("cost", 0),
            "time": time.time(),
        }
        record.update(request_meta or {})
        self.runtime.record_usage(record)

    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        blocking_failure = self.runtime.blocking_failure()
        if blocking_failure is not None:
            return _quota_decision(blocking_failure[1])

        # Static rulebook is byte-identical across all agents and ticks of a run, so it
        # rides in the system/instructions slot as a stable prefix (provider prompt caches
        # can reuse it); only the slim dynamic state varies per call.
        static_context = build_static_context(observation.get("world", {}))
        dynamic_json = json.dumps(build_dynamic_observation(observation), separators=(",", ":"), sort_keys=True)
        endpoint = "/chat/completions"
        payload = self._chat_payload(static_context, dynamic_json)
        extractor = extract_chat_text
        request_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        request_meta = {
            "agent_id": observation.get("self", {}).get("id"),
            "tick": observation.get("tick"),
            "agent_static_context_chars": len(static_context),
            "agent_dynamic_observation_chars": len(dynamic_json),
            "request_payload_bytes": len(request_bytes),
            "static_prompt_sha256": hashlib.sha256(
                f"{SYSTEM_INSTRUCTIONS}\n\n{static_context}".encode("utf-8")
            ).hexdigest(),
            "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        }
        request_started_at = time.monotonic()

        def timed_request_meta(extra: dict[str, Any] | None = None) -> dict[str, Any]:
            return {
                **request_meta,
                "duration_seconds": round(time.monotonic() - request_started_at, 3),
                **(extra or {}),
            }

        try:
            self._active_request_meta = request_meta
            response = self._post_json_with_retries(endpoint, payload)
            try:
                decision = extractor(response)
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}"
                self._record_usage(
                    response,
                    timed_request_meta(
                        ambiguous_boundary_metadata(
                            serialize_raw(response),
                            detail,
                        )
                    ),
                )
                return failure_decision(
                    message=f"OpenRouter boundary failed: {detail}",
                )

            attribution = attribute_decision_failure(
                decision,
                AGENT_DECISION_SCHEMA,
            )
            if attribution.origin == "model_output":
                adapter_detail = (
                    "Independent contract validation failed: "
                    f"{attribution.contract_validation.detail}"
                )
                self._record_usage(
                    response,
                    timed_request_meta(attribution.usage_metadata(adapter_detail)),
                )
                return failure_decision(
                    message=attributed_failure_message(
                        "OpenRouter",
                        attribution,
                        adapter_detail,
                    ),
                )

            adapter_detail: str | None = None
            try:
                parsed_decision = parse_agent_response(decision)
            except Exception as exc:
                adapter_detail = f"{type(exc).__name__}: {exc}"
                parsed_decision = None
            if (
                parsed_decision is not None
                and parsed_decision.intent.startswith("Invalid JSON response:")
            ):
                adapter_detail = parsed_decision.intent
            if adapter_detail is not None:
                self._record_usage(
                    response,
                    timed_request_meta(attribution.usage_metadata(adapter_detail)),
                )
                return failure_decision(
                    message=attributed_failure_message(
                        "OpenRouter",
                        attribution,
                        adapter_detail,
                    ),
                )
            assert parsed_decision is not None
            self._record_usage(response, timed_request_meta())
            return parsed_decision
        except OpenRouterQuotaError as exc:
            self._mark_quota_unavailable(str(exc))
            return _quota_decision(str(exc))
        except OpenRouterRateLimitError as exc:
            message = f"OpenRouter provider unavailable: {exc}"
            return failure_decision(
                message=message,
            )
        except OSError as exc:
            message = f"OpenRouter provider unavailable: {exc}"
            return failure_decision(
                message=message,
            )
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            detail = f"{type(exc).__name__}: {exc}"
            self.runtime.record_usage(
                {
                    "model": self.model,
                    "response_model": None,
                    "provider": None,
                    "api_style": self.api_style,
                    "base_url": self.base_url,
                    "reasoning_effort": self.reasoning_effort,
                    "prompt_tokens": 0,
                    "cached_tokens": 0,
                    "completion_tokens": 0,
                    "reasoning_tokens": 0,
                    "cost": 0,
                    "time": time.time(),
                    **timed_request_meta(),
                    **ambiguous_boundary_metadata(detail, detail),
                }
            )
            return failure_decision(
                message=f"OpenRouter boundary failed: {detail}",
            )

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
        provider_order = [
            name.strip()
            for name in os.environ.get("OPENROUTER_PROVIDER_ORDER", "").split(",")
            if name.strip()
        ]
        if provider_order and "openrouter.ai" in self.base_url:
            # Pin routing to reliable providers: OpenRouter otherwise load-balances across
            # dozens of hosts, and one degraded host means hung requests and cold caches.
            payload["provider"] = {"order": provider_order, "allow_fallbacks": True}
        if self.reasoning_effort:
            # OpenRouter normalizes this across providers; reasoning-capable models (GLM-5.2)
            # use it, and providers that ignore reasoning simply drop it.
            payload["reasoning"] = {"effort": self.reasoning_effort}
        return payload

    def _post_json_with_retries(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        request_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_meta = request_meta or self._active_request_meta
        last_error: Exception | None = None
        max_attempts = self.max_retries + 1
        for attempt in range(max_attempts):
            self._throttle()
            attempt_started_at = time.monotonic()
            try:
                return self._post_json(path, payload)
            except OpenRouterQuotaError as exc:
                record_provider_attempt(
                    self.runtime,
                    event_type="quota_exhausted",
                    failure_kind="quota",
                    provider="openrouter",
                    model=self.model,
                    response_model=None,
                    billing_mode="api",
                    reasoning_effort=self.reasoning_effort,
                    request_meta=request_meta or {},
                    attempt=attempt + 1,
                    max_attempts=max_attempts,
                    duration_seconds=time.monotonic() - attempt_started_at,
                    detail=str(exc),
                    provider_trace_id=exc.provider_trace_id,
                    http_status=exc.http_status,
                )
                raise
            except OpenRouterRateLimitError as exc:
                last_error = exc
                record_provider_attempt(
                    self.runtime,
                    event_type="rate_limit",
                    failure_kind="rate_limit",
                    provider="openrouter",
                    model=self.model,
                    response_model=None,
                    billing_mode="api",
                    reasoning_effort=self.reasoning_effort,
                    request_meta=request_meta or {},
                    attempt=attempt + 1,
                    max_attempts=max_attempts,
                    duration_seconds=time.monotonic() - attempt_started_at,
                    detail=str(exc),
                    provider_trace_id=exc.provider_trace_id,
                    http_status=exc.http_status,
                    retry_after_seconds=exc.retry_after_seconds,
                )
                if attempt >= self.max_retries:
                    break
                time.sleep(exc.retry_after_seconds or min(30.0, 2.0 + attempt * 2.0))
            except OSError as exc:
                record_provider_attempt(
                    self.runtime,
                    event_type=(
                        "request_timeout"
                        if isinstance(exc, OpenRouterRequestTimeoutError)
                        else "provider_error"
                    ),
                    failure_kind=(
                        "timeout"
                        if isinstance(exc, OpenRouterRequestTimeoutError)
                        else "provider"
                    ),
                    provider="openrouter",
                    model=self.model,
                    response_model=None,
                    billing_mode="api",
                    reasoning_effort=self.reasoning_effort,
                    request_meta=request_meta or {},
                    attempt=attempt + 1,
                    max_attempts=max_attempts,
                    duration_seconds=time.monotonic() - attempt_started_at,
                    detail=str(exc),
                    provider_trace_id=getattr(exc, "provider_trace_id", None),
                    http_status=getattr(exc, "http_status", None),
                )
                raise
            except ValueError as exc:
                last_error = exc
                break
        if last_error is not None:
            raise last_error
        raise ValueError("OpenRouter request failed without an error.")

    def _throttle(self) -> None:
        self.runtime.throttle(self.min_request_interval_seconds)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        hard_deadline_seconds = (
            self.timeout_seconds + self.hard_deadline_grace_seconds
        )
        deadline = time.monotonic() + hard_deadline_seconds
        try:
            return self._post_json_blocking(path, payload, deadline=deadline)
        except TimeoutError as exc:
            if time.monotonic() >= deadline:
                raise OpenRouterHardDeadlineError(
                    f"Request exceeded hard deadline of {hard_deadline_seconds:g}s."
                ) from exc
            raise OpenRouterRequestTimeoutError(f"Request timed out: {exc}") from exc

    def _post_json_blocking(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        deadline: float,
    ) -> dict[str, Any]:
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"Invalid OpenRouter base URL: {self.base_url}")
        target = f"{parsed.path.rstrip('/')}{path}" or "/"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        connection = self._open_connection(parsed, self._remaining_timeout(deadline))
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter.ai" in self.base_url:
            headers["X-Title"] = "Agent World"
            headers["HTTP-Referer"] = "https://github.com/agent-world"
        watchdog = None
        transport_socket = None
        try:
            connection.connect()
            transport_socket = connection.sock
            def expire():
                if transport_socket is not None:
                    try:
                        transport_socket.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
            watchdog = threading.Timer(max(0, deadline - time.monotonic()), expire)
            watchdog.daemon = True
            watchdog.start()
            connection.request(
                "POST",
                target,
                body=json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
                headers=headers,
            )
            self._set_connection_timeout(connection, deadline)
            response = connection.getresponse()
            response_headers = {
                key.lower(): value for key, value in response.getheaders()
            }
            trace_id = _provider_trace_id(response_headers)
            body = self._read_response_body(response, connection, deadline)
            self._remaining_timeout(deadline)
            detail = body.decode("utf-8", errors="replace")
            if 200 <= response.status < 300:
                return json.loads(detail)
            if response.status == 402:
                raise OpenRouterQuotaError(
                    "OpenRouter quota unavailable: insufficient_credits",
                    http_status=response.status,
                    provider_trace_id=trace_id,
                )
            if response.status == 429:
                if _is_insufficient_quota(detail):
                    raise OpenRouterQuotaError(
                        "OpenRouter quota unavailable: insufficient_quota",
                        http_status=response.status,
                        provider_trace_id=trace_id,
                    )
                raise OpenRouterRateLimitError(
                    f"OpenRouter API error 429: {detail}",
                    _retry_after_seconds(response_headers, detail),
                    provider_trace_id=trace_id,
                )
            if response.status >= 500:
                raise OpenRouterProviderError(
                    f"OpenRouter API error {response.status}: {detail}",
                    http_status=response.status,
                    provider_trace_id=trace_id,
                )
            raise ValueError(f"OpenRouter API error {response.status}: {detail}")
        finally:
            if watchdog is not None:
                watchdog.cancel()
                watchdog.join()
            connection.close()

    def _open_connection(
        self, parsed: Any, timeout: float
    ) -> http_client.HTTPConnection:
        port = parsed.port
        if parsed.scheme == "https":
            return http_client.HTTPSConnection(
                parsed.hostname,
                port=port,
                timeout=timeout,
                context=self.ssl_context,
            )
        return http_client.HTTPConnection(parsed.hostname, port=port, timeout=timeout)

    def _remaining_timeout(self, deadline: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OpenRouterHardDeadlineError(
                "Request exceeded its total wall-clock deadline."
            )
        return max(0.001, min(float(self.timeout_seconds), remaining))

    def _set_connection_timeout(
        self, connection: http_client.HTTPConnection, deadline: float
    ) -> None:
        remaining = self._remaining_timeout(deadline)
        if connection.sock is not None:
            connection.sock.settimeout(remaining)

    def _read_response_body(
        self,
        response: http_client.HTTPResponse,
        connection: http_client.HTTPConnection,
        deadline: float,
    ) -> bytes:
        chunks: list[bytes] = []
        size = 0
        while True:
            self._set_connection_timeout(connection, deadline)
            chunk = response.read1(64 * 1024)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            size += len(chunk)
            if size > 16 * 1024 * 1024:
                raise ValueError("Provider response exceeded 16 MiB")

    def _quota_message(self) -> str | None:
        return self.runtime.quota_message()

    def _mark_quota_unavailable(self, message: str) -> None:
        self.runtime.mark_quota_unavailable(message)


class OpenRouterProviderError(OSError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        provider_trace_id: str | None = None,
    ):
        super().__init__(message)
        self.http_status = http_status
        self.provider_trace_id = provider_trace_id


class OpenRouterRequestTimeoutError(OpenRouterProviderError):
    pass


class OpenRouterHardDeadlineError(OpenRouterRequestTimeoutError):
    pass


class OpenRouterRateLimitError(ValueError):
    def __init__(
        self,
        message: str,
        retry_after_seconds: float | None = None,
        *,
        provider_trace_id: str | None = None,
    ):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.http_status = 429
        self.provider_trace_id = provider_trace_id


class OpenRouterQuotaError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        provider_trace_id: str | None = None,
    ):
        super().__init__(message)
        self.http_status = http_status
        self.provider_trace_id = provider_trace_id


def _quota_decision(message: str) -> AgentDecision:
    return failure_decision(
        message=message,
    )


def extract_chat_text(response: dict[str, Any]) -> str:
    """Extract the assistant message text from an OpenRouter response."""

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


def _retry_after_seconds(headers: dict[str, str], detail: str) -> float | None:
    header = headers.get("retry-after")
    if header:
        try:
            return max(0.0, float(header))
        except ValueError:
            pass
    match = re.search(r"try again in ([0-9.]+)s", detail)
    if match:
        return max(0.0, float(match.group(1)) + 0.25)
    return None


def _provider_trace_id(headers: dict[str, str]) -> str | None:
    for name in ("x-request-id", "x-openrouter-request-id", "cf-ray"):
        value = headers.get(name)
        if value:
            return value
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
