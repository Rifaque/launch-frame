#!/usr/bin/env python3
"""Capture a running web app (or a desktop app's web UI) at an exact viewport.

  python capture_web.py http://localhost:5173/library --viewport 1920x1080 \
      --out source-screenshots/web-library.png --screen library [--scale 1] [--wait-for "text=Library"] \
      [--dark] [--target other-platforms/web]

Uses Playwright for Python (preferred: supports --wait-for and --dark) or a local Chrome/Edge in
headless mode. Captures the real rendered page; never reconstruct UI from source code.
Requires: Python 3.9+, Pillow, Playwright or Chrome/Edge/Chromium.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from captures import record  # noqa: E402
from render_html import find_browser  # noqa: E402

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover
    sys.stderr.write("Pillow is required: pip install Pillow\n")
    sys.exit(2)


def shoot_playwright(url, w, h, scale, out, wait_for, dark):
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as p:
        browser = None
        for kw in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
            try:
                browser = p.chromium.launch(**kw)
                break
            except Exception:  # noqa: BLE001
                continue
        if browser is None:
            raise RuntimeError("Playwright could not launch Chromium")
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=scale,
                                  color_scheme="dark" if dark else "light")
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        if wait_for:
            page.locator(wait_for).first.wait_for(timeout=30000)
        page.evaluate("document.fonts ? document.fonts.ready.then(() => true) : true")
        page.screenshot(path=str(out), full_page=False)
        browser.close()
    return "playwright"


def shoot_chrome(url, w, h, scale, out):
    browser = find_browser(None)
    if not browser:
        raise RuntimeError("No Playwright and no Chrome/Edge found")
    with tempfile.TemporaryDirectory(prefix="launchframe-web-") as prof:
        subprocess.run([browser, "--headless=new", "--hide-scrollbars", f"--force-device-scale-factor={scale}",
                        f"--user-data-dir={prof}", f"--window-size={w},{h}", "--virtual-time-budget=8000",
                        f"--screenshot={out}", url], capture_output=True, timeout=120)
    if not out.exists():
        raise RuntimeError("Chrome did not write a screenshot")
    return "headless chrome"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--viewport", required=True, help="CSS pixels, e.g. 1440x900")
    ap.add_argument("--scale", type=float, default=1, help="device scale factor (2 gives 2x pixels)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--screen", required=True)
    ap.add_argument("--wait-for", help="Playwright selector that must be visible before capture")
    ap.add_argument("--dark", action="store_true", help="prefers-color-scheme: dark (Playwright only)")
    ap.add_argument("--target")
    args = ap.parse_args(argv)
    w, h = (int(x) for x in args.viewport.lower().split("x"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    method = None
    try:
        method = shoot_playwright(args.url, w, h, args.scale, out, args.wait_for, args.dark)
    except ImportError:
        errors.append("playwright not installed")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"playwright: {exc}")
    if method is None:
        if args.wait_for or args.dark:
            errors.append("--wait-for/--dark need Playwright")
        try:
            method = shoot_chrome(args.url, w, h, args.scale, out)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"chrome: {exc}")
    if method is None:
        sys.stderr.write("error: " + "; ".join(errors) + "\n")
        return 1
    with Image.open(out) as im:
        blank = ImageStat.Stat(im.convert("L").resize((64, 64))).stddev[0] < 2.0
    if blank:
        out.unlink()
        sys.stderr.write("error: page rendered blank (not loaded, or needs --wait-for); not saved\n")
        return 1
    device = {"kind": "web", "viewport": f"{w}x{h}", "scale": args.scale, "url": args.url}
    entry = record(out.parent, out, "auto-captured", args.screen, f"browser screenshot ({method})", device,
                   args.target)
    print(f"Captured {out} {entry['width']}x{entry['height']} via {method}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
