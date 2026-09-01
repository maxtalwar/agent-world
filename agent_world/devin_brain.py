"""Devin-subscription-backed AgentBrain implemented through Devin CLI ACP.

The connector uses Devin CLI's documented Agent Client Protocol server instead
of editor automation or private endpoints. Decisions are tool-less, stateless
by default, and use the user's saved subscription login rather than provider
API keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from functools import lru_cache
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, TextIO

from agent_world.brain_boundary import (
    DEFAULT_SESSION_MAX_TURNS,
    ConversationBoundary,
    ConversationInvocation,
)
from agent_world.brain_runtime import BrainRuntime
from agent_world.decision_failure import (
    ambiguous_boundary_metadata,
    attribute_decision_failure,
    attributed_failure_message,
)
from agent_world.interface import (
    _extract_json_object,
    build_dynamic_observation,
    build_static_context,
    parse_agent_response,
)
from agent_world.models import AgentDecision
from agent_world.openrouter_brain import AGENT_DECISION_SCHEMA, SYSTEM_INSTRUCTIONS


DEVIN_HARNESS_INSTRUCTIONS = (
    "This is a simulation decision, not a software-engineering task. "
    "Do not inspect files, run commands, browse, call tools, or delegate. "
    "Choose exactly one tick of behavior from the supplied rulebook and private observation. "
    "The simulation engine will validate every action. "
    "Return only one JSON object matching the supplied output schema, with no markdown."
)

DEVIN_AGENT_CONFIG = {
    "system_instructions": f"{DEVIN_HARNESS_INSTRUCTIONS}\n\n{SYSTEM_INSTRUCTIONS}",
    "allowed_tools": [],
    "permissions": {"allow": [], "deny": [], "ask": []},
}

_MODEL_KEYS = {
    "alias",
    "id",
    "model",
    "model_id",
    "model_or_alias",
    "model_uid",
    "slug",
    "value",
}
_KNOWN_MODEL_ALIASES = {
    "adaptive",
    "codex",
    "gemini",
    "gpt",
    "opus",
    "sonnet",
    "swe",
}
_REASONING_CONFIG_IDS = {
    "effort",
    "reasoning",
    "reasoning_effort",
    "thinking",
    "thinking_level",
    "thought_level",
}


@dataclass
class AcpTurnResult:
    session_id: str
    response_text: str
    response_model: str | None
    resolved_reasoning_effort: str | None
    stop_reason: str
    usage: dict[str, Any]
    agent_info: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    transcript: list[dict[str, Any]]
    stderr: str = ""

    def envelope(self) -> str:
        return json.dumps(
            {
                "messages": self.transcript,
                "stderr": self.stderr,
            },
            separators=(",", ":"),
            sort_keys=True,
        )


class AcpProtocolError(RuntimeError):
    """A JSON-RPC or subprocess failure at the Devin boundary."""

    def __init__(self, message: str, *, transcript: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.transcript = list(transcript or [])

    def envelope(self) -> str:
        return json.dumps(
            {"messages": self.transcript, "error": str(self)},
            separators=(",", ":"),
            sort_keys=True,
        )


class DevinBrain:
    """Agent brain that spends saved Devin subscription capacity."""

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
        session_max_turns: int = DEFAULT_SESSION_MAX_TURNS,
    ):
        self.runtime = runtime or BrainRuntime()
        self.boundary = ConversationBoundary(
            agent_id=agent_id,
            connector_profile=connector_profile,
            conversation_mode=conversation_mode,
            max_turns=session_max_turns,
        )
        self.connector_profile = self.boundary.connector_profile
        self.conversation_mode = self.boundary.conversation_mode
        connector_profile = self.connector_profile
        conversation_mode = self.conversation_mode
        self.session_max_turns = session_max_turns
        self.model = model or os.environ.get("DEVIN_MODEL", "swe-1-6-fast")
        self.reasoning_effort = reasoning_effort or os.environ.get(
            "DEVIN_REASONING_EFFORT", "low"
        )
        self.timeout_seconds = timeout_seconds or int(
            os.environ.get("DEVIN_TIMEOUT_SECONDS", "300")
        )
        self.timeout_retries = max(
            0, int(os.environ.get("DEVIN_TIMEOUT_RETRIES", "1"))
        )
        self.executable = (
            executable
            or os.environ.get("DEVIN_EXECUTABLE")
            or _resolve_devin_executable()
        )
        self.resolved_model = self.model
        if not self.executable:
            raise ValueError(
                "DevinBrain requires Devin CLI, but no 'devin' executable was "
                "found. Install Devin CLI or set DEVIN_EXECUTABLE."
            )
        self._stable_work_dir = (
            _devin_decision_working_directory(connector_profile)
            if connector_profile in {"connector-v2", "connector-v3"}
            or conversation_mode != "fresh-conversation"
            else None
        )

    def preflight(self) -> str | None:
        """Verify saved login and resolve the requested account model."""

        try:
            status = subprocess.run(
                [self.executable, "auth", "status"],
                text=True,
                capture_output=True,
                timeout=min(self.timeout_seconds, 30),
                env=_subscription_environment(),
                check=False,
            )
            detail = f"{status.stdout}\n{status.stderr}".strip()
            if status.returncode != 0 or "not logged in" in detail.lower():
                return (
                    "Devin provider unavailable: Devin CLI is not logged in; "
                    "run `devin auth login`. Legacy Windsurf Enterprise users can "
                    "select the Windsurf login option."
                )
            listed = subprocess.run(
                [self.executable, "models", "list", "--format", "json"],
                text=True,
                capture_output=True,
                timeout=min(self.timeout_seconds, 30),
                env=_subscription_environment(),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return (
                "Devin provider unavailable: authentication/model preflight "
                f"failed: {exc}"
            )
        if listed.returncode != 0:
            return (
                "Devin provider unavailable: could not list subscription "
                f"models: {_failure_detail(listed.stdout, listed.stderr)}"
            )
        try:
            catalog = json.loads(listed.stdout)
        except json.JSONDecodeError as exc:
            return (
                "Devin provider unavailable: model catalog was not valid JSON: "
                f"{exc}"
            )
        available = parse_devin_model_catalog(catalog)
        resolved = resolve_devin_model(self.model, available)
        if resolved is None:
            return (
                f"Devin provider unavailable: model {self.model!r} is not "
                "available on this account; run `devin models list`."
            )
        self.resolved_model = resolved
        return None

    def copy_preflight_state_from(self, other: Any) -> None:
        """Reuse account/model resolution from an equivalent checked brain."""

        if not isinstance(other, DevinBrain):
            raise TypeError("Devin preflight state must come from another DevinBrain")
        if (self.model, self.reasoning_effort) != (
            other.model,
            other.reasoning_effort,
        ):
            raise ValueError("Devin preflight state requires matching model and effort")
        self.resolved_model = other.resolved_model

    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        quota_message = self.runtime.quota_message()
        if quota_message is not None:
            return _failure_decision(quota_message)

        static_context = build_static_context(observation.get("world", {}))
        dynamic_json = json.dumps(
            build_dynamic_observation(observation),
            separators=(",", ":"),
            sort_keys=True,
        )
        full_prompt = build_devin_prompt(static_context, dynamic_json)
        invocation = self.boundary.prepare()
        prompt = (
            full_prompt
            if invocation.full_context
            else build_devin_continuation_prompt(dynamic_json)
        )
        started_at = time.monotonic()
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
            **self.boundary.usage_metadata(invocation),
        }

        try:
            turn: AcpTurnResult | None = None
            for attempt in range(self.timeout_retries + 1):
                try:
                    turn = self._execute(prompt, invocation)
                    break
                except subprocess.TimeoutExpired:
                    if attempt >= self.timeout_retries:
                        raise
                    if self.conversation_mode != "fresh-conversation":
                        self.boundary.reset("timeout_retry")
                        invocation = self.boundary.prepare()
                        prompt = full_prompt
            assert turn is not None
            elapsed = time.monotonic() - started_at
            if turn.response_model:
                self.resolved_model = turn.response_model
            request_meta = {
                **request_meta,
                "duration_seconds": round(elapsed, 3),
            }

            if turn.tool_calls:
                detail = (
                    "ACP agent attempted a forbidden tool call despite the "
                    "tool-less connector policy"
                )
                self._record_usage(
                    turn,
                    {
                        **request_meta,
                        **ambiguous_boundary_metadata(turn.envelope(), detail),
                    },
                )
                if self.conversation_mode != "fresh-conversation":
                    self.boundary.reset("forbidden_tool_call")
                return _failure_decision(f"Devin boundary failed: {detail}")

            if turn.stop_reason != "end_turn":
                detail = f"ACP turn stopped with {turn.stop_reason!r}"
                self._record_usage(
                    turn,
                    {
                        **request_meta,
                        **ambiguous_boundary_metadata(turn.envelope(), detail),
                    },
                )
                if self.conversation_mode != "fresh-conversation":
                    self.boundary.reset("ambiguous_boundary_failure")
                return _failure_decision(f"Devin boundary failed: {detail}")

            raw_response = turn.response_text.strip()
            if not raw_response:
                detail = "ACP turn returned no agent message"
                self._record_usage(
                    turn,
                    {
                        **request_meta,
                        **ambiguous_boundary_metadata(turn.envelope(), detail),
                    },
                )
                if self.conversation_mode != "fresh-conversation":
                    self.boundary.reset("ambiguous_boundary_failure")
                return _failure_decision(f"Devin boundary failed: {detail}")

            payload: dict[str, Any] | str = raw_response
            try:
                parsed_json = json.loads(raw_response)
                if isinstance(parsed_json, dict):
                    payload = parsed_json
            except json.JSONDecodeError:
                salvaged = _extract_json_object(raw_response)
                if salvaged is not None:
                    payload = salvaged

            attribution = attribute_decision_failure(payload, AGENT_DECISION_SCHEMA)
            if attribution.origin == "model_output":
                adapter_detail = (
                    "Independent contract validation failed: "
                    f"{attribution.contract_validation.detail}"
                )
                self._record_usage(
                    turn,
                    {
                        **request_meta,
                        **attribution.usage_metadata(adapter_detail),
                    },
                )
                if self.conversation_mode != "fresh-conversation":
                    self.boundary.reset("model_output_failure")
                return _failure_decision(
                    attributed_failure_message("Devin", attribution, adapter_detail)
                )

            adapter_detail: str | None = None
            try:
                parsed_decision = parse_agent_response(payload)
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
                    turn,
                    {
                        **request_meta,
                        **attribution.usage_metadata(adapter_detail),
                    },
                )
                if self.conversation_mode != "fresh-conversation":
                    self.boundary.reset(f"{attribution.origin}_failure")
                return _failure_decision(
                    attributed_failure_message("Devin", attribution, adapter_detail)
                )

            assert parsed_decision is not None
            self._record_usage(turn, request_meta)
            self.boundary.commit(invocation, turn.session_id)
            return parsed_decision
        except subprocess.TimeoutExpired:
            message = (
                f"Devin provider unavailable: exceeded {self.timeout_seconds}s timeout"
            )
            self._record_failed_boundary(
                message,
                invocation=invocation,
                request_meta=request_meta,
                duration_seconds=time.monotonic() - started_at,
            )
            self.runtime.mark_quota_unavailable(message)
            return _failure_decision(message)
        except AcpProtocolError as exc:
            detail = _clean_detail(str(exc))
            self._record_failed_boundary(
                detail,
                invocation=invocation,
                request_meta=request_meta,
                duration_seconds=time.monotonic() - started_at,
                transcript=exc.transcript,
            )
            if _is_quota_error(detail):
                message = f"Devin quota unavailable: {detail}"
                self.runtime.mark_quota_unavailable(message)
                return _failure_decision(message)
            if _is_auth_error(detail) or _is_provider_error(detail):
                message = f"Devin provider unavailable: {detail}"
                self.runtime.mark_quota_unavailable(message)
                return _failure_decision(message)
            if self.conversation_mode != "fresh-conversation":
                self.boundary.reset("ambiguous_boundary_failure")
            return _failure_decision(f"Devin boundary failed: {detail}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._record_failed_boundary(
                f"{type(exc).__name__}: {exc}",
                invocation=invocation,
                request_meta=request_meta,
                duration_seconds=time.monotonic() - started_at,
            )
            if self.conversation_mode != "fresh-conversation":
                self.boundary.reset("decision_failure")
            return _failure_decision(f"Devin decision failed: {exc}")

    def _execute(
        self,
        prompt: str,
        invocation: ConversationInvocation | None = None,
    ) -> AcpTurnResult:
        invocation = invocation or ConversationInvocation(None, True, 0, 1)
        if self._stable_work_dir is not None:
            return self._run_turn(prompt, invocation, self._stable_work_dir)
        with tempfile.TemporaryDirectory(prefix="agent-world-devin-") as temp_dir:
            return self._run_turn(prompt, invocation, temp_dir)

    def _run_turn(
        self,
        prompt: str,
        invocation: ConversationInvocation,
        workspace: str,
    ) -> AcpTurnResult:
        config_path = _write_agent_config(Path(workspace))
        return run_devin_acp_turn(
            command=self._command(config_path),
            cwd=workspace,
            prompt=prompt,
            invocation=invocation,
            reasoning_effort=self.reasoning_effort,
            timeout_seconds=self.timeout_seconds,
            env=_subscription_environment(),
        )

    def _command(self, agent_config_path: Path) -> list[str]:
        return [
            self.executable,
            "--respect-workspace-trust",
            "false",
            "--agent-config",
            str(agent_config_path),
            "acp",
            "--model",
            self.resolved_model,
        ]

    def export_checkpoint_state(self) -> dict[str, Any]:
        return self.boundary.export_state() | {
            "provider": "devin_cli",
            "connector_runtime": "devin_cli_acp",
            "model": self.model,
            "resolved_model": self.resolved_model,
        }

    def restore_checkpoint_state(self, state: dict[str, Any]) -> None:
        if state.get("provider") not in {None, "devin_cli"}:
            raise ValueError("checkpoint brain state is not for Devin")
        if state.get("model") not in {None, self.model}:
            raise ValueError("checkpoint Devin model does not match")
        self.boundary.restore_checkpoint_metadata(state)

    def reset_conversation(self, reason: str) -> None:
        self.boundary.reset(reason)

    def _record_usage(
        self,
        turn: AcpTurnResult,
        request_meta: dict[str, Any],
    ) -> None:
        raw_response = turn.response_text
        usage = turn.usage
        reported_cost = usage.get("cost") if isinstance(usage.get("cost"), dict) else {}
        self.runtime.record_usage(
            {
                "model": self.model,
                "response_model": turn.response_model or self.resolved_model,
                "provider": "devin_cli",
                "connector_runtime": "devin_cli",
                "api_style": "agent_client_protocol",
                "acp_protocol_version": 1,
                "base_url": None,
                "billing_mode": "devin_subscription",
                "reasoning_effort": self.reasoning_effort,
                "resolved_reasoning_effort": turn.resolved_reasoning_effort,
                "prompt_tokens": _nonnegative_int(usage.get("input_tokens")),
                "cached_tokens": _nonnegative_int(usage.get("cache_read_tokens")),
                "completion_tokens": _nonnegative_int(usage.get("output_tokens")),
                "reasoning_tokens": _nonnegative_int(usage.get("reasoning_tokens")),
                "session_context_tokens": _nonnegative_int(usage.get("context_used")),
                "session_context_window": _nonnegative_int(usage.get("context_size")),
                "provider_reported_cost_amount": reported_cost.get("amount"),
                "provider_reported_cost_currency": reported_cost.get("currency"),
                "committed_credit_cost": usage.get("committed_credit_cost"),
                "committed_acu_cost": usage.get("committed_acu_cost"),
                "cost": 0,
                "time": time.time(),
                "devin_session_id": turn.session_id,
                "devin_request_id": usage.get("request_id"),
                "devin_stop_reason": turn.stop_reason,
                "devin_agent_name": turn.agent_info.get("name"),
                "devin_agent_version": turn.agent_info.get("version"),
                "devin_tool_call_count": len(turn.tool_calls),
                "raw_response": raw_response,
                "raw_response_sha256": hashlib.sha256(
                    raw_response.encode("utf-8")
                ).hexdigest(),
                **request_meta,
            }
        )

    def _record_failed_boundary(
        self,
        detail: str,
        *,
        invocation: ConversationInvocation,
        request_meta: dict[str, Any],
        duration_seconds: float,
        transcript: list[dict[str, Any]] | None = None,
    ) -> None:
        turn = AcpTurnResult(
            session_id=invocation.resume_session_id or "",
            response_text="",
            response_model=self.resolved_model,
            resolved_reasoning_effort=None,
            stop_reason="error",
            usage={},
            agent_info={},
            tool_calls=[],
            transcript=list(transcript or []),
        )
        self._record_usage(
            turn,
            {
                **request_meta,
                "duration_seconds": round(duration_seconds, 3),
                **ambiguous_boundary_metadata(turn.envelope(), detail),
            },
        )


def build_devin_prompt(static_context: str, dynamic_json: str) -> str:
    schema = json.dumps(AGENT_DECISION_SCHEMA, separators=(",", ":"), sort_keys=True)
    return (
        f"{static_context}\n\n"
        f"Output JSON schema:\n{schema}\n\n"
        f"The current private observation follows as JSON:\n{dynamic_json}"
    )


def build_devin_continuation_prompt(dynamic_json: str) -> str:
    return (
        "Continue the same simulated agent. Choose exactly one tick from this new "
        "private observation and return only the previously established decision JSON:\n"
        f"{dynamic_json}"
    )


def parse_devin_model_catalog(value: Any) -> set[str]:
    """Extract model IDs and aliases from Devin CLI's account-scoped JSON."""

    models: set[str] = set()

    def visit(node: Any, parent_key: str | None = None) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                normalized = str(key).lower()
                if normalized in _MODEL_KEYS and isinstance(child, str) and child.strip():
                    models.add(child.strip())
                visit(child, normalized)
        elif isinstance(node, list):
            for child in node:
                visit(child, parent_key)
        elif (
            isinstance(node, str)
            and parent_key in {"aliases", "models", "model_ids", "values"}
            and node.strip()
        ):
            models.add(node.strip())

    visit(value)
    return models


