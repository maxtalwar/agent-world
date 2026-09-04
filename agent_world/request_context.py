"""Run-owned request admission and correlation, shared across all transports."""
from contextlib import contextmanager
from contextvars import ContextVar
import math

_current = ContextVar("request_context", default=None)


class RunBudgetExceeded(RuntimeError):
    pass


@contextmanager
def request_context(runtime, agent_id, tick):
    parent = getattr(runtime, "parent", runtime)
    token = _current.set({"runtime": parent, "agent_id": agent_id, "tick": tick})
    try:
        yield
    finally:
        _current.reset(token)


def admit_attempt():
    context = _current.get()
    if context and context["runtime"] is not None:
        context.pop("transport_timings", None)
        context["attempt_id"] = context["runtime"].admit_attempt(context)


def request_identity():
    context = _current.get()
    return {key: context[key] for key in ("agent_id", "tick", "attempt_id", "transport_timings") if key in context} if context else {}


def validate_limits(limits):
    for name, value in limits.items():
        if name not in {"calls", "tokens", "cost_usd"} or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid run resource limit: {name}={value!r}")
        if name != "cost_usd" and type(value) is not int:
            raise ValueError(f"{name} limit must be an integer")


def record_transport_timing(timings):
    context = _current.get()
    if context:
        context["transport_timings"] = timings
