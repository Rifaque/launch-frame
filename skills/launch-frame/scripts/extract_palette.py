#!/usr/bin/env python3
"""Measure the colors an app's real screenshots actually use (visual DNA evidence).

Usage:
  python extract_palette.py source-screenshots/*.png [--colors 10] [--json palette.json]
  python extract_palette.py contrast "#FFFFFF" "#1A1A2E"      # WCAG contrast ratio

Output: merged palette across all images with share of pixels, luminance and
saturation, plus whether the UI is predominantly light or dark. Roles
(background / surface / accent) are hints only; confirm them against the
source code and by looking at the screens.
Requires: Python 3.9+, Pillow.
"""
from __future__ import annotations

import argparse
import colorsys
import glob
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.stderr.write("Pillow is required: pip install Pillow\n")
    sys.exit(2)


def hex_to_rgb(text: str) -> tuple[int, int, int]:
    t = text.strip().lstrip("#")
    if len(t) == 3:
        t = "".join(c * 2 for c in t)
    if len(t) != 6:
        raise ValueError(f"not a hex color: {text}")
    return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rel_luminance(rgb) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b) -> float:
    la, lb = sorted((rel_luminance(a), rel_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def palette_for(path: Path, colors: int) -> list[tuple[tuple[int, int, int], int]]:
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((400, 400))
        q = im.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
        pal = q.getpalette()
        counts = q.getcolors() or []
    return [((pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]), n) for n, i in counts]


def merge(entries, threshold=18.0):
    merged: list[list] = []  # [rgb, count]
    for rgb, n in sorted(entries, key=lambda e: -e[1]):
        for m in merged:
            if sum((a - b) ** 2 for a, b in zip(rgb, m[0])) ** 0.5 < threshold:
                m[1] += n
                break
        else:
            merged.append([rgb, n])
    return merged


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "contrast":
        if len(argv) != 3:
            sys.stderr.write("usage: extract_palette.py contrast FG BG\n")
            return 2
        ratio = contrast(hex_to_rgb(argv[1]), hex_to_rgb(argv[2]))
        verdict = "AAA" if ratio >= 7 else "AA" if ratio >= 4.5 else "AA large text only" if ratio >= 3 else "fails"
        print(f"{argv[1]} on {argv[2]}: {ratio:.2f}:1 ({verdict})")
        return 0

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+", help="screenshot files or glob patterns")
    ap.add_argument("--colors", type=int, default=10, help="colors per image before merging (default 10)")
    ap.add_argument("--json", dest="json_out", help="write results as JSON")
    args = ap.parse_args(argv)

    files: list[Path] = []
    for pattern in args.images:
        hits = glob.glob(pattern)
        files += [Path(h) for h in (hits or [pattern])]
    files = [f for f in files if f.is_file()]
    if not files:
        sys.stderr.write("No image files found.\n")
        return 2

    entries = []
    for f in files:
        try:
            entries += palette_for(f, args.colors)
        except OSError as exc:
            sys.stderr.write(f"skip {f}: {exc}\n")
    merged = merge(entries)
    total = sum(n for _, n in merged) or 1
    rows = []
    for rgb, n in sorted(merged, key=lambda m: -m[1]):
        h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
        rows.append({"hex": "#%02X%02X%02X" % rgb, "share": round(n / total, 4),
                     "luminance": round(rel_luminance(rgb), 3), "saturation": round(s, 2), "hue": round(h * 360)})
    weighted = sum(r["luminance"] * r["share"] for r in rows)
    theme = "light" if weighted > 0.4 else "dark" if weighted < 0.18 else "mixed/mid-tone"
    # Hints: most common = likely background; saturated + small share = likely accent.
    for r in rows:
        r["hint"] = ""
    if rows:
        rows[0]["hint"] = "likely background"
        neutrals = [r for r in rows[1:] if r["saturation"] < 0.15]
        if neutrals:
            neutrals[0]["hint"] = "likely surface/text"
        accents = [r for r in rows if r["saturation"] >= 0.35 and r["share"] < 0.25]
        for r in accents[:3]:
            r["hint"] = "possible accent"

    print(f"Images analysed: {len(files)}")
    print(f"Overall UI tone: {theme} (pixel-weighted luminance {weighted:.2f})\n")
    print(f"{'hex':8}  {'share':>6}  {'lum':>5}  {'sat':>4}  {'hue':>4}  hint")
    for r in rows[:16]:
        print(f"{r['hex']:8}  {r['share'] * 100:5.1f}%  {r['luminance']:5.3f}  {r['saturation']:4.2f}  {r['hue']:4d}  {r['hint']}")
    print("\nHints are heuristics. Confirm roles in source code/design tokens before using them.")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({"images": [str(f) for f in files], "tone": theme,
                                                   "weighted_luminance": round(weighted, 3), "colors": rows},
                                                  indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