def resolve_devin_model(model: str, available: set[str]) -> str | None:
    by_lower = {candidate.lower(): candidate for candidate in available}
    normalized = model.lower()
    if normalized in by_lower:
        return by_lower[normalized]
    if normalized in _KNOWN_MODEL_ALIASES and available:
        # Devin documents these as stable fuzzy aliases, resolved account-side.
        return model
    partial = [
        candidate
        for candidate in available
        if normalized in candidate.lower() or candidate.lower() in normalized
    ]
    return partial[0] if len(partial) == 1 else None


def run_devin_acp_turn(
    *,
    command: list[str],
    cwd: str,
    prompt: str,
    invocation: ConversationInvocation,
    reasoning_effort: str,
    timeout_seconds: int,
    env: dict[str, str],
) -> AcpTurnResult:
    """Run one ACP prompt turn and return its structured boundary evidence."""

    client = _AcpClient(
        command=command,
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
    )
    try:
        initialized = client.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {},
                "clientInfo": {"name": "agent-world", "version": "0.1.0"},
            },
        )
        agent_info = (
            initialized.get("agentInfo")
            if isinstance(initialized.get("agentInfo"), dict)
            else {}
        )
        if invocation.resume_session_id:
            setup = client.request(
                "session/load",
                {
                    "sessionId": invocation.resume_session_id,
                    "cwd": cwd,
                    "mcpServers": [],
                },
            )
        else:
            setup = client.request(
                "session/new",
                {"cwd": cwd, "mcpServers": []},
            )
        session_id = str(setup.get("sessionId") or invocation.resume_session_id or "")
        if not session_id:
            raise AcpProtocolError(
                "ACP session setup returned no sessionId",
                transcript=client.transcript,
            )
        config_options = _config_options(setup)
        if _config_option(config_options, "mode") is not None:
            configured = client.request(
                "session/set_config_option",
                {
                    "sessionId": session_id,
                    "configId": "mode",
                    "value": "ask",
                },
            )
            config_options = _config_options(configured) or config_options

        resolved_reasoning: str | None = None
        reasoning_option = next(
            (
                option
                for option in config_options
                if str(option.get("id") or "").lower() in _REASONING_CONFIG_IDS
                or str(option.get("category") or "").lower() == "thought_level"
            ),
            None,
        )
        if reasoning_option is not None:
            reasoning_value = _resolve_config_option_value(
                reasoning_option, reasoning_effort
            )
            if reasoning_value is not None:
                configured = client.request(
                    "session/set_config_option",
                    {
                        "sessionId": session_id,
                        "configId": reasoning_option.get("id"),
                        "value": reasoning_value,
                    },
                )
                config_options = _config_options(configured) or config_options
                resolved_reasoning = reasoning_value

        prompt_result = client.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": prompt}],
            },
        )
        stop_reason = str(prompt_result.get("stopReason") or "unknown")
        response_text, tool_calls, usage = _summarize_acp_updates(client.transcript)
        response_model = _current_config_value(config_options, "model")
        return AcpTurnResult(
            session_id=session_id,
            response_text=response_text,
            response_model=response_model,
            resolved_reasoning_effort=resolved_reasoning,
            stop_reason=stop_reason,
            usage=usage,
            agent_info=agent_info,
            tool_calls=tool_calls,
            transcript=client.transcript,
            stderr=client.stderr_text,
        )
    finally:
        client.close()


