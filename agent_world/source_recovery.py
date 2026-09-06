"""Explicit connector migration: no automatic certification compatibility."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess


def validate_recovery_record(record_path, checkpoint, protocol, fingerprint, providers):
    record = json.loads(Path(record_path).read_text())
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    archive = Path(record["checkpoint_archive"])
    expected = {
        "schema_version": 1,
        "to_commit": commit,
        "protocol": protocol,
        "from_fingerprint": fingerprint,
        "providers": sorted(providers or []),
        "checkpoint": str(Path(checkpoint).resolve()),
        "certification": "requires_source_migration_review",
    }
    if any(record.get(k) != v for k, v in expected.items()):
        raise ValueError("Connector recovery record does not match this checkpoint/source/recipe")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != record.get("checkpoint_sha256"):
        raise ValueError("Archived pre-recovery checkpoint hash mismatch")
    if not record.get("reason") or not record.get("from_commit"):
        raise ValueError("Connector recovery requires historical source and reason")
    return record
