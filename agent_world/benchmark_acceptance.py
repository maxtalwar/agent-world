"""Explicit owner decisions applied to derived views, never original reports."""
import copy
import hashlib
import json
from pathlib import Path


def accepted_report(root, path, report):
    catalog = Path(root) / "data/run-sources.json"
    if not catalog.exists():
        return report
    relative = str(Path(path).resolve().relative_to(Path(root).resolve()))
    decisions = json.loads(catalog.read_text()).get("benchmark_acceptances", [])
    entry = next((e for e in decisions if e["report_path"] == relative), None)
    if entry is None:
        return report
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != entry["report_sha256"]:
        raise ValueError("Owner acceptance does not match current report bytes")
    benchmark = report["benchmarks"]
    protocol, trial = benchmark["protocol"], benchmark["trial"]
    cohorts = list(benchmark["cohorts"].values())
    if (protocol["id"] != entry["recipe"] or protocol.get("recipe_fingerprint_sha256") != entry["recipe_sha256"]
            or trial["seed"] != entry["seed"] or not report["run"]["completed"]
            or any(c["model"] != entry["model"] for c in cohorts)):
        raise ValueError("Owner acceptance identity mismatch")
    if any(set(c.get("quality_flags", [])) - {"benchmark_code_fingerprint_mismatch"} for c in [trial, *cohorts]):
        raise ValueError("Owner acceptance does not waive other integrity failures")
    result = copy.deepcopy(report)
    result["owner_acceptance"] = entry
    for c in [result["benchmarks"]["trial"], *result["benchmarks"]["cohorts"].values()]:
        c["original_quality_flags"] = c.get("quality_flags", [])
        c["quality_flags"] = []
        c["protocol_compliant"] = True
    result["benchmarks"]["trial"]["certification"] = "eligible_replication"
    return result
