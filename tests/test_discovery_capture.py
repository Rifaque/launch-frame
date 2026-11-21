"""Tests for target discovery, environment planning, capture helpers, provenance and v2 validator rules.

Run:  python -m unittest discover -s tests -v
Fixture repositories and images are SYNTHETIC TEST DATA (evals/fixtures.py).
Live device tests run only when LAUNCHFRAME_LIVE_SERIAL names an emulator serial.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "launch-frame" / "scripts"
sys.path.insert(0, str(ROOT / "evals"))
sys.path.insert(0, str(SCRIPTS))
from fixtures import NAMES, build  # noqa: E402


def run(script: str, *args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True,
                          timeout=300, env=env)


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def img(path: Path, size, color=(40, 80, 120), mode="RGB"):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, color if mode == "RGB" else color + (255,)).save(path)
    return path


class Discovery(unittest.TestCase):
    """Deterministic halves of eval scenarios 1-7, 10-13, 18-20."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="lf-disc-"))
        cls.data = {}
        for name in NAMES:
            repo = build(name, cls.tmp / name)
            out = cls.tmp / f"{name}.json"
            r = run("discover_targets.py", str(repo), "--json", str(out))
            assert r.returncode == 0, r.stderr
            cls.data[name] = json.loads(out.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def status(self, fixture):
        return {t["target"]: t["status"] for t in self.data[fixture]["targets"]}

    def confirmed(self, fixture):
        return {k for k, v in self.status(fixture).items() if v == "Confirmed"}

    def test_phone_only(self):
        self.assertEqual(self.confirmed("phone-only"), {"android-phone"})
        self.assertEqual(self.status("phone-only")["android-tablet"], "Unknown")

    def test_phone_tablet(self):
        self.assertEqual(self.confirmed("phone-tablet"), {"android-phone", "android-tablet"})

    def test_tv_only_excludes_phone(self):
        st = self.status("tv-only")
        self.assertEqual(st["android-tv"], "Confirmed")
        self.assertEqual(st["android-phone"], "Unsupported")
        self.assertEqual(st["android-tablet"], "Unsupported")

    def test_phone_tv_and_amazon(self):
        self.assertEqual(self.confirmed("phone-tv"), {"android-phone", "android-tv"})
        self.assertEqual(self.status("phone-tv")["fire-tv"], "Unknown")  # no Amazon intent
        self.assertEqual(self.confirmed("phone-tv-amazon"), {"android-phone", "android-tv", "fire-tv"})

    def test_cross_platform(self):
        st = self.status("cross-platform")
        self.assertTrue({"android-phone", "iphone", "ipad"} <= self.confirmed("cross-platform"))
        self.assertIn(st["web"], ("Probable", "Confirmed"))

    def test_misleading_keywords_do_not_confirm(self):
        st = self.status("misleading-keywords")
        self.assertEqual(self.confirmed("misleading-keywords"), {"android-phone"})
        for t in ("android-tv", "wear-os", "android-tablet", "chromebook", "web"):
            self.assertIn(st[t], ("Unknown",), t)
        modules = " ".join(self.data["misleading-keywords"]["facts"]["android_app_modules"])
        self.assertNotIn("tvlib", modules)
        self.assertNotRegex(modules, r"^\. ")  # root 'apply false' is not an app module

    def test_capture_infrastructure_and_existing(self):
        facts = self.data["existing-automation"]["facts"]
        infra = " ".join(facts["capture_infrastructure"])
        self.assertIn("Maestro", infra)
        self.assertIn("Roborazzi", infra)
        self.assertTrue(facts["existing_screenshots"])

    def test_apple(self):
        self.assertEqual(self.status("apple-only")["iphone"], "Confirmed")
        self.assertEqual(self.status("apple-only")["ipad"], "Unsupported")
        self.assertEqual(self.confirmed("apple-tv"), {"iphone", "ipad", "apple-tv"})
        self.assertNotIn("com.example.fixture.UITests", self.data["apple-only"]["facts"]["bundle_ids"])

    def test_capture_considerations_and_prior_release(self):
        self.assertTrue(self.data["login-required"]["facts"]["capture_considerations"])
        self.assertEqual(self.data["prior-release"]["facts"]["existing_store_assets"],
                         ["store-assets/release-1.0.0"])
        self.assertTrue(self.data["limited-captures"]["facts"]["existing_screenshots"])

    def test_deep_links_variants_launchers(self):
        facts = self.data["phone-only"]["facts"]
        self.assertTrue(any("fixture://open" in d for d in facts["deep_links"]))
        self.assertTrue(any("release" in v for v in facts["build_variants"]))
        self.assertTrue(any("LAUNCHER" in a for a in facts["launch_activities"]))

    def test_markdown_report(self):
        r = run("discover_targets.py", str(self.tmp / "tv-only"))
        self.assertIn("| Android phone | Unsupported |", r.stdout)
        self.assertIn("Skip (unsupported)", r.stdout)


class EnvironmentPlanning(unittest.TestCase):
    def setUp(self):
        self.ce = load("check_env")
        self.base = {"host": "Test", "python": "3", "pillow": True, "playwright": False, "browser": None,
                     "android": {"sdk": None, "adb": None, "emulator": None, "android_cli": None,
                                 "system_images": [], "avds": [], "devices": [], "errors": []},
                     "apple": {"available": False, "reason": "needs macOS", "simulators": []}}

    def env(self, **android):
        e = json.loads(json.dumps(self.base))
        e["android"].update(android)
        return e

    def test_no_sdk(self):
        p = self.ce.plan_for("android-phone", self.env())
        self.assertEqual(p["auto"], "no")
        self.assertIn("adb", p["setup"])

    def test_avd_preferred_over_physical(self):
        e = self.env(adb="adb", avds=[{"name": "P", "kind": "phone"}],
                     devices=[{"serial": "x", "emulator": False, "kind": "phone", "manufacturer": "M", "model": "Q"}])
        p = self.ce.plan_for("android-phone", e)
        self.assertIn("emulator P", p["env"])
        self.assertEqual(p["help"], "no")

    def test_physical_needs_approval(self):
        e = self.env(adb="adb", devices=[{"serial": "x", "emulator": False, "kind": "fire-tv",
                                          "manufacturer": "Amazon", "model": "AFT"}])
        p = self.ce.plan_for("fire-tv", e)
        self.assertIn("approval", p["auto"])
        self.assertIn("Fire OS", p["env"])

    def test_fire_tv_without_device_is_honest(self):
        e = self.env(adb="adb", avds=[{"name": "TV", "kind": "tv"}])
        p = self.ce.plan_for("fire-tv", e)
        self.assertIn("not Fire OS", p["help"])

    def test_missing_avd_requires_approval(self):
        p = self.ce.plan_for("android-tablet", self.env(adb="adb", android_cli="android"))
        self.assertIn("android emulator create medium_tablet", p["setup"])
        self.assertIn("approve", p["help"])

    def test_apple_unavailable(self):
        p = self.ce.plan_for("iphone", self.env())
        self.assertEqual(p["auto"], "no")
        self.assertIn("macOS", p["setup"])

    def test_env_report_runs(self):
        r = run("check_env.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Environment capability report", r.stdout)


class AndroidHelpers(unittest.TestCase):
    def setUp(self):
        self.ca = load("capture_android")

    def test_avd_parsing_with_spaced_ini(self):
        tmp = Path(tempfile.mkdtemp(prefix="lf-avd-"))
        try:
            (tmp / "TV.avd").mkdir()
            (tmp / "TV.ini").write_text(f"path={tmp / 'TV.avd'}\n")
            (tmp / "TV.avd" / "config.ini").write_text(
                "hw.lcd.width = 1920\nhw.lcd.height = 1080\nhw.lcd.density = 320\ntag.id = google-tv\n")
            (tmp / "Tab.avd").mkdir()
            (tmp / "Tab.ini").write_text(f"path={tmp / 'Tab.avd'}\n")
            (tmp / "Tab.avd" / "config.ini").write_text(
                "hw.lcd.width=2560\nhw.lcd.height=1600\nhw.lcd.density=320\ntag.id=google_apis\n")
            with mock.patch.dict(os.environ, {"ANDROID_AVD_HOME": str(tmp)}):
                kinds = {a["name"]: a["kind"] for a in self.ca.list_avds()}
            self.assertEqual(kinds, {"TV": "tv", "Tab": "tablet"})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_size_classification(self):
        self.assertEqual(self.ca.classify_size(1080, 2400, 420), "phone")
        self.assertEqual(self.ca.classify_size(2560, 1600, 320), "tablet")

    def test_grounded_target_resolution(self):
        els = [
            {"text": "", "desc": "", "id": "", "bounds": [367, 2175, 535, 2301], "center": [451, 2238],
             "clickable": True, "focused": False},
            {"text": "", "desc": "Movies", "id": "", "bounds": [367, 2180, 535, 2296], "center": [451, 2238],
             "clickable": False, "focused": False},
            {"text": "Movies near you", "desc": "", "id": "", "bounds": [0, 100, 500, 200], "center": [250, 150],
             "clickable": True, "focused": False},
        ]
        hits = self.ca.find(els, desc="Movies")
        self.assertEqual(len(hits), 1)
        resolved = self.ca.resolve_target(els, hits)
        self.assertTrue(resolved[0]["clickable"])
        self.assertEqual(resolved[0]["bounds"], [367, 2175, 535, 2301])
        self.assertEqual(len(self.ca.find(els, text="movies")), 1)
        self.assertEqual(self.ca.find(els, text="Movies", exact=True), [])

    def test_blank_detection(self):
        self.assertTrue(self.ca.is_blank(Image.new("RGB", (100, 200), (0, 0, 0))))
        im = Image.new("RGB", (100, 200), (0, 0, 0))
        im.paste((255, 255, 255), (0, 0, 50, 100))
        self.assertFalse(self.ca.is_blank(im))

    def test_physical_guard(self):
        fake = {"emulator": False, "manufacturer": "X", "model": "Y"}
        with mock.patch.object(self.ca, "device_info", return_value=fake):
            with self.assertRaises(self.ca.AndroidError):
                self.ca.require_ok("serial", allow_physical=False)
            self.assertEqual(self.ca.require_ok("serial", allow_physical=True), fake)
            with mock.patch.dict(os.environ, {"LAUNCHFRAME_DENY_PHYSICAL": "1"}):
                with self.assertRaises(self.ca.AndroidError):
                    self.ca.require_ok("serial", allow_physical=True)


class AppleHelpers(unittest.TestCase):
    def test_parse_devices(self):
        capl = load("capture_apple")
        data = {"devices": {
            "com.apple.CoreSimulator.SimRuntime.iOS-18-2": [
                {"udid": "A", "name": "iPhone 16 Pro Max", "state": "Shutdown", "isAvailable": True},
                {"udid": "B", "name": "iPad Pro 13-inch (M4)", "state": "Booted", "isAvailable": True},
                {"udid": "C", "name": "Old", "state": "Shutdown", "isAvailable": False}],
            "com.apple.CoreSimulator.SimRuntime.tvOS-18-2": [
                {"udid": "D", "name": "Apple TV 4K (3rd generation)", "state": "Shutdown", "isAvailable": True}]}}
        kinds = {d["udid"]: d["kind"] for d in capl.parse_devices(data)}
        self.assertEqual(kinds, {"A": "iphone", "B": "ipad", "D": "apple-tv"})

    @unittest.skipIf(sys.platform == "darwin", "non-macOS behavior")
    def test_unavailable_off_mac(self):
        r = run("capture_apple.py", "devices")
        self.assertEqual(r.returncode, 3)
        self.assertIn("macOS", r.stderr)


class Provenance(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lf-prov-"))
        self.src = self.tmp / "source-screenshots"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_list_verify(self):
        a = img(self.tmp / "docs" / "home.png", (1080, 2400))
        r = run("captures.py", "add", str(a), "--dir", str(self.src), "--provenance", "existing", "--screen", "home")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.src / "home.png").read_bytes(), a.read_bytes())  # byte-for-byte copy
        entry = json.loads((self.src / "captures.json").read_text())["captures"][0]
        self.assertEqual(entry["provenance"], "existing")
        self.assertIn("docs", entry["source"])
        self.assertEqual(run("captures.py", "verify", "--dir", str(self.src)).returncode, 0)
        img(self.src / "home.png", (1080, 2400), (1, 2, 3))           # edited source
        img(self.src / "mystery.png", (100, 100))                     # unregistered
        v = run("captures.py", "verify", "--dir", str(self.src))
        self.assertEqual(v.returncode, 1)
        self.assertIn("CHANGED", v.stdout)
        self.assertIn("UNREGISTERED", v.stdout)

    def test_add_refuses_auto_captured(self):
        a = img(self.tmp / "x.png", (10, 10))
        r = run("captures.py", "add", str(a), "--dir", str(self.src), "--provenance", "auto-captured",
                "--screen", "x")
        self.assertEqual(r.returncode, 2)


