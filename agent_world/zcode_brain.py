"""Z.ai Coding Plan-backed AgentBrain implemented with the ZCode headless CLI."""

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
import uuid

from agent_world.brain_runtime import BrainRuntime
from agent_world.brain_boundary import CONNECTOR_PROFILES, normalize_connector_profile, normalize_conversation_mode
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
from agent_world.decision_outcome import failure_decision as _failure_decision
from agent_world.openrouter_brain import AGENT_DECISION_SCHEMA, SYSTEM_INSTRUCTIONS
from agent_world.provider_limits import is_quota_detail
from agent_world.provider_telemetry import record_provider_attempt

ZCODE_HARNESS_INSTRUCTIONS = (
    "This is a simulation decision, not a software-engineering task. "
    "Do not inspect files, run commands, browse, call tools, or delegate. "
    "Choose exactly one tick of behavior from the supplied rulebook and private observation. "
    "The simulation engine will validate every action. Return only the JSON object required "
    "by the output schema, with no markdown or commentary."
)
ZCODE_DISALLOWED_TOOLS = ",".join(
    (
        "Bash", "Read", "Edit", "Write", "Grep", "Glob", "WebFetch", "WebSearch",
    )
)


class ZCodeBrain:
    """Stateless GLM brain using the user's saved Z.ai Coding Plan login."""

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
        session_max_turns: int = 1,
    ):
        del session_max_turns
        connector_profile = normalize_connector_profile(connector_profile)
        conversation_mode = normalize_conversation_mode(conversation_mode)
        if connector_profile not in CONNECTOR_PROFILES:
            raise ValueError(f"unsupported connector profile: {connector_profile}")
        if conversation_mode != "fresh-conversation":
            raise ValueError("ZCodeBrain supports only stateless conversation mode")
        self.runtime = runtime or BrainRuntime()
        self.agent_id = agent_id
        self.connector_profile = connector_profile
        self.conversation_mode = conversation_mode
        self.model = model or os.environ.get("ZCODE_MODEL_ID", "glm-5.3")
        self.reasoning_effort = reasoning_effort or os.environ.get(
            "ZCODE_REASONING_EFFORT", "max"
        )
        if self.reasoning_effort != "max":
            raise ValueError(
                "ZCode CLI 0.16.5 exposes no reliable headless effort selector; "
                "the GLM-5.3 connector currently requires native max effort"
            )
        self.timeout_seconds = timeout_seconds or int(
            os.environ.get("ZCODE_TIMEOUT_SECONDS", "300")
        )
        self.timeout_retries = max(0, int(os.environ.get("ZCODE_TIMEOUT_RETRIES", "1")))
        self.executable = (
            executable or os.environ.get("ZCODE_EXECUTABLE") or _resolve_zcode_executable()
        )
        self.resolved_model = self.model
        if not self.executable:
            raise ValueError(
                "ZCode CLI is required for ZCodeBrain, but 'zcode-cli' was not found"
            )
        self._command_prefix = _zcode_command_prefix(self.executable)
        self._stable_work_dir = (
            _zcode_decision_working_directory(connector_profile)
            if connector_profile in {"connector-v2", "connector-v3"}
            else None
        )

    def preflight(self) -> str | None:
        """Verify CLI health and Coding Plan authentication without a model turn."""
        try:
            completed = subprocess.run(
                [*self._command_prefix, "doctor", "--json"],
                text=True,
                capture_output=True,
                timeout=min(self.timeout_seconds, 30),
                env=_coding_plan_environment(self.model),
                check=False,
            )
            doctor = json.loads(completed.stdout or "{}")
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            return f"ZCode provider unavailable: CLI preflight failed: {exc}"
        if completed.returncode != 0 or not isinstance(doctor, dict):
            detail = _failure_detail(None, completed.stdout, completed.stderr)
            return f"ZCode provider unavailable: CLI preflight failed: {detail}"
        error = _coding_plan_config_error(self.model)
        if error is not None:
            return error
        self.resolved_model = self.model
        return None

    def copy_preflight_state_from(self, other: Any) -> None:
        if not isinstance(other, ZCodeBrain):
            raise TypeError("ZCode preflight state must come from another ZCodeBrain")
        if (self.model, self.reasoning_effort) != (other.model, other.reasoning_effort):
            raise ValueError("ZCode preflight state requires matching model and effort")
        self.resolved_model = other.resolved_model

    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        blocking_failure = self.runtime.blocking_failure()
        if blocking_failure is not None:
            return _failure_decision(blocking_failure[1])
        static_context = build_static_context(observation.get("world", {}))
        dynamic_json = json.dumps(
            build_dynamic_observation(observation), separators=(",", ":"), sort_keys=True
        )
        prompt = build_zcode_prompt(static_context, dynamic_json)
        request_meta = {
            "agent_id": observation.get("self", {}).get("id"),
            "tick": observation.get("tick"),
            "agent_static_context_chars": len(static_context),
            "agent_dynamic_observation_chars": len(dynamic_json),
            "request_payload_bytes": len(prompt.encode("utf-8")),
            "static_prompt_sha256": hashlib.sha256(
                static_context.encode("utf-8")
            ).hexdigest(),
            "request_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "connector_profile": self.connector_profile,
            "conversation_mode": self.conversation_mode,
        }
        started_at = time.monotonic()
        try:
            completed = None
            for attempt in range(self.timeout_retries + 1):
                attempt_started_at = time.monotonic()
                try:
                    completed = self._execute(prompt)
                    break
                except subprocess.TimeoutExpired as exc:
                    self._record_timeout_event(
                        exc,
                        request_meta,
                        attempt=attempt + 1,
                        max_attempts=self.timeout_retries + 1,
                        duration_seconds=time.monotonic() - attempt_started_at,
                    )
                    if attempt >= self.timeout_retries:
                        raise
            assert completed is not None
            request_meta["duration_seconds"] = round(time.monotonic() - started_at, 3)
            result = _parse_result_json(completed.stdout)
            if completed.returncode != 0 or not isinstance(result, dict):
                detail = _failure_detail(result, completed.stdout, completed.stderr)
                if _is_quota_error(detail):
                    message = f"ZCode quota unavailable: {detail}"
                    record_provider_attempt(
                        self.runtime,
                        event_type="quota_exhausted",
                        failure_kind="quota",
                        provider="zcode_cli",
                        model=self.model,
                        response_model=self.resolved_model,
                        billing_mode="zai_coding_plan",
                        reasoning_effort=self.reasoning_effort,
                        request_meta=request_meta,
                        attempt=attempt + 1,
                        max_attempts=self.timeout_retries + 1,
                        duration_seconds=time.monotonic() - started_at,
                        detail=detail,
                    )
                    self.runtime.mark_quota_unavailable(message)
                    return _failure_decision(message)
                if _is_auth_error(detail):
                    message = f"ZCode authentication required: {detail}"
                    record_provider_attempt(
                        self.runtime,
                        event_type="authentication_required",
                        failure_kind="authentication",
                        provider="zcode_cli",
                        model=self.model,
                        response_model=self.resolved_model,
                        billing_mode="zai_coding_plan",
                        reasoning_effort=self.reasoning_effort,
                        request_meta=request_meta,
                        attempt=attempt + 1,
                        max_attempts=self.timeout_retries + 1,
                        duration_seconds=time.monotonic() - started_at,
                        detail=detail,
                    )
                    self.runtime.mark_authentication_required(message)
                    return _failure_decision(message)
                if _is_provider_error(detail):
                    message = f"ZCode provider unavailable: {detail}"
                    record_provider_attempt(
                        self.runtime,
                        event_type="provider_error",
                        failure_kind="provider",
                        provider="zcode_cli",
                        model=self.model,
                        response_model=self.resolved_model,
                        billing_mode="zai_coding_plan",
                        reasoning_effort=self.reasoning_effort,
                        request_meta=request_meta,
                        attempt=attempt + 1,
                        max_attempts=self.timeout_retries + 1,
                        duration_seconds=time.monotonic() - started_at,
                        detail=detail,
                    )
                    return _failure_decision(message)
                self._record_usage(
                    {},
                    result,
                    {
                        **request_meta,
                        **ambiguous_boundary_metadata(completed.stdout, detail),
                    },
                )
                return _failure_decision(f"ZCode boundary failed: {detail}")
            try:
                response, usage = extract_zcode_result(result)
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}"
                self._record_usage(
                    _best_effort_usage(result),
                    result,
                    {
                        **request_meta,
                        **ambiguous_boundary_metadata(completed.stdout, detail),
                    },
                )
                return _failure_decision(f"ZCode boundary failed: {detail}")
            payload = _extract_json_object(response)
            attribution = attribute_decision_failure(
                payload if payload is not None else response, AGENT_DECISION_SCHEMA
            )
            if attribution.origin == "model_output":
                detail = (
                    "Independent contract validation failed: "
                    f"{attribution.contract_validation.detail}"
                )
                self._record_usage(
                    usage, result, {**request_meta, **attribution.usage_metadata(detail)}
                )
                return _failure_decision(
                    attributed_failure_message("ZCode", attribution, detail)
                )
            try:
                decision = parse_agent_response(payload)
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}"
                self._record_usage(
                    usage, result, {**request_meta, **attribution.usage_metadata(detail)}
                )
                return _failure_decision(
                    attributed_failure_message("ZCode", attribution, detail)
                )
            if decision.intent.startswith("Invalid JSON response:"):
                detail = decision.intent
                self._record_usage(
                    usage, result, {**request_meta, **attribution.usage_metadata(detail)}
                )
                return _failure_decision(
                    attributed_failure_message("ZCode", attribution, detail)
                )
            self._record_usage(usage, result, request_meta)
            return decision
        except subprocess.TimeoutExpired:
            message = f"ZCode provider unavailable: exceeded {self.timeout_seconds}s timeout"
            return _failure_decision(message)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return _failure_decision(f"ZCode decision failed: {exc}")

    def _execute(self, prompt: str) -> subprocess.CompletedProcess[str]:
        if self._stable_work_dir is not None:
            return self._run_command(prompt, self._stable_work_dir)
        with tempfile.TemporaryDirectory(prefix="agent-world-zcode-") as temp_dir:
            return self._run_command(prompt, temp_dir)

    def _run_command(
        self, prompt: str, workspace: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self._command(prompt, workspace),
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            env=_coding_plan_environment(self.model),
            check=False,
        )

    def _command(self, prompt: str, workspace: str) -> list[str]:
        return [
            *self._command_prefix,
            "--prompt",
            prompt,
            "--output-format",
            "json",
            "--no-color",
            "--mode",
            "plan",
            f"--disallowed-tools={ZCODE_DISALLOWED_TOOLS}",
            "--cwd",
            workspace,
        ]

    def export_checkpoint_state(self) -> dict[str, Any]:
        return {
            "provider": "zcode_cli",
            "model": self.model,
            "resolved_model": self.resolved_model,
        }

    def restore_checkpoint_state(self, state: dict[str, Any]) -> None:
        if state.get("provider") not in {None, "zcode_cli"}:
            raise ValueError("checkpoint brain state is not for ZCode")
        if state.get("model") not in {None, self.model}:
            raise ValueError("checkpoint ZCode model does not match")
        if isinstance(state.get("resolved_model"), str):
            self.resolved_model = state["resolved_model"]

    def reset_conversation(self, reason: str) -> None:
        del reason

    def _record_usage(
        self,
        usage: dict[str, Any],
        result: dict[str, Any] | None,
        request_meta: dict[str, Any],
    ) -> None:
        projection = (result or {}).get("projection")
        self.runtime.record_usage(
            {
                "model": self.model,
                "response_model": self.resolved_model,
                "provider": "zcode_cli",
                "api_style": "zcode_headless_json",
                "base_url": None,
                "billing_mode": "zai_coding_plan",
                "reasoning_effort": self.reasoning_effort,
                "prompt_tokens": _usage_int(
                    usage, "inputTokens", "input_tokens", "promptTokens", "prompt_tokens"
                ),
                "cached_tokens": _usage_int(
                    usage,
                    "cachedInputTokens",
                    "cached_input_tokens",
                    "cacheReadInputTokens",
                    "cache_read_input_tokens",
                ),
                "completion_tokens": _usage_int(
                    usage,
                    "outputTokens",
                    "output_tokens",
                    "completionTokens",
                    "completion_tokens",
                ),
                "reasoning_tokens": _usage_int(
                    usage, "reasoningTokens", "reasoning_tokens"
                ),
                "cost": 0,
                "provider_reported_cost_usd": 0,
                "time": time.time(),
                "zcode_session_id": (result or {}).get("sessionId"),
                "zcode_trace_id": (result or {}).get("traceId"),
                "zcode_turn_id": (result or {}).get("turnId"),
                "zcode_event_count": (result or {}).get("eventCount"),
                "zcode_projection": projection if isinstance(projection, dict) else None,
                **request_meta,
            }
        )

    def _record_timeout_event(
        self,
        exc: subprocess.TimeoutExpired,
        request_meta: dict[str, Any],
        *,
        attempt: int,
        max_attempts: int,
        duration_seconds: float,
    ) -> None:
        stdout = _timeout_stream(exc.stdout)
        stderr = _timeout_stream(exc.stderr)
        self.runtime.record_provider_event(
            {
                "schema_version": 1,
                "event_id": str(uuid.uuid4()),
                "event_type": "request_timeout",
                "provider": "zcode_cli",
                "model": self.model,
                "response_model": self.resolved_model,
                "billing_mode": "zai_coding_plan",
                "reasoning_effort": self.reasoning_effort,
                "time": time.time(),
                "attempt": attempt,
                "max_attempts": max_attempts,
                "timeout_seconds": self.timeout_seconds,
                "duration_seconds": round(duration_seconds, 3),
                "provider_trace_id": None,
                "partial_stdout_bytes": len(stdout),
                "partial_stdout_sha256": (
                    hashlib.sha256(stdout).hexdigest() if stdout else None
                ),
                "partial_stderr_bytes": len(stderr),
                "partial_stderr_sha256": (
                    hashlib.sha256(stderr).hexdigest() if stderr else None
                ),
                **request_meta,
            }
        )