class _AcpClient:
    """Small newline-delimited JSON-RPC client for a local ACP subprocess."""

    def __init__(
        self,
        *,
        command: list[str],
        cwd: str,
        env: dict[str, str],
        timeout_seconds: int,
    ):
        self.timeout_seconds = timeout_seconds
        self.process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if self.process.stdin is None or self.process.stdout is None or self.process.stderr is None:
            self.close()
            raise AcpProtocolError("failed to open ACP subprocess pipes")
        self._events: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self._next_id = 1
        self.transcript: list[dict[str, Any]] = []
        self._stderr_lines: list[str] = []
        self._closed_streams: set[str] = set()
        self._threads = [
            threading.Thread(
                target=self._pump,
                args=("stdout", self.process.stdout),
                daemon=True,
            ),
            threading.Thread(
                target=self._pump,
                args=("stderr", self.process.stderr),
                daemon=True,
            ),
        ]
        for thread in self._threads:
            thread.start()

    @property
    def stderr_text(self) -> str:
        return "\n".join(self._stderr_lines)

    def _pump(self, source: str, stream: TextIO) -> None:
        try:
            for line in stream:
                self._events.put((source, line.rstrip("\r\n")))
        finally:
            self._events.put((source, None))

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            message = self._next_message(deadline)
            if message is None:
                continue
            if message.get("id") == request_id and "method" not in message:
                if "error" in message:
                    raise AcpProtocolError(
                        _jsonrpc_error_detail(message["error"]),
                        transcript=self.transcript,
                    )
                result = message.get("result")
                if not isinstance(result, dict):
                    raise AcpProtocolError(
                        f"ACP {method} returned a non-object result",
                        transcript=self.transcript,
                    )
                return result
            if "id" in message and "method" in message:
                self._reject_server_request(message)

    def _next_message(self, deadline: float) -> dict[str, Any] | None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(self.process.args, self.timeout_seconds)
        try:
            source, line = self._events.get(timeout=remaining)
        except queue.Empty as exc:
            raise subprocess.TimeoutExpired(
                self.process.args, self.timeout_seconds
            ) from exc
        if line is None:
            self._closed_streams.add(source)
            if source == "stderr":
                return None
            if self.process.poll() is not None:
                detail = self.stderr_text or f"ACP process exited {self.process.returncode}"
                raise AcpProtocolError(detail, transcript=self.transcript)
            return None
        if source == "stderr":
            self._stderr_lines.append(line)
            return None
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AcpProtocolError(
                f"ACP emitted non-JSON stdout: {line[:500]} ({exc})",
                transcript=self.transcript,
            ) from exc
        if not isinstance(message, dict):
            raise AcpProtocolError(
                "ACP emitted a non-object JSON message",
                transcript=self.transcript,
            )
        self.transcript.append(message)
        return message

    def _reject_server_request(self, message: dict[str, Any]) -> None:
        if message.get("method") == "session/request_permission":
            params = message.get("params")
            options = params.get("options") if isinstance(params, dict) else []
            rejection = next(
                (
                    option.get("optionId")
                    for option in options
                    if isinstance(option, dict)
                    and str(option.get("kind") or "").startswith("reject")
                ),
                None,
            )
            outcome = (
                {"outcome": "selected", "optionId": rejection}
                if rejection
                else {"outcome": "cancelled"}
            )
            self._write(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {"outcome": outcome},
                }
            )
            return
        self._write(
            {
                "jsonrpc": "2.0",
                "id": message["id"],
                "error": {
                    "code": -32601,
                    "message": "Agent World exposes no client tools",
                },
            }
        )

    def _write(self, message: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise AcpProtocolError("ACP stdin is unavailable", transcript=self.transcript)
        try:
            self.process.stdin.write(
                json.dumps(message, separators=(",", ":"), sort_keys=True) + "\n"
            )
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise AcpProtocolError(
                f"ACP stdin closed: {exc}", transcript=self.transcript
            ) from exc

    def close(self) -> None:
        process = getattr(self, "process", None)
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)


