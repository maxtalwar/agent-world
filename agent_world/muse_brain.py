"""Meta account-backed decisions through Muse Code's native headless CLI."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from agent_world.headless_brain import BoundaryError, HeadlessBrain, resolve_executable
from agent_world.process_transport import run_process

REMINDERS = ("skill-reminder", "goal-reminder", "verify-reminder", "scope-reminder", "todo-reminder", "memory")


def muse_settings() -> dict[str, Any]:
    return {"schema_version": 1, "runtime_capabilities": {
        f"plugin:tbh-reminders:reminder:{name}": {"enabled": False} for name in REMINDERS
    }}


def muse_auth_path() -> Path:
    return Path(os.environ.get("MUSE_AUTH_PATH") or
                str(Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "muse/auth.json"))


def pinned_muse_executable() -> str:
    launcher = resolve_executable("muse")
    if not launcher:
        return ""
    # Hash and run the actual native binary, not the auto-updating shell launcher.
    version_path = Path(launcher).parent / ".muse-version"
    if version_path.is_file():
        version = version_path.read_text().strip()
        if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-R[0-9]+(?:\.[0-9]+)?", version):
            binary = version_path.parent / f"muse-bin-{version}"
            if binary.is_file():
                return str(binary)
    return launcher


class MuseBrain(HeadlessBrain):
    provider = "muse_cli"
    label = "Muse Code"
    env_prefix = "MUSE"
    command_name = "muse"
    default_model = "muse-spark-1.3"
    billing_mode = "meta_account"
    api_style = "muse_exec_jsonl"
    efforts = frozenset({"minimal", "low", "medium", "high", "xhigh", "max"})

    def __init__(self, model=None, reasoning_effort=None, timeout_seconds=None, executable=None,
                 runtime=None, agent_id=None, connector_profile="connector-v1",
                 conversation_mode="fresh-conversation", session_max_turns=1):
        super().__init__(model, reasoning_effort, timeout_seconds,
                         executable or os.environ.get("MUSE_EXECUTABLE") or pinned_muse_executable(),
                         runtime, agent_id, connector_profile, conversation_mode, session_max_turns)

    def preflight(self) -> str | None:
        try:
            version = run_process([self.executable, "--version"], capture_output=True, text=True, timeout=30, check=False,
                                  env={**os.environ, "MUSE_NO_AUTO_UPDATE": "1"})
            if version.returncode:
                return "Muse Code version check failed"
            current = version.stdout.strip()
            if self.cli_version and self.cli_version != current:
                return "Muse Code version changed since checkpoint; explicit migration is required."
            self.cli_version = current
            auth = muse_auth_path()
            if not auth.is_file() or auth.stat().st_size == 0:
                return "Muse Code account credentials absent; run muse login."
            # Do not issue a paid prompt merely to prove account/model entitlement.
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return f"Muse Code preflight failed: {exc}"
        return None

    def _environment(self, workspace: str) -> dict[str, str]:
        env = os.environ.copy()
        auth = muse_auth_path().resolve()
        for key in ("META_API_KEY", "MODEL_API_KEY", "OPENAI_API_KEY", "MUSE_BASE_URL",
                    "META_BASE_URL", "MUSE_CUSTOM_HEADERS", "MUSE_WWW_ROUTING"):
            env.pop(key, None)
        root = Path(workspace)
        config = root / "config/muse"
        config.mkdir(parents=True)
        (config / "settings.json").write_text(json.dumps(muse_settings()), encoding="utf-8")
        # Keep authentication in the user's credential store. Only a reference is
        # made; settings, memory, logs, and plugins are private to this invocation.
        if auth.is_file():
            (config / "auth.json").symlink_to(auth)
        env.update({"XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data"),
                    "MUSE_AUTH_PATH": str(auth), "MUSE_NO_AUTO_UPDATE": "1", "NO_COLOR": "1"})
        return env

    def _execute(self, prompt: str, workspace: str):
        env = self._environment(workspace)
        work = Path(workspace) / "work"
        work.mkdir()
        prompt_file = Path(workspace) / "prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        command = [
            self.executable, "exec", "--json", "--provider", "meta", "--model", self.model,
            "--reasoning-effort", self.reasoning_effort, "--workspace", str(work),
            "--prompt-file", str(prompt_file), "--max-model-steps", "1",
            "--disable-shell", "--disable-write", "--disable-web-tools",
            "--no-foreign-personal-context", "--approval-mode", "untrusted",
            "--approval-judge", "off", "--no-parallel-tool-calls",
        ]
        completed = run_process(command, cwd=str(work), text=True, capture_output=True,
                                timeout=self.timeout_seconds, check=False, env=env)
        return completed, {"data_root": str(Path(workspace) / "data/muse/sessions")}

    def _parse(self, stdout: str, artifacts: dict[str, Any]) -> dict[str, Any]:
        result = parse_muse_result(stdout)
        root = Path(artifacts["data_root"])
        session_id = result["session_id"]
        if not isinstance(session_id, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", session_id):
            raise BoundaryError("Muse returned an invalid session ID")
        matches = list(root.glob(f"*/*/*/{session_id}/session.jsonl"))
        if len(matches) > 1:
            raise BoundaryError("Muse session log is ambiguous")
        if matches:
            trace = matches[0].read_text(encoding="utf-8")
            facts = parse_muse_trace(trace, result["run_id"])
            facts["tool_calls"] = max(result.get("tool_calls", 0), facts.get("tool_calls", 0))
            result.update(facts)
            result["trace_sha256"] = hashlib.sha256(trace.encode()).hexdigest()
        return result


def parse_muse_result(stdout: str) -> dict[str, Any]:
    rows = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise BoundaryError("Muse returned no JSONL event stream")
    session_ids = {row.get("stream", {}).get("id") for row in rows}
    if len(session_ids) != 1 or None in session_ids:
        raise BoundaryError("Muse mixed or omitted session identities")
    finals = [row["payload"] for row in rows if str(row.get("payload_type", "")).startswith("run.terminal.")]
    if len(finals) != 1 or not isinstance(finals[0], dict):
        raise BoundaryError("Muse requires exactly one terminal event")
    final = finals[0]
    run_id = final.get("run_stream", {}).get("id")
    if not run_id or any(row.get("payload", {}).get("run_stream", {}).get("id", run_id) != run_id for row in rows):
        raise BoundaryError("Muse mixed run identities")
    if final.get("terminal") not in {"completed", "failed", "cancelled"}:
        raise BoundaryError("Muse returned an unknown terminal status")
    return {
        "response": final.get("text"), "session_id": next(iter(session_ids)), "run_id": run_id,
        "error": None if final["terminal"] == "completed" else final.get("reason") or final["terminal"],
        "usage": {}, "tool_calls": sum(
            row.get("payload", {}).get("event", {}).get("task_kind", "").startswith(
                ("tool.", "reminder.", "workflow.", "agent."))
            for row in rows if row.get("payload_type") == "task.lifecycle.proposed"),
    }


def parse_muse_trace(trace: str, run_id: str) -> dict[str, Any]:
    """Read only model-completion facts for this root run; never sum mirrored usage."""
    completions, tool_calls, first_token, seen = [], 0, None, set()
    for line in trace.splitlines():
        row = json.loads(line)
        payload = row.get("payload", {})
        if row.get("payload_type") != "runtime.session" or payload.get("run_id") != run_id:
            continue
        source_id = payload.get("source_run_record_id")
        if source_id and source_id in seen:
            continue
        if source_id:
            seen.add(source_id)
        event = payload.get("event", {})
        kind = event.get("kind", "")
        if kind == "model_completed":
            completions.append(event)
        elif kind.startswith(("tool_", "subagent_", "workflow_")):
            tool_calls += 1
        elif kind == "terminal":
            first_token = event.get("time_to_first_token_ms")
    if len(completions) > 1:
        raise BoundaryError("Muse made multiple model completions for one decision")
    if not completions:
        return {"usage": {}, "tool_calls": tool_calls}
    fact = completions[0]
    raw = fact.get("usage")
    if not isinstance(raw, dict):
        raise BoundaryError("Muse model completion has no usage object")
    return {
        # Muse 1.0.3 copies the request model here, even if the API returns
        # a different ID. This is configuration evidence, not observed identity.
        "native_configured_model": fact.get("model"), "model_provenance": "requested_only",
        "tool_calls": tool_calls,
        "time_to_first_token_ms": first_token,
        "usage": {"prompt_tokens": raw.get("input_tokens"), "completion_tokens": raw.get("output_tokens"),
                  "cached_tokens": raw.get("cache_read_tokens", raw.get("cached_tokens")),
                  "cache_write_tokens": raw.get("cache_write_tokens"), "reasoning_tokens": raw.get("reasoning_tokens")},
    }
