"""Claude-plan-backed AgentBrain implemented with headless ``claude -p``.

Each decision is an independent, non-interactive Claude Code run billed against
the account's saved claude.ai subscription (Pro/Max usage limits) instead of
the metered Anthropic API.  The simulation remains the source of agent memory
and world state; Claude only receives the current private observation and
returns one schema-constrained decision.

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
    ):
        self.runtime = runtime or BrainRuntime()
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
        system_prompt, user_prompt = build_claude_prompts(static_context, dynamic_json)
        request_meta = {
            "agent_id": observation.get("self", {}).get("id"),
            "tick": observation.get("tick"),
            "agent_static_context_chars": len(static_context),
            "agent_dynamic_observation_chars": len(dynamic_json),
            "request_payload_bytes": len(f"{system_prompt}\n\n{user_prompt}".encode("utf-8")),
            "static_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
            "request_sha256": hashlib.sha256(f"{system_prompt}\n\n{user_prompt}".encode("utf-8")).hexdigest(),
        }

        started_at = time.monotonic()
        try:
            completed = None
            for attempt in range(self.timeout_retries + 1):
                try:
                    completed = self._execute(system_prompt, user_prompt)
                    break
                except subprocess.TimeoutExpired:
                    if attempt >= self.timeout_retries:
                        raise
            assert completed is not None
            elapsed = time.monotonic() - started_at
            result = _parse_result_json(completed.stdout)
            if completed.returncode != 0 or (isinstance(result, dict) and result.get("is_error")):
                detail = _failure_detail(result, completed.stdout, completed.stderr)
                if _is_quota_error(detail):
                    message = f"Claude quota unavailable: {detail}"
                    self._mark_quota_unavailable(message)
                    return _failure_decision(message)
                if _is_auth_error(detail):
                    message = f"Claude provider unavailable: {detail}"
                    self._mark_quota_unavailable(message)
                    return _failure_decision(message)
                raise ValueError(f"claude -p exited {completed.returncode}: {detail}")

            decision, usage, response_model = extract_claude_result(result)
            self._record_usage(usage, response_model, request_meta | {"duration_seconds": round(elapsed, 3)})
            return parse_agent_response(decision)
        except subprocess.TimeoutExpired:
            return _failure_decision(f"Claude decision failed: exceeded {self.timeout_seconds}s timeout")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return _failure_decision(f"Claude decision failed: {exc}")

    def _execute(self, system_prompt: str, user_prompt: str) -> subprocess.CompletedProcess[str]:
        # Run in an empty cwd so no project CLAUDE.md, settings, or git state
        # can leak into the decision context. One stable directory per process
        # keeps the request prefix identical across calls.
        return subprocess.run(
            self._command(system_prompt),
            cwd=_decision_working_directory(),
            input=user_prompt,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            env=_plan_auth_environment(),
            check=False,
        )

    def _command(self, system_prompt: str) -> list[str]:
        return [
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
            "--no-session-persistence",
            "--setting-sources",
            "",
            "--system-prompt",
            system_prompt,
            "--json-schema",
            json.dumps(CLAUDE_AGENT_DECISION_SCHEMA, sort_keys=True),
        ]

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
