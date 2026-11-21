#!/usr/bin/env python3
"""Scan an app repository for brand evidence: fonts, color tokens, icons/logos.
(Platform/device support is discover_targets.py's job.)

It finds candidates; it does not decide. Read the files it points to and
confirm before writing design-system.md or choosing platforms.

Usage:
  python scan_brand.py [REPO_DIR] [--json brand-scan.json] [--max-colors 40]

Requires: Python 3.9+. Pillow is optional (used to read font family names).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "build", "dist", "out", ".next", ".gradle", ".idea", "Pods", "DerivedData",
             ".venv", "venv", "__pycache__", ".dart_tool", "store-assets", ".expo", "coverage", "vendor",
             "target", ".turbo", ".cache", "intermediates", "generated", ".kotlin"}
TEXT_EXTS = {".kt", ".kts", ".java", ".xml", ".swift", ".dart", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
             ".css", ".scss", ".sass", ".less", ".json", ".yaml", ".yml", ".html", ".vue", ".svelte", ".plist",
             ".gradle", ".toml", ".md"}
FONT_EXTS = {".ttf", ".otf", ".woff", ".woff2", ".ttc"}
THEMEY = re.compile(r"(theme|color|colour|palette|token|tailwind|style|global|variable|brand|design|type|font)",
                    re.I)
HEX = re.compile(r"(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
# 0xAARRGGBB literals: Compose Color(0xFF...), custom wrappers like Argb(0xFF...L), Flutter Color(0xFF...)
ARGB_LITERAL = re.compile(r"\b0x([0-9a-fA-F]{8})[uUlL]{0,2}\b")
NAMED_COLOR = re.compile(
    r"""(?P<name>[A-Za-z_][\w.-]{1,40})["']?\s*[:=]\s*["']?(?:[A-Za-z]+\(\s*)?(?:0x(?P<argb>[0-9a-fA-F]{8})|(?P<hex>#[0-9a-fA-F]{3,8}))""")
XML_COLOR = re.compile(r"""<color\s+name="(?P<name>[^"]+)"\s*>\s*(?P<hex>#[0-9a-fA-F]{3,8})\s*</color>""")
CSS_VAR = re.compile(r"(--[\w-]+)\s*:\s*([^;}{]{1,80});")
FONT_REFS = [
    re.compile(r"""font-?family\s*[:=]\s*["']?([^;"'\n,}]+)""", re.I),
    re.compile(r"""fontFamily\s*[:=]\s*["']([^"']+)["']"""),
    re.compile(r"""import\s*\{([^}]+)\}\s*from\s*["']next/font/google["']"""),
    re.compile(r"""@expo-google-fonts/([\w-]+)"""),
    re.compile(r"""fonts\.googleapis\.com/css2?\?family=([^"'&>\s]+)"""),
    re.compile(r"""UIFont\(name:\s*"([^"]+)\""""),
    re.compile(r"""Font\.custom\(\s*"([^"]+)\""""),
    re.compile(r"""GoogleFont\(\s*"([^"]+)"\s*\)"""),
    re.compile(r"""R\.font\.(\w+)"""),
    re.compile(r"""family:\s*([A-Za-z][\w ]+)\s*$""", re.M),  # pubspec.yaml fonts
]
TEST_DIR = re.compile(r"^(tests?|__tests__|spec|fixtures?|\w*Test)$", re.I)
ICON_NAME = re.compile(r"(icon|logo|ic_launcher|appicon|favicon|brand|wordmark|splash|banner)", re.I)


def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            yield Path(dirpath) / name


def font_name(path: Path) -> str:
    try:
        from PIL import ImageFont
        fam, style = ImageFont.truetype(str(path), 12).getname()
        return f"{fam} {style}".strip()
    except Exception:  # noqa: BLE001 - optional enrichment only
        return ""


def read_text(path: Path, limit=600_000) -> str:
    try:
        if path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def norm_hex(h: str) -> str:
    h = h.lstrip("#").upper()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 8:  # treat as RRGGBBAA for CSS; ARGB handled separately
        h = h[:6]
    return "#" + h


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", nargs="?", default=".", help="app repository root (default: current dir)")
    ap.add_argument("--json", dest="json_out", help="write findings as JSON")
    ap.add_argument("--max-colors", type=int, default=40)
    args = ap.parse_args(argv)
    root = Path(args.repo).resolve()
    if not root.is_dir():
        sys.stderr.write(f"Not a directory: {root}\n")
        return 2

    fonts, icons = [], []
    font_refs: Counter = Counter()
    color_count: Counter = Counter()
    color_names: dict[str, set] = defaultdict(set)
    color_files: dict[str, set] = defaultdict(set)
    css_vars: dict[str, str] = {}
    for path in walk(root):
        rel = path.relative_to(root).as_posix()
        ext = path.suffix.lower()
        name = path.name
        if ext in FONT_EXTS:
            fonts.append({"path": rel, "name": font_name(path)})
            continue
        if ext in {".png", ".svg", ".webp", ".jpg", ".jpeg", ".ico", ".icns"} and ICON_NAME.search(rel):
            icons.append(rel)
            continue
        if ext not in TEXT_EXTS:
            continue
        text = read_text(path)
        if not text:
            continue

        # ---- fonts referenced in code
        for rx in FONT_REFS:
            for m in rx.findall(text):
                for part in str(m).split(","):
                    part = part.strip().strip("'\" ").replace("+", " ")
                    if 1 < len(part) < 60 and not part.startswith(("var(", "$", "{", "inherit")):
                        font_refs[part] += 1

        # ---- colors (only theme-like files, to stay meaningful)
        if not THEMEY.search(rel) and name != "colors.xml":
            continue
        if any(TEST_DIR.match(part) for part in Path(rel).parts[:-1]):
            continue  # test fixtures use arbitrary colors
        for m in XML_COLOR.finditer(text):
            h = norm_hex(m.group("hex"))
            color_count[h] += 1
            color_names[h].add(m.group("name"))
            color_files[h].add(rel)
        for m in NAMED_COLOR.finditer(text):
            h = ("#" + m.group("argb")[2:].upper()) if m.group("argb") else norm_hex(m.group("hex"))
            color_count[h] += 1
            color_names[h].add(m.group("name"))
            color_files[h].add(rel)
        for m in ARGB_LITERAL.finditer(text) if ext in {".kt", ".kts", ".java", ".dart", ".swift"} else ():
            h = "#" + m.group(1)[2:].upper()
            color_count[h] += 1
            color_files[h].add(rel)
        for m in HEX.finditer(text):
            h = norm_hex(m.group(0))
            color_count[h] += 1
            color_files[h].add(rel)
        if ext in {".css", ".scss", ".sass", ".less"}:
            for var, val in CSS_VAR.findall(text):
                if any(k in var.lower() for k in ("color", "bg", "background", "primary", "secondary", "accent",
                                                   "surface", "foreground", "muted", "border", "font", "radius",
                                                   "brand")) and len(css_vars) < 80:
                    css_vars.setdefault(var, val.strip())

    colors = [{"hex": h, "occurrences": n, "names": sorted(color_names[h])[:6],
               "files": sorted(color_files[h])[:4]} for h, n in color_count.most_common(args.max_colors)]
    result = {"repo": str(root), "font_files": fonts[:60],
              "font_references": font_refs.most_common(25), "colors": colors, "css_variables": css_vars,
              "icon_and_logo_files": icons[:60]}

    print(f"# Brand scan: {root.name}\n")
    print("## Font files")
    for f in fonts[:30]:
        print(f"- {f['path']}" + (f"  ({f['name']})" if f["name"] else ""))
    if not fonts:
        print("- none bundled")
    print("\n## Font references in code (name: count)")
    for n, c in font_refs.most_common(15):
        print(f"- {n}: {c}")
    print("\n## Color candidates from theme-like files (hex, count, names)")
    for c in colors[:25]:
        print(f"- {c['hex']}  x{c['occurrences']}  {', '.join(c['names'])}  [{', '.join(c['files'][:2])}]")
    if css_vars:
        print("\n## CSS custom properties")
        for k, v in list(css_vars.items())[:30]:
            print(f"- {k}: {v}")
    print("\n## Icons / logos / brand images")
    for i in icons[:25]:
        print(f"- {i}")
    print("\nCandidates only: open the files above to confirm roles before documenting them.")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
