"""Price retained usage with the current shared rate card, without rewriting reports."""
from functools import lru_cache
from pathlib import Path
import json
import subprocess
import sys

_SCRIPT = """
import json,sys
from pathlib import Path
from agent_world.usage import summarize_usd_cost
from agent_world.run_report import _normalize_loaded_usage_record
rows=[_normalize_loaded_usage_record(json.loads(line)) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
seen=set()
unique=[]
for row in rows:
    identity=row.get('record_id')
    if identity and identity in seen: continue
    if identity: seen.add(identity)
    unique.append(row)
s=summarize_usd_cost(unique)
print(json.dumps(s['cost_usd']['total'] if s and s['available'] else None))
"""

@lru_cache(maxsize=512)
def _cost(root, usage, modified, size, pricing_modified):
    result = subprocess.run([sys.executable, "-c", _SCRIPT, usage], cwd=root,
                            capture_output=True, text=True, check=True, timeout=30)
    return json.loads(result.stdout)

def historical_run_cost(root, report_path):
    usage = Path(str(report_path).removesuffix("-report.json") + "-usage.jsonl")
    if not usage.is_file():
        return None
    try:
        stat = usage.stat()
        pricing_modified = max((Path(root)/"agent_world"/name).stat().st_mtime_ns
                               for name in ["usage.py", "main_harness_pricing.py"])
        return _cost(str(root), str(usage), stat.st_mtime_ns, stat.st_size, pricing_modified)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
