#!/usr/bin/env python3
"""Render HTML/CSS compositions to exact-size, opaque store images.

Each HTML file is rendered in headless Chromium at exactly WIDTH x HEIGHT CSS
pixels with device scale factor 1, then flattened to RGB (no alpha) and saved
as PNG or JPEG. The output size is verified; nothing is ever resized.

Usage:
  python render_html.py working/google-play/phone/01.html --out google-play/phone/01.png --size 1080x1920
  python render_html.py "working/google-play/phone/*.html" --outdir google-play/phone --size 1080x1920
  python render_html.py comp.html --out 01.jpg --size 1320x2868 --format jpeg --quality 92

Engines (auto order): Playwright for Python (if installed and a Chromium is
available), then a local Chrome / Edge / Chromium in headless mode.
Override with --engine and --browser PATH, or env LAUNCHFRAME_BROWSER.

Requires: Python 3.9+, Pillow, and either `pip install playwright`
(+ `python -m playwright install chromium`, or an installed Chrome/Edge) or
an installed Chrome/Edge/Chromium.
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.stderr.write("Pillow is required: pip install Pillow\n")
    sys.exit(2)

BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
PATH_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge",
              "microsoft-edge"]
# Time budget for web fonts and images to load before capture (ms).
SETTLE_MS = 4000


def find_browser(explicit: str | None) -> str | None:
    for cand in [explicit, os.environ.get("LAUNCHFRAME_BROWSER")]:
        if cand and Path(cand).exists():
            return cand
    for cand in BROWSER_CANDIDATES:
        if Path(cand).exists():
            return cand
    for name in PATH_NAMES:
        hit = shutil.which(name)
        if hit:
            return hit
    return None


def render_playwright(jobs, width, height, browser_path):
    from playwright.sync_api import sync_playwright  # noqa: PLC0415 - optional dependency

    with sync_playwright() as p:
        browser = None
        attempts = [{}]
        if browser_path:
            attempts.insert(0, {"executable_path": browser_path})
        attempts += [{"channel": "chrome"}, {"channel": "msedge"}]
        last = None
        for kw in attempts:
            try:
                browser = p.chromium.launch(**kw)
                break
            except Exception as exc:  # noqa: BLE001
                last = exc
        if browser is None:
            raise RuntimeError(f"Playwright could not launch Chromium: {last}")
        ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
        page = ctx.new_page()
        for html, tmp in jobs:
            page.goto(Path(html).resolve().as_uri(), wait_until="networkidle")
            page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")
            page.evaluate("""Promise.all(Array.from(document.images).map(i => i.complete ? 1 :
                new Promise(r => { i.onload = i.onerror = r; })))""")
            page.screenshot(path=str(tmp), full_page=False)
        browser.close()


def render_cli(jobs, width, height, browser_path):
    if not browser_path:
        raise RuntimeError("No Chrome/Edge/Chromium found. Install one, or pip install playwright, "
                           "or pass --browser PATH.")
    for html, tmp in jobs:
        with tempfile.TemporaryDirectory(prefix="launchframe-profile-") as profile:
            cmd = [browser_path, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                   "--no-default-browser-check", "--force-device-scale-factor=1",
                   "--allow-file-access-from-files", f"--user-data-dir={profile}",
                   f"--window-size={width},{height}", f"--virtual-time-budget={SETTLE_MS}",
                   f"--screenshot={tmp}", Path(html).resolve().as_uri()]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if not Path(tmp).exists():
                raise RuntimeError(f"Browser did not write a screenshot for {html}:\n{proc.stderr[-2000:]}")


def finalize(tmp: Path, out: Path, width: int, height: int, fmt: str, quality: int, bg: str) -> None:
    with Image.open(tmp) as im:
        im.load()
        if im.size != (width, height):
            raise RuntimeError(f"Rendered {im.size[0]}x{im.size[1]}, expected {width}x{height}. "
                               "Not resizing (it would distort the UI). Check the page has no scaling "
                               "and try --engine playwright.")
        if im.mode in ("RGBA", "LA", "P"):
            rgba = im.convert("RGBA")
            base = Image.new("RGB", im.size, bg)
            base.paste(rgba, mask=rgba.getchannel("A"))
            rgb = base
        else:
            rgb = im.convert("RGB")
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "jpeg":
        rgb.save(out, "JPEG", quality=quality, subsampling=0, optimize=True)
    else:
        rgb.save(out, "PNG", optimize=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", nargs="+", help="HTML file(s) or glob pattern(s)")
    ap.add_argument("--size", required=True, help="WIDTHxHEIGHT in pixels, e.g. 1080x1920")
    ap.add_argument("--out", help="output file (single input only)")
    ap.add_argument("--outdir", help="output folder; file name = HTML name with new extension")
    ap.add_argument("--format", choices=["png", "jpeg"], default="png")
    ap.add_argument("--quality", type=int, default=92, help="JPEG quality (default 92)")
    ap.add_argument("--bg", default="#FFFFFF", help="color used to flatten any transparency (default white)")
    ap.add_argument("--engine", choices=["auto", "playwright", "chrome"], default="auto")
    ap.add_argument("--browser", help="path to Chrome/Edge/Chromium executable")
    args = ap.parse_args(argv)

    try:
        width, height = (int(x) for x in args.size.lower().split("x"))
    except ValueError:
        ap.error("--size must look like 1080x1920")
    inputs: list[Path] = []
    for pattern in args.html:
        hits = sorted(glob.glob(pattern))
        inputs += [Path(h) for h in (hits or [pattern])]
    missing = [str(p) for p in inputs if not p.is_file()]
    if missing:
        sys.stderr.write("Not found: " + ", ".join(missing) + "\n")
        return 2
    if args.out and len(inputs) != 1:
        ap.error("--out works with a single input; use --outdir for several")
    if not args.out and not args.outdir:
        ap.error("give --out or --outdir")
    ext = ".jpg" if args.format == "jpeg" else ".png"
    outputs = [Path(args.out)] if args.out else [Path(args.outdir) / (p.stem + ext) for p in inputs]

    browser = find_browser(args.browser)
    with tempfile.TemporaryDirectory(prefix="launchframe-render-") as tmpdir:
        jobs = [(str(p), Path(tmpdir) / f"{i:03d}.png") for i, p in enumerate(inputs)]
        engine_used = None
        errors = []
        engines = ["playwright", "chrome"] if args.engine == "auto" else [args.engine]
        for engine in engines:
            try:
                if engine == "playwright":
                    render_playwright(jobs, width, height, browser)
                else:
                    render_cli(jobs, width, height, browser)
                engine_used = engine
                break
            except ImportError:
                errors.append("playwright: not installed")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{engine}: {exc}")
        if engine_used is None:
            sys.stderr.write("Rendering failed:\n  " + "\n  ".join(errors) + "\n")
            return 1
        for (html, tmp), out in zip(jobs, outputs):
            try:
                finalize(tmp, out, width, height, args.format, args.quality, args.bg)
            except RuntimeError as exc:
                sys.stderr.write(f"{html}: {exc}\n")
                return 1
            print(f"{html} -> {out} ({width}x{height} {args.format.upper()}, engine={engine_used})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
