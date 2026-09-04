"""Direct grok.com subscription-backed AgentBrain implemented with the grok CLI."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

from agent_world.brain_boundary import (
    normalize_connector_profile,
    normalize_conversation_mode,
)
from agent_world.brain_runtime import BrainRuntime
from agent_world.decision_failure import (
    ambiguous_boundary_metadata,
    attribute_decision_failure,
    attributed_failure_message,
)
from agent_world.interface import build_dynamic_observation, build_static_context, parse_agent_response
from agent_world.process_transport import run_process, terminate_owned_process
from agent_world.models import AgentDecision
from agent_world.decision_outcome import failure_decision as _failure_decision
from agent_world.openrouter_brain import AGENT_DECISION_SCHEMA, SYSTEM_INSTRUCTIONS
from agent_world.provider_limits import is_quota_detail
from agent_world.provider_telemetry import record_provider_attempt

GROK_HARNESS_INSTRUCTIONS = (
    "This is a simulation decision, not a software-engineering task. "
    "Do not inspect files, run commands, browse, call tools, or delegate. "
    "Choose exactly one tick of behavior from the supplied rulebook and private observation. "
    "The simulation engine will validate every action."
)

# Grok treats empty and unknown-only allowlists as no filter. Include both the
# documented IDs and internal aliases observed in retained session traces.
GROK_DISALLOWED_TOOLS = ",".join(
    (
        "run_terminal_cmd",
        "run_terminal_command",
        "grep",
        "read_file",
        "search_replace",
        "list_dir",
        "web_search",
        "web_fetch",
        "todo_write",
        "task",
        "Agent",
        "ask_user_question",
        "search_tool",
    )
)


class GrokBrain:
    """Stateless agent brain using the user's saved grok.com login."""

    def __init__(
        self,
        model: str | None = None,
        reasoning_effort: str | None = None,
        timeout_seconds: int | None = None,
        executable: str | None = None,
        runtime: BrainRuntime | None = None,
        agent_id: str | None = None,
        connector_profile: str = "connector-v1",
        conversation_mode: str = "fresh-conversation",
        session_max_turns: int = 1,
    ):
        del session_max_turns
        connector_profile = normalize_connector_profile(connector_profile)
        conversation_mode = normalize_conversation_mode(conversation_mode)
        if conversation_mode != "fresh-conversation":
            raise ValueError("GrokBrain supports only fresh-conversation mode")
        self.runtime = runtime or BrainRuntime()
        self.agent_id = agent_id
        self.connector_profile = connector_profile
        self.conversation_mode = conversation_mode
        self.model = model or os.environ.get("GROK_MODEL", "grok-4.6")
        self.reasoning_effort = reasoning_effort or os.environ.get(
            "GROK_REASONING_EFFORT", "medium"
        )
        self.timeout_seconds = timeout_seconds or int(
            os.environ.get("GROK_TIMEOUT_SECONDS", "300")
        )
        self.timeout_retries = max(0, int(os.environ.get("GROK_TIMEOUT_RETRIES", "1")))
        self.executable = executable or os.environ.get("GROK_EXECUTABLE") or _resolve_grok_executable()
        self.resolved_model = self.model
        if not self.executable:
            raise ValueError("Grok CLI is required for GrokBrain, but 'grok' was not found")
        self._stable_work_dir = (
            _grok_decision_working_directory(connector_profile)
            if connector_profile in {"connector-v2", "connector-v3"}
            else None
        )

    def preflight(self) -> str | None:
        try:
            listed = run_process(
                [self.executable, "models"],
                text=True,
                capture_output=True,
                timeout=min(self.timeout_seconds, 30),
                env=_subscription_environment(),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"Grok provider unavailable: authentication/model preflight failed: {exc}"
        detail = f"{listed.stdout}\n{listed.stderr}".strip()
        if listed.returncode != 0 or "not logged in" in detail.lower():
            return "Grok provider unavailable: Grok CLI is not logged in; run grok login."
        if self.model not in parse_grok_model_list(listed.stdout):
            return f"Grok provider unavailable: model {self.model!r} is not available on this account"
        self.resolved_model = self.model
        return None

    def copy_preflight_state_from(self, other: Any) -> None:
        if not isinstance(other, GrokBrain):
            raise TypeError("Grok preflight state must come from another GrokBrain")
        if (self.model, self.reasoning_effort) != (other.model, other.reasoning_effort):
            raise ValueError("Grok preflight state requires matching model and effort")
        self.resolved_model = other.resolved_model

    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        blocking_failure = self.runtime.blocking_failure()
        if blocking_failure is not None:
            return _failure_decision(blocking_failure[1])
        static_context = build_static_context(observation.get("world", {}))
        dynamic_json = json.dumps(
            build_dynamic_observation(observation), separators=(",", ":"), sort_keys=True
        )
        system_prompt, user_prompt = build_grok_prompts(static_context, dynamic_json)
        request_payload = json.dumps(
            {"system": system_prompt, "user": user_prompt, "schema": AGENT_DECISION_SCHEMA},
            separators=(",", ":"),
            sort_keys=True,
        )
        request_attempt_meta = {
            "agent_id": observation.get("self", {}).get("id"),
            "tick": observation.get("tick"),
            "request_sha256": hashlib.sha256(request_payload.encode("utf-8")).hexdigest(),
        }
        timeout_recorded = False
        started_at = time.monotonic()
        try:
            completed = None
            for attempt in range(self.timeout_retries + 1):
                attempt_started_at = time.monotonic()
                try:
                    completed = self._execute(system_prompt, user_prompt)
                    break
                except subprocess.TimeoutExpired as exc:
                    timeout_recorded = True
                    record_provider_attempt(
                        self.runtime,
                        event_type="request_timeout",
                        failure_kind="timeout",
                        provider="grok_cli",
                        model=self.model,
                        response_model=self.resolved_model,
                        billing_mode="grok_subscription",
                        reasoning_effort=self.reasoning_effort,
                        request_meta=request_attempt_meta,
                        attempt=attempt + 1,
                        max_attempts=self.timeout_retries + 1,
                        duration_seconds=time.monotonic() - attempt_started_at,
                        detail=f"Exceeded {self.timeout_seconds}s timeout",
                        exception=exc,
                    )
                    if attempt >= self.timeout_retries:
                        raise
            assert completed is not None
            elapsed = time.monotonic() - started_at
            result = _parse_result_json(completed.stdout)
            request_meta = {
                "agent_id": observation.get("self", {}).get("id"),
                "tick": observation.get("tick"),
                "agent_static_context_chars": len(static_context),
                "agent_dynamic_observation_chars": len(dynamic_json),
                "request_payload_bytes": len(request_payload.encode("utf-8")),
                "static_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
                "request_sha256": hashlib.sha256(request_payload.encode("utf-8")).hexdigest(),
                "duration_seconds": round(elapsed, 3),
                "connector_profile": self.connector_profile,
                "conversation_mode": "fresh-conversation",
            }
            if (
                completed.returncode != 0
                or not isinstance(result, dict)
                or result.get("type") == "error"
            ):
                detail = _failure_detail(result, completed.stdout, completed.stderr)
                if _is_quota_error(detail):
                    message = f"Grok quota unavailable: {detail}"
                    record_provider_attempt(
                        self.runtime,
                        event_type="quota_exhausted",
                        failure_kind="quota",
                        provider="grok_cli",
                        model=self.model,
                        response_model=self.resolved_model,
                        billing_mode="grok_subscription",
                        reasoning_effort=self.reasoning_effort,
                        request_meta=request_attempt_meta,
                        attempt=attempt + 1,
                        max_attempts=self.timeout_retries + 1,
                        duration_seconds=elapsed,
                        detail=detail,
                    )
                    self.runtime.mark_quota_unavailable(message)
                    return _failure_decision(message)
                if _is_auth_error(detail):
                    message = f"Grok authentication required: {detail}"
                    record_provider_attempt(
                        self.runtime,
                        event_type="authentication_required",
                        failure_kind="authentication",
                        provider="grok_cli",
                        model=self.model,
                        response_model=self.resolved_model,
                        billing_mode="grok_subscription",
                        reasoning_effort=self.reasoning_effort,
                        request_meta=request_attempt_meta,
                        attempt=attempt + 1,
                        max_attempts=self.timeout_retries + 1,
                        duration_seconds=elapsed,
                        detail=detail,
                    )
                    self.runtime.mark_authentication_required(message)
                    return _failure_decision(message)
                if _is_provider_error(detail):
                    message = f"Grok provider unavailable: {detail}"
                    record_provider_attempt(
                        self.runtime,
                        event_type="provider_error",
                        failure_kind="provider",
                        provider="grok_cli",
                        model=self.model,
                        response_model=self.resolved_model,
                        billing_mode="grok_subscription",
                        reasoning_effort=self.reasoning_effort,
                        request_meta=request_attempt_meta,
                        attempt=attempt + 1,
                        max_attempts=self.timeout_retries + 1,
                        duration_seconds=elapsed,
                        detail=detail,
                    )
                    return _failure_decision(message)
                self._record_usage(
                    {}, self.resolved_model, result,
                    {**request_meta, **ambiguous_boundary_metadata(completed.stdout, detail)},
                )
                return _failure_decision(f"Grok boundary failed: {detail}")
            stop_reason = result.get("stopReason")
            if stop_reason != "end_turn":
                structured_error = result.get("structuredOutputError")
                detail = f"unexpected stopReason {stop_reason!r}"
                if isinstance(structured_error, str) and structured_error.strip():
                    detail += f": {structured_error.strip()}"
                usage, response_model = _best_effort_grok_metadata(result)
                self._record_usage(
                    usage,
                    response_model or self.resolved_model,
                    result,
                    {**request_meta, **ambiguous_boundary_metadata(completed.stdout, detail)},
                )
                return _failure_decision(f"Grok boundary failed: {detail}")
            try:
                decision, usage, response_model = extract_grok_result(result)
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}"
                usage, response_model = _best_effort_grok_metadata(result)
                self._record_usage(
                    usage, response_model or self.resolved_model, result,
                    {**request_meta, **ambiguous_boundary_metadata(completed.stdout, detail)},
                )
                return _failure_decision(f"Grok boundary failed: {detail}")
            self.resolved_model = response_model or self.resolved_model
            attribution = attribute_decision_failure(decision, AGENT_DECISION_SCHEMA)
            if attribution.origin == "model_output":
                adapter_detail = (
                    "Independent contract validation failed: "
                    f"{attribution.contract_validation.detail}"
                )
                self._record_usage(
                    usage, self.resolved_model, result,
                    {**request_meta, **attribution.usage_metadata(adapter_detail)},
                )
                return _failure_decision(
                    attributed_failure_message("Grok", attribution, adapter_detail)
                )
            adapter_detail: str | None = None
            try:
                parsed_decision = parse_agent_response(decision)
            except Exception as exc:
                adapter_detail = f"{type(exc).__name__}: {exc}"
                parsed_decision = None
            if parsed_decision is not None and parsed_decision.intent.startswith("Invalid JSON response:"):
                adapter_detail = parsed_decision.intent
            if adapter_detail is not None:
                self._record_usage(
                    usage, self.resolved_model, result,
                    {**request_meta, **attribution.usage_metadata(adapter_detail)},
                )
                return _failure_decision(
                    attributed_failure_message("Grok", attribution, adapter_detail)
                )
            assert parsed_decision is not None
            self._record_usage(usage, self.resolved_model, result, request_meta)
            return parsed_decision
        except subprocess.TimeoutExpired as exc:
            message = f"Grok provider unavailable: exceeded {self.timeout_seconds}s timeout"
            if not timeout_recorded:
                record_provider_attempt(
                    self.runtime,
                    event_type="request_timeout",
                    failure_kind="timeout",
                    provider="grok_cli",
                    model=self.model,
                    response_model=self.resolved_model,
                    billing_mode="grok_subscription",
                    reasoning_effort=self.reasoning_effort,
                    request_meta=request_attempt_meta,
                    attempt=1,
                    max_attempts=1,
                    duration_seconds=time.monotonic() - started_at,
                    detail=message,
                    exception=exc,
                )
            return _failure_decision(message)
        except OSError as exc:
            detail = f"{type(exc).__name__}: {exc}"
            record_provider_attempt(
                self.runtime,
                event_type="provider_error",
                failure_kind="provider",
                provider="grok_cli",
                model=self.model,
                response_model=self.resolved_model,
                billing_mode="grok_subscription",
                reasoning_effort=self.reasoning_effort,
                request_meta=request_attempt_meta,
                attempt=1,
                max_attempts=1,
                duration_seconds=time.monotonic() - started_at,
                detail=detail,
            )
            return _failure_decision(f"Grok provider unavailable: {detail}")
        except (ValueError, json.JSONDecodeError) as exc:
            return _failure_decision(f"Grok decision failed: {exc}")

    def _execute(self, system_prompt: str, user_prompt: str) -> subprocess.CompletedProcess[str]:
        if self._stable_work_dir is not None:
            return self._run_command(system_prompt, user_prompt, self._stable_work_dir)
        with tempfile.TemporaryDirectory(prefix="agent-world-grok-") as temp_dir:
            return self._run_command(system_prompt, user_prompt, temp_dir)

    def _run_command(
        self, system_prompt: str, user_prompt: str, workspace: str
    ) -> subprocess.CompletedProcess[str]:
        return run_process(
            self._command(system_prompt, user_prompt, workspace),
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            env=_subscription_environment(),
            check=False,
        )

    def _command(self, system_prompt: str, user_prompt: str, workspace: str) -> list[str]:
        schema = json.dumps(AGENT_DECISION_SCHEMA, separators=(",", ":"), sort_keys=True)
        return [
            self.executable,
            "--single", user_prompt,
            # The CLI accepts the public catalog name requested by the user.
            # `modelUsage` may expose a backend build label (for example
            # `grok-4.6-build`), but that response label is telemetry, not a
            # callable model ID. Reusing it here makes the first decision
            # succeed and every subsequent decision fail as "unknown model
            # id".
            "--model", self.model,
            "--reasoning-effort", self.reasoning_effort,
            "--output-format", "json",
            "--json-schema", schema,
            "--system-prompt-override", system_prompt,
            "--disable-web-search",
            "--no-subagents",
            "--no-plan",
            "--max-turns", "1",
            "--permission-mode", "plan",
            "--disallowed-tools", GROK_DISALLOWED_TOOLS,
            "--cwd", workspace,
        ]

    def export_checkpoint_state(self) -> dict[str, Any]:
        return {"provider": "grok_cli", "model": self.model, "resolved_model": self.resolved_model}

    def restore_checkpoint_state(self, state: dict[str, Any]) -> None:
        if state.get("provider") not in {None, "grok_cli"}:
            raise ValueError("checkpoint brain state is not for Grok")
        if state.get("model") not in {None, self.model}:
            raise ValueError("checkpoint Grok model does not match")
        if isinstance(state.get("resolved_model"), str):
            self.resolved_model = state["resolved_model"]

    def reset_conversation(self, reason: str) -> None:
        del reason

    def _record_usage(
        self,
        usage: dict[str, Any],
        response_model: str | None,
        result: dict[str, Any] | None,
        request_meta: dict[str, Any],
    ) -> None:
        model_usage = (result or {}).get("modelUsage")
        self.runtime.record_usage(
            {
                "model": self.model,
                "response_model": response_model,
                "provider": "grok_cli",
                "api_style": "grok_single_json_schema",
                "base_url": None,
                "billing_mode": "grok_subscription",
                "reasoning_effort": self.reasoning_effort,
                # Grok Build reports input_tokens, cache reads, and cache
                # creations as disjoint counts. The shared ledger contract
                # stores prompt_tokens as their inclusive total.
                "prompt_tokens": sum(
                    int(usage.get(key) or 0)
                    for key in (
                        "input_tokens",
                        "cache_read_input_tokens",
                        "cache_creation_input_tokens",
                    )
                ),
                "cached_tokens": int(usage.get("cache_read_input_tokens") or 0),
                "cache_write_tokens": int(usage.get("cache_creation_input_tokens") or 0),
                "completion_tokens": int(usage.get("output_tokens") or 0),
                "reasoning_tokens": int(usage.get("reasoning_tokens") or 0),
                "cost": 0,
                "provider_reported_cost_usd": float((result or {}).get("total_cost_usd") or 0),
                "time": time.time(),
                "grok_session_id": (result or {}).get("sessionId"),
                "grok_request_id": (result or {}).get("requestId"),
                "grok_model_usage": model_usage if isinstance(model_usage, dict) else None,
                **request_meta,
            }
        )


