"""Server-owned model identities for the benchmark picker.

Connector advertisements are read-only. Historical identities are suggestions;
the managed startup gate still verifies account access before model calls.
"""
import re
import shutil
import subprocess
from pathlib import Path

CONNECTORS = {"codex": "Codex", "claude": "Claude Code", "antigravity": "Antigravity",
              "muse": "Muse", "grok": "Grok", "zcode": "ZCode", "openrouter": "OpenRouter",
              "cursor": "Cursor", "devin": "Devin"}


def recipe_label(recipe):
    return "Participant " + ("v8.1" if recipe == "participant-v8-revised"
                            else recipe.removeprefix("participant-").replace("-", " "))


def friendly(model):
    name = re.sub(r"(?<=\d)-(?=\d)", ".", model)
    name = name.replace("-", " ").title()
    return name.replace("Gpt ", "GPT-").replace("Glm ", "GLM ").replace("Qwen", "Qwen")


def lab_for(model):
    for prefix, lab in [("gpt", "openai"), ("claude", "anthropic"), ("gemini", "google"),
                        ("gemma", "google"), ("muse", "meta"), ("llama", "meta"),
                        ("grok", "xai"), ("glm", "zai"), ("qwen", "alibabacloud"),
                        ("kimi", "moonshot"), ("deepseek", "deepseek"),
                        ("mistral", "mistral"), ("minimax", "minimax")]:
        if model.lower().startswith(prefix):
            return lab
    return "unknown"


def model_catalog(sources, client=None, environment=None):
    entries = {}

    def add(brain, model, name=None, efforts=None, variants=None):
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/+\-]{0,127}", model):
            return
        key = brain + ":" + model
        entries[key] = {"key": key, "name": name or friendly(model), "lab": lab_for(model),
                        "brain": brain, "connector": CONNECTORS.get(brain, brain),
                        "model": model, "efforts": efforts, "variants": variants}

    for source in sources.values():
        for m in source.get("models", []):
            model, brain = m["id"], m["brain"]
            # Reporting cohort labels and diagnostic names are not provider IDs.
            if any(x in model for x in ("diagnostic", "build-", "oracle", "stealth-", "luna-max")):
                continue
            if brain != "antigravity":
                add(brain, model)

    warnings = []
    if client:
        try:
            live = []
            cursor = None
            while True:
                result = client.rpc("model/list", {"includeHidden": False, **({"cursor": cursor} if cursor else {})})
                live.extend(result.get("data", []))
                cursor = result.get("nextCursor")
                if not cursor:
                    break
            if live:
                entries = {k: v for k, v in entries.items() if v["brain"] != "codex"}
                for m in live:
                    add("codex", m["model"], efforts=[e["reasoningEffort"] for e in m.get("supportedReasoningEfforts", [])])
        except (OSError, RuntimeError, KeyError):
            warnings.append("Codex catalog could not refresh; showing known models.")
    binary = shutil.which("agy", path=(environment or {}).get("PATH"))
    if binary:
        try:
            result = subprocess.run([binary, "models"], env=environment, capture_output=True,
                                    text=True, timeout=20, check=True)
            grouped = {}
            for line in result.stdout.splitlines():
                parts = line.strip().split("\t", 1)
                if len(parts) != 2:
                    continue
                model, name = parts
                match = re.fullmatch(r"(.+)-(low|medium|high)", model)
                if match:
                    base, effort = match.groups()
                    group = grouped.setdefault(base, {"name": re.sub(r"\s*\((Low|Medium|High)\)$", "", name), "variants": {}})
                    group["variants"][effort] = model
                else:
                    add("antigravity", model, name)
            for model, group in grouped.items():
                add("antigravity", model, group["name"], list(group["variants"]), group["variants"])
        except (OSError, subprocess.SubprocessError):
            warnings.append("Antigravity catalog is unavailable.")
    # Prefer each lab's native connector when the same identity is advertised twice.
    native = {"openai": "codex", "anthropic": "claude", "google": "antigravity",
              "meta": "muse", "xai": "grok", "zai": "zcode"}
    ordered = sorted(entries.values(), key=lambda m: (
        m["brain"] != native.get(m["lab"]), m["name"]))
    result, seen = [], set()
    for entry in ordered:
        identity = entry["model"].removesuffix("-thinking")
        if identity in seen:
            continue
        seen.add(identity)
        result.append(entry)
    return sorted(result, key=lambda m: (m["lab"], m["name"])), warnings


def for_recipe(entries, source):
    effort = source["defaults"]["reasoning_effort"]
    result = []
    for m in entries:
        if m["brain"] not in source["brains"] or (m["efforts"] is not None and effort not in m["efforts"]):
            continue
        result.append({**m, "model": m["variants"].get(effort) if m["variants"] else m["model"]})
    return result
