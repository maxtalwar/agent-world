"""Explicit, versioned information policies; existing benchmarks use full-v1."""
from collections import Counter

HISTORY_POLICIES = frozenset({"full-v1", "bounded-v1"})


def apply_history_policy(observation, policy):
    if policy not in HISTORY_POLICIES:
        raise ValueError(f"Unknown observation history policy: {policy}")
    if policy == "full-v1":
        return observation
    contracts = observation.get("known_contracts", [])
    active = [row for row in contracts if row.get("status") in {"offered", "active", "proposed"}]
    closed = [row for row in contracts if row.get("status") not in {"offered", "active", "proposed"}]
    observation["known_contracts"] = active + closed[-12:]
    omitted = {"contracts": max(0, len(closed) - 12)}
    for group_id, group in observation.get("known_groups", {}).items():
        for key in ("rules", "agreements"):
            rows = group.get(key, [])
            group[key] = rows[-8:]
            omitted[f"group:{group_id}:{key}"] = max(0, len(rows) - 8)
    observation["history_policy"] = {
        "version": policy,
        "description": "All active obligations, 12 most recent closed contracts, 8 recent rules/agreements per group.",
        "contract_status_counts": dict(sorted(Counter(row.get("status", "unknown") for row in contracts).items())),
        "omitted": {key: value for key, value in omitted.items() if value},
    }
    return observation
