"""Claude-plan-backed AgentBrain implemented with headless ``claude -p``.

Decisions use the account's saved claude.ai subscription (Pro/Max usage limits)
instead of the metered Anthropic API. They are session-less by default; the
optional bounded-session boundary keeps one short, private conversation per
simulated agent. Agent World remains the canonical source of memory and state.

Unlike Codex, the Claude CLI has no stable headless endpoint for reading the
plan's rate-limit windows, so there is no ``capture_plan_usage``; per-call
token usage is still recorded from the CLI's JSON result.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any
import uuid

from agent_world.brain_boundary import (
    DEFAULT_SESSION_MAX_TURNS,
    ConversationBoundary,
    ConversationInvocation,
)
from agent_world.brain_runtime import BrainRuntime
from agent_world.interface import build_dynamic_observation, build_static_context, parse_agent_response
from agent_world.models import AgentDecision
from agent_world.openai_brain import AGENT_DECISION_SCHEMA, SYSTEM_INSTRUCTIONS


CLAUDE_HARNESS_INSTRUCTIONS = (
    "This is a simulation decision, not a software-engineering task. "
    "Do not inspect files, run commands, browse, call tools, or delegate. "
    "Choose exactly one tick of behavior from the supplied rulebook and private observation. "
    "The simulation engine will validate every action. "
    "Return only the JSON object required by the output schema."
)

# The CLI validates structured output against a plain JSON schema, so the flat
# action shape used by the API brain works directly (no wrapper needed).
CLAUDE_AGENT_DECISION_SCHEMA: dict[str, Any] = AGENT_DECISION_SCHEMA


class ClaudeBrain:
    """Agent brain that spends saved Claude plan capacity, not API credits."""

    def __init__(
        self,
        model: str | None = None,
        reasoning_effort: str | None = None,
        timeout_seconds: int | None = None,
        executable: str | None = None,
        runtime: BrainRuntime | None = None,
        agent_id: str | None = None,
        connector_profile: str = "stateless-v1",
        conversation_mode: str = "stateless",
        session_max_turns: int = DEFAULT_SESSION_MAX_TURNS,
    ):
        self.runtime = runtime or BrainRuntime()
        self.boundary = ConversationBoundary(
            agent_id=agent_id,
            connector_profile=connector_profile,
            conversation_mode=conversation_mode,
            max_turns=session_max_turns,
        )
        self.connector_profile = connector_profile
        self.conversation_mode = conversation_mode
        self.session_max_turns = session_max_turns
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
        self.reasoning_effort = reasoning_effort or os.environ.get("CLAUDE_REASONING_EFFORT", "low")
        self.timeout_seconds = timeout_seconds or int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "300"))
        self.timeout_retries = max(0, int(os.environ.get("CLAUDE_TIMEOUT_RETRIES", "1")))
        self.executable = executable or os.environ.get("CLAUDE_EXECUTABLE") or _resolve_claude_executable()
        if not self.executable:
            raise ValueError("Claude Code CLI is required for ClaudeBrain, but 'claude' was not found on PATH.")

    def preflight(self) -> str | None:
        """Verify saved Claude-plan authentication without spending a model turn."""

        try:
            completed = subprocess.run(
                [self.executable, "auth", "status"],
                text=True,
                capture_output=True,
                timeout=min(self.timeout_seconds, 30),
                env=_plan_auth_environment(),
                check=False,
            )
            status = json.loads(completed.stdout or "{}")
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            return f"Claude provider unavailable: authentication preflight failed: {exc}"
        if completed.returncode != 0 or not status.get("loggedIn"):
            return "Claude provider unavailable: Claude Code is not logged in; run `claude auth login`."
        return None

    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        quota_message = self._quota_message()
        if quota_message is not None:
            return _failure_decision(quota_message)

        static_context = build_static_context(observation.get("world", {}))
        dynamic_json = json.dumps(build_dynamic_observation(observation), separators=(",", ":"), sort_keys=True)
        system_prompt, full_user_prompt = build_claude_prompts(static_context, dynamic_json)
        invocation = self.boundary.prepare()
        user_prompt = (
            full_user_prompt
            if invocation.full_context
            else build_claude_continuation_prompt(dynamic_json)
        )
        fresh_session_id = str(uuid.uuid4()) if self.conversation_mode != "stateless" else None

        started_at = time.monotonic()
        try:
            completed = None
            for attempt in range(self.timeout_retries + 1):
                try:
                    completed = self._execute(
                        system_prompt,
                        user_prompt,
                        invocation,
                        fresh_session_id,
                    )
                    break
                except subprocess.TimeoutExpired:
                    if attempt >= self.timeout_retries:
                        raise
                    if self.conversation_mode != "stateless":
                        # A timed-out turn may already exist in the provider
                        # session, so retry from canonical simulation state.
                        self.boundary.reset("timeout_retry")
                        invocation = self.boundary.prepare()
                        user_prompt = full_user_prompt
                        fresh_session_id = str(uuid.uuid4())
            assert completed is not None
            elapsed = time.monotonic() - started_at
            result = _parse_result_json(completed.stdout)
            if completed.returncode != 0 or (isinstance(result, dict) and result.get("is_error")):
                detail = _failure_detail(result, completed.stdout, completed.stderr)
                if invocation.resumed and not (
                    _is_quota_error(detail)
                    or _is_auth_error(detail)
                    or _is_provider_error(detail)
                ):
                    self.boundary.reset("resume_failure")
                    invocation = self.boundary.prepare()
                    user_prompt = full_user_prompt
                    fresh_session_id = str(uuid.uuid4())
                    completed = self._execute(
                        system_prompt,
                        user_prompt,
                        invocation,
                        fresh_session_id,
                    )
                    elapsed = time.monotonic() - started_at
                    result = _parse_result_json(completed.stdout)
                    detail = _failure_detail(result, completed.stdout, completed.stderr)
                still_error = completed.returncode != 0 or (
                    isinstance(result, dict) and result.get("is_error")
                )
                if still_error:
                    if _is_quota_error(detail):
                        message = f"Claude quota unavailable: {detail}"
                        self._mark_quota_unavailable(message)
                        return _failure_decision(message)
                    if _is_auth_error(detail):
                        message = f"Claude provider unavailable: {detail}"
                        self._mark_quota_unavailable(message)
                        return _failure_decision(message)
                    if _is_provider_error(detail):
                        message = f"Claude provider unavailable: {detail}"
                        self._mark_quota_unavailable(message)
                        return _failure_decision(message)
                    raise ValueError(f"claude -p exited {completed.returncode}: {detail}")

            decision, usage, response_model = extract_claude_result(result)
            session_id = (
                result.get("session_id")
                if isinstance(result, dict) and isinstance(result.get("session_id"), str)
                else invocation.resume_session_id or fresh_session_id
            )
            request_payload = (
                f"{system_prompt}\n\n{user_prompt}"
                if invocation.full_context
                else user_prompt
            )
            request_meta = {
                "agent_id": observation.get("self", {}).get("id"),
                "tick": observation.get("tick"),
                "agent_static_context_chars": len(static_context),
                "agent_dynamic_observation_chars": len(dynamic_json),
                "request_payload_bytes": len(request_payload.encode("utf-8")),
                "static_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
                "request_sha256": hashlib.sha256(request_payload.encode("utf-8")).hexdigest(),
                "claude_session_id": session_id,
                "duration_seconds": round(elapsed, 3),
                **self.boundary.usage_metadata(invocation),
            }
            try:
                parsed_decision = parse_agent_response(decision)
            except (ValueError, json.JSONDecodeError) as exc:
                failed_raw_response = (
                    decision
                    if isinstance(decision, str)
                    else json.dumps(decision, separators=(",", ":"), sort_keys=True)
                )
                self._record_usage(
                    usage,
                    response_model,
                    {
                        **request_meta,
                        "decision_failure_origin": "model_output",
                        "decision_failure_detail": f"{type(exc).__name__}: {exc}",
                        "failed_raw_response": failed_raw_response,
                        "failed_raw_response_sha256": hashlib.sha256(
                            failed_raw_response.encode("utf-8")
                        ).hexdigest(),
                    },
                )
                if self.conversation_mode != "stateless":
                    self.boundary.reset("model_output_failure")
                return _failure_decision(f"Claude model output failed: {exc}")
            if parsed_decision.intent.startswith("Invalid JSON response:"):
                failed_raw_response = (
                    decision
                    if isinstance(decision, str)
                    else json.dumps(decision, separators=(",", ":"), sort_keys=True)
                )
                self._record_usage(
                    usage,
                    response_model,
                    {
                        **request_meta,
                        "decision_failure_origin": "model_output",
                        "decision_failure_detail": parsed_decision.intent,
                        "failed_raw_response": failed_raw_response,
                        "failed_raw_response_sha256": hashlib.sha256(
                            failed_raw_response.encode("utf-8")
                        ).hexdigest(),
                    },
                )
                if self.conversation_mode != "stateless":
                    self.boundary.reset("model_output_failure")
                return _failure_decision(
                    f"Claude model output failed: {parsed_decision.intent}"
                )
            self._record_usage(usage, response_model, request_meta)
            self.boundary.commit(invocation, session_id)
            return parsed_decision
        except subprocess.TimeoutExpired:
            message = f"Claude provider unavailable: exceeded {self.timeout_seconds}s timeout"
            self._mark_quota_unavailable(message)
            return _failure_decision(message)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            if self.conversation_mode != "stateless":
                self.boundary.reset("decision_failure")
            return _failure_decision(f"Claude decision failed: {exc}")

    def _execute(
        self,
        system_prompt: str,
        user_prompt: str,
        invocation: ConversationInvocation | None = None,
        fresh_session_id: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        # Run in an empty cwd so no project CLAUDE.md, settings, or git state
        # can leak into the decision context. One stable directory per process
        # keeps the request prefix identical across calls.
        return subprocess.run(
            self._command(system_prompt, invocation, fresh_session_id),
            cwd=_decision_working_directory(),
            input=user_prompt,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            env=_plan_auth_environment(),
            check=False,
        )

    def _command(
        self,
        system_prompt: str,
        invocation: ConversationInvocation | None = None,
        fresh_session_id: str | None = None,
    ) -> list[str]:
        invocation = invocation or ConversationInvocation(None, True, 0, 1)
        command = [
            self.executable,
            "--print",
            "--output-format",
            "json",
            "--model",
            self.model,
            "--effort",
            _claude_effort(self.reasoning_effort),
            "--tools",
            "",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--setting-sources",
            "",
            "--json-schema",
            json.dumps(CLAUDE_AGENT_DECISION_SCHEMA, sort_keys=True),
        ]
        if self.conversation_mode == "stateless":
            command.append("--no-session-persistence")
        elif invocation.resume_session_id:
            command.extend(["--resume", invocation.resume_session_id])
        elif fresh_session_id:
            command.extend(["--session-id", fresh_session_id])
        if invocation.full_context:
            command.extend(["--system-prompt", system_prompt])
        return command

    def export_checkpoint_state(self) -> dict[str, Any]:
        return self.boundary.export_state() | {
            "provider": "claude_cli",
            "model": self.model,
        }

    def restore_checkpoint_state(self, state: dict[str, Any]) -> None:
        if state.get("provider") not in {None, "claude_cli"}:
            raise ValueError("checkpoint brain state is not for Claude")
        if state.get("model") not in {None, self.model}:
            raise ValueError("checkpoint Claude model does not match")
        self.boundary.restore_checkpoint_metadata(state)

    def reset_conversation(self, reason: str) -> None:
        self.boundary.reset(reason)

    def _record_usage(self, usage: dict[str, Any], response_model: str | None, request_meta: dict[str, Any]) -> None:
        input_tokens = int(usage.get("input_tokens") or 0)
        cache_read = int(usage.get("cache_read_input_tokens") or 0)
        cache_creation = int(usage.get("cache_creation_input_tokens") or 0)
        record = {
            "model": self.model,
            "response_model": response_model,
            "provider": "claude_cli",
            "api_style": "claude_print",
            "base_url": None,
            "billing_mode": "claude_plan",
            "reasoning_effort": self.reasoning_effort,
            "prompt_tokens": input_tokens + cache_read + cache_creation,
            "cached_tokens": cache_read,
            "completion_tokens": int(usage.get("output_tokens") or 0),
            "reasoning_tokens": 0,
            "cost": 0,
            "time": time.time(),
            **request_meta,
        }
        self.runtime.record_usage(record)

    def _quota_message(self) -> str | None:
        return self.runtime.quota_message()

    def _mark_quota_unavailable(self, message: str) -> None:
        self.runtime.mark_quota_unavailable(message)


def build_claude_prompts(static_context: str, dynamic_json: str) -> tuple[str, str]:
    """Return the (system, user) prompt pair for one decision.

    The system prompt is byte-identical across all agents and ticks of a run so
    the provider prompt cache can reuse it; only the slim dynamic state varies.
    """

    system_prompt = f"{CLAUDE_HARNESS_INSTRUCTIONS}\n\n{SYSTEM_INSTRUCTIONS}\n\n{static_context}"
    user_prompt = f"The current private observation follows as JSON:\n{dynamic_json}"
    return system_prompt, user_prompt


def build_claude_continuation_prompt(dynamic_json: str) -> str:
    return (
        "Continue the same simulated agent. Choose exactly one tick from this new "
        "private observation and return only the previously established decision JSON:\n"
        f"{dynamic_json}"
    )


def extract_claude_result(result: dict[str, Any]) -> tuple[dict[str, Any] | str, dict[str, Any], str | None]:
    """Extract the decision, usage, and resolved model from ``claude -p --output-format json``."""

    if not isinstance(result, dict):
        raise ValueError("claude -p did not return a JSON result object")
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    response_model = None
    model_usage = result.get("modelUsage")
    if isinstance(model_usage, dict) and model_usage:
        response_model = next(iter(model_usage))
    structured = result.get("structured_output")
    if isinstance(structured, dict):
        return structured, usage, response_model
    text = result.get("result")
    if isinstance(text, str) and text.strip():
        return text, usage, response_model
    raise ValueError(f"claude -p returned no decision (subtype={result.get('subtype')})")


def _parse_result_json(stdout: str) -> dict[str, Any] | None:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _failure_decision(message: str) -> AgentDecision:
    return AgentDecision(intent=message, actions=[{"type": "wait"}], messages=[], memory_updates=[])


def _failure_detail(result: dict[str, Any] | None, stdout: str, stderr: str) -> str:
    if isinstance(result, dict):
        for key in ("result", "error", "message", "subtype"):
            detail = result.get(key)
            if isinstance(detail, str) and detail.strip():
                return " ".join(detail.split())[:1000]
    detail = stderr.strip() or stdout.strip() or "unknown error"
    return " ".join(detail.split())[:1000]


def _claude_effort(reasoning_effort: str) -> str:
    # The simulation exposes OpenAI-style efforts; the Claude CLI has no "minimal".
    effort = (reasoning_effort or "low").strip().lower()
    return "low" if effort == "minimal" else effort


def _plan_auth_environment() -> dict[str, str]:
    child_env = os.environ.copy()
    # API and third-party-gateway credentials take precedence over the saved
    # claude.ai login. Remove them so decisions bill the subscription plan.
    for key in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_FOUNDRY",
    ):
        child_env.pop(key, None)
    child_env["NO_COLOR"] = "1"
    child_env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    # Extended thinking burns thousands of plan tokens and ~a minute per tick
    # for a single schema-constrained decision; keep it off unless asked for.
    child_env["MAX_THINKING_TOKENS"] = os.environ.get("CLAUDE_MAX_THINKING_TOKENS", "0")
    # Nested-session guard: allow launching claude from inside another claude.
    child_env.pop("CLAUDECODE", None)
    return child_env


@lru_cache(maxsize=1)
def _decision_working_directory() -> str:
    return tempfile.mkdtemp(prefix="agent-world-claude-")


def _is_quota_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "usage limit",
            "session limit",
            "rate limit",
            "out of extra usage",
            "out of usage credits",
            "insufficient_quota",
            "quota unavailable",
            "credit balance is too low",
            "credits exhausted",
            "limit reached",
        )
    )


def _is_auth_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(marker in lowered for marker in ("not logged in", "please run /login", "authentication required"))


def _is_provider_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "unable to connect to api",
            "connection refused",
            "connection closed mid-response",
            "connection reset",
            "network error",
            "service unavailable",
        )
    )


@lru_cache(maxsize=1)
def _resolve_claude_executable() -> str:
    candidates = [
        shutil.which("claude"),
        str(Path.home() / ".claude" / "local" / "claude"),
        str(Path.home() / ".local" / "bin" / "claude"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""
