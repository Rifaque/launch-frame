"""LaunchFrame repository tests.

Run:  python -m unittest discover -s tests -v

All images created here are SYNTHETIC TEST DATA (flat colored rectangles labelled
"TEST DATA") used only to exercise the scripts. They are not store assets.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "launch-frame"
SCRIPTS = SKILL / "scripts"


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True,
                          timeout=300)


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def opened(path: Path) -> Image.Image:
    """Load an image fully and close the file handle."""
    with Image.open(path) as im:
        im.load()
        return im.copy()


def fixture_image(path: Path, size, mode="RGB", color=(40, 90, 160), fmt=None, label="TEST DATA"):
    path.parent.mkdir(parents=True, exist_ok=True)
    fill = color if mode != "RGBA" else color + (255,)
    im = Image.new(mode if mode != "CMYK" else "RGB", size, fill)
    ImageDraw.Draw(im).text((10, 10), label, fill=(255, 255, 255))
    if mode == "CMYK":
        im = im.convert("CMYK")
    im.save(path, fmt or ("JPEG" if path.suffix.lower() in (".jpg", ".jpeg") else "PNG"))
    return path


class SkillMetadata(unittest.TestCase):
    def setUp(self):
        self.text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", self.text, re.S)
        self.assertIsNotNone(m, "SKILL.md must start with YAML frontmatter on line 1")
        self.front = {}
        for line in m.group(1).splitlines():
            key, _, value = line.partition(":")
            self.front[key.strip()] = value.strip()

    def test_frontmatter_fields(self):
        allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
        self.assertTrue(set(self.front) <= allowed, f"non-portable keys: {set(self.front) - allowed}")
        name = self.front["name"]
        self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(name), 64)
        self.assertEqual(name, SKILL.name, "name must match the skill folder")
        desc = self.front["description"]
        self.assertTrue(0 < len(desc) <= 1024, f"description length {len(desc)}")
        self.assertNotRegex(desc, r"<[^>]+>", "no XML tags in description")
        self.assertNotIn("claude", name)
        self.assertNotIn("anthropic", name)

    def test_body_length(self):
        self.assertLess(len(self.text.splitlines()), 500)

    def test_links_resolve(self):
        files = [SKILL / "SKILL.md"] + list((SKILL / "references").rglob("*.md"))
        for f in files:
            for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", f.read_text(encoding="utf-8")):
                if target.startswith("http"):
                    continue
                self.assertTrue((f.parent / target).exists(), f"{f.relative_to(SKILL)} links missing {target}")

    def test_every_reference_is_linked_from_skill(self):
        linked = set(re.findall(r"\]\(([^)#\s]+)", self.text))
        for ref in (SKILL / "references").rglob("*.md"):
            rel = ref.relative_to(SKILL).as_posix()
            self.assertIn(rel, linked, f"{rel} is not reachable from SKILL.md")

    def test_script_paths_in_skill_exist(self):
        for script in re.findall(r"scripts/(\w+\.py)", self.text):
            self.assertTrue((SCRIPTS / script).exists(), script)


class Profiles(unittest.TestCase):
    def test_profiles_are_well_formed(self):
        data = json.loads((SKILL / "assets" / "platform-profiles.json").read_text(encoding="utf-8"))
        self.assertRegex(data["checked"], r"^\d{4}-\d{2}-\d{2}$")
        for pk, platform in data["platforms"].items():
            self.assertTrue(platform["sources"], pk)
            for src in platform["sources"]:
                self.assertTrue(src.startswith("https://"), src)
            for tk, t in platform["targets"].items():
                where = f"{pk}/{tk}"
                self.assertIn("formats", t, where)
                self.assertIn(t.get("alpha"), {"forbidden", "discouraged", "allowed"}, where)
                self.assertIn("count", t, where)
                for size in t.get("sizes", []) + t.get("recommended", {}).get("sizes", []):
                    self.assertEqual(len(size), 2, where)
                for a in t.get("aspects", []) + t.get("recommended", {}).get("aspects", []):
                    self.assertRegex(a, r"^\d+:\d+$", where)


class Validator(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lf-test-"))
        self.rel = self.tmp / "store-assets" / "release-0.0.0-test"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_valid_google_play_phone_passes(self):
        for i in range(1, 5):
            fixture_image(self.rel / "google-play" / "phone" / f"{i:02d}.png", (1080, 1920), color=(i * 40, 80, 120))
        fixture_image(self.rel / "google-play" / "feature-graphic" / "01.png", (1024, 500))
        report = self.rel / "validation-report.md"
        r = run("validate_assets.py", str(self.rel), "--report", str(report))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS", report.read_text(encoding="utf-8"))
        self.assertIn("Not checked automatically", r.stdout)

    def test_windows_and_posix_paths(self):
        for i in range(1, 4):
            fixture_image(self.rel / "amazon-appstore" / "fire-tv" / f"{i:02d}.png", (1920, 1080), color=(i * 50, 0, 0))
        for p in (str(self.rel), self.rel.as_posix()):
            r = run("validate_assets.py", p)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_invalid_assets_are_errors(self):
        phone = self.rel / "google-play" / "phone"
        rgba = fixture_image(phone / "01.png", (1080, 1920), mode="RGBA")
        img = opened(rgba)
        img.putpixel((0, 0), (0, 0, 0, 0))
        img.save(rgba)
        fixture_image(phone / "02.png", (1080, 1920), fmt="JPEG")                # JPEG named .png
        fixture_image(phone / "03.png", (800, 2000))                            # ratio 2.5 > 2.3
        fixture_image(phone / "04.jpg", (1080, 1920), mode="CMYK")              # CMYK
        fixture_image(phone / "05.png", (300, 600))                             # below 320
        iphone = self.rel / "apple-app-store" / "iphone"
        fixture_image(iphone / "01.png", (1080, 1920))                          # not an Apple size
        r = run("validate_assets.py", str(self.rel), "--json", str(self.tmp / "out.json"))
        self.assertEqual(r.returncode, 1, r.stdout)
        out = json.loads((self.tmp / "out.json").read_text(encoding="utf-8"))
        files = {f"{res['target']}/{f['file']}": f for res in out["results"] for f in res["files"]}
        self.assertTrue(any("transparent" in e for e in files["google-play/phone/01.png"]["errors"]))
        self.assertTrue(any("extension" in e for e in files["google-play/phone/02.png"]["errors"]))
        self.assertTrue(any("2.3" in e for e in files["google-play/phone/03.png"]["errors"]))
        self.assertTrue(any("CMYK" in e for e in files["google-play/phone/04.jpg"]["errors"]))
        self.assertTrue(any("below minimum" in e for e in files["google-play/phone/05.png"]["errors"]))
        self.assertTrue(any("not an accepted size" in e for e in files["apple-app-store/iphone/01.png"]["errors"]))

    def test_opaque_alpha_channel_still_error_when_forbidden(self):
        fixture_image(self.rel / "apple-app-store" / "iphone" / "01.png", (1320, 2868), mode="RGBA")
        r = run("validate_assets.py", str(self.rel))
        self.assertEqual(r.returncode, 1)
        self.assertIn("alpha channel (fully opaque)", r.stdout)

    def test_count_naming_duplicates_and_missing(self):
        phone = self.rel / "google-play" / "phone"
        fixture_image(phone / "01.png", (1080, 1920))
        shutil.copy(phone / "01.png", phone / "home.png")                       # duplicate + unnumbered
        fixture_image(phone / "03.png", (1080, 1920), color=(1, 2, 3))           # gap in numbering
        (self.rel / "release.json").write_text(json.dumps(
            {"app": "Fixture", "release": "0.0.0", "targets": ["google-play/phone", "google-play/feature-graphic"]}))
        (self.rel / "google-play" / "mystery").mkdir()
        fixture_image(self.rel / "google-play" / "mystery" / "01.png", (100, 100))
        r = run("validate_assets.py", str(self.rel))
        self.assertEqual(r.returncode, 1)
        self.assertIn("feature-graphic", r.stdout)
        self.assertIn("directory is missing", r.stdout)
        self.assertIn("identical to 01.png", r.stdout)
        self.assertIn("not numbered", r.stdout)
        self.assertIn("not contiguous", r.stdout)
        self.assertIn("recommended", r.stdout)           # 3 < 4 recommended
        self.assertIn("google-play/mystery", r.stdout)   # reported as not validated

    def test_too_many_and_automotive_orientation(self):
        for i in range(1, 10):
            fixture_image(self.rel / "google-play" / "phone" / f"{i:02d}.png", (1080, 1920), color=(i, i, i))
        auto = self.rel / "google-play" / "automotive"
        fixture_image(auto / "01.png", (800, 1280))
        fixture_image(auto / "02.png", (1024, 768))
        r = run("validate_assets.py", str(self.rel))
        self.assertEqual(r.returncode, 1)
        self.assertIn("at most 8 allowed", r.stdout)
        self.assertIn("at least 2 portrait and 2 landscape", r.stdout)

    def test_override_profile_and_list_targets(self):
        override = self.tmp / "extra.json"
        override.write_text(json.dumps({"checked": "2026-01-01", "platforms": {"test-store": {
            "name": "Test Store", "sources": ["https://example.invalid/specs"],
            "targets": {"phone": {"formats": ["png"], "alpha": "forbidden", "count": {"min": 1, "max": 2},
                                  "sizes": [[100, 200]]}}}}}))
        fixture_image(self.rel / "test-store" / "phone" / "01.png", (100, 200))
        r = run("validate_assets.py", str(self.rel), "--profiles", str(override))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2026-01-01", r.stdout)
        r = run("validate_assets.py", "--list-targets")
        self.assertIn("google-play/feature-graphic", r.stdout)
        self.assertIn("amazon-appstore/fire-tv-background", r.stdout)

    def test_aspect_matching(self):
        v = load("validate_assets")
        self.assertTrue(v.matches_aspect(1920, 1080, "16:9"))
        self.assertTrue(v.matches_aspect(1080, 1920, "9:16"))
        self.assertTrue(v.matches_aspect(3840, 2400, "8:5"))
        self.assertFalse(v.matches_aspect(1920, 1200, "16:9"))


class OtherScripts(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lf-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_contact_sheet(self):
        rel = self.tmp / "release"
        for i in range(1, 4):
            fixture_image(rel / "google-play" / "phone" / f"{i:02d}.png", (1080, 1920), color=(i * 60, 40, 40))
        fixture_image(rel / "google-play" / "tv" / "01.png", (1920, 1080))
        fixture_image(rel / "source-screenshots" / "raw.png", (500, 500))   # must be ignored
        r = run("contact_sheet.py", str(rel))
        self.assertEqual(r.returncode, 0, r.stderr)
        sheet = rel / "previews" / "contact-sheet.png"
        self.assertTrue(sheet.exists())
        self.assertIn("4 images in 2 set(s)", r.stdout)
        small = rel / "previews" / "store-scale.png"
        r = run("contact_sheet.py", str(rel), "--thumb-height", "180", "--out", str(small))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(opened(small).height, opened(sheet).height)

    def test_palette_and_contrast(self):
        a = fixture_image(self.tmp / "a.png", (400, 800), color=(14, 18, 28))
        r = run("extract_palette.py", str(a), "--json", str(self.tmp / "p.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((self.tmp / "p.json").read_text())
        self.assertEqual(data["tone"], "dark")
        self.assertEqual(data["colors"][0]["hex"], "#0E121C")
        r = run("extract_palette.py", "contrast", "#FFFFFF", "#000000")
        self.assertIn("21.00:1", r.stdout)

    def test_scan_brand(self):
        repo = self.tmp / "app"
        (repo / "app/src/main/res/values").mkdir(parents=True)
        (repo / "app/src/main/res/values/colors.xml").write_text(
            '<resources><color name="brand_primary">#E85D3A</color></resources>')
        (repo / "app/src/main/AndroidManifest.xml").write_text(
            '<manifest><uses-feature android:name="android.software.leanback"/></manifest>')
        (repo / "web").mkdir()
        (repo / "web/globals.css").write_text(":root { --color-primary: #E85D3A; font-family: 'Fraunces', serif; }")
        (repo / "node_modules/x").mkdir(parents=True)
        (repo / "node_modules/x/theme.css").write_text(":root{--color-bad:#123456}")
        r = run("scan_brand.py", str(repo), "--json", str(self.tmp / "b.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((self.tmp / "b.json").read_text())
        hexes = {c["hex"]: c for c in data["colors"]}
        self.assertIn("#E85D3A", hexes)
        self.assertIn("brand_primary", hexes["#E85D3A"]["names"])
        self.assertNotIn("#123456", hexes)
        self.assertNotIn("platform_evidence", data)  # platform support is discover_targets.py's job
        self.assertIn("Fraunces", dict(data["font_references"]))


def browser_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return load("render_html").find_browser(None) is not None


@unittest.skipUnless(browser_available(), "no Playwright or Chrome/Edge available")
class Renderer(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lf-test-"))
        fixture_image(self.tmp / "source-screenshots" / "home.png", (540, 1170), color=(30, 160, 90))
        work = self.tmp / "working" / "google-play" / "phone"
        work.mkdir(parents=True)
        starter = (SKILL / "assets" / "templates" / "composition-starter.html").read_text(encoding="utf-8")
        for i in (1, 2):
            (work / f"0{i}.html").write_text(starter, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _check(self, engine):
        out = self.tmp / "google-play" / "phone"
        r = run("render_html.py", str(self.tmp / "working/google-play/phone/*.html"), "--outdir", str(out),
                "--size", "1080x1920", "--engine", engine)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for name in ("01.png", "02.png"):
            im = opened(out / name)
            self.assertEqual(im.size, (1080, 1920))
            self.assertEqual(im.mode, "RGB")
        # The fixture screenshot (green) must appear, i.e. relative image paths resolved.
        px = opened(out / "01.png").getpixel((540, 1900))
        self.assertGreater(px[1], px[0])
        v = run("validate_assets.py", str(self.tmp), "--target", "google-play/phone")
        self.assertIn("phone", v.stdout)
        self.assertNotIn("ERROR", v.stdout)

    def test_render_playwright(self):
        try:
            import playwright  # noqa: F401
        except ImportError:
            self.skipTest("playwright not installed")
        self._check("playwright")

    def test_render_chrome_cli(self):
        if load("render_html").find_browser(None) is None:
            self.skipTest("no Chrome/Edge")
        self._check("chrome")

    def test_size_mismatch_is_refused(self):
        v = load("render_html")
        tmp = self.tmp / "wrong.png"
        Image.new("RGB", (100, 100)).save(tmp)
        with self.assertRaises(RuntimeError):
            v.finalize(tmp, self.tmp / "out.png", 200, 200, "png", 90, "#FFFFFF")


if __name__ == "__main__":
    unittest.main()
