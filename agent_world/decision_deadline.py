"""One monotonic budget shared across preparation, retries and transport calls."""
from contextlib import contextmanager
from contextvars import ContextVar
import time

_deadline = ContextVar("decision_deadline", default=None)


@contextmanager
def decision_deadline(seconds):
    token = _deadline.set(time.monotonic() + seconds if seconds else None)
    try:
        yield
    finally:
        _deadline.reset(token)


def remaining_timeout(seconds):
    deadline = _deadline.get()
    if deadline is None:
        return seconds
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Logical decision deadline exceeded")
    return min(seconds, remaining)


def deadline_sleep(seconds):
    delay = remaining_timeout(seconds)
    time.sleep(delay)
    remaining_timeout(0.001)