class ValidatorV2(unittest.TestCase):
    def setUp(self):
        self.rel = Path(tempfile.mkdtemp(prefix="lf-val2-")) / "release-9.9.9"

    def tearDown(self):
        shutil.rmtree(self.rel.parent, ignore_errors=True)

    def test_companions_reused_and_expected(self):
        for i in range(1, 4):
            img(self.rel / "google-play" / "tv" / f"0{i}.png", (1920, 1080), (i * 30, 0, 0))
        (self.rel / "release.json").write_text(json.dumps({"targets": ["google-play/tv"],
                                                           "expected": {"google-play/tv": 4}}))
        r = run("validate_assets.py", str(self.rel))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("google-play/feature-graphic is required", r.stdout)
        self.assertIn("google-play/tv-banner is required", r.stdout)
        self.assertIn("expects 4", r.stdout)
        (self.rel / "release.json").write_text(json.dumps({"targets": ["google-play/tv"], "reused": {
            "google-play/feature-graphic": "kept from 1.0", "google-play/tv-banner": "kept from 1.0"}}))
        r = run("validate_assets.py", str(self.rel))
        self.assertIn("**INFO** google-play/feature-graphic reused", r.stdout)
        self.assertNotIn("is required alongside", r.stdout)

    def test_tablet_16_10_accepted(self):
        for i in range(1, 5):
            img(self.rel / "google-play" / "tablet-10-inch" / f"0{i}.png", (2560, 1600), (0, i * 40, 0))
        r = run("validate_assets.py", str(self.rel), "--target", "google-play/tablet-10-inch")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("recommended aspect", r.stdout)

    def test_thumbnails(self):
        img(self.rel / "google-play" / "phone" / "01.png", (1080, 1920))
        thumbs = self.rel / "previews" / "thumbnails"
        r = run("contact_sheet.py", str(self.rel), "--thumb-height", "180", "--thumbnails", str(thumbs))
        self.assertEqual(r.returncode, 0, r.stderr)
        with Image.open(thumbs / "google-play-phone-01.png") as t:
            self.assertEqual(t.height, 180)


@unittest.skipUnless(os.environ.get("LAUNCHFRAME_LIVE_SERIAL"), "set LAUNCHFRAME_LIVE_SERIAL to an emulator serial")
class LiveEmulator(unittest.TestCase):
    def test_ui_and_shot(self):
        serial = os.environ["LAUNCHFRAME_LIVE_SERIAL"]
        tmp = Path(tempfile.mkdtemp(prefix="lf-live-"))
        try:
            r = run("capture_android.py", "ui", "--serial", serial, "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIsInstance(json.loads(r.stdout), list)
            out = tmp / "src" / "live.png"
            r = run("capture_android.py", "shot", "--serial", serial, "--out", str(out), "--screen", "live")
            self.assertEqual(r.returncode, 0, r.stderr)
            entry = json.loads((out.parent / "captures.json").read_text())["captures"][0]
            self.assertEqual(entry["provenance"], "auto-captured")
            self.assertTrue(entry["device"]["emulator"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
