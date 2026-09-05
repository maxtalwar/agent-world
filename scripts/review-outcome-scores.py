#!/usr/bin/env python3
"""Review new outcome components on frozen evidence; never rewrite reports.

Input: JSON object mapping study labels to lists of report paths.
Output: provenance, source hashes, additive counts, and old/new scores.
Run from the repository root with --studies PATH --out NEW_PATH.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_world.outcome_scoring import (
    SCORING_COMPONENT_VERSION, ScoringEvidenceError,
    derive_outcome_counts, score_outcome_counts,
)


def review(studies):
    output = {"evidence_class": "counterfactual_scoring_review",
              "scoring_component_version": SCORING_COMPONENT_VERSION, "studies": {}}
    for label, paths in studies.items():
        total, cells = {}, []
        study_identity = None
        for path in paths:
            p = Path(path)
            report = json.loads(p.read_text())
            snapshot_path = p.with_name("run-snapshot.json")
            events_path = p.with_name("run.jsonl")
            manifest_path = p.with_name("run-manifest.json")
            snapshot = json.loads(snapshot_path.read_text())
            events = [json.loads(line) for line in events_path.open()]
            manifest = json.loads(manifest_path.read_text())
            cohorts = report["benchmarks"]["cohorts"]
            if len(cohorts) != 1:
                raise ScoringEvidenceError("Review each cohort explicitly for mixed populations")
            cohort = next(iter(cohorts.values()))
            if report["reliability"]["benchmark_integrity_status"] != "clean":
                raise ScoringEvidenceError(f"Compromised run: {path}")
            world = {k: v for k, v in report["config"].items() if k != "seed"}
            identity = json.dumps({
                "world": world,
                "model": cohort.get("model"),
                "brain": cohort.get("brain"),
                "effort": cohort.get("reasoning_effort"),
                "recipe": report["benchmarks"]["protocol"]["id"],
                "boundary": manifest.get("agent_boundary"),
            }, sort_keys=True)
            if study_identity is not None and study_identity != identity:
                raise ScoringEvidenceError("Cannot pool different treatments, models, or recipes")
            study_identity = identity
            horizon = report["run"]["target_ticks"]
            tail = min(horizon, report["config"]["season_length_ticks"])
            raw = derive_outcome_counts(events, snapshot, member_ids=cohort["agents"],
                                        target_ticks=horizon, tail_ticks=tail)
            signature = (horizon, tail)
            if cells and tuple(cells[0]["horizon_and_tail"]) != signature:
                raise ScoringEvidenceError("Cannot pool different horizon/window definitions")
            for k, v in raw.items():
                total[k] = total.get(k, 0) + v
            cells.append({
                "report_path": str(p), "seed": report["config"]["seed"],
                "horizon_and_tail": signature,
                "original_recipe": manifest.get("recipe") or manifest.get("benchmark_protocol"),
                "source_commit": manifest["provenance"]["git_sha"],
                "raw": raw, "scores": score_outcome_counts(raw),
                "original_execution": cohort["scores"]["effective_execution"]["score"],
                "original_competence": cohort["scores"]["sustained_competence"]["score"],
                "sha256": {str(f): hashlib.sha256(f.read_bytes()).hexdigest()
                           for f in (p, snapshot_path, events_path, manifest_path)},
            })
        output["studies"][label] = {"cells": cells, "raw": total,
                                    "scores": score_outcome_counts(total)}
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studies", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = review(json.loads(args.studies.read_text()))
    with args.out.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    for name, value in result["studies"].items():
        print(name, {key: score["score"] for key, score in value["scores"].items()})
