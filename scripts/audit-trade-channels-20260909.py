#!/usr/bin/env python3
"""Reproduce the retrospective channel inventory; never change frozen scores/labels."""
import collections
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/trade-channel-audit-20260909.json"
LEADERS = {
    "participant-v6": ["Fable 5", "Grok 4.6 Build via Grok CLI", "Opus 5", "Opus 4.8", "GPT-5.6 Sol"],
    "participant-v8-revised": ["GPT-6 Astra", "Grok 4.6", "Sonnet 5", "GPT-5.6 Terra"],
}
SUPPLEMENTAL = [
    ("GPT-6 Astra", "participant-v6", "astra-v6-restored-20260908"),
    ("GPT-6 Astra", "participant-v6.1", "web-gpt-6-astra-1dafc66aaaea"),
    ("GPT-5.6 Sol", "participant-v6.1", "sol-v61-ledger-comparison-20260908"),
]

# Manual retrospective annotations: transfer indices reference the frozen classifier;
# benefit lines reference successful engine events, not agent claims.
SERVICE_FOLLOWTHROUGH = [
    ("astra-v6-restored-20260908", 11, [1], [1186, 1254], "Farm access delivered; grant precedes/repeats alongside fiber payment."),
    ("astra-v6-restored-20260908", 11, [2], [2070, 2328], "Storage upkeep supplied at tick 29; requested access arrives at tick 33, five ticks after payment."),
    ("astra-v6-restored-20260908", 11, [3], [2459, 2460, 2529, 2530], "Shared shelter completed/access granted; farm restored and shelter maintained."),
    ("astra-v6-restored-20260908", 11, [6], [1562, 2763], "Existing shelter access plus later upkeep; not a newly negotiated sale."),
    ("astra-v6-restored-20260908", 11, [8], [3089, 3157], "Requested tile access granted and delivered stone contributed."),
    ("web-gpt-6-astra-1dafc66aaaea", 11, [0], [842, 1991], "Access granted before shelter completion; benefit available when completed at tick 28."),
    ("web-gpt-6-astra-1dafc66aaaea", 11, [1], [1830, 1900], "Shelter access and completed shared shelter."),
    ("web-gpt-6-astra-1dafc66aaaea", 11, [2], [2055, 2057], "Tile access and shelter restoration recorded at tick 29."),
    ("web-gpt-6-astra-1dafc66aaaea", 11, [4, 5], [2666, 3079], "Two payers fund one well: restoration at tick 37 and further upkeep at tick 43; not two separate well repairs."),
    ("web-gpt-6-astra-1dafc66aaaea", 41, [0, 1], [1916, 1980, 1981], "Two same-tick installments; shelter completed tick 27 and made active/public tick 28. Eighteen-tick lag from payment."),
    ("web-gpt-6-astra-1dafc66aaaea", 41, [2], [1244, 1245, 1310, 1311], "Farm/shelter access and upkeep."),
    ("web-gpt-6-astra-1dafc66aaaea", 41, [3], [1310, 1311], "Ongoing shared farm/shelter upkeep; existing access."),
    ("web-gpt-6-astra-1dafc66aaaea", 41, [5], [1947], "Farm maintained four ticks later; materials are fungible, attribution is not causal proof."),
    ("web-gpt-6-astra-1dafc66aaaea", 41, [8], [1947, 2016], "Requested farm upkeep at same/next tick; same-tick action order does not prove response to payment."),
    ("web-gpt-6-astra-1dafc66aaaea", 41, [10], [3035], "Contributor eventually supplies shelter upkeep; ongoing support, not a priced deadline."),
    ("web-gpt-6-astra-1dafc66aaaea", 41, [11, 13], [2375, 2440, 2745], "Fiber and food installments for one storage relationship: access, storage and upkeep observed."),
    ("web-gpt-6-astra-1dafc66aaaea", 41, [12], [2298, 2300], "Storage access and food storage recorded."),
]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    db = sqlite3.connect(f"file:{ROOT / 'data/model-benchmarks.sqlite'}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    sources = []
    for r in db.execute("""SELECT m.label,m.suite,r.run_id,r.source_report,r.seed
            FROM runs r JOIN run_cohorts rc USING(run_id)
            JOIN models m ON m.model_key=rc.model
            JOIN benchmark_trials bt USING(run_id)
            WHERE bt.included_in_model_result=1"""):
        if r["label"] in LEADERS.get(r["suite"], []):
            sources.append(dict(r, evidence_basis="catalog_admitted"))
    for label, suite, job_id in SUPPLEMENTAL:
        job_path = ROOT / f"runs/jobs/{job_id}/job.json"
        job = json.loads(job_path.read_text())
        ready = job["analysis_readiness"]
        assert ready["status"] == "ready" and not ready["blockers"]
        assert ready["integrity"] == "clean" and ready["usage_coverage_pct"] == 100
        for seed in (11, 41):
            sources.append(dict(label=label, suite=suite, run_id=f"{job_id}:seed-{seed}",
                source_report=f"runs/managed/{job_id}/seed-{seed}/run-report.json", seed=seed,
                evidence_basis="ready_managed_study_not_new_leaderboard_admission",
                readiness_path=str(job_path.relative_to(ROOT)), readiness_sha256=digest(job_path),
                original_protocol=job["protocol"], launch_commit=job["launch_commit"]))
    results = []
    for source in sources:
        folder = (ROOT / source["source_report"]).parent
        report = json.loads((folder / "run-report.json").read_text())
        events = [dict(json.loads(line), line=i) for i, line in enumerate(
            (folder / "run.jsonl").read_text().splitlines(), 1)]
        counts = collections.Counter(e["type"] for e in events)
        assert counts["run_completed"] == 1
        assert max(e["tick"] for e in events) == (60 if source["suite"] == "participant-v8-revised" else 50)
        gifts = [e for e in events if e["type"] == "gift"]
        cls_path = folder / "gift-classifications.json"
        cls = json.loads(cls_path.read_text())["classifications"] if cls_path.exists() else []
        if cls:
            assert len(cls) == len(gifts)
            for idx, (g, item) in enumerate(zip(gifts, cls)):
                assert (item["gift_index"], item["tick"], item["giver"], item["recipient"], item["items"]) == (
                    idx, g["tick"], g["actor_id"], g["data"]["to"], g["data"]["items"])
        classification_counts = dict(collections.Counter(x["verdict"] for x in cls))
        declared_counts = dict(collections.Counter(e["data"].get("kind", "absent_in_event") for e in gifts))
        def compact(e):
            return {k:e[k] for k in ("line", "tick", "actor_id", "type", "message", "data", "position") if k in e}
        formal = [e for e in events if e["type"] in ("offer_trade", "accept_trade", "expire_trade", "reject_trade", "cancel_trade")]
        builds = [e for e in events if e["type"] == "build" and len(e["data"]["structure"].get("contributors", [])) > 1]
        metric = {k:counts[k] for k in ("offer_trade", "accept_trade", "gift", "contribute", "grant_access", "maintain_structure", "contract_proposed", "contract_accepted", "contract_fulfilled", "contract_defaulted")}
        metric.update(cooperative_completed_projects=len(builds), frozen_transfer_labels=classification_counts,
            event_transfer_kinds=declared_counts, formal_conversion_pct=100*counts["accept_trade"]/counts["offer_trade"] if counts["offer_trade"] else None)
        transfer_context = []
        for idx, gift in enumerate(gifts):
            participants = [gift["actor_id"], gift["data"]["to"]]
            context = [compact(e) for e in events if abs(e["tick"]-gift["tick"]) <= 2 and e["actor_id"] in participants
                and e["type"] in ("say", "broadcast", "whisper", "ledger_note", "grant_access", "set_access_fee", "maintain_structure", "contribute", "store")]
            transfer_context.append(dict(event=compact(gift), classification=cls[idx] if cls else None, nearby_context=context))
        hashes = {str(path.relative_to(ROOT)): digest(path) for path in [folder / "run.jsonl", folder / "run-report.json", folder / "run-manifest.json", folder / "run-usage.jsonl", cls_path] if path.exists()}
        result = dict(source=source, hashes=hashes, metrics=metric,
            frozen_scores={key: {k:v.get("score") for k,v in cohort["scores"].items()} for key,cohort in report["benchmarks"]["cohorts"].items()},
            formal_events=[compact(e) for e in formal], transfers=transfer_context,
            cooperative_projects=[dict(line=e["line"], tick=e["tick"], **{k:e["data"]["structure"].get(k) for k in ("id", "type", "owner_id", "contributors")}) for e in builds])
        results.append(result)
    results.sort(key=lambda r:(r["source"]["suite"],r["source"]["label"],r["source"]["seed"]))
    annotations = []
    for job, seed, indices, lines, note in SERVICE_FOLLOWTHROUGH:
        folder = ROOT / f"runs/managed/{job}/seed-{seed}"
        events = [json.loads(x) for x in (folder / "run.jsonl").read_text().splitlines()]
        classifications = json.loads((folder / "gift-classifications.json").read_text())["classifications"]
        for index in indices:
            assert classifications[index]["verdict"] == "payment_for_service"
        benefits = []
        for line in lines:
            e = events[line-1]
            assert e["type"] in ("build", "contribute", "grant_access", "set_access_fee", "maintain_structure", "store")
            benefits.append(dict(line=line, **e))
        annotations.append(dict(run_id=f"{job}:seed-{seed}", gift_indices=indices, benefit_events=benefits, interpretation=note))
    covered = collections.defaultdict(list)
    for annotation in annotations:
        covered[annotation["run_id"]].extend(annotation["gift_indices"])
    for result in results:
        key = result["source"]["run_id"]
        if key in covered:
            expected = [t["classification"]["gift_index"] for t in result["transfers"]
                if t["classification"]["verdict"] == "payment_for_service"]
            assert sorted(expected) == sorted(covered[key])
    prior_audit = json.loads((ROOT / "docs/astra-v81-exchange-audit.json").read_text())
    for source in prior_audit["sources"]:
        assert digest(ROOT / source["path"]) == source["sha256"]
    OUT.write_text(json.dumps(dict(schema_version=1, generator_sha256=digest(Path(__file__)), manual_service_followthrough=annotations, audit_date="2026-09-09", scope="Retrospective channel inventory and evidence contexts, not semantic reclassification or new benchmark admission", catalog_sha256=digest(ROOT / "data/run-sources.json"), runs=results), indent=2, ensure_ascii=False)+"\n")
    pooled = {}
    for r in results:
        s, m = r["source"],r["metrics"]
        p = pooled.setdefault((s["suite"], s["label"]), collections.Counter())
        for k,v in m.items():
            if isinstance(v,int): p[k] += v
        for k,v in m["frozen_transfer_labels"].items():p[k] += v
        for k,v in m["event_transfer_kinds"].items():p["kind_"+k] += v
    for key, p in pooled.items():print(key, dict(p))
    print(f"Wrote {len(results)} worlds to {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
