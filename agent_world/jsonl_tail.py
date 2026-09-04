"""Incremental JSONL projections that tolerate unfinished last lines."""
import json
import threading
from functools import lru_cache
from pathlib import Path


class JsonlTail:
    def __init__(self, path, types=None, latest=False):
        self.path = Path(path)
        self.types = types
        self.latest = latest
        self.offset = 0
        self.signature = None
        self.rows = []
        self.lock = threading.Lock()

    def read(self):
        with self.lock:
            try:
                stat = self.path.stat()
            except FileNotFoundError:
                self.rows = []
                self.offset = 0
                self.signature = None
                return self.rows
            signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
            if signature == self.signature:
                return self.rows
            if (self.signature is None or signature[:2] != self.signature[:2]
                    or stat.st_size < self.offset
                    or (stat.st_size == self.signature[2] and signature != self.signature)):
                self.rows = []
                self.offset = 0
            with self.path.open("rb") as handle:
                handle.seek(self.offset)
                while True:
                    line = handle.readline()
                    if not line:
                        break
                    if not line.endswith(b"\n"):
                        try:
                            json.loads(line)
                        except (ValueError, UnicodeDecodeError):
                            break
                    self.offset += len(line)
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if not isinstance(row, dict) or (self.types and row.get("type") not in self.types):
                        continue
                    if self.latest:
                        self.rows[:] = [row]
                    else:
                        self.rows.append(row)
            self.signature = signature
            return self.rows


@lru_cache(maxsize=32)
def tail_for(path: str, types: frozenset | None = None, latest: bool = False):
    return JsonlTail(path, types, latest)
