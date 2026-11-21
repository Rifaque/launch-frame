#!/usr/bin/env python3
"""Build a contact sheet (one row per asset set) for reviewing a release at a glance.

Usage:
  python contact_sheet.py RELEASE_DIR                      # all <platform>/<target> export folders
  python contact_sheet.py DIR [DIR ...] --out sheet.png     # specific folders
  python contact_sheet.py RELEASE_DIR --thumb-height 180 --out previews/store-scale.png
      (small thumbnails approximate how a listing looks in store search results)

Default output: RELEASE_DIR/previews/contact-sheet.png
Requires: Python 3.9+, Pillow.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    sys.stderr.write("Pillow is required: pip install Pillow\n")
    sys.exit(2)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
NON_EXPORT_DIRS = {"source-screenshots", "previews", "working", "other-platforms"}


def font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf", "Helvetica.ttc", "SegoeUI.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def images_in(folder: Path) -> list[Path]:
    return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
                  key=lambda p: p.name.lower())


def discover(release: Path) -> list[tuple[str, Path]]:
    rows = []
    for pdir in sorted(p for p in release.iterdir() if p.is_dir()):
        if pdir.name in NON_EXPORT_DIRS or pdir.name.startswith("."):
            continue
        for tdir in sorted(t for t in pdir.iterdir() if t.is_dir()):
            if images_in(tdir):
                rows.append((f"{pdir.name}/{tdir.name}", tdir))
    return rows


def build(rows: list[tuple[str, Path]], thumb_h: int, bg: str, max_width: int) -> Image.Image:
    pad = max(12, thumb_h // 20)
    label_h = max(14, thumb_h // 22)
    title_f, label_f = font(label_h + 6), font(label_h)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    laid = []  # (title, [(thumb, caption, cell_width)])
    for title, folder in rows:
        cells = []
        for p in images_in(folder):
            with Image.open(p) as im:
                im = im.convert("RGB")
                w = max(1, round(im.width * thumb_h / im.height))
                caption = f"{p.name}  {im.width}x{im.height}"
                cell_w = max(w, int(measure.textlength(caption, font=label_f)) + 4)
                cells.append((im.resize((w, thumb_h), Image.LANCZOS), caption, cell_w))
        laid.append((title, cells))

    # Wrap each set into lines no wider than max_width.
    lines = []  # list of (title or None, cells)
    for title, cells in laid:
        current, width, first = [], pad, True
        for cell in cells:
            cw = cell[2] + pad
            if current and width + cw > max_width:
                lines.append((title if first else None, current))
                current, width, first = [], pad, False
            current.append(cell)
            width += cw
        lines.append((title if first else None, current))

    row_h = thumb_h + label_h + pad * 2
    title_h = label_h + 6 + pad
    sheet_w = max(sum(c[2] + pad for c in cells) + pad for _, cells in lines)
    sheet_h = pad + sum(row_h + (title_h if t else 0) for t, _ in lines)
    sheet = Image.new("RGB", (sheet_w, sheet_h), bg)
    draw = ImageDraw.Draw(sheet)
    dark_bg = sum(sheet.getpixel((0, 0))) < 384
    fg = (235, 235, 235) if dark_bg else (30, 30, 30)
    muted = (150, 150, 150) if dark_bg else (110, 110, 110)
    y = pad
    for title, cells in lines:
        if title:
            draw.text((pad, y), title, fill=fg, font=title_f)
            y += title_h
        x = pad
        for thumb, caption, cell_w in cells:
            sheet.paste(thumb, (x, y))
            draw.rectangle([x - 1, y - 1, x + thumb.width, y + thumb.height], outline=muted)
            draw.text((x, y + thumb_h + 4), caption, fill=muted, font=label_f)
            x += cell_w + pad
        y += row_h
    return sheet


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="release folder, or one or more image folders")
    ap.add_argument("--out", help="output PNG path")
    ap.add_argument("--thumb-height", type=int, default=520, help="thumbnail height in px (default 520)")
    ap.add_argument("--max-width", type=int, default=4200, help="wrap rows wider than this (default 4200)")
    ap.add_argument("--bg", default="#f2f2f0", help="sheet background color (default #f2f2f0)")
    ap.add_argument("--thumbnails", help="also write one store-scale thumbnail per asset into this folder "
                                         "(height = --thumb-height)")
    args = ap.parse_args(argv)

    paths = [Path(p).resolve() for p in args.paths]
    for p in paths:
        if not p.is_dir():
            sys.stderr.write(f"Not a directory: {p}\n")
            return 2
    if len(paths) == 1 and not images_in(paths[0]):
        rows = discover(paths[0])
        default_out = paths[0] / "previews" / "contact-sheet.png"
    else:
        rows = [(p.name if p.parent == p else f"{p.parent.name}/{p.name}", p) for p in paths if images_in(p)]
        default_out = Path.cwd() / "contact-sheet.png"
    if not rows:
        sys.stderr.write("No images found.\n")
        return 2
    out = Path(args.out).resolve() if args.out else default_out
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet = build(rows, args.thumb_height, args.bg, args.max_width)
    sheet.save(out, "PNG")
    count = sum(len(images_in(p)) for _, p in rows)
    if args.thumbnails:
        tdir = Path(args.thumbnails).resolve()
        tdir.mkdir(parents=True, exist_ok=True)
        for title, folder in rows:
            for p in images_in(folder):
                with Image.open(p) as im:
                    im = im.convert("RGB")
                    w = max(1, round(im.width * args.thumb_height / im.height))
                    im.resize((w, args.thumb_height), Image.LANCZOS).save(
                        tdir / f"{title.replace('/', '-')}-{p.stem}.png", "PNG")
        print(f"Wrote {count} thumbnails to {tdir}")
    print(f"Wrote {out} ({sheet.width}x{sheet.height}, {count} images in {len(rows)} set(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
