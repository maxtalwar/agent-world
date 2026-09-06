"""Server-owned model identities for the benchmark picker.

Connector advertisements are read-only. Historical run identities are never used;
the managed startup gate still verifies account access before model calls.
"""
import re
import json
import os
import time
import tempfile
import threading
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



_NATIVE_CHECKS = {}
_NATIVE_LOCK = threading.Lock()

def claude_explicit_model(model, environment):
    """Validate a current connector candidate with Claude's zero-inference /model command."""
    binary = shutil.which("claude", path=environment.get("PATH"))
    if not binary:
        return False
    key = (str(Path(binary).resolve()), Path(binary).stat().st_mtime_ns, model)
    with _NATIVE_LOCK:
        cached = _NATIVE_CHECKS.get(key)
        if cached and time.monotonic() - cached[0] < 600:
            return cached[1]
    child = dict(environment)
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                 "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "CLAUDECODE"):
        child.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="aw-model-check-") as cwd:
        result = subprocess.run([binary, "-p", "--output-format", "json", "--no-session-persistence",
            "--settings", '{"disableAllHooks":true}', "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}'],
            input="/model " + model, cwd=cwd, env=child, capture_output=True, text=True, timeout=25, check=True)
    response = json.loads(result.stdout)
    selected = re.search(r"^Set model to `([^`]+)` for this session only", response.get("result", ""))
    expected = friendly(model).removeprefix("Claude ").lower()
    valid = (not response.get("is_error") and response.get("num_turns") == 0
             and bool(selected) and selected[1].lower() == expected)
    with _NATIVE_LOCK:
        _NATIVE_CHECKS[key] = (time.monotonic(), valid)
    return valid


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
    if brain == "zcode":
        # Use the same configured Coding Plan catalog as ZCodeBrain's preflight.
        if not shutil.which("zcode-cli", path=environment.get("PATH")):
            raise ValueError("Connector is not installed")
        path = Path(environment.get("ZCODE_CONFIG_PATH") or Path.home() / ".zcode/cli/config.json").expanduser()
        config = json.loads(path.read_text())
        providers = config.get("provider") or config.get("providers") or {}
        models = (providers.get("zai") or {}).get("models") or {}
        return [(model, details.get("name") or friendly(model), None)
                for model, details in models.items() if isinstance(details, dict)]
    if brain == "muse":
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
    # The short Claude menu contains aliases, not every supported version.
    # Other live catalogs provide candidates only; Claude must accept each exact version.
    if "claude" in brains and any(m["brain"] == "claude" for m in entries.values()):
        candidates = set()
        for entry in list(entries.values()):
            model = entry["model"].split("/")[-1].replace(".", "-")
            if re.fullmatch(r"claude-(?:opus|sonnet|haiku|fable)-[0-9]+(?:-[0-9]+){0,3}", model):
                if "claude:" + model not in entries:
                    candidates.add(model)
        with ThreadPoolExecutor(max_workers=4) as pool:
            checks = {pool.submit(claude_explicit_model, model, environment): model for model in candidates}
            for future in as_completed(checks):
                try:
                    if future.result():
                        add("claude", checks[future], efforts=["low", "medium", "high"])
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass
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
