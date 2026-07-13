"""ChatGPT-plan-backed AgentBrain implemented with ``codex exec``.

Each decision is an independent, non-interactive Codex run.  The simulation
remains the source of agent memory and world state; Codex only receives the
current private observation and returns one schema-constrained decision.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import time
from typing import Any

from agent_world.brain_runtime import BrainRuntime
from agent_world.interface import (
    build_dynamic_observation,
    build_static_context,
    game_context_format,
    parse_agent_response,
)
from agent_world.models import AgentDecision
from agent_world.openai_brain import SYSTEM_INSTRUCTIONS
from agent_world.rules import ACTION_SCHEMA


CODEX_HARNESS_INSTRUCTIONS = (
    "This is a simulation decision, not a software-engineering task. "
    "Do not inspect files, run commands, browse, call tools, or delegate. "
    "Choose exactly one tick of behavior from the supplied rulebook and private observation. "
    "The simulation engine will validate every action. "
    "For each action, put its type in `type` and encode every other flat action field in "
    "`arguments_json` (use `{}` when there are no arguments). "
    "Return only the JSON object required by the output schema."
)


CODEX_AGENT_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["intent", "actions", "messages", "memory_updates"],
    "properties": {
        "intent": {"type": "string", "maxLength": 180},
        "actions": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "arguments_json"],
                "properties": {
                    "type": {"type": "string", "enum": [action["type"] for action in ACTION_SCHEMA]},
                    "arguments_json": {
                        "type": "string",
                        "description": "A JSON object containing flat action fields other than type; use {} when empty.",
                    },
                },
            },
        },
        "messages": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["mode", "text", "to"],
                "properties": {
                    "mode": {"type": "string", "enum": ["say", "whisper", "broadcast"]},
                    "text": {"type": "string", "maxLength": 240},
                    "to": {"type": "string", "description": "Target agent id, or an empty string when untargeted."},
                },
            },
        },
        "memory_updates": {
            "type": "array",
            "maxItems": 3,
            "items": {"type": "string", "maxLength": 180},
        },
    },
}


class CodexBrain:
    """Agent brain that spends saved ChatGPT/Codex plan capacity, not API credits."""

    def __init__(
        self,
        model: str | None = None,
        reasoning_effort: str | None = None,
        timeout_seconds: int | None = None,
        executable: str | None = None,
        runtime: BrainRuntime | None = None,
    ):
        self.runtime = runtime or BrainRuntime()
        self.model = model or os.environ.get("CODEX_MODEL", "gpt-5.6-luna")
        self.reasoning_effort = reasoning_effort or os.environ.get("CODEX_REASONING_EFFORT", "low")
        self.timeout_seconds = timeout_seconds or int(os.environ.get("CODEX_TIMEOUT_SECONDS", "300"))
        self.timeout_retries = max(0, int(os.environ.get("CODEX_TIMEOUT_RETRIES", "1")))
        self.executable = executable or os.environ.get("CODEX_EXECUTABLE") or _resolve_codex_executable()
        if not self.executable:
            raise ValueError("Codex CLI is required for CodexBrain, but 'codex' was not found on PATH.")

    def capture_plan_usage(self) -> dict[str, Any]:
        """Read the account's current Codex plan limits without spending a model turn.

        The app-server endpoint is account-level, so a before/after delta can also
        include Codex work running elsewhere on the same account.  Callers retain
        the raw checkpoints so resets and concurrent usage remain auditable.
        """

        captured_at = datetime.now(timezone.utc).isoformat()
        request_lines = [
            {
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "agent-world", "version": "0.1"},
                    "capabilities": {"experimentalApi": True},
                },
            },
            {"id": 2, "method": "account/rateLimits/read", "params": None},
        ]
        try:
            result = _read_plan_usage_from_app_server(
                self.executable,
                request_lines,
                timeout_seconds=min(self.timeout_seconds, 30),
            )
            return {"captured_at_utc": captured_at, "result": result}
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return {"captured_at_utc": captured_at, "error": f"{type(exc).__name__}: {exc}"}

    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        quota_message = self._quota_message()
        if quota_message is not None:
            return _failure_decision(quota_message)

        static_context = build_static_context(observation.get("world", {}))
        dynamic_json = json.dumps(build_dynamic_observation(observation), separators=(",", ":"), sort_keys=True)
        prompt = build_codex_prompt(static_context, dynamic_json)
        request_meta = {
            "agent_id": observation.get("self", {}).get("id"),
            "tick": observation.get("tick"),
            "agent_static_context_chars": len(static_context),
            "agent_dynamic_observation_chars": len(dynamic_json),
            "request_payload_bytes": len(prompt.encode("utf-8")),
            "static_prompt_sha256": hashlib.sha256(
                f"{SYSTEM_INSTRUCTIONS}\n\n{static_context}".encode("utf-8")
            ).hexdigest(),
            "game_static_context_sha256": hashlib.sha256(static_context.encode("utf-8")).hexdigest(),
            "game_dynamic_observation_sha256": hashlib.sha256(dynamic_json.encode("utf-8")).hexdigest(),
            "game_context_format": game_context_format(observation),
            "request_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        }

        started_at = time.monotonic()
        try:
            completed = None
            for attempt in range(self.timeout_retries + 1):
                try:
                    completed = self._execute(prompt)
                    break
                except subprocess.TimeoutExpired:
                    if attempt >= self.timeout_retries:
                        raise
            assert completed is not None
            elapsed = time.monotonic() - started_at
            if completed.returncode != 0:
                detail = _failure_detail(completed.stdout, completed.stderr)
                if _is_quota_error(detail):
                    message = f"Codex quota unavailable: {detail}"
                    self._mark_quota_unavailable(message)
                    return _failure_decision(message)
                raise ValueError(f"codex exec exited {completed.returncode}: {detail}")

            response_text, usage = parse_codex_jsonl(completed.stdout)
            self._record_usage(usage, request_meta | {"duration_seconds": round(elapsed, 3)})
            return parse_agent_response(normalize_codex_response(response_text))
        except subprocess.TimeoutExpired:
            return _failure_decision(f"Codex decision failed: exceeded {self.timeout_seconds}s timeout")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return _failure_decision(f"Codex decision failed: {exc}")

    def _execute(self, prompt: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="agent-world-codex-") as temp_dir:
            schema_path = Path(temp_dir) / "agent-decision.schema.json"
            schema_path.write_text(json.dumps(CODEX_AGENT_DECISION_SCHEMA, sort_keys=True), encoding="utf-8")
            command = self._command(schema_path)
            return subprocess.run(
                command,
                cwd=temp_dir,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                env=_plan_auth_environment(),
                check=False,
            )

    def _command(self, schema_path: Path) -> list[str]:
        return [
            self.executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--disable",
            "multi_agent",
            "--disable",
            "shell_tool",
            "--disable",
            "apps",
            "--model",
            self.model,
            "--config",
            f'model_reasoning_effort="{self.reasoning_effort}"',
            "--config",
            'approval_policy="never"',
            "--output-schema",
            str(schema_path),
            "--json",
            "-",
        ]

    def _record_usage(self, usage: dict[str, Any], request_meta: dict[str, Any]) -> None:
        record = {
            "model": self.model,
            "response_model": None,
            "provider": "codex_cli",
            "api_style": "codex_exec",
            "base_url": None,
            "billing_mode": "chatgpt_plan",
            "reasoning_effort": self.reasoning_effort,
            "prompt_tokens": usage.get("input_tokens", 0),
            "cached_tokens": usage.get("cached_input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "reasoning_tokens": usage.get("reasoning_output_tokens", 0),
            "cost": 0,
            "time": time.time(),
            **request_meta,
        }
        self.runtime.record_usage(record)

    def _quota_message(self) -> str | None:
        return self.runtime.quota_message()

    def _mark_quota_unavailable(self, message: str) -> None:
        self.runtime.mark_quota_unavailable(message)


def build_codex_prompt(static_context: str, dynamic_json: str) -> str:
    return (
        f"{CODEX_HARNESS_INSTRUCTIONS}\n\n"
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"{static_context}\n\n"
        f"The current private observation follows as JSON:\n{dynamic_json}"
    )


def parse_codex_jsonl(text: str) -> tuple[str, dict[str, Any]]:
    """Extract the final agent message and usage record from ``codex exec --json``."""

    final_message: str | None = None
    usage: dict[str, Any] = {}
    errors: list[str] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        event = json.loads(raw_line)
        event_type = event.get("type")
        item = event.get("item")
        if event_type == "item.completed" and isinstance(item, dict) and item.get("type") == "agent_message":
            if isinstance(item.get("text"), str):
                final_message = item["text"]
        elif event_type == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
        elif event_type in {"error", "turn.failed"}:
            detail = event.get("message") or event.get("error")
            if detail:
                errors.append(str(detail))
    if final_message is None:
        suffix = f": {'; '.join(errors)}" if errors else ""
        raise ValueError(f"codex exec returned no final agent message{suffix}")
    return final_message, usage


def summarize_plan_usage(checkpoints: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize account limit drawdown between successful raw checkpoints."""

    successful = [row for row in checkpoints if isinstance(row.get("result"), dict)]
    summary: dict[str, Any] = {
        "available": bool(successful),
        "checkpoint_count": len(checkpoints),
        "successful_checkpoint_count": len(successful),
        "attribution": (
            "Account-level observed delta during this run; concurrent Codex usage on the same account may be included."
        ),
        "buckets": {},
    }
    if not successful:
        summary["errors"] = [row.get("error") for row in checkpoints if row.get("error")]
        return summary

    before = successful[0]
    after = successful[-1]
    summary["started_at_utc"] = before.get("captured_at_utc")
    summary["ended_at_utc"] = after.get("captured_at_utc")
    before_buckets = _rate_limit_buckets(before["result"])
    after_buckets = _rate_limit_buckets(after["result"])
    for limit_id in sorted(set(before_buckets) | set(after_buckets)):
        before_bucket = before_buckets.get(limit_id, {})
        after_bucket = after_buckets.get(limit_id, {})
        bucket_summary: dict[str, Any] = {
            "limit_name": after_bucket.get("limitName") or before_bucket.get("limitName"),
            "plan_type": after_bucket.get("planType") or before_bucket.get("planType"),
        }
        for window_name in ("primary", "secondary"):
            bucket_summary[window_name] = _window_delta(
                before_bucket.get(window_name), after_bucket.get(window_name)
            )
        bucket_summary["credits"] = _credits_delta(
            before_bucket.get("credits"), after_bucket.get("credits")
        )
        bucket_summary["rate_limit_reached_type"] = after_bucket.get("rateLimitReachedType")
        summary["buckets"][limit_id] = bucket_summary
    return summary


