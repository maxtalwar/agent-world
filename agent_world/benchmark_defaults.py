"""User launch preferences; never change a recipe's replication requirements."""
import re


def benchmark_seeds(model, required_seeds):
    """Fable defaults to one provisional world unless seeds are explicit."""
    if re.search(r"(?:^|[/ :_-])fable(?:$|[ /:_-]|[0-9])", str(model).lower()) and 41 in required_seeds:
        return [41]
    return list(required_seeds)
