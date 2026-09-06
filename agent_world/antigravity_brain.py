"""Google account-backed decisions through the official Antigravity CLI."""
from __future__ import annotations

import json
import hashlib
import sqlite3
import uuid
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
            # The catalog works for ineligible accounts, and "agy agents"
            # produces empty stdout in 1.1.26 even for valid workspace agents.
            # /usage is handled by the CLI without inference and requires the
            # authenticated backend. Do not treat an empty report as success.
            with tempfile.TemporaryDirectory(prefix="agent-world-agy-preflight-") as workspace:
                self._prepare_workspace(workspace)
                quota = run_process([self.executable, "--print", "/usage"], cwd=workspace,
                                    capture_output=True, text=True, timeout=30,
                                    check=False, env=self._environment())
                rows = [line.split("\t") for line in quota.stdout.splitlines()]
                has_quota_report = any(
                    len(row) == 4
                    and row[1] in {"Weekly Limit Remaining", "Five Hour Limit Remaining"}
                    and re.fullmatch(r"(?:100|[0-9]{1,2})(?:\.[0-9]+)?%", row[2])
                    for row in rows
                )
                if quota.returncode or not has_quota_report:
                    return ("Antigravity account quota status unavailable. Complete agy onboarding "
                            "with an eligible account and verify agy --print /usage. "
                            "Model catalog access alone does not prove readiness.")
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
        return parse_antigravity_result(stdout, trace_root=Path.home() / ".gemini/antigravity-cli/conversations")


def parse_antigravity_result(stdout: str, *, trace_root: Path | None = None) -> dict[str, Any]:
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
    tool_steps = [row["step_update"] for row in events
                  if row.get("step_update", {}).get("step_type") == "tool"]
    tool_calls = len(tool_steps)
    trace_hash = None
    if tool_steps and trace_root is not None:
        tool_calls, trace_hash = audit_schema_finish_steps(
            tool_steps, result.get("conversation_id"), trace_root)

    return {
        "response": response, "error": None if result["status"] == "SUCCESS" else result.get("error") or result["status"],
        "response_model": result.get("model"), "observed_reasoning_effort": result.get("reasoning_effort"),
        "session_id": result.get("conversation_id"), "tool_calls": tool_calls,
        "trace_sha256": trace_hash,
        "usage": {"prompt_tokens": usage.get("input_tokens"), "completion_tokens": usage.get("output_tokens"),
                  "reasoning_tokens": usage.get("thinking_tokens"), "cached_tokens": usage.get("cache_read_tokens"),
                  "cache_write_tokens": usage.get("cache_write_tokens")},
    }


def _wire_fields(data: bytes) -> dict[int, list[Any]]:
    """Read only protobuf wire fields; reject malformed native evidence."""
    fields: dict[int, list[Any]] = {}
    pos = 0
    def varint():
        nonlocal pos
        value = 0
        for shift in range(0, 70, 7):
            if pos >= len(data):
                raise ValueError("truncated protobuf")
            byte = data[pos]
            pos += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError("oversized protobuf varint")
    while pos < len(data):
        tag = varint()
        field, wire = tag >> 3, tag & 7
        if not field:
            raise ValueError("invalid protobuf field")
        if wire == 0:
            value = varint()
        elif wire in (1, 2, 5):
            size = varint() if wire == 2 else (8 if wire == 1 else 4)
            if pos + size > len(data):
                raise ValueError("truncated protobuf field")
            value = data[pos:pos + size]
            pos += size
        else:
            raise ValueError("unsupported protobuf wire type")
        fields.setdefault(field, []).append(value)
    return fields


def _one(fields, key):
    values = fields.get(key, [])
    if len(values) != 1:
        raise ValueError("ambiguous native evidence field")
    return values[0]


def audit_schema_finish_steps(steps, session_id, trace_root):
    """Exempt only native finish calls authenticated by local CLI step records.

    CLI 1.1.27 sometimes emits finish-schema retries as generic `tool` updates.
    Step.metadata.tool_call.name (5/4/2) identifies the actual native operation;
    text, toolSummary and model-authored arguments are never allowlist evidence.
    Missing, foreign, malformed or external records retain the boundary failure.
    """
    try:
        if str(uuid.UUID(session_id)) != session_id:
            raise ValueError("invalid native session")
        path = trace_root / (session_id + ".db")
        digest = hashlib.sha256()
        external = 0
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
            for step in steps:
                idx = step.get("step_index")
                if step.get("conversation_id") != session_id or type(idx) is not int or idx < 0:
                    raise ValueError("foreign native step")
                row = conn.execute(
                    "SELECT step_type, has_subtrajectory, step_format, step_payload FROM steps WHERE idx=?",
                    (idx,),
                ).fetchone()
                if row is None or row[1] or row[2] != 0 or not isinstance(row[3], bytes):
                    raise ValueError("missing native step evidence")
                digest.update(str(idx).encode() + b":" + row[3])
                fields = _wire_fields(row[3])
                metadata = _wire_fields(_one(fields, 5))
                call = _wire_fields(_one(metadata, 4))
                name = _one(call, 2)
                if row[0] != 132 or _one(fields, 1) != 132 or name != b"finish":
                    external += 1
        return external, digest.hexdigest()
    except (ValueError, TypeError, AttributeError, OSError, sqlite3.Error):
        return len(steps), None
