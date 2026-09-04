"""Small atomic artifact-writing helpers shared by run entry points."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


def atomic_write_text(path: Path, text: str, *, fsync: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
        os.replace(temporary, path)
        if fsync:
            fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(path: Path, value: Any, *, fsync: bool = False) -> None:
    atomic_write_text(
        path,
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        fsync=fsync,
    )


def fsync_directory(path: Path) -> None:
    """Make a successful atomic rename durable on supported POSIX filesystems."""
    if os.name != "posix":
        return
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    """Read durable records, tolerating only an unfinished trailing write."""
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                if not line.endswith("\n"):
                    break
                raise ValueError(f"Corrupt ledger {path.name}, line {number}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Non-object ledger record in {path.name}, line {number}")
            records.append(row)
    return records