def build_zcode_prompt(static_context: str, dynamic_json: str) -> str:
    schema = json.dumps(AGENT_DECISION_SCHEMA, separators=(",", ":"), sort_keys=True)
    return (
        f"{ZCODE_HARNESS_INSTRUCTIONS}\n\n{SYSTEM_INSTRUCTIONS}\n\n{static_context}\n\n"
        f"Output schema:\n{schema}\n\n"
        f"The current private observation follows as JSON:\n{dynamic_json}"
    )


def extract_zcode_result(
    result: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    if not isinstance(result, dict):
        raise ValueError("ZCode did not return a JSON result object")
    response = result.get("response")
    if not isinstance(response, str) or not response.strip():
        raise ValueError("ZCode returned no decision response")
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    return response, usage


def _best_effort_usage(result: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(result, dict) and isinstance(result.get("usage"), dict):
        return result["usage"]
    return {}


def _usage_int(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _parse_result_json(stdout: str) -> dict[str, Any] | None:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None




def _timeout_stream(value: str | bytes | None) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace")
    return b""


def _failure_detail(
    result: dict[str, Any] | None, stdout: str, stderr: str
) -> str:
    if isinstance(result, dict):
        for key in ("error", "message", "response", "status"):
            detail = result.get(key)
            if isinstance(detail, str) and detail.strip():
                return " ".join(detail.split())[:1000]
    detail = stderr.strip() or stdout.strip() or "unknown error"
    return " ".join(detail.split())[:1000]


def _read_coding_plan_config() -> dict[str, Any] | None:
    configured = os.environ.get("ZCODE_CONFIG_PATH")
    path = Path(configured).expanduser() if configured else Path.home() / ".zcode" / "cli" / "config.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return config if isinstance(config, dict) else None


def _coding_plan_environment(model: str) -> dict[str, str]:
    child_env = os.environ.copy()
    for key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "ZAI_API_KEY",
        "ZHIPUAI_API_KEY",
        "ZCODE_API_KEY",
        "ZCODE_ENDPOINT",
        "ZCODE_BASE_URL",
    ):
        child_env.pop(key, None)
    config = _read_coding_plan_config() or {}
    providers = config.get("provider") or config.get("providers")
    zai = providers.get("zai") if isinstance(providers, dict) else None
    options = zai.get("options") if isinstance(zai, dict) else None
    api_key = options.get("apiKey") if isinstance(options, dict) else None
    base_url = options.get("baseURL") if isinstance(options, dict) else None
    if isinstance(api_key, str) and api_key.strip():
        child_env["ZCODE_API_KEY"] = api_key
    if isinstance(base_url, str) and base_url.strip():
        child_env["ZCODE_BASE_URL"] = base_url
    child_env["ZCODE_MODEL"] = model if "/" in model else f"zai/{model}"
    child_env["NO_COLOR"] = "1"
    return child_env


def _coding_plan_config_error(model: str) -> str | None:
    config = _read_coding_plan_config()
    if config is None:
        return (
            "ZCode provider unavailable: Z.ai Coding Plan is not configured; "
            "run `zcode-cli login --no-browser`."
        )
    providers = config.get("provider") or config.get("providers")
    zai = providers.get("zai") if isinstance(providers, dict) else None
    options = zai.get("options") if isinstance(zai, dict) else None
    api_key = options.get("apiKey") if isinstance(options, dict) else None
    if not isinstance(api_key, str) or not api_key.strip():
        return (
            "ZCode provider unavailable: Z.ai Coding Plan is not configured; "
            "run `zcode-cli login --no-browser`."
        )
    model_id = model.split("/", 1)[-1]
    models = zai.get("models") if isinstance(zai, dict) else None
    if not isinstance(models, dict) or model_id not in models:
        return (
            "ZCode provider unavailable: "
            f"{model_id} is absent from the local Z.ai Coding Plan model catalog; "
            "open ZCode Model Settings, enable the model, and retry."
        )
    return None


def _is_quota_error(detail: str) -> bool:
    return is_quota_detail(detail)


def _is_auth_error(detail: str) -> bool:
    lowered = detail.lower()
    return any(
        marker in lowered
        for marker in (
            "not logged in",
            "authentication required",
            "unauthorized",
            "model config is missing",
            "coding plan is not configured",
        )
    )


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


def _zcode_decision_working_directory(
    connector_profile: str = "stateless-v2",
) -> str:
    if normalize_connector_profile(connector_profile) == "connector-v3":
        configured = os.environ.get("AGENT_WORLD_PROVIDER_WORKSPACE_ROOT")
        root = (
            Path(configured).expanduser()
            if configured
            else Path(tempfile.gettempdir()) / "agent-world-provider-workspaces"
        )
        directory = root / "zcode-stateless-v3"
        directory.mkdir(parents=True, exist_ok=True)
        return str(directory)
    return tempfile.mkdtemp(prefix="agent-world-zcode-stable-")


def _zcode_command_prefix(executable: str) -> list[str]:
    """Invoke the bundled CJS directly when its env-node shebang is unavailable."""

    try:
        resolved = Path(executable).resolve(strict=True)
    except OSError:
        return [executable]
    if resolved.suffix != ".cjs":
        return [executable]
    node = _resolve_node_executable()
    return [node, str(resolved)] if node else [executable]


def _resolve_node_executable() -> str:
    discovered = shutil.which("node")
    if discovered:
        return discovered
    candidates = sorted(
        (Path.home() / ".local" / "lib" / "nodejs").glob("node-*/bin/node"),
        reverse=True,
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def _resolve_zcode_executable() -> str:
    candidates = [
        shutil.which("zcode-cli"),
        str(Path.home() / ".local" / "bin" / "zcode-cli"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""