def _config_options(value: dict[str, Any]) -> list[dict[str, Any]]:
    raw = value.get("configOptions")
    return [option for option in raw if isinstance(option, dict)] if isinstance(raw, list) else []


def _config_option(
    options: list[dict[str, Any]], config_id: str
) -> dict[str, Any] | None:
    return next(
        (
            option
            for option in options
            if str(option.get("id") or "").lower() == config_id.lower()
        ),
        None,
    )


def _current_config_value(
    options: list[dict[str, Any]], config_id: str
) -> str | None:
    option = _config_option(options, config_id)
    value = option.get("currentValue") if option else None
    return str(value) if isinstance(value, str) and value else None


def _resolve_config_option_value(
    option: dict[str, Any], requested: str
) -> str | None:
    raw_options = option.get("options")
    values = [
        str(value.get("value"))
        for value in raw_options
        if isinstance(value, dict) and isinstance(value.get("value"), str)
    ] if isinstance(raw_options, list) else []
    by_lower = {value.lower(): value for value in values}
    normalized = requested.lower()
    if normalized in by_lower:
        return by_lower[normalized]
    aliases = {
        "minimal": ("none", "off", "lowest"),
        "xhigh": ("extra-high", "extra_high", "maximum", "max"),
        "max": ("maximum", "xhigh", "extra-high", "extra_high"),
    }
    return next(
        (
            by_lower[candidate]
            for candidate in aliases.get(normalized, ())
            if candidate in by_lower
        ),
        None,
    )


