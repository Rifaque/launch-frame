#!/usr/bin/env python3
"""Provenance manifest for source screenshots (source-screenshots/captures.json).

Every source screenshot gets one entry recording where it came from:
  auto-captured   - taken by an agent with capture_android.py / capture_apple.py / capture_web.py
  existing        - found in the repository (path recorded)
  user-provided   - supplied by the user
plus device, resolution, screen name, method and SHA-256, so READMEs can state
provenance truthfully and later steps can detect edited sources.

Usage:
  python captures.py add FILE --dir source-screenshots --provenance existing|user-provided \
      --screen home [--device "Pixel 8 (physical)"] [--target google-play/phone] [--note TEXT]
  python captures.py list --dir source-screenshots
  python captures.py verify --dir source-screenshots     # hashes still match? files unregistered?

`add` copies FILE byte-for-byte into the folder (never re-encodes) unless it is already there.
Requires: Python 3.9+, Pillow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.stderr.write("Pillow is required: pip install Pillow\n")
    sys.exit(2)

MANIFEST = "captures.json"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
PROVENANCE = {"auto-captured", "existing", "user-provided"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(folder: Path) -> dict:
    mf = folder / MANIFEST
    if mf.is_file():
        return json.loads(mf.read_text(encoding="utf-8"))
    return {"schema": 1, "captures": []}


def save(folder: Path, data: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / MANIFEST).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def record(folder: Path, file: Path, provenance: str, screen: str, method: str, device: dict | None = None,
           target: str | None = None, source: str | None = None, note: str | None = None) -> dict:
    """Register a file that is already inside `folder`. Returns the entry."""
    if provenance not in PROVENANCE:
        raise ValueError(f"provenance must be one of {sorted(PROVENANCE)}")
    with Image.open(file) as im:
        width, height = im.size
        fmt = (im.format or "").lower()
    entry = {
        "file": file.name, "screen": screen, "provenance": provenance, "method": method,
        "width": width, "height": height, "format": fmt, "sha256": sha256(file),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if device:
        entry["device"] = device
    if target:
        entry["target"] = target
    if source:
        entry["source"] = source
    if note:
        entry["note"] = note
    data = load(folder)
    data["captures"] = [c for c in data["captures"] if c["file"] != file.name] + [entry]
    save(folder, data)
    return entry


def cmd_add(args) -> int:
    folder = Path(args.dir)
    src = Path(args.file)
    if not src.is_file():
        sys.stderr.write(f"Not found: {src}\n")
        return 2
    if args.provenance == "auto-captured":
        sys.stderr.write("Use the capture_* scripts for auto-captured files; 'add' is for existing or "
                         "user-provided screenshots.\n")
        return 2
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (args.name or src.name)
    if src.resolve() != dest.resolve():
        if dest.exists() and sha256(dest) != sha256(src):
            sys.stderr.write(f"{dest} exists with different content; choose --name\n")
            return 2
        shutil.copy2(src, dest)
    device = {"description": args.device} if args.device else None
    entry = record(folder, dest, args.provenance, args.screen, "copied unchanged", device, args.target,
                   source=str(src), note=args.note)
    print(f"Registered {dest.name}: {entry['width']}x{entry['height']} {args.provenance}")
    return 0


def cmd_list(args) -> int:
    data = load(Path(args.dir))
    if not data["captures"]:
        print("No captures registered.")
        return 0
    print("| File | Screen | Provenance | Method | Size | Device |")
    print("|---|---|---|---|---|---|")
    for c in data["captures"]:
        dev = c.get("device", {})
        desc = dev.get("description") or " ".join(str(dev.get(k, "")) for k in ("model", "kind")).strip() or "-"
        print(f"| {c['file']} | {c['screen']} | {c['provenance']} | {c['method']} | {c['width']}x{c['height']} | {desc} |")
    return 0


def cmd_verify(args) -> int:
    folder = Path(args.dir)
    data = load(folder)
    problems = 0
    known = {c["file"] for c in data["captures"]}
    for c in data["captures"]:
        p = folder / c["file"]
        if not p.is_file():
            print(f"MISSING  {c['file']}")
            problems += 1
        elif sha256(p) != c["sha256"]:
            print(f"CHANGED  {c['file']} (source screenshots must stay untouched)")
            problems += 1
    for p in sorted(folder.iterdir()) if folder.is_dir() else []:
        if p.suffix.lower() in IMAGE_EXTS and p.name not in known:
            print(f"UNREGISTERED  {p.name} (provenance unknown)")
            problems += 1
    print("OK" if not problems else f"{problems} problem(s)")
    return 1 if problems else 0


def cmd_remove(args) -> int:
    """Drop an unusable capture (duplicate, wrong screen, private data) from the folder and the manifest."""
    folder = Path(args.dir)
    data = load(folder)
    before = len(data["captures"])
    data["captures"] = [c for c in data["captures"] if c["file"] != args.file]
    if len(data["captures"]) == before and not (folder / args.file).exists():
        sys.stderr.write(f"{args.file} is not in {folder}\n")
        return 2
    removed = data.setdefault("removed", [])
    removed.append({"file": args.file, "reason": args.reason,
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    save(folder, data)
    (folder / args.file).unlink(missing_ok=True)
    print(f"Removed {args.file} ({args.reason})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="register an existing or user-provided screenshot")
    a.add_argument("file")
    a.add_argument("--dir", required=True)
    a.add_argument("--provenance", required=True, choices=sorted(PROVENANCE))
    a.add_argument("--screen", required=True, help="screen name, e.g. home, player")
    a.add_argument("--name", help="file name inside --dir (default: original name)")
    a.add_argument("--device", help="free-text device description, e.g. 'Fire TV Stick 4K Plus (physical)'")
    a.add_argument("--target", help="intended store target, e.g. google-play/tv")
    a.add_argument("--note")
    a.set_defaults(fn=cmd_add)
    r = sub.add_parser("remove", help="delete an unusable capture and record why")
    r.add_argument("file")
    r.add_argument("--dir", required=True)
    r.add_argument("--reason", required=True)
    r.set_defaults(fn=cmd_remove)
    for name, fn in (("list", cmd_list), ("verify", cmd_verify)):
        s = sub.add_parser(name)
        s.add_argument("--dir", required=True)
        s.set_defaults(fn=fn)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