def normalize_codex_response(text: str) -> str:
    """Convert strict Codex action wrappers back to Agent World's flat action shape."""

    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Codex decision was not a JSON object")
    actions: list[dict[str, Any]] = []
    for raw_action in value.get("actions", []):
        if not isinstance(raw_action, dict):
            continue
        action_type = raw_action.get("type")
        arguments_json = raw_action.get("arguments_json")
        if isinstance(arguments_json, str):
            arguments = _parse_action_arguments(arguments_json)
            if not isinstance(arguments, dict):
                raise ValueError("Codex action arguments_json must decode to an object")
            arguments.pop("type", None)
            actions.append({"type": action_type, **arguments})
        else:
            # Accept direct flat actions in mocked/legacy responses.
            actions.append(dict(raw_action))
    messages: list[dict[str, Any]] = []
    for raw_message in value.get("messages", []):
        if not isinstance(raw_message, dict):
            continue
        message = dict(raw_message)
        if not message.get("to"):
            message.pop("to", None)
        messages.append(message)
    normalized = {
        "intent": value.get("intent", ""),
        "actions": actions,
        "messages": messages,
        "memory_updates": value.get("memory_updates", []),
    }
    return json.dumps(normalized, separators=(",", ":"), sort_keys=True)


def _parse_action_arguments(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        stripped = text.lstrip()
        if stripped.startswith("```"):
            first_newline = stripped.find("\n")
            stripped = stripped[first_newline + 1 :] if first_newline >= 0 else stripped[3:]
        try:
            value, _ = json.JSONDecoder().raw_decode(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Codex action arguments_json is invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Codex action arguments_json must decode to an object")
    return value


def _failure_decision(message: str) -> AgentDecision:
    return AgentDecision(intent=message, actions=[{"type": "wait"}], messages=[], memory_updates=[])


def _failure_detail(stdout: str, stderr: str) -> str:
    errors: list[str] = []
    for raw_line in stdout.splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if event.get("type") in {"error", "turn.failed"}:
            detail = event.get("message") or event.get("error")
            if isinstance(detail, dict):
                detail = detail.get("message") or detail
            if detail:
                errors.append(str(detail))
    detail = errors[-1] if errors else (stderr.strip() or stdout.strip() or "unknown error")
    return " ".join(detail.split())[:1000]


def _plan_auth_environment() -> dict[str, str]:
    child_env = os.environ.copy()
    # API credentials take precedence for some non-interactive paths. Remove
    # them so both decisions and limit snapshots use the saved ChatGPT login.
    child_env.pop("CODEX_API_KEY", None)
    child_env.pop("OPENAI_API_KEY", None)
    child_env["NO_COLOR"] = "1"
    return child_env


def _read_plan_usage_from_app_server(
    executable: str,
    requests: list[dict[str, Any]],
    timeout_seconds: int,
) -> dict[str, Any]:
    process = subprocess.Popen(
        [executable, "app-server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_plan_auth_environment(),
    )
    if process.stdin is None or process.stdout is None:
        process.kill()
        raise ValueError("codex app-server did not expose stdio pipes")
    deadline = time.monotonic() + timeout_seconds
    try:
        for request in requests:
            process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            process.stdin.flush()
            result = _read_app_server_response(process, request["id"], deadline)
        return result
    finally:
        try:
            process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()


def _read_app_server_response(
    process: subprocess.Popen[str],
    request_id: int,
    deadline: float,
) -> dict[str, Any]:
    assert process.stdout is not None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, timeout=remaining)
        readable, _, _ = select.select([process.stdout], [], [], remaining)
        if not readable:
            raise subprocess.TimeoutExpired(process.args, timeout=remaining)
        raw_line = process.stdout.readline()
        if not raw_line:
            stderr = process.stderr.read() if process.stderr is not None else ""
            detail = " ".join(stderr.split()) or "app-server closed stdout"
            raise ValueError(f"codex app-server exited before response {request_id}: {detail[:1000]}")
        try:
            message = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if message.get("id") != request_id:
            continue
        if message.get("error") is not None:
            raise ValueError(f"codex app-server error: {message['error']}")
        result = message.get("result")
        if isinstance(result, dict):
            return result
        raise ValueError(f"codex app-server response {request_id} had no result object")


def _rate_limit_buckets(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    buckets = result.get("rateLimitsByLimitId")
    if isinstance(buckets, dict):
        return {str(key): value for key, value in buckets.items() if isinstance(value, dict)}
    legacy = result.get("rateLimits")
    if isinstance(legacy, dict):
        return {str(legacy.get("limitId") or "codex"): legacy}
    return {}


def _window_delta(before: Any, after: Any) -> dict[str, Any] | None:
    if not isinstance(before, dict) and not isinstance(after, dict):
        return None
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    before_used = before.get("usedPercent")
    after_used = after.get("usedPercent")
    same_window = bool(before) and bool(after) and before.get("resetsAt") == after.get("resetsAt")
    delta = None
    if same_window and isinstance(before_used, (int, float)) and isinstance(after_used, (int, float)):
        delta = after_used - before_used
    return {
        "before_used_percent": before_used,
        "after_used_percent": after_used,
        "used_percent_delta": delta,
        "window_duration_mins": after.get("windowDurationMins") or before.get("windowDurationMins"),
        "before_resets_at": before.get("resetsAt"),
        "after_resets_at": after.get("resetsAt"),
        "same_window": same_window,
    }


def _credits_delta(before: Any, after: Any) -> dict[str, Any] | None:
    if not isinstance(before, dict) and not isinstance(after, dict):
        return None
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    before_balance = before.get("balance")
    after_balance = after.get("balance")
    balance_delta: str | None = None
    try:
        if before_balance is not None and after_balance is not None:
            balance_delta = str(Decimal(str(after_balance)) - Decimal(str(before_balance)))
    except InvalidOperation:
        pass
    return {
        "before_balance": before_balance,
        "after_balance": after_balance,
        "balance_delta": balance_delta,
        "has_credits": after.get("hasCredits", before.get("hasCredits")),
        "unlimited": after.get("unlimited", before.get("unlimited")),
    }


def _is_quota_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "usage limit",
            "rate limit exceeded",
            "insufficient_quota",
            "quota unavailable",
            "credits exhausted",
        )
    )


@lru_cache(maxsize=1)
def _resolve_codex_executable() -> str:
    """Prefer the newest locally installed Codex binary (CLI or desktop bundle)."""

    candidates = [
        shutil.which("codex"),
        "/Applications/ChatGPT.app/Contents/Resources/codex",
        "/Applications/Codex.app/Contents/Resources/codex",
    ]
    available = [candidate for candidate in candidates if candidate and Path(candidate).is_file()]
    if not available:
        return ""
    return max(available, key=_codex_version)


def _codex_version(executable: str) -> tuple[int, ...]:
    try:
        completed = subprocess.run(
            [executable, "--version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()
    version_text = completed.stdout.strip().split()[-1] if completed.stdout.strip() else ""
    numeric = version_text.split("-", 1)[0]
    try:
        return tuple(int(part) for part in numeric.split("."))
    except ValueError:
        return ()