def _summarize_acp_updates(
    transcript: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    response_chunks: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}
    for message in transcript:
        if message.get("method") != "session/update":
            continue
        params = message.get("params")
        update = params.get("update") if isinstance(params, dict) else None
        if not isinstance(update, dict):
            continue
        update_type = update.get("sessionUpdate")
        if update_type == "agent_message_chunk":
            content = update.get("content")
            if isinstance(content, dict) and content.get("type") == "text":
                text = content.get("text")
                if isinstance(text, str):
                    response_chunks.append(text)
        elif update_type == "tool_call":
            tool_calls.append(update)
        elif update_type == "usage_update":
            usage["context_used"] = update.get("used")
            usage["context_size"] = update.get("size")
            if isinstance(update.get("cost"), dict):
                usage["cost"] = update["cost"]
        telemetry = _find_token_telemetry(update)
        if telemetry:
            usage.update(telemetry)
    return "".join(response_chunks), tool_calls, usage


def _find_token_telemetry(value: Any) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if any(
                key in node
                for key in (
                    "input_tokens",
                    "output_tokens",
                    "cache_read_tokens",
                    "committed_credit_cost",
                    "committed_acu_cost",
                )
            ):
                candidates.append(node)
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    if not candidates:
        return {}
    raw = candidates[-1]
    return {
        key: raw.get(key)
        for key in (
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_creation_tokens",
            "reasoning_tokens",
            "request_id",
            "committed_credit_cost",
            "committed_acu_cost",
        )
        if key in raw
    }


