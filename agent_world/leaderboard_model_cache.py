"""Persistent daily model discovery, independent of recipe and launch readiness."""
from __future__ import annotations
import fcntl
import json
import os
from pathlib import Path
import time

REFRESH_SECONDS = 24 * 60 * 60


def saved_catalog(path, discover):
    """Refresh on use once daily, including failed attempts, across processes/restarts."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    def write(value):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value))
        os.replace(temporary, path)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            saved = json.loads(path.read_text())
        except (OSError, ValueError):
            saved = {}
        if saved.get("next_refresh", 0) > time.time():
            return saved.get("models", []), saved.get("warnings", [])
        # Persist the backoff before calling providers so a crash cannot cause a retry loop.
        saved.update(next_refresh=time.time() + REFRESH_SECONDS)
        write(saved)
        try:
            models, warnings = discover()
        except Exception:
            models, warnings = [], ["Model catalog refresh failed; saved models remain available until the next daily check."]
        if warnings:
            # A partial discovery must not erase previously verified availability.
            merged = {m["key"]: m for m in saved.get("models", [])}
            merged.update({m["key"]: m for m in models})
            models = list(merged.values())
        saved.update(models=models, warnings=warnings, checked_at=time.time())
        write(saved)
        return models, warnings
