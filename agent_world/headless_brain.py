"""Shared decision boundary for native, stateless headless CLI adapters."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any

from agent_world.brain_boundary import CONNECTOR_PROFILES, normalize_connector_profile, normalize_conversation_mode
from agent_world.brain_runtime import BrainRuntime
from agent_world.decision_contract import AGENT_DECISION_SCHEMA, SYSTEM_INSTRUCTIONS
from agent_world.decision_failure import ambiguous_boundary_metadata, attribute_decision_failure
from agent_world.decision_outcome import failure_decision
from agent_world.interface import build_static_context, dynamic_observation_json, parse_agent_response
from agent_world.process_transport import ProcessOutputLimitError
from agent_world.tool_boundary import ToolBoundaryError
from agent_world.provider_limits import is_quota_detail
from agent_world.provider_telemetry import record_provider_attempt

HARNESS_INSTRUCTIONS = (
    "This is a simulation decision, not a software-engineering task. "
    "Do not inspect files, run commands, browse, call tools, or delegate. "
    "Choose exactly one tick of behavior from the supplied rulebook and private observation. "
    "Return only one JSON object matching the output schema, with no markdown."
)


def build_headless_prompt(static_context: str, dynamic_json: str) -> str:
    schema = json.dumps(AGENT_DECISION_SCHEMA, separators=(",", ":"), sort_keys=True)
    return (
        f"{HARNESS_INSTRUCTIONS}\n\n{SYSTEM_INSTRUCTIONS}\n\n{static_context}\n\n"
        f"Output schema:\n{schema}\n\nThe current private observation follows as JSON:\n{dynamic_json}"
    )


def resolve_executable(command: str) -> str:
    for candidate in (shutil.which(command), str(Path.home() / ".local/bin" / command)):
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def token_count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


class BoundaryError(ValueError):
    """An invalid or incomplete CLI envelope, not evidence of a model mistake."""


class HeadlessBrain:
    provider: str
    label: str
    env_prefix: str
    command_name: str
    default_model: str
    billing_mode: str
    api_style: str
    efforts: frozenset[str]

    def __init__(
        self, model: str | None = None, reasoning_effort: str | None = None,
        timeout_seconds: int | None = None, executable: str | None = None,
        runtime: BrainRuntime | None = None, agent_id: str | None = None,
        connector_profile: str = "connector-v1",
        conversation_mode: str = "fresh-conversation", session_max_turns: int = 1,
    ):
        del session_max_turns
        self.connector_profile = normalize_connector_profile(connector_profile)
        if self.connector_profile not in CONNECTOR_PROFILES:
            raise ValueError(f"unsupported connector profile: {self.connector_profile}")
        self.conversation_mode = normalize_conversation_mode(conversation_mode)
        if self.conversation_mode != "fresh-conversation":
            raise ValueError(f"{self.label} supports only fresh-conversation mode")
        self.model = model or os.environ.get(f"{self.env_prefix}_MODEL", self.default_model)
        if not self.model.strip() or self.model.lower() in {"auto", "default"}:
            raise ValueError(f"{self.label} requires an explicit model ID")
        self.resolved_model = self.model
        self.reasoning_effort = reasoning_effort or os.environ.get(f"{self.env_prefix}_REASONING_EFFORT", "low")
        if self.reasoning_effort not in self.efforts:
            raise ValueError(f"{self.label} does not support effort {self.reasoning_effort!r}")
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else int(os.environ.get(f"{self.env_prefix}_TIMEOUT_SECONDS", "300"))
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.executable = executable or os.environ.get(f"{self.env_prefix}_EXECUTABLE") or resolve_executable(self.command_name)
        if not self.executable:
            raise ValueError(f"{self.label} CLI not found; install {self.command_name} first")
        self.runtime = runtime or BrainRuntime()
        self.agent_id = agent_id
        self.cli_version: str | None = None

    def copy_preflight_state_from(self, other: Any) -> None:
        if type(other) is not type(self) or (self.model, self.reasoning_effort, self.executable) != (
            other.model, other.reasoning_effort, other.executable
        ):
            raise ValueError("preflight state requires the same connector, model, effort, and executable")
        self.resolved_model, self.cli_version = other.resolved_model, other.cli_version

    def export_checkpoint_state(self) -> dict[str, Any]:
        return {"provider": self.provider, "model": self.model,
                "resolved_model": self.resolved_model, "reasoning_effort": self.reasoning_effort,
                "cli_version": self.cli_version, "connector_profile": self.connector_profile,
                "conversation_mode": self.conversation_mode}

    def restore_checkpoint_state(self, state: dict[str, Any]) -> None:
        for key, expected in (("provider", self.provider), ("model", self.model),
                              ("reasoning_effort", self.reasoning_effort),
                              ("connector_profile", self.connector_profile),
                              ("conversation_mode", self.conversation_mode)):
            if state.get(key) not in (None, expected):
                raise ValueError(f"checkpoint {key} does not match {self.label}")
        if state.get("resolved_model") not in (None, self.model):
            raise ValueError("checkpoint resolved model does not match")
        self.cli_version = state.get("cli_version")

    def reset_conversation(self, reason: str) -> None:
        pass

    def _execute(self, prompt: str, workspace: str) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
        raise NotImplementedError

    def _parse(self, stdout: str, artifacts: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def decide(self, observation: dict[str, Any]):
        blocked = self.runtime.blocking_failure()
        if blocked:
            return failure_decision(blocked[1], kind=blocked[0])
        static = build_static_context(observation.get("world", {}))
        dynamic = dynamic_observation_json(observation)
        prompt = build_headless_prompt(static, dynamic)
        meta = {
            "agent_id": observation.get("self", {}).get("id"), "tick": observation.get("tick"),
            "request_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "static_prompt_sha256": hashlib.sha256(static.encode()).hexdigest(),
            "request_payload_bytes": len(prompt.encode()),
            "agent_static_context_chars": len(static), "agent_dynamic_observation_chars": len(dynamic),
            "connector_profile": self.connector_profile, "conversation_mode": self.conversation_mode,
        }
        start = time.monotonic()
        result: dict[str, Any] = {}
        try:
            # Per-call workspace and native session state prevent private information
            # from leaking between agents, seeds, or resumed checkpoints.
            with tempfile.TemporaryDirectory(prefix=f"agent-world-{self.command_name}-") as workspace:
                completed, artifacts = self._execute(prompt, workspace)
                meta["duration_seconds"] = round(time.monotonic() - start, 3)
                try:
                    result = self._parse(completed.stdout, artifacts)
                except (ValueError, TypeError, KeyError, AttributeError) as exc:
                    # Only process diagnostics, never model-authored response text,
                    # are eligible to set the provider's blocking state.
                    if completed.returncode:
                        return self._failed(completed.stderr or str(exc), meta, start)
                    self._record(result, {**meta, **ambiguous_boundary_metadata(completed.stdout, str(exc))})
                    return failure_decision(f"{self.label} boundary failed: {exc}", kind="harness")
            if completed.returncode or result.get("error"):
                self._record(result, {**meta, "error": True, "failure_origin": "provider_or_harness"})
                return self._failed(result.get("error") or completed.stderr or "CLI exited unsuccessfully", meta, start)
            if result.get("tool_calls", 0):
                raise BoundaryError("CLI performed a tool call or delegated during a simulation decision")
            native_model = result.get("native_configured_model")
            if native_model and native_model != self.model:
                raise BoundaryError("CLI configured a model different from the request")
            response_model = result.get("response_model")
            if response_model and response_model != self.model:
                raise BoundaryError(f"returned model {response_model!r} differs from requested {self.model!r}")
            observed_effort = result.get("observed_reasoning_effort")
            if observed_effort and observed_effort != self.reasoning_effort:
                raise BoundaryError("CLI changed the requested reasoning effort")
            response = result.get("response")
            if not isinstance(response, str) or not response.strip():
                raise BoundaryError("CLI returned no decision text")
            # Strict JSON: do not repair prose/fences or select an unrelated JSON object.
            try:
                payload = json.loads(response)
            except json.JSONDecodeError:
                payload = response
            attribution = attribute_decision_failure(payload, AGENT_DECISION_SCHEMA)
            if attribution.origin == "model_output":
                detail = str(attribution.contract_validation.detail)
                self._record(result, {**meta, **attribution.usage_metadata(detail)})
                return failure_decision(f"{self.label} invalid decision: {detail}", kind="model_output")
            decision = parse_agent_response(payload)
            self._record(result, meta)
            return decision
        except subprocess.TimeoutExpired as exc:
            return self._failed(f"CLI timed out after {self.timeout_seconds}s", meta, start, exception=exc)
        except (OSError, BoundaryError, ValueError, ProcessOutputLimitError, ToolBoundaryError) as exc:
            meta["duration_seconds"] = round(time.monotonic() - start, 3)
            self._record(result, {**meta, "error": True, "failure_origin": "harness",
                                  "failure_detail": str(exc)})
            return failure_decision(f"{self.label} boundary failed: {exc}", kind="harness")

    def _failed(self, detail: str, meta: dict[str, Any], start: float, exception=None):
        detail = " ".join(str(detail).split())[:1000]
        lowered = detail.lower()
        kind = "provider"
        if is_quota_detail(detail) or "resource_exhausted" in lowered:
            kind = "quota"
            self.runtime.mark_quota_unavailable(f"{self.label} quota unavailable: {detail}")
        elif any(x in lowered for x in ("sign in", "not logged in", "authentication", "unauthorized",
                                       "credential", "login", "invalid api key", "not eligible", "eligibility check failed")):
            kind = "authentication"
            self.runtime.mark_authentication_required(f"{self.label} authentication required: {detail}")
        record_provider_attempt(
            self.runtime, event_type={"quota": "quota_exhausted", "authentication": "authentication_required"}.get(
                kind, "request_timeout" if exception else "provider_error"),
            failure_kind=kind, provider=self.provider, model=self.model,
            billing_mode=self.billing_mode, reasoning_effort=self.reasoning_effort,
            request_meta=meta, attempt=1, max_attempts=1,
            duration_seconds=time.monotonic() - start, detail=detail, exception=exception,
        )
        return failure_decision(f"{self.label} {kind} failure: {detail}", kind=kind)

    def _record(self, result: dict[str, Any], meta: dict[str, Any]) -> None:
        usage = result.get("usage") or {}
        self.runtime.record_usage({
            "provider": self.provider, "model": self.model, "configured_model": self.resolved_model,
            "response_model": result.get("response_model"),
            "native_configured_model": result.get("native_configured_model"),
            "api_style": self.api_style, "billing_mode": self.billing_mode, "base_url": None,
            "reasoning_effort": self.reasoning_effort,
            "observed_reasoning_effort": result.get("observed_reasoning_effort"),
            "reasoning_effort_provenance": "observed" if result.get("observed_reasoning_effort") else "requested_only",
            "model_provenance": result.get("model_provenance", "observed" if result.get("response_model") else "requested_only"),
            **{key: token_count(usage.get(key)) for key in (
                "prompt_tokens", "completion_tokens", "cached_tokens", "cache_write_tokens", "reasoning_tokens")},
            "provider_reported_reasoning_tokens": token_count(usage.get("reasoning_tokens")),
            "usage_status": "reported" if usage.get("prompt_tokens") is not None and usage.get("completion_tokens") is not None else "unavailable",
            "cost": None, "provider_reported_cost_usd": None,
            "cli_version": self.cli_version, "native_session_id": result.get("session_id"),
            "time_to_first_token_ms": result.get("time_to_first_token_ms"),
            "native_trace_sha256": result.get("trace_sha256"),
            "tool_calls": result.get("tool_calls", 0), "time": time.time(), **meta,
        })
