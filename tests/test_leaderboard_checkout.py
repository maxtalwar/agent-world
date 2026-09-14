"""Real Git integration tests for pinned source clones and shared run evidence."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from agent_world.leaderboard_launch import LaunchService, LaunchError


class LaunchCheckoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repository"
        self.root.mkdir()
        self.git(self.root, "init", "-q")
        self.git(self.root, "config", "user.name", "Checkout Test")
        self.git(self.root, "config", "user.email", "test@example.invalid")
        self.files = {"agent_world/source.py": "# pinned source\n",
                      "runs/jobs/old/recovery.json": "{}\n",
                      "runs/managed/old/run-report.json": '{"score":1}\n',
                      "runs/benchmarks/old/run-report.json": "{}\n",
                      ".gitignore": "*.log\n.local/\n"}
        for name, text in self.files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.git(self.root, "add", ".")
        self.git(self.root, "commit", "-qm", "Source and archived evidence")
        self.commit = self.git(self.root, "rev-parse", "HEAD").strip()
        self.service = LaunchService(self.root, settings={})
        self.target = self.root / ".local/leaderboard-sources" / self.commit

    @staticmethod
    def git(root, *args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                       stderr=subprocess.PIPE)

    def old_clone(self):
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.git(self.root, "clone", "--shared", str(self.root), str(self.target))
        self.git(self.target, "checkout", "--detach", self.commit)

    def check_links_and_evidence(self):
        for name in ("jobs", "managed"):
            link = self.target / "runs" / name
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), self.root / "runs" / name)
        for name, text in self.files.items():
            self.assertEqual((self.root / name).read_text(), text)
            self.assertEqual((self.target / name).read_text(), text)
        self.assertEqual(self.git(self.target, "rev-parse", "HEAD").strip(), self.commit)
        self.assertEqual(self.git(self.target, "status", "--porcelain", "--", "agent_world"), "")
        self.assertEqual(self.git(self.target, "diff", "--cached", "--name-only"), "")

    def test_scoring_source_extracts_only_the_package_once(self):
        from agent_world.leaderboard import scoring_source
        target = scoring_source(self.root, self.commit)
        self.assertEqual(target, self.root / ".local/leaderboard-scoring" / self.commit)
        self.assertEqual((target / "agent_world/source.py").read_text(), "# pinned source\n")
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["agent_world"])
        self.assertFalse((target / ".git").exists())
        marker = target / "agent_world/marker"
        marker.write_text("cached")
        self.assertTrue((scoring_source(self.root, self.commit) / "agent_world/marker").exists())
        with self.assertRaises(ValueError):
            scoring_source(self.root, "HEAD")

    def test_new_clone_links_registries_with_tracked_evidence(self):
        self.assertEqual(self.service.launch_checkout({"commit": self.commit}), self.target)
        self.check_links_and_evidence()
        # Repeated catalog requests must retain the same links and commit.
        self.service.launch_checkout({"commit": self.commit})
        self.check_links_and_evidence()

    def test_recovers_pristine_clone_left_by_old_launcher(self):
        self.old_clone()
        self.service.launch_checkout({"commit": self.commit})
        self.check_links_and_evidence()

    def test_refuses_modified_untracked_and_ignored_run_data(self):
        self.old_clone()
        for name in ("run-report.json", "checkpoint.json", "worker.log"):
            with self.subTest(name=name):
                path = self.target / "runs/managed/old" / name
                original = path.read_bytes() if path.exists() else None
                path.write_text("local data must survive")
                with self.assertRaisesRegex(LaunchError, "conflicting run registry"):
                    self.service.launch_checkout({"commit": self.commit})
                self.assertEqual(path.read_text(), "local data must survive")
                self.assertFalse((self.target / "runs/jobs").is_symlink())
                if original is None:
                    path.unlink()
                else:
                    path.write_bytes(original)

    def test_refuses_wrong_registry_symlink(self):
        self.service.launch_checkout({"commit": self.commit})
        link = self.target / "runs/jobs"
        link.unlink()
        wrong = self.root / "other-jobs"
        wrong.mkdir()
        link.symlink_to(wrong, target_is_directory=True)
        with self.assertRaisesRegex(LaunchError, "conflicting run registry"):
            self.service.launch_checkout({"commit": self.commit})
        self.assertEqual(link.resolve(), wrong)

    def test_source_only_commit_still_works(self):
        self.git(self.root, "rm", "-r", "runs/jobs", "runs/managed")
        self.git(self.root, "commit", "-qm", "Source only")
        commit = self.git(self.root, "rev-parse", "HEAD").strip()
        target = self.service.launch_checkout({"commit": commit})
        self.assertEqual((target / "runs/jobs").resolve(), self.root / "runs/jobs")
        self.assertEqual((target / "runs/managed").resolve(), self.root / "runs/managed")


if __name__ == "__main__":
    unittest.main()
