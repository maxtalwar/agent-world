import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from agent_world.benchmark_acceptance import accepted_report

class AcceptanceTests(unittest.TestCase):
    def test_exact_report_only_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"data").mkdir(); path=root/"report.json"
            report={"run":{"completed":True},"benchmarks":{"protocol":{"id":"recipe","recipe_fingerprint_sha256":"recipehash"},
                "trial":{"seed":11,"quality_flags":["benchmark_code_fingerprint_mismatch"]},
                "cohorts":{"one":{"model":"gemini","protocol_compliant":False,"quality_flags":["benchmark_code_fingerprint_mismatch"]}}}}
            path.write_text(json.dumps(report))
            entry={"report_path":"report.json","report_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"recipe":"recipe","recipe_sha256":"recipehash","seed":11,"model":"gemini"}
            catalog=root/"data/run-sources.json";catalog.write_text(json.dumps({"benchmark_acceptances":[entry]}))
            accepted=accepted_report(root,path,report)
            self.assertTrue(accepted["benchmarks"]["cohorts"]["one"]["protocol_compliant"])
            self.assertFalse(report["benchmarks"]["cohorts"]["one"]["protocol_compliant"])
            path.write_text(path.read_text()+" ")
            with self.assertRaisesRegex(ValueError,"bytes"):accepted_report(root,path,report)
            entry["report_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest();entry["model"]="other"
            catalog.write_text(json.dumps({"benchmark_acceptances":[entry]}))
            with self.assertRaisesRegex(ValueError,"identity"):accepted_report(root,path,report)
            entry["model"]="gemini";catalog.write_text(json.dumps({"benchmark_acceptances":[entry]}))
            report["benchmarks"]["cohorts"]["one"]["quality_flags"].append("external_tool_use")
            with self.assertRaisesRegex(ValueError,"other integrity"):accepted_report(root,path,report)

    def test_infrastructure_review_cannot_waive_resampling(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"data").mkdir(); path=root/"report.json"
            report={"run":{"completed":True},"benchmarks":{"protocol":{"id":"recipe","recipe_fingerprint_sha256":"hash"},
                "trial":{"seed":11,"quality_flags":["benchmark_code_fingerprint_mismatch"]},
                "cohorts":{"one":{"model":"sonnet","quality_flags":[]}}}}
            path.write_text(json.dumps(report)); (root/"review.md").write_text("reviewed")
            recovery=root/"recovery.json"; recovery.write_text("{}")
            entry={"report_path":"report.json","report_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                "recipe":"recipe","recipe_sha256":"hash","seed":11,"model":"sonnet",
                "review_type":"infrastructure_compatibility","review_path":"review.md",
                "review_sha256":hashlib.sha256((root/"review.md").read_bytes()).hexdigest(),
                "recovery_path":"recovery.json","recovery_sha256":hashlib.sha256(recovery.read_bytes()).hexdigest()}
            catalog=root/"data/run-sources.json"
            catalog.write_text(json.dumps({"benchmark_acceptances":[entry]}))
            result=accepted_report(root,path,report)
            self.assertIn("provenance_acceptance",result); self.assertNotIn("owner_acceptance",result)
            recovery.write_text(json.dumps({"resampling_deviation":{"count":8}}))
            entry["recovery_sha256"]=hashlib.sha256(recovery.read_bytes()).hexdigest()
            catalog.write_text(json.dumps({"benchmark_acceptances":[entry]}))
            with self.assertRaisesRegex(ValueError,"resampled"): accepted_report(root,path,report)

if __name__=="__main__":unittest.main()
