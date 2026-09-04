"""Structural action validation; world handlers still own feasibility and costs."""
import math

_BUNDLES = {"items", "give", "receive", "collateral", "advance", "repayment", "fee"}
_NUMBERS = {"x", "y", "quantity", "lots", "expires_in", "deadline_tick", "due_in"}


def action_shape_error(action):
    for key, value in action.items():
        if key == "parties" and not isinstance(value, list):
            return "Agreement parties must be a list."
        if key in _BUNDLES and value is not None and not isinstance(value, dict):
            return f"{key} must be an item-count object."
        if key == "public" and not isinstance(value, bool):
            return "public must be a boolean."
        if key in _NUMBERS and value is not None:
            if isinstance(value, (bool, list, dict)):
                return f"{key} must be a number."
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, float) and not math.isfinite(item):
                return f"{key} must contain only finite numbers."
            if isinstance(item, dict):
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
    return None
