"""Machine-local setup and worker recommendations for Agent World.

The checked-in defaults are safe fallbacks, not benchmark requirements. A
host profile lets each clone reuse a machine-specific recommendation across
ordinary checkouts and isolated run worktrees without committing local state.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from agent_world.io import atomic_write_json
from typing import Any, Mapping


HOST_PROFILE_ENV = "AGENT_WORLD_HOST_PROFILE"
HOST_PROFILE_SCHEMA_VERSION = 1
MIB = 1024 * 1024
GIB = 1024 * MIB

# These preserve the known-good desktop recommendations when no setup profile
# exists. They are operational throughput defaults, never certification gates.
FALLBACK_GLOBAL_MAX_WORKERS = 40
FALLBACK_PROVIDER_MAX_WORKERS: dict[str, int] = {
    "openrouter": 4,
    "codex_cli": 40,
    "claude_cli": 20,
    "cursor_cli": 4,
    "devin_cli": 4,
    "grok_cli": 20,
    "zcode_cli": 20,
}

_HARNESS_COMMANDS: dict[str, tuple[str, ...]] = {
    "codex_cli": ("codex",),
    "claude_cli": ("claude",),
    "cursor_cli": ("cursor-agent",),
    "devin_cli": ("devin",),
    "grok_cli": ("grok",),
    "zcode_cli": ("zcode-cli",),
}


def default_host_profile_path() -> Path:
    override = os.environ.get(HOST_PROFILE_ENV)
    if override:
        return Path(override).expanduser()
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_root / "agent-world" / "host-profile.json"


def detect_host() -> dict[str, Any]:
    logical_cpus = max(1, os.cpu_count() or 1)
    total_memory_bytes = _total_memory_bytes()
    system = platform.system() or "unknown"
    release = platform.release()
    is_wsl = bool(
        os.environ.get("WSL_DISTRO_NAME")
        or "microsoft" in release.lower()
        or "microsoft" in _read_text(Path("/proc/sys/kernel/osrelease")).lower()
    )
    return {
        "system": system,
        "release": release,
        "machine": platform.machine() or "unknown",
        "logical_cpus": logical_cpus,
        "total_memory_bytes": total_memory_bytes,
        "total_memory_gib": round(total_memory_bytes / GIB, 2) if total_memory_bytes else None,
        "wsl": is_wsl,
    }


def recommend_worker_limits(host: Mapping[str, Any]) -> dict[str, Any]:
    """Estimate useful concurrency from the repository's measured local costs.

    The prior ramps found a CPU knee near 3.3 active CLI processes per logical
    CPU and roughly 70 MB RSS per Codex subprocess. We use 96 MiB for memory
    planning to leave room for the engine, logs, and connector variation.
    """

    logical_cpus = max(1, int(host.get("logical_cpus") or 1))
    total_memory_bytes = max(0, int(host.get("total_memory_bytes") or 0))

    cpu_ceiling = _round_down(max(4, logical_cpus * 10 // 3), 4)
    if total_memory_bytes:
        reserve = max(2 * GIB, total_memory_bytes // 4)
        worker_memory = max(96 * MIB, total_memory_bytes - reserve)
        memory_ceiling = max(1, worker_memory // (96 * MIB))
        if memory_ceiling >= 4:
            memory_ceiling = _round_down(memory_ceiling, 4)
    else:
        memory_ceiling = cpu_ceiling

    global_workers = max(1, min(cpu_ceiling, memory_ceiling))
    ordinary_default = min(4, global_workers)
    half_capacity = min(
        global_workers,
        max(ordinary_default, _round_down(max(1, global_workers // 2), 2)),
    )
    provider_workers = {
        "openrouter": ordinary_default,
        "codex_cli": global_workers,
        "claude_cli": half_capacity,
        "cursor_cli": ordinary_default,
        "devin_cli": ordinary_default,
        "grok_cli": half_capacity,
        "zcode_cli": half_capacity,
    }
    return {
        "ordinary_default": ordinary_default,
        "global": global_workers,
        "providers": provider_workers,
        "estimate": {
            "cpu_ceiling": cpu_ceiling,
            "memory_ceiling": memory_ceiling,
            "planning_memory_mib_per_worker": 96,
            "status": "estimated",
            "note": (
                "Codex is scaled to the measured host CPU knee. Claude, Grok, and "
                "ZCode start at half that ceiling pending harness-specific calibration; "
                "other providers retain the ordinary four-worker default."
            ),
        },
    }


def inspect_harnesses() -> dict[str, dict[str, Any]]:
    harnesses: dict[str, dict[str, Any]] = {
        "openrouter": {
            "installed": True,
            "executable": None,
            "note": "HTTP connector; requires OPENROUTER_API_KEY when used.",
        }
    }
    for provider, commands in _HARNESS_COMMANDS.items():
        executable = next(
            (path for command in commands if (path := shutil.which(command))),
            None,
        )
        harnesses[provider] = {
            "installed": executable is not None,
            "executable": executable,
            "note": "Authentication is checked separately by the native harness.",
        }
    return harnesses


def build_host_profile() -> dict[str, Any]:
    host = detect_host()
    return {
        "schema_version": HOST_PROFILE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": host,
        "workers": recommend_worker_limits(host),
        "harnesses": inspect_harnesses(),
    }


def load_host_profile(path: Path | None = None) -> dict[str, Any] | None:
    profile_path = path or default_host_profile_path()
    if not profile_path.exists():
        return None
    try:
        value = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read Agent World host profile {profile_path}: {exc}") from exc
    validate_host_profile(value)
    return value


def validate_host_profile(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("Agent World host profile must be a JSON object")
    if value.get("schema_version") != HOST_PROFILE_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported Agent World host profile schema: {value.get('schema_version')!r}"
        )
    workers = value.get("workers")
    if not isinstance(workers, dict):
        raise ValueError("Agent World host profile is missing workers")
    _positive_int(workers.get("global"), "workers.global")
    providers = workers.get("providers")
    if not isinstance(providers, dict):
        raise ValueError("Agent World host profile is missing workers.providers")
    for provider in FALLBACK_PROVIDER_MAX_WORKERS:
        if provider in providers:
            _positive_int(providers[provider], f"workers.providers.{provider}")


def write_host_profile(profile: Mapping[str, Any], path: Path | None = None) -> Path:
    validate_host_profile(dict(profile))
    profile_path = path or default_host_profile_path()
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(profile_path, dict(profile), fsync=True)
    return profile_path


def resolved_worker_recommendations(
    profile: Mapping[str, Any] | None = None,
) -> tuple[int, dict[str, int]]:
    if profile is None:
        profile = load_host_profile()
    if profile is None:
        return FALLBACK_GLOBAL_MAX_WORKERS, dict(FALLBACK_PROVIDER_MAX_WORKERS)
    validate_host_profile(profile)
    workers = profile["workers"]
    global_workers = int(workers["global"])
    configured = workers["providers"]
    providers = {
        provider: min(global_workers, int(configured.get(provider, fallback)))
        for provider, fallback in FALLBACK_PROVIDER_MAX_WORKERS.items()
    }
    return global_workers, providers


def format_setup_summary(profile: Mapping[str, Any], *, path: Path | None = None) -> str:
    host = profile["host"]
    workers = profile["workers"]
    providers = workers["providers"]
    lines = [
        "Agent World host profile",
        f"  system: {host['system']} {host['release']} ({host['machine']})",
        f"  WSL: {'yes' if host.get('wsl') else 'no'}",
        f"  logical CPUs: {host['logical_cpus']}",
        f"  visible RAM: {host.get('total_memory_gib') or 'unknown'} GiB",
        f"  ordinary default: {workers['ordinary_default']}",
        f"  estimated global ceiling: {workers['global']}",
        "  provider ceilings:",
    ]
    for provider in sorted(providers):
        status = profile.get("harnesses", {}).get(provider, {})
        installed = "installed" if status.get("installed") else "not found"
        lines.append(f"    {provider}: {providers[provider]} ({installed})")
    if path is not None:
        lines.append(f"  wrote: {path}")
    lines.append("  estimates are starting points; explicit run flags override them")
    return "\n".join(lines)


def _total_memory_bytes() -> int:
    if hasattr(os, "sysconf"):
        try:
            pages = int(os.sysconf("SC_PHYS_PAGES"))
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            if pages > 0 and page_size > 0:
                return pages * page_size
        except (OSError, TypeError, ValueError):
            pass
    if platform.system() == "Windows":
        try:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("memory_load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong),
                    ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong),
                    ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended_virtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.total_physical)
        except (AttributeError, OSError, TypeError, ValueError):
            pass
    if platform.system() == "Darwin":
        try:
            completed = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return max(0, int(completed.stdout.strip()))
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return 0


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed < 1 or parsed != value:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _round_down(value: int, multiple: int) -> int:
    return max(multiple, value - value % multiple)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