def build_grok_prompts(static_context: str, dynamic_json: str) -> tuple[str, str]:
    return (
        f"{GROK_HARNESS_INSTRUCTIONS}\n\n{SYSTEM_INSTRUCTIONS}\n\n{static_context}",
        f"The current private observation follows as JSON:\n{dynamic_json}",
    )


def extract_grok_result(
    result: dict[str, Any] | None,
) -> tuple[dict[str, Any] | str, dict[str, Any], str | None]:
    if not isinstance(result, dict):
        raise ValueError("grok did not return a JSON result object")
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    model_usage = result.get("modelUsage") if isinstance(result.get("modelUsage"), dict) else {}
    response_model = next(iter(model_usage), None)
    decision = result.get("structuredOutput")
    if isinstance(decision, dict):
        return decision, usage, response_model
    text = result.get("text")
    if isinstance(text, str) and text.strip():
        return text, usage, response_model
    raise ValueError("grok returned no structured decision")


def _best_effort_grok_metadata(
    result: dict[str, Any] | None,
) -> tuple[dict[str, Any], str | None]:
    if not isinstance(result, dict):
        return {}, None
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    model_usage = result.get("modelUsage") if isinstance(result.get("modelUsage"), dict) else {}
    return usage, next(iter(model_usage), None)


