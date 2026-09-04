"""Detect forbidden tool activity when a harness exposes it in its trace."""
import json


class ToolBoundaryError(RuntimeError):
    pass


def validate_tool_trace(text):
    for line in text.splitlines():
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        pending = [payload]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                kind = value.get("type") or value.get("sessionUpdate")
                if isinstance(kind, str) and kind in {
                    "command_execution", "file_change", "web_search", "mcp_tool_call",
                    "tool_call", "tool_use", "tool_call_update",
                } and value.get("name") not in {"StructuredOutput", "structured_output"}:
                    raise ToolBoundaryError(f"Harness exposed forbidden tool activity: {kind}")
                if value.get("tool_calls") or value.get("toolCalls"):
                    raise ToolBoundaryError("Harness exposed forbidden tool calls")
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
