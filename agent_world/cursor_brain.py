"""Cursor-subscription-backed AgentBrain implemented with ``cursor-agent -p``.

Decisions are read-only and authenticated by the user's saved Cursor login.
They are stateless by default; the optional bounded-session boundary keeps one
short, private conversation per simulated agent. Calls spend subscription
capacity rather than metered API credits.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
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
    DEFAULT_SESSION_MAX_TURNS,
    ConversationBoundary,
    ConversationInvocation,
)
from agent_world.brain_runtime import BrainRuntime
from agent_world.interface import build_dynamic_observation, build_static_context, parse_agent_response
from agent_world.models import AgentDecision
from agent_world.openai_brain import AGENT_DECISION_SCHEMA, SYSTEM_INSTRUCTIONS


CURSOR_HARNESS_INSTRUCTIONS = (
    "This is a simulation decision, not a software-engineering task. "
    "Do not inspect files, run commands, browse, call tools, or delegate. "
    "Choose exactly one tick of behavior from the supplied rulebook and private observation. "
    "The simulation engine will validate every action. "
    "Return only one JSON object matching the supplied output schema, with no markdown."
)


class CursorBrain:
    """Agent brain that spends saved Cursor subscription capacity."""

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
        self.model = model or os.environ.get("CURSOR_MODEL", "cursor-grok-4.5")
        self.reasoning_effort = reasoning_effort or os.environ.get("CURSOR_REASONING_EFFORT", "low")
        self.timeout_seconds = timeout_seconds or int(os.environ.get("CURSOR_TIMEOUT_SECONDS", "300"))
        self.timeout_retries = max(0, int(os.environ.get("CURSOR_TIMEOUT_RETRIES", "1")))
        self.executable = executable or os.environ.get("CURSOR_EXECUTABLE") or _resolve_cursor_executable()
        self.resolved_model = self.model
        if not self.executable:
            raise ValueError(
                "Cursor Agent CLI is required for CursorBrain, but 'cursor-agent' was not found. "
                "Install it with `cursor agent --help` or Cursor's official installer."
            )
        self._stable_work_dir = (
            _cursor_decision_working_directory(connector_profile)
            if connector_profile in {"stateless-v2", "stateless-v3"}
            or conversation_mode != "stateless"
            else None
        )

    def preflight(self) -> str | None:
        """Verify subscription login and resolve the requested account model."""

        try:
            status = subprocess.run(
                [self.executable, "status"],
                text=True,
                capture_output=True,
                timeout=min(self.timeout_seconds, 30),
                env=_subscription_environment(),
                check=False,
            )
            detail = f"{status.stdout}\n{status.stderr}".strip()
            if status.returncode != 0 or "not logged in" in detail.lower():
                return "Cursor provider unavailable: Cursor Agent is not logged in; run `cursor-agent login`."

            listed = subprocess.run(
                [self.executable, "--list-models"],
                text=True,
                capture_output=True,
                timeout=min(self.timeout_seconds, 30),
                env=_subscription_environment(),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"Cursor provider unavailable: authentication/model preflight failed: {exc}"
        if listed.returncode != 0:
            detail = _failure_detail(None, listed.stdout, listed.stderr)
            return f"Cursor provider unavailable: could not list subscription models: {detail}"

        available = parse_cursor_model_list(listed.stdout)
        resolved = resolve_cursor_model(self.model, self.reasoning_effort, available)
        if resolved is None:
            candidates = ", ".join(cursor_model_candidates(self.model, self.reasoning_effort))
            return (
                f"Cursor provider unavailable: model {self.model!r} at effort "
                f"{self.reasoning_effort!r} is not available on this account "
                f"(tried {candidates}); run `cursor-agent --list-models`."
            )
        self.resolved_model = resolved
        return None

    def copy_preflight_state_from(self, other: Any) -> None:
        """Reuse account/model resolution from an equivalent checked brain."""

        if not isinstance(other, CursorBrain):
            raise TypeError("Cursor preflight state must come from another CursorBrain")
        if (self.model, self.reasoning_effort) != (other.model, other.reasoning_effort):
            raise ValueError("Cursor preflight state requires matching model and effort")
        self.resolved_model = other.resolved_model

    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        quota_message = self.runtime.quota_message()
        if quota_message is not None:
            return _failure_decision(quota_message)

        static_context = build_static_context(observation.get("world", {}))
        dynamic_json = json.dumps(build_dynamic_observation(observation), separators=(",", ":"), sort_keys=True)
        full_prompt = build_cursor_prompt(static_context, dynamic_json)
        invocation = self.boundary.prepare()
        prompt = (
            full_prompt
            if invocation.full_context
            else build_cursor_continuation_prompt(dynamic_json)
        )

        started_at = time.monotonic()
        try:
            completed = None
            for attempt in range(self.timeout_retries + 1):
                try:
                    completed = self._execute(prompt, invocation)
                    break
                except subprocess.TimeoutExpired:
                    if attempt >= self.timeout_retries:
                        raise
                    if self.conversation_mode != "stateless":
                        # A timed-out turn may already have mutated the saved
                        # chat. Retry in a new chat from Agent World state.
                        self.boundary.reset("timeout_retry")
                        invocation = self.boundary.prepare()
                        prompt = full_prompt
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
                    prompt = full_prompt
                    completed = self._execute(prompt, invocation)
                    elapsed = time.monotonic() - started_at
                    result = _parse_result_json(completed.stdout)
                    detail = _failure_detail(result, completed.stdout, completed.stderr)
                still_error = completed.returncode != 0 or (
                    isinstance(result, dict) and result.get("is_error")
                )
                if still_error:
                    if _is_quota_error(detail):
                        message = f"Cursor quota unavailable: {detail}"
                        self.runtime.mark_quota_unavailable(message)
                        return _failure_decision(message)
                    if _is_auth_error(detail) or _is_provider_error(detail):
                        message = f"Cursor provider unavailable: {detail}"
                        self.runtime.mark_quota_unavailable(message)
                        return _failure_decision(message)
                    raise ValueError(f"cursor-agent -p exited {completed.returncode}: {detail}")

            decision, usage, response_model = extract_cursor_result(result)
            session_id = (
                result.get("session_id")
                if isinstance(result, dict) and isinstance(result.get("session_id"), str)
                else invocation.resume_session_id
            )
            request_meta = {
                "agent_id": observation.get("self", {}).get("id"),
                "tick": observation.get("tick"),
                "agent_static_context_chars": len(static_context),
                "agent_dynamic_observation_chars": len(dynamic_json),
                "request_payload_bytes": len(prompt.encode("utf-8")),
                "static_prompt_sha256": hashlib.sha256(
                    f"{SYSTEM_INSTRUCTIONS}\n\n{static_context}".encode("utf-8")
                ).hexdigest(),
                "request_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
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
                    response_model or self.resolved_model,
                    result,
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
                return _failure_decision(f"Cursor model output failed: {exc}")
            if parsed_decision.intent.startswith("Invalid JSON response:"):
                failed_raw_response = (
                    decision
                    if isinstance(decision, str)
                    else json.dumps(decision, separators=(",", ":"), sort_keys=True)
                )
                self._record_usage(
                    usage,
                    response_model or self.resolved_model,
                    result,
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
                    f"Cursor model output failed: {parsed_decision.intent}"
                )
            self._record_usage(
                usage,
                response_model or self.resolved_model,
                result,
                request_meta,
            )
            self.boundary.commit(invocation, session_id)
            return parsed_decision
        except subprocess.TimeoutExpired:
            message = f"Cursor provider unavailable: exceeded {self.timeout_seconds}s timeout"
            self.runtime.mark_quota_unavailable(message)
            return _failure_decision(message)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            if self.conversation_mode != "stateless":
                self.boundary.reset("decision_failure")
            return _failure_decision(f"Cursor decision failed: {exc}")

    def _execute(
        self,
        prompt: str,
        invocation: ConversationInvocation | None = None,
    ) -> subprocess.CompletedProcess[str]:
        invocation = invocation or ConversationInvocation(None, True, 0, 1)
        if self._stable_work_dir is not None:
            return self._run_command(prompt, invocation, self._stable_work_dir)
        with tempfile.TemporaryDirectory(prefix="agent-world-cursor-") as temp_dir:
            return self._run_command(prompt, invocation, temp_dir)

    def _run_command(
        self,
        prompt: str,
        invocation: ConversationInvocation,
        workspace: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self._command(workspace, invocation),
            cwd=workspace,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            env=_subscription_environment(),
            check=False,
        )

    def _command(
        self,
        workspace: str,
        invocation: ConversationInvocation | None = None,
    ) -> list[str]:
        invocation = invocation or ConversationInvocation(None, True, 0, 1)
        command = [
            self.executable,
            "--print",
            "--trust",
            "--output-format",
            "json",
            "--mode",
            "ask",
            "--sandbox",
            "enabled",
            "--workspace",
            workspace,
            "--model",
            self.resolved_model,
        ]
        if invocation.resume_session_id:
            command.extend(["--resume", invocation.resume_session_id])
        return command

    def export_checkpoint_state(self) -> dict[str, Any]:
        return self.boundary.export_state() | {
            "provider": "cursor_cli",
            "model": self.model,
            "resolved_model": self.resolved_model,
        }

    def restore_checkpoint_state(self, state: dict[str, Any]) -> None:
        if state.get("provider") not in {None, "cursor_cli"}:
            raise ValueError("checkpoint brain state is not for Cursor")
        if state.get("model") not in {None, self.model}:
            raise ValueError("checkpoint Cursor model does not match")
        self.boundary.restore_checkpoint_metadata(state)

    def reset_conversation(self, reason: str) -> None:
        self.boundary.reset(reason)

    def _record_usage(
        self,
        usage: dict[str, Any],
        response_model: str | None,
        result: dict[str, Any],
        request_meta: dict[str, Any],
    ) -> None:
        input_tokens = int(usage.get("inputTokens") or usage.get("input_tokens") or 0)
        cache_read = int(usage.get("cacheReadTokens") or usage.get("cache_read_tokens") or 0)
        cache_write = int(usage.get("cacheWriteTokens") or usage.get("cache_write_tokens") or 0)
        self.runtime.record_usage(
            {
                "model": self.model,
                "response_model": response_model,
                "provider": "cursor_cli",
                "api_style": "cursor_agent_print",
                "base_url": None,
                "billing_mode": "cursor_subscription",
                "reasoning_effort": self.reasoning_effort,
                "prompt_tokens": input_tokens + cache_read + cache_write,
                "cached_tokens": cache_read,
                "completion_tokens": int(usage.get("outputTokens") or usage.get("output_tokens") or 0),
                "reasoning_tokens": 0,
                "cost": 0,
                "time": time.time(),
                "cursor_session_id": result.get("session_id"),
                "cursor_request_id": result.get("request_id"),
                **request_meta,
            }
        )


def build_cursor_prompt(static_context: str, dynamic_json: str) -> str:
    schema = json.dumps(AGENT_DECISION_SCHEMA, separators=(",", ":"), sort_keys=True)
    return (
        f"{CURSOR_HARNESS_INSTRUCTIONS}\n\n"
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"{static_context}\n\n"
        f"Output JSON schema:\n{schema}\n\n"
        f"The current private observation follows as JSON:\n{dynamic_json}"
    )


def build_cursor_continuation_prompt(dynamic_json: str) -> str:
    return (
        "Continue the same simulated agent. Choose exactly one tick from this new "
        "private observation and return only the previously established decision JSON:\n"
        f"{dynamic_json}"
    )


def extract_cursor_result(result: dict[str, Any] | None) -> tuple[dict[str, Any] | str, dict[str, Any], str | None]:
    if not isinstance(result, dict):
        raise ValueError("cursor-agent did not return a JSON result object")
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    response_model = result.get("model") if isinstance(result.get("model"), str) else None
    decision = result.get("result")
    if isinstance(decision, dict):
        return decision, usage, response_model
    if isinstance(decision, str) and decision.strip():
        return decision, usage, response_model
    raise ValueError(f"cursor-agent returned no decision (subtype={result.get('subtype')})")


def parse_cursor_model_list(text: str) -> set[str]:
    return {
        match.group(1)
        for line in text.splitlines()
        if (match := re.match(r"^([^\s]+)\s+-\s+", line.strip()))
    }


def cursor_model_candidates(model: str, reasoning_effort: str) -> list[str]:
    normalized_effort = "none" if reasoning_effort == "minimal" else reasoning_effort
    effort_suffixes = {"none", "low", "medium", "high", "xhigh", "max"}
    stripped = model[:-5] if model.endswith("-fast") else model
    if "[" in model or stripped.rsplit("-", 1)[-1] in effort_suffixes:
        return [model]
    candidates = [f"{model}-{normalized_effort}", model]
    if reasoning_effort == "minimal":
        candidates.insert(1, f"{model}-low")
    return list(dict.fromkeys(candidates))


def resolve_cursor_model(model: str, reasoning_effort: str, available: set[str]) -> str | None:
    return next((candidate for candidate in cursor_model_candidates(model, reasoning_effort) if candidate in available), None)


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


def _subscription_environment() -> dict[str, str]:
    child_env = os.environ.copy()
    # The saved browser login must be the only Cursor credential source.
    for key in ("CURSOR_API_KEY", "CURSOR_AUTH_TOKEN", "CURSOR_ENDPOINT"):
        child_env.pop(key, None)
    child_env["NO_COLOR"] = "1"
    return child_env


def _is_quota_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "usage limit",
            "rate limit",
            "quota",
            "credits exhausted",
            "credit balance",
            "limit reached",
            "too many requests",
        )
    )


def _is_auth_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(marker in lowered for marker in ("not logged in", "authentication required", "unauthorized"))


def _is_provider_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "connection refused",
            "connection reset",
            "network error",
            "service unavailable",
            "server overload",
            "internal server error",
        )
    )


@lru_cache(maxsize=None)
def _cursor_decision_working_directory(connector_profile: str = "stateless-v2") -> str:
    if connector_profile == "stateless-v3":
        configured = os.environ.get("AGENT_WORLD_PROVIDER_WORKSPACE_ROOT")
        if configured:
            root = Path(configured).expanduser()
        else:
            root = Path(tempfile.gettempdir()) / "agent-world-provider-workspaces"
        directory = root / "cursor-stateless-v3"
        directory.mkdir(parents=True, exist_ok=True)
        return str(directory)
    return tempfile.mkdtemp(prefix="agent-world-cursor-stable-")


def _resolve_cursor_executable() -> str:
    candidates = [
        shutil.which("cursor-agent"),
        str(Path.home() / ".local" / "bin" / "cursor-agent"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""
