"""Google account-backed decisions through the official Antigravity CLI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from agent_world.decision_contract import AGENT_DECISION_SCHEMA
from agent_world.headless_brain import BoundaryError, HARNESS_INSTRUCTIONS, HeadlessBrain
from agent_world.process_transport import run_process

AGENT_NAME = "agent-world-decision"


class AntigravityBrain(HeadlessBrain):
    provider = "antigravity_cli"
    label = "Antigravity"
    env_prefix = "ANTIGRAVITY"
    command_name = "agy"
    default_model = "gemini-3.7-flash-low"
    billing_mode = "google_ai_plan"
    api_style = "antigravity_stream_json"
    efforts = frozenset({"low", "medium", "high"})

    def _environment(self) -> dict[str, str]:
        env = os.environ.copy()
        for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GEMINI_BASE_URL"):
            env.pop(key, None)
        env["NO_COLOR"] = "1"
        return env

    def preflight(self) -> str | None:
        try:
            settings_path = Path.home() / ".gemini/antigravity-cli/settings.json"
            settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
            if not isinstance(settings, dict):
                return "Antigravity settings must contain a JSON object."
            if settings.get("modelProvider"):
                return "Antigravity connector requires Google account authentication; remove modelProvider from CLI settings."
            if settings.get("useG1Credits"):
                return "Antigravity credit overages are enabled; disable useG1Credits for subscription-only runs."
            version = run_process([self.executable, "--version"], capture_output=True, text=True,
                                  timeout=30, check=False, env=self._environment())
            if version.returncode:
                return "Antigravity CLI version check failed"
            current = version.stdout.strip()
            if self.cli_version and self.cli_version != current:
                return "Antigravity CLI version changed since checkpoint; explicit migration is required."
            self.cli_version = current
            models = run_process([self.executable, "models"], capture_output=True, text=True,
                                 timeout=30, check=False, env=self._environment())
            if models.returncode:
                return "Antigravity model catalog unavailable; run agy and complete Google sign-in."
            ids = set(re.findall(r"(?m)^\s*([a-z0-9][a-z0-9_.-]+)(?=\s|$)", models.stdout))
            if self.model not in ids:
                return f"Antigravity model {self.model!r} is absent from agy models; select an exact listed ID."
            suffix = self.model.rsplit("-", 1)[-1]
            if suffix in self.efforts and suffix != self.reasoning_effort:
                return "Antigravity model slug effort conflicts with requested reasoning effort."
            # A catalog is readable even when the account is ineligible. Require
            # the native CLI to actually initialize and discover our boundary.
            with tempfile.TemporaryDirectory(prefix="agent-world-agy-preflight-") as workspace:
                self._prepare_workspace(workspace)
                agents = run_process([self.executable, "agents"], cwd=workspace,
                                     capture_output=True, text=True, timeout=30,
                                     check=False, env=self._environment())
                if agents.returncode or not re.search(
                    rf"(?<![\w.-]){re.escape(AGENT_NAME)}(?![\w.-])", agents.stdout
                ):
                    return ("Antigravity cannot discover the isolated decision agent. "
                            "Complete agy onboarding with an eligible account; catalog access alone "
                            "does not prove readiness. Check native agent discovery before running.")
        except (OSError, ValueError, TimeoutError) as exc:
            return f"Antigravity preflight failed: {exc}"
        except subprocess.TimeoutExpired:
            return "Antigravity preflight timed out"
        return None

    def _prepare_workspace(self, workspace: str) -> None:
        definition = Path(workspace) / ".agents/agents" / AGENT_NAME / "agent.md"
        definition.parent.mkdir(parents=True)
        definition.write_text(
            f"---\nname: {AGENT_NAME}\ndescription: One isolated simulation decision.\n"
            "tools: []\nmcpServers: []\nskills: []\nplugins: []\n"
            "mainAgent: true\nsubagent: false\ncommandExecutionPolicy: 'off'\n---\n"
            + HARNESS_INSTRUCTIONS + "\n", encoding="utf-8")

    def _execute(self, prompt: str, workspace: str):
        self._prepare_workspace(workspace)
        command = [
            self.executable, "--print", prompt, "--model", self.model,
            "--effort", self.reasoning_effort, "--agent", AGENT_NAME,
            "--output-format", "stream-json", "--json-schema",
            json.dumps(AGENT_DECISION_SCHEMA, separators=(",", ":")),
            "--disable-slash-commands", "--sandbox",
            "--print-timeout", f"{self.timeout_seconds}s",
        ]
        return run_process(command, cwd=workspace, capture_output=True, text=True,
                           timeout=self.timeout_seconds, check=False, env=self._environment()), {}

    def _parse(self, stdout: str, artifacts: dict[str, Any]) -> dict[str, Any]:
        return parse_antigravity_result(stdout)


def parse_antigravity_result(stdout: str) -> dict[str, Any]:
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    if not events or any(not isinstance(row, dict) for row in events):
        raise BoundaryError("Antigravity returned no JSON events")
    finals = [row["result"] for row in events if row.get("event") == "result" and isinstance(row.get("result"), dict)]
    # JSON mode is useful for captured fixtures and older compatible CLI versions.
    if len(events) == 1 and "status" in events[0]:
        finals = events
    if len(finals) != 1:
        raise BoundaryError("Antigravity requires exactly one terminal result")
    result = finals[0]
    if result.get("status") not in {"SUCCESS", "ERROR", "CANCELED", "INTERRUPTED", "INVALID", "WAITING", "RUNNING"}:
        raise BoundaryError("Antigravity returned an unknown terminal status")
    usage = result.get("usage") or {}
    if not isinstance(usage, dict):
        raise BoundaryError("Antigravity usage is not an object")
    structured = result.get("structured_output")
    response = json.dumps(structured) if isinstance(structured, dict) else result.get("response")
    tool_calls = sum(row.get("step_update", {}).get("step_type") == "tool" for row in events)
    return {
        "response": response, "error": None if result["status"] == "SUCCESS" else result.get("error") or result["status"],
        "response_model": result.get("model"), "observed_reasoning_effort": result.get("reasoning_effort"),
        "session_id": result.get("conversation_id"), "tool_calls": tool_calls,
        "usage": {"prompt_tokens": usage.get("input_tokens"), "completion_tokens": usage.get("output_tokens"),
                  "reasoning_tokens": usage.get("thinking_tokens"), "cached_tokens": usage.get("cache_read_tokens"),
                  "cache_write_tokens": usage.get("cache_write_tokens")},
    }
