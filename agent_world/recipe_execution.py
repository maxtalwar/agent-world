"""Fail closed when a published benchmark's implementation drifts."""
import hashlib
import json
from pathlib import Path


def verify_recipe_execution(recipe, root=None):
    from agent_world.protocols import get_recipe
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    manifest = json.loads((root / "agent_world/recipe-execution-locks.json").read_text())
    lock = manifest["recipes"].get(recipe)
    if lock is None:
        raise ValueError(f"Benchmark {recipe} has no reviewed execution lock")
    if get_recipe(recipe).digest != lock["recipe_digest"]:
        raise ValueError(f"Benchmark {recipe} definition changed; publish a new recipe or review its restoration")
    changed = [name for name, expected in manifest["files"].items()
               if not (root / name).is_file() or hashlib.sha256((root / name).read_bytes()).hexdigest() != expected]
    if changed:
        raise ValueError(f"Benchmark {recipe} implementation changed: {', '.join(changed)}. "
                         "Review compatibility before launching; changed conditions need a new recipe.")
    return lock