def _write_agent_config(workspace: Path) -> Path:
    content = json.dumps(DEVIN_AGENT_CONFIG, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    path = workspace / f".agent-world-devin-{digest}.json"
    if not path.exists():
        try:
            path.write_text(content, encoding="utf-8")
        except FileExistsError:
            pass
    return path


def _jsonrpc_error_detail(value: Any) -> str:
    if not isinstance(value, dict):
        return _clean_detail(str(value))
    message = str(value.get("message") or "unknown JSON-RPC error")
    data = value.get("data")
    if data is not None and data != "":
        message = f"{message}: {data}"
    return _clean_detail(message)


def _failure_decision(message: str) -> AgentDecision:
    return AgentDecision(
        intent=message,
        actions=[{"type": "wait"}],
        messages=[],
        memory_updates=[],
    )


def _failure_detail(stdout: str, stderr: str) -> str:
    return _clean_detail(stderr.strip() or stdout.strip() or "unknown error")


def _clean_detail(detail: str) -> str:
    return " ".join(detail.split())[:1000]


def _subscription_environment() -> dict[str, str]:
    child_env = os.environ.copy()
    # Saved Devin login must be the only credential source.
    for key in (
        "ANTHROPIC_API_KEY",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CODEX_API_KEY",
        "CURSOR_API_KEY",
        "DEVIN_API_KEY",
        "DEVIN_MODEL",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "WINDSURF_API_KEY",
    ):
        child_env.pop(key, None)
    child_env["NO_COLOR"] = "1"
    return child_env


def _is_quota_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "acu limit",
            "credit balance",
            "credits exhausted",
            "limit reached",
            "quota",
            "rate limit",
            "too many requests",
            "usage limit",
        )
    )


