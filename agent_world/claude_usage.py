"""Read subscription reset windows without making model requests."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import urllib.request


def read_claude_usage():
    # Use exactly the environment/config directory used by the native CLI.
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if not token:
        config = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
        token = json.loads((config / ".credentials.json").read_text())["claudeAiOauth"]["accessToken"]
    request = urllib.request.Request("https://api.anthropic.com/api/oauth/usage", headers={
        "Authorization": "Bearer " + token, "anthropic-beta": "oauth-2025-04-20"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def exhausted_reset(usage, model, *, now=None):
    """Latest exhausted applicable window; incomplete/unknown scope stays unknown."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(usage, dict):
        return None
    deadlines = []
    model_tokens = set(re.findall(r"[a-z0-9]+", model.lower()))
    limits = usage.get("limits")
    if not isinstance(limits, list):
        return None
    for window in limits:
        if not isinstance(window, dict):
            return None
        scope = window.get("scope") or {}
        if scope.get("surface"):
            return None  # Do not guess applicability of an unfamiliar surface.
        scoped = scope.get("model") or {}
        if scoped:
            names = [scoped.get("id"), scoped.get("display_name")]
            if not any(name and set(re.findall(r"[a-z0-9]+", name.lower())) <= model_tokens for name in names):
                continue
        elif window.get("kind") == "weekly_scoped":
            return None
        percent = window.get("percent")
        if not isinstance(percent, (int, float)) or percent < 100:
            continue
        try:
            raw = window.get("resets_at")
            if not isinstance(raw, str):
                return None
            deadline = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if deadline.tzinfo is None or deadline <= now:
                return None
        except (KeyError, TypeError, ValueError):
            return None
        deadlines.append(deadline)
    return max(deadlines) if deadlines else None


def claude_quota_reset(model):
    try:
        return exhausted_reset(read_claude_usage(), model)
    except (OSError, ValueError, KeyError, TypeError):
        # Failed usage reads are uncertainty, never evidence of available quota.
        return None
