"""Shared recognition of provider rate-limit and quota exhaustion messages.

Every model adapter used to carry its own list of quota marker strings. The
lists drifted: Claude's omitted "weekly limit", so when a Fable trial hit the
weekly cap the failure was classified as a generic boundary failure. The
harness then substituted a wait action for every agent and advanced the world
for eighteen ticks against a provider that was refusing every call. One shared
classifier removes the whole class of drift.

Matching is deliberately generous. A false positive pauses a run that could
have continued and is recovered by resuming a checkpoint; a false negative
silently fabricates agent behavior, which corrupts the trial. The two errors
are not remotely symmetric.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Literal fragments that appear in provider quota/rate-limit errors. Union of
# what the Claude, Codex, and Cursor adapters each carried separately.
QUOTA_MARKERS: tuple[str, ...] = (
    "usage limit",
    "session limit",
    "weekly limit",
    "daily limit",
    "hourly limit",
    "monthly limit",
    "rate limit",
    "rate_limit",
    "limit reached",
    "out of extra usage",
    "out of usage credits",
    "insufficient_quota",
    "quota exceeded",
    "quota unavailable",
    "credit balance is too low",
    "credits exhausted",
    "too many requests",
)

# Shapes that no fixed marker list can enumerate, because providers reword
# them. "You've hit your weekly limit" is the exact phrasing that escaped the
# old lists; the first pattern generalizes the whole family.
QUOTA_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "hit your weekly limit", "reached the usage limit", "exceeded your limit"
    re.compile(r"\b(?:hit|reached|exceeded)\b[^.]{0,40}?\blimits?\b"),
    # "limit · resets 2pm", "limit will reset at 10:00"
    re.compile(r"\blimits?\b[^.]{0,40}?\breset"),
    re.compile(r"\b429\b"),
)


def is_quota_detail(detail: str | None) -> bool:
    """Return whether a provider error means "out of quota", not "bad output"."""

    if not detail:
        return False
    lowered = detail.lower()
    if any(marker in lowered for marker in QUOTA_MARKERS):
        return True
    return any(pattern.search(lowered) for pattern in QUOTA_PATTERNS)


_RELATIVE_PATTERN = re.compile(
    r"\b(?:try again|retry|resets?|available again)\b[^.]{0,20}?\bin\s+"
    r"(?:(\d+)\s*h(?:ours?|rs?)?)?\s*(?:(\d+)\s*m(?:in(?:ute)?s?)?)?"
    r"\s*(?:(\d+)\s*s(?:ec(?:ond)?s?)?)?",
    re.IGNORECASE,
)
_RETRY_AFTER_PATTERN = re.compile(r"retry[-_ ]after[:=\s]+(\d+)", re.IGNORECASE)
_ISO_PATTERN = re.compile(
    r"reset(?:s|s at|_at)?[:=\s]+(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)",
    re.IGNORECASE,
)
# "resets 2pm (America/Los_Angeles)", "resets at 10:30am (UTC)"
_CLOCK_PATTERN = re.compile(
    r"reset(?:s|s at)?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
    r"(?:\s*\(([A-Za-z_]+(?:/[A-Za-z_+\-0-9]+)?)\))?",
    re.IGNORECASE,
)


def quota_reset_at(detail: str | None, *, now: datetime | None = None) -> datetime | None:
    """Parse the provider's stated reset time, if it states one.

    Returns an aware UTC datetime, or None when the message carries no usable
    hint. A parsed time lets a paused run sleep once until the cap lifts
    instead of probing on a blind interval and burning failed calls.
    """

    if not detail:
        return None
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    match = _RETRY_AFTER_PATTERN.search(detail)
    if match:
        return reference + timedelta(seconds=int(match.group(1)))

    match = _RELATIVE_PATTERN.search(detail)
    if match and any(match.group(index) for index in (1, 2, 3)):
        return reference + timedelta(
            hours=int(match.group(1) or 0),
            minutes=int(match.group(2) or 0),
            seconds=int(match.group(3) or 0),
        )

    match = _ISO_PATTERN.search(detail)
    if match:
        try:
            parsed = datetime.fromisoformat(match.group(1).replace(" ", "T"))
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)

    match = _CLOCK_PATTERN.search(detail)
    if match:
        return _next_wall_clock(match, reference)
    return None


def _next_wall_clock(match: re.Match[str], reference: datetime) -> datetime | None:
    """Resolve "resets 2pm (America/Los_Angeles)" to the next such instant."""

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None

    zone: timezone | ZoneInfo = timezone.utc
    name = match.group(4)
    if name:
        try:
            zone = ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            zone = timezone.utc

    local_now = reference.astimezone(zone)
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)