def _is_auth_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "authentication required",
            "login required",
            "no credentials",
            "not logged in",
            "unauthorized",
        )
    )


def _is_provider_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "connection refused",
            "connection reset",
            "internal server error",
            "network error",
            "provider unavailable",
            "server overload",
            "service unavailable",
        )
    )


def _nonnegative_int(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


@lru_cache(maxsize=None)
def _devin_decision_working_directory(
    connector_profile: str = "connector-v2",
) -> str:
    if connector_profile == "connector-v3":
        configured = os.environ.get("AGENT_WORLD_PROVIDER_WORKSPACE_ROOT")
        if configured:
            root = Path(configured).expanduser()
        else:
            root = Path(tempfile.gettempdir()) / "agent-world-provider-workspaces"
        directory = root / "devin-connector-v3"
        directory.mkdir(parents=True, exist_ok=True)
        return str(directory)
    return tempfile.mkdtemp(prefix="agent-world-devin-stable-")


def _resolve_devin_executable() -> str:
    candidates = [
        shutil.which("devin"),
        str(Path.home() / ".local" / "bin" / "devin"),
        "/Applications/Devin.app/Contents/Resources/app/extensions/windsurf/devin/bin/devin",
        "/Applications/Windsurf.app/Contents/Resources/app/extensions/windsurf/devin/bin/devin",
        str(
            Path.home()
            / "Applications"
            / "Devin.app"
            / "Contents"
            / "Resources"
            / "app"
            / "extensions"
            / "windsurf"
            / "devin"
            / "bin"
            / "devin"
        ),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""
