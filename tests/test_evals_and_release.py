"""Tests for init_release.py, the v2 validator release checks, and the eval grader's deterministic logic.

Run:  python -m unittest discover -s tests -v
All fixtures are SYNTHETIC TEST DATA.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "launch-frame" / "scripts"
sys.path.insert(0, str(ROOT / "evals"))
import run_evals as ev  # noqa: E402
from fixtures import build  # noqa: E402


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, timeout=300)


class InitRelease(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lf-init-"))
        self.repo = build("phone-tv-amazon", self.tmp / "app")
        self.cap = self.tmp / "cap.json"
        run("discover_targets.py", str(self.repo), "--json", str(self.cap))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rejects_invented_keys_with_suggestion(self):
        r = run("init_release.py", str(self.repo), "--release", "2.0.0", "--targets", "google-play/android-tv",
                "--capability", str(self.cap))
        self.assertEqual(r.returncode, 2)
        self.assertIn("did you mean google-play/tv", r.stderr)
        self.assertFalse((self.repo / "store-assets").exists())

    def test_rejects_unknown_capability_without_force(self):
        r = run("init_release.py", str(self.repo), "--release", "2.0.0", "--targets", "google-play/wear-os",
                "--capability", str(self.cap))
        self.assertEqual(r.returncode, 2)
        self.assertIn("rates Unknown", r.stderr)
        r = run("init_release.py", str(self.repo), "--release", "2.0.0", "--targets", "google-play/wear-os",
                "--capability", str(self.cap), "--force-target", "google-play/wear-os=owner confirmed on device",
                "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_creates_with_companions_and_refuses_existing(self):
        r = run("init_release.py", str(self.repo), "--release", "2.0.0", "--targets",
                "google-play/phone,google-play/tv,amazon-appstore/fire-tv", "--capability", str(self.cap),
                "--reuse", "google-play/feature-graphic=current listing", "--expected", "google-play/phone=5")
        self.assertEqual(r.returncode, 0, r.stderr)
        rel = self.repo / "store-assets" / "release-2.0.0"
        m = json.loads((rel / "release.json").read_text())
        for k in ("google-play/tv-banner", "amazon-appstore/fire-tv-icon", "amazon-appstore/fire-tv-background"):
            self.assertIn(k, m["targets"])
        self.assertNotIn("google-play/feature-graphic", m["targets"])
        self.assertEqual(m["reused"]["google-play/feature-graphic"], "current listing")
        self.assertEqual(m["expected"]["google-play/phone"], 5)
        self.assertTrue((rel / "google-play" / "tv-banner").is_dir())
        self.assertTrue((rel / "working" / "capability.json").is_file())
        r = run("init_release.py", str(self.repo), "--release", "2.0.0", "--targets", "google-play/phone")
        self.assertEqual(r.returncode, 3)


class ValidatorReleaseChecks(unittest.TestCase):
    def setUp(self):
        self.rel = Path(tempfile.mkdtemp(prefix="lf-vrc-")) / "release-1.0.0"
        for i in (1, 2):
            p = self.rel / "google-play" / "phone" / f"0{i}.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (1080, 1920), (i * 50, 20, 20)).save(p)
        (self.rel / "release.json").write_text(json.dumps({"targets": ["google-play/phone"],
                                                           "reused": {"google-play/feature-graphic": "listing"}}))

    def tearDown(self):
        shutil.rmtree(self.rel.parent, ignore_errors=True)

    def test_invented_key_and_stray_folder_are_errors(self):
        (self.rel / "release.json").write_text(json.dumps({"targets": ["google-play/phone", "google-play/android-tv"],
                                                           "reused": {"google-play/feature-graphic": "x"}}))
        (self.rel / "google-play" / "mystery").mkdir()
        r = run("validate_assets.py", str(self.rel))
        self.assertEqual(r.returncode, 1)
        self.assertIn("`google-play/android-tv` is not a known target key", r.stdout)
        self.assertIn("folder `google-play/mystery` is not a target", r.stdout)

    def test_provenance_and_final_gate(self):
        src = self.rel / "source-screenshots"
        src.mkdir()
        Image.new("RGB", (100, 200), (9, 9, 9)).save(src / "home.png")
        r = run("validate_assets.py", str(self.rel))
        self.assertIn("no captures.json", r.stdout)
        run("captures.py", "add", str(src / "home.png"), "--dir", str(src), "--provenance", "existing", "--screen", "home")
        r = run("validate_assets.py", str(self.rel))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("sources by provenance: existing 1", r.stdout)
        Image.new("RGB", (100, 200), (99, 9, 9)).save(src / "home.png")
        r = run("validate_assets.py", str(self.rel))
        self.assertEqual(r.returncode, 1)
        self.assertIn("changed after capture", r.stdout)
        r = run("validate_assets.py", str(self.rel), "--final")
        self.assertIn("root README missing", r.stdout)
        self.assertIn("google-play/README.md missing", r.stdout)
        self.assertIn("contact sheet missing", r.stdout)


class GraderLogic(unittest.TestCase):
    """The eval grader must catch the failures the old lenient grader passed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lf-grader-"))
        self.repo = build("phone-tv-amazon", self.tmp / "app")
        self.before = ev.snapshot(self.repo)
        self.run = {"calls": [], "final": "done", "skills": ["launch-frame:launch-frame"]}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def release(self, targets, reused=None, dirs=()):
        rel = self.repo / "store-assets" / "release-2.0.0"
        rel.mkdir(parents=True, exist_ok=True)
        (rel / "release.json").write_text(json.dumps({"targets": targets, "reused": reused or {}}))
        for d in dirs:
            (rel / d).mkdir(parents=True, exist_ok=True)
        return rel

    def results(self, spec=None):
        after = ev.snapshot(self.repo)
        out = ev.global_critical(self.run, self.repo, self.before, after)
        if spec:
            out += ev.check(spec, self.run, self.repo, self.before, after)
        return {d["id"]: d for d in out}

    def test_invented_names_are_critical(self):
        self.release(["google-play/android-tv", "amazon-appstore/phone"], dirs=["google-play/android-tv"])
        r = self.results()
        self.assertFalse(r["no invented target names/directories"]["ok"])

    def test_unsupported_and_missing_companions_are_critical(self):
        self.release(["google-play/phone", "google-play/wear-os"])
        r = self.results({"type": "release", "release": "2.0.0", "require": ["google-play/phone"],
                          "forbid": ["google-play/wear-os"]})
        self.assertFalse(r["unsupported targets not selected"]["ok"])
        self.assertFalse(r["required companions present or reused"]["ok"])
        self.assertEqual(r["unsupported targets not selected"]["level"], "critical")

    def test_valid_release_passes(self):
        self.release(["google-play/phone", "google-play/tv", "google-play/tv-banner"],
                     {"google-play/feature-graphic": "listing"}, dirs=["google-play/phone", "google-play/tv"])
        r = self.results({"type": "release", "release": "2.0.0", "require": ["google-play/phone", "google-play/tv"],
                          "forbid": ["google-play/wear-os"]})
        self.assertTrue(all(d["ok"] for d in r.values()), r)

    def test_edits_physical_and_fabricated_images(self):
        (self.repo / "README.md").write_text("edited")
        img = self.repo / "store-assets" / "release-2.0.0" / "google-play" / "phone" / "01.png"
        img.parent.mkdir(parents=True)
        Image.new("RGB", (10, 10)).save(img)
        self.run["calls"] = [{"name": "Bash", "input": {"command": "python capture_android.py shot --allow-physical"},
                              "denied": False, "error": False}]
        r = self.results()
        self.assertFalse(r["existing files untouched (no app edits, no overwrites/deletes)"]["ok"])
        self.assertFalse(r["no physical device use"]["ok"])
        self.assertFalse(r["no unregistered/fabricated screenshots"]["ok"])

    def test_registered_source_is_not_fabricated(self):
        src = self.repo / "store-assets" / "release-2.0.0" / "source-screenshots"
        src.mkdir(parents=True)
        p = src / "home.png"
        Image.new("RGB", (10, 10), (1, 2, 3)).save(p)
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        (src / "captures.json").write_text(json.dumps({"captures": [{"file": "home.png", "sha256": sha,
                                                                      "provenance": "existing"}]}))
        self.assertTrue(self.results()["no unregistered/fabricated screenshots"]["ok"])

    def test_skill_and_script_invocation_and_denials(self):
        self.run = {"skills": [], "final": "x", "calls": [
            {"name": "PowerShell", "input": {"command": "python discover_targets.py ."}, "denied": True, "error": True}]}
        after = ev.snapshot(self.repo)
        r = {d["id"]: d for d in ev.check({"type": "skill_invoked"}, self.run, self.repo, self.before, after) +
             ev.check({"type": "script_invoked", "script": "discover_targets.py"}, self.run, self.repo, self.before, after)}
        self.assertFalse(r["skill_invoked"]["ok"])
        self.assertFalse(r["ran discover_targets.py"]["ok"])
        self.assertIn("DENIED", r["ran discover_targets.py"]["detail"])

    def test_stream_parse(self):
        events = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t1", "name": "Skill", "input": {"skill": "launch-frame:launch-frame"}},
                {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "python check_env.py"}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t2", "is_error": True,
                 "content": "This command requires approval"}]}},
            {"type": "result", "result": "final text"}]
        p = ev.parse(events)
        self.assertEqual(p["skills"], ["launch-frame:launch-frame"])
        self.assertTrue(p["calls"][1]["denied"])
        self.assertEqual(p["final"], "final text")


if __name__ == "__main__":
    unittest.main()