def parse_grok_model_list(text: str) -> set[str]:
    return {
        match.group(1)
        for line in text.splitlines()
        if (match := re.match(r"^[*-]\s+([^\s(]+)", line.strip()))
    }


def _parse_result_json(stdout: str) -> dict[str, Any] | None:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None




def _failure_detail(result: dict[str, Any] | None, stdout: str, stderr: str) -> str:
    if isinstance(result, dict):
        for key in ("error", "message", "text", "stopReason"):
            detail = result.get(key)
            if isinstance(detail, str) and detail.strip():
                return " ".join(detail.split())[:1000]
    detail = stderr.strip() or stdout.strip() or "unknown error"
    return " ".join(detail.split())[:1000]


def _subscription_environment() -> dict[str, str]:
    child_env = os.environ.copy()
    for key in ("XAI_API_KEY", "GROK_API_KEY", "GROK_AUTH_TOKEN", "GROK_ENDPOINT"):
        child_env.pop(key, None)
    child_env["NO_COLOR"] = "1"
    return child_env


def _is_quota_error(detail: str) -> bool:
    return is_quota_detail(detail)


def _is_auth_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(marker in lowered for marker in ("not logged in", "authentication required", "unauthorized"))


def _is_provider_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "connection refused", "connection reset", "network error",
            "service unavailable", "server overload", "internal server error",
        )
    )


def _grok_decision_working_directory(connector_profile: str = "connector-v2") -> str:
    if connector_profile == "connector-v3":
        configured = os.environ.get("AGENT_WORLD_PROVIDER_WORKSPACE_ROOT")
        root = Path(configured).expanduser() if configured else Path(tempfile.gettempdir()) / "agent-world-provider-workspaces"
        directory = root / "grok-connector-v3"
        directory.mkdir(parents=True, exist_ok=True)
        return str(directory)
    return tempfile.mkdtemp(prefix="agent-world-grok-stable-")


def _resolve_grok_executable() -> str:
    candidates = [shutil.which("grok"), str(Path.home() / ".local" / "bin" / "grok")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""
