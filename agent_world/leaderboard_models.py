"""Server-owned model identities for the benchmark picker.

Connector advertisements are read-only. Historical run identities are never used;
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
    name = re.sub(r"-20[0-9]{6}$", "", model)
    name = re.sub(r"(?<=\d)-(?=\d)", ".", name)
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



def command_models(brain, environment):
    import json
    import tempfile
    commands = {"antigravity": ["agy", "models"], "grok": ["grok", "models"],
                "cursor": ["cursor-agent", "models"], "devin": ["devin", "models", "list"]}
    def run(args, **kwargs):
        binary = shutil.which(args[0], path=environment.get("PATH"))
        if not binary:
            raise ValueError("Connector is not installed")
        return subprocess.run([binary, *args[1:]], env=environment, capture_output=True,
                              text=True, timeout=25, check=True, **kwargs).stdout
    if brain == "claude":
        child = dict(environment)
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                    "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "CLAUDECODE"):
            child.pop(key, None)
        environment = child
        with tempfile.TemporaryDirectory(prefix="aw-model-catalog-") as workspace:
            output = run(["claude", "--print", "--input-format", "stream-json", "--output-format",
                          "stream-json", "--verbose", "--no-session-persistence", "--settings",
                          '{"disableAllHooks":true}', "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}'],
                         cwd=workspace, input=json.dumps({"type": "control_request", "request_id": "catalog",
                         "request": {"subtype": "initialize"}}) + "\n")
        for line in output.splitlines():
            row = json.loads(line)
            if row.get("type") == "control_response":
                models = row.get("response", {}).get("response", {}).get("models", [])
                return [(m["resolvedModel"], friendly(m["resolvedModel"]), m.get("supportedEffortLevels"))
                        for m in models if m.get("resolvedModel")]
        raise ValueError("No Claude model catalog returned")
    if brain in {"muse", "zcode"}:
        args = ["muse", "serve", "--no-session-log"] if brain == "muse" else ["zcode-cli", "app-server"]
        result = rpc_catalog(args, environment)
        return [(m.get("modelId") or m.get("model") or m.get("id"),
                 m.get("displayName") or friendly(m.get("modelId") or m.get("model") or m.get("id", "")), None)
                for m in result.get("models", result.get("data", []))]
    if brain == "openrouter":
        from urllib.request import urlopen
        with urlopen("https://openrouter.ai/api/v1/models", timeout=20) as response:
            models = json.load(response)["data"]
        return [(m["id"], m.get("name") or friendly(m["id"]), None) for m in models
                if "text" in m.get("architecture", {}).get("output_modalities", ["text"])
                and not m["id"].endswith(":batch") and m["id"] != "openrouter/auto"]
    output = re.sub(r"\x1b\[[0-9;]*m", "", run(commands[brain]))
    rows = []
    for line in output.splitlines():
        if brain == "antigravity":
            match = re.match(r"^([a-z0-9][\w./-]*)\t(.+)$", line.strip())
        elif brain == "grok":
            match = re.match(r"^\s*[*-]\s+(grok-[\w.-]+)", line)
        elif brain == "cursor":
            match = re.match(r"^([a-z0-9][\w./-]*) - (.+)$", line)
        else:
            match = re.match(r"^\s{2}([a-z0-9][\w./-]*)\s{2,}(.+?)\s+\[", line)
        if match and match[1] not in {"auto", "default"}:
            rows.append((match[1], match[2] if match.lastindex > 1 else friendly(match[1]), None))
    return rows


def rpc_catalog(args, environment):
    import json
    import queue
    import threading
    binary = shutil.which(args[0], path=environment.get("PATH"))
    if not binary:
        raise ValueError("Connector is not installed")
    process = subprocess.Popen([binary, *args[1:]], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, env=environment)
    messages = queue.Queue()
    def read():
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                pass
    threading.Thread(target=read, daemon=True).start()
    def send(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()
    def rpc(identifier, method, params):
        send({"jsonrpc": "2.0", "id": identifier, "method": method, "params": params})
        import time
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            message = messages.get(timeout=max(.1, deadline-time.monotonic()))
            if message.get("id") == identifier:
                if "error" in message:
                    raise ValueError("Connector rejected catalog request")
                return message["result"]
        raise ValueError("Catalog timed out")
    try:
        if args[0] == "zcode-cli":
            result = rpc(1, "workspace/readState", {"workspace": {
                "workspaceKey": str(Path.cwd()), "workspacePath": str(Path.cwd())}})
            return {"models": result.get("settings", {}).get("model", {}).get("available", [])}
        rpc(1, "initialize", {"clientInfo": {"name": "leaderboard", "version": "1"}})
        send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        return rpc(2, "model/list", {})
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()


def model_catalog(sources, client=None, environment=None):
    """Discover current models only; retained runs never supply identities."""
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed
    entries = {}
    warnings = []
    environment = environment or dict(os.environ)

    def add(brain, model, name=None, efforts=None, variants=None):
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/+\[\]\-]{0,127}", model):
            return
        entries[brain + ":" + model] = {
            "key": brain + ":" + model, "name": name or friendly(model),
            "lab": lab_for(model.split("/")[-1].removeprefix("cursor-")),
            "brain": brain, "connector": CONNECTORS.get(brain, brain),
            "model": model, "efforts": efforts, "variants": variants}

    if client:
        try:
            cursor = None
            while True:
                result = client.rpc("model/list", {"includeHidden": False, **({"cursor": cursor} if cursor else {})})
                for m in result.get("data", []):
                    add("codex", m["model"], efforts=[e["reasoningEffort"] for e in m.get("supportedReasoningEfforts", [])])
                cursor = result.get("nextCursor")
                if not cursor:
                    break
        except (OSError, RuntimeError, KeyError):
            warnings.append("Codex catalog unavailable; no historical models substituted.")
    brains = set().union(*(set(s["brains"]) for s in sources.values())) if sources else set()
    brains.discard("codex")
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(command_models, brain, environment): brain for brain in brains}
        for future in as_completed(futures):
            brain = futures[future]
            try:
                rows = future.result()
                if not rows:
                    raise ValueError("Empty catalog")
                grouped = {}
                for model, name, efforts in rows:
                    # Effort-bearing slugs are alternatives for one model; resolve
                    # the exact advertised slug only after selecting the recipe.
                    match = re.fullmatch(r"(.+)-(low|medium|high|xhigh|max)(-fast)?", model)
                    if match and brain in {"antigravity", "devin", "cursor"}:
                        base, effort, fast = match.groups()
                        base += fast or ""
                        group = grouped.setdefault(base, {"name": re.sub(
                            r"\s+(?:Extra High|XHigh|Low|Medium|High|Max)(?=\s+(?:Fast|\()|$)|\s*\((?:Low|Medium|High)\)$", "", name),
                            "variants": {}})
                        group["variants"][effort] = model
                    else:
                        add(brain, model, name, efforts)
                for model, group in grouped.items():
                    add(brain, model, group["name"], list(group["variants"]), group["variants"])
            except Exception:
                warnings.append(CONNECTORS.get(brain, brain) + " catalog unavailable; no historical models substituted.")
    return sorted(entries.values(), key=lambda m: (m["lab"], m["name"], m["brain"])), sorted(warnings)


def for_recipe(entries, source):
    effort = source["defaults"]["reasoning_effort"]
    result = []
    for m in entries:
        if m["brain"] not in source["brains"] or (m["efforts"] is not None and effort not in m["efforts"]):
            continue
        result.append({**m, "model": m["variants"].get(effort) if m["variants"] else m["model"]})
    native = {"openai": "codex", "anthropic": "claude", "google": "antigravity",
              "meta": "muse", "xai": "grok", "zai": "zcode"}
    result.sort(key=lambda m: (m["brain"] != native.get(m["lab"]), m["brain"] == "openrouter", m["name"]))
    chosen = {}
    for m in result:
        identity = re.sub(r"^[^:]+:\s*", "", m["name"]).lower()
        chosen.setdefault(identity, m)
    return sorted(chosen.values(), key=lambda m: (m["lab"], m["name"]))
