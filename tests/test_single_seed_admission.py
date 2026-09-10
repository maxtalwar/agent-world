import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from agent_world.benchmark_acceptance import single_seed_admission

class SingleSeedAdmissionTests(unittest.TestCase):
    def test_exact_owner_exception_and_integrity_guards(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/"data").mkdir();p=root/"report.json"
            report={"run":{"completed":True},"benchmarks":{"trial":{"protocol_compliant":True,"seed":41,"quality_flags":[]},"protocol":{"id":"recipe","recipe_fingerprint_sha256":"digest"},"cohorts":{"one":{"model":"fable","protocol_compliant":True,"quality_flags":[]}}}}
            p.write_text(json.dumps(report))
            self.assertIsNone(single_seed_admission(root,[p]))
            entry={"report_path":"report.json","report_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"model":"fable","recipe":"recipe","recipe_sha256":"digest","seed":41}
            catalog=root/"data/run-sources.json";catalog.write_text(json.dumps({"single_seed_admissions":[entry]}))
            self.assertEqual(single_seed_admission(root,[p]),entry)
            self.assertIsNone(single_seed_admission(root,[p,p]))
            p.write_text(p.read_text()+" ")
            with self.assertRaises(ValueError):single_seed_admission(root,[p])
            report["benchmarks"]["trial"]["quality_flags"]=["bad_integrity"]
            p.write_text(json.dumps(report));entry["report_sha256"]=hashlib.sha256(p.read_bytes()).hexdigest();catalog.write_text(json.dumps({"single_seed_admissions":[entry]}))
            with self.assertRaises(ValueError):single_seed_admission(root,[p])
