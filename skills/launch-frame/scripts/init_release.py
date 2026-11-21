#!/usr/bin/env python3
"""Create a release folder with exact, validated target names. Use this instead of making folders by hand.

  python init_release.py <repo> --release 1.0.0 --targets google-play/phone,google-play/tv \
      [--reuse google-play/feature-graphic="current Play listing graphic"] \
      [--expected google-play/phone=5] [--force-target amazon-appstore/fire-tablet="owner confirmed"] [--dry-run]

What it enforces:
- Every target key exists in platform-profiles.json (no invented names like google-play/android-tv).
- Targets whose capability status is Unknown/Unsupported are refused unless --force-target gives a reason.
- Required companions (Google Play feature graphic; TV banner; Fire TV icon/background; Fire tablet icons)
  are added as targets automatically unless listed with --reuse and a reason.
- An existing store-assets/release-<version>/ folder is never touched (exit 3).

It runs repository discovery itself (discover_targets.py) and saves capability-report.md and
working/capability.json in the new release. Creates store-assets/release-<version>/ with release.json,
source-screenshots/, working/, previews/ and one folder per target.
Exit codes: 0 ok, 2 invalid input, 3 folder exists.
Requires: Python 3.9+.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PROFILES = SKILL_DIR / "assets" / "platform-profiles.json"
VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+_-]{0,40}$")


def parse_pairs(items: list[str], flag: str) -> dict[str, str]:
    out = {}
    for item in items:
        key, sep, val = item.partition("=")
        if not sep or not val.strip():
            raise ValueError(f"{flag} needs KEY=VALUE, got {item!r}")
        out[key.strip()] = val.strip().strip('"')
    return out


def valid_keys(profiles: dict) -> list[str]:
    return [f"{p}/{t}" for p, pv in profiles["platforms"].items() for t in pv["targets"]]


def companions_for(profiles: dict, key: str) -> list[str]:
    p, t = key.split("/", 1)
    comp = profiles["platforms"].get(p, {}).get("companions", {})
    return [f"{p}/{c}" for c in comp.get("*", []) + comp.get(t, [])]


def capability_status(cap: dict, key: str) -> tuple[str | None, str | None]:
    """Status of the capability row whose store sets include this key (None if no row maps to it)."""
    for row in cap.get("targets", []):
        if key in row.get("store_targets", []):
            return row["status"], row["label"]
    return None, None


_DISCOVERY: dict = {}


def run_discovery(args) -> dict | None:
    """Run discover_targets on the repo (unless --no-discovery); keeps JSON + markdown for the release."""
    if args.no_discovery:
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import discover_targets as dt  # noqa: PLC0415

    root = Path(args.repo).resolve()
    f = dt.scan(root)
    rows = dt.classify(f)
    data = {"repo": str(root), "ecosystems": sorted(f.ecosystems),
            "targets": [{**r, "action": dt.action_for(r), "evidence": [{"strength": s, "detail": e}
                                                                       for s, e in r["evidence"]]} for r in rows],
            "facts": f.facts}
    _DISCOVERY["json"] = data
    _DISCOVERY["markdown"] = dt.to_markdown(root, dt.relevant_rows(rows, f), f)
    return data


def plan(args) -> tuple[dict, list[str]]:
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    known = valid_keys(profiles)
    errors = []
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    reused = parse_pairs(args.reuse, "--reuse")
    forced = parse_pairs(args.force_target, "--force-target")
    expected = {k: int(v) for k, v in parse_pairs(args.expected, "--expected").items()}
    if not VERSION.match(args.release):
        errors.append(f"release {args.release!r} is not a plain version label (e.g. 1.0.0)")
    for key in list(targets) + list(reused) + list(forced) + list(expected):
        if key not in known:
            hint = difflib.get_close_matches(key, known, n=3)
            errors.append(f"unknown target {key!r}" + (f"; did you mean {', '.join(hint)}?" if hint else
                                                         "; run validate_assets.py --list-targets"))
    cap = json.loads(Path(args.capability).read_text(encoding="utf-8")) if args.capability else run_discovery(args)
    notes = []
    if cap is None:
        notes.append("--no-discovery: target support was NOT checked against repository evidence")
    else:
        for key in targets:
            if key in companions_for(profiles, key) or key not in known:
                continue
            status, label = capability_status(cap, key)
            if status in ("Confirmed", None):
                continue
            if status == "Probable" and key in forced:
                notes.append(f"{key}: Probable ({label}); confirmed by: {forced[key]}")
            elif key in forced:
                notes.append(f"{key}: {status} ({label}); forced: {forced[key]}")
            else:
                errors.append(f"{key} maps to {label}, which discovery rates {status}. Confirm it at runtime and "
                              f"pass --force-target {key}=\"<evidence>\", or drop it.")
    final = []
    for key in targets:
        if key not in final:
            final.append(key)
        for comp in companions_for(profiles, key) if key in known else []:
            if comp not in final and comp not in targets and comp not in reused:
                final.append(comp)
                notes.append(f"added required companion {comp} (for {key}); use --reuse to keep an existing one")
    if any(k.startswith("apple-app-store/") for k in final) and sys.platform != "darwin":
        notes.append("Apple targets selected on a non-macOS host: simulator capture (capture_apple.py) is NOT "
                     "available here. Use a Mac, the project's CI screenshots, or user-provided captures.")
    for comp in reused:
        if comp in final:
            errors.append(f"{comp} is both a target and --reuse; pick one")
    manifest = {"app": args.app or Path(args.repo).resolve().name, "release": args.release,
                "created": date.today().isoformat(), "repo": str(Path(args.repo).resolve()), "targets": final}
    if expected:
        manifest["expected"] = expected
    if reused:
        manifest["reused"] = reused
    if forced:
        manifest["forced"] = forced
    if notes:
        manifest["notes"] = notes
    return manifest, errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", help="app repository root (output goes to <repo>/store-assets/)")
    ap.add_argument("--release", required=True)
    ap.add_argument("--targets", required=True, help="comma-separated platform/target keys")
    ap.add_argument("--capability", help="use this discover_targets.py --json file instead of running discovery")
    ap.add_argument("--no-discovery", action="store_true", help="skip the evidence check (not recommended)")
    ap.add_argument("--reuse", action="append", default=[], help='companion="where the existing asset is"')
    ap.add_argument("--expected", action="append", default=[], help="target=count from the storyboard")
    ap.add_argument("--force-target", action="append", default=[], help='target="runtime/user evidence"')
    ap.add_argument("--app", help="app name for release.json (default: repo folder name)")
    ap.add_argument("--out", help="write store-assets/ under this folder instead of the repo (read-only repos)")
    ap.add_argument("--dry-run", action="store_true", help="print release.json without creating anything")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        sys.stderr.write(f"Not a directory: {repo}\n")
        return 2
    try:
        manifest, errors = plan(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    if errors:
        sys.stderr.write("Not created:\n" + "\n".join(f"  - {e}" for e in errors) + "\n")
        return 2
    out_root = Path(args.out).resolve() if args.out else repo
    rel = out_root / "store-assets" / f"release-{args.release}"
    if args.dry_run:
        print(json.dumps(manifest, indent=2))
        print(f"(dry run) would create {rel}")
        return 0
    if rel.exists():
        sys.stderr.write(f"{rel} already exists. LaunchFrame never writes into an existing release folder; "
                         "inspect it and ask the user, or choose another version.\n")
        return 3
    for sub in ("source-screenshots", "working", "previews"):
        (rel / sub).mkdir(parents=True)
    for key in manifest["targets"]:
        (rel / key).mkdir(parents=True, exist_ok=True)
    if args.capability:
        shutil.copy2(args.capability, rel / "working" / "capability.json")
    elif _DISCOVERY:
        (rel / "working" / "capability.json").write_text(json.dumps(_DISCOVERY["json"], indent=2), encoding="utf-8")
        (rel / "capability-report.md").write_text(_DISCOVERY["markdown"], encoding="utf-8")
    (rel / "release.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Created {rel}")
    print("Targets: " + ", ".join(manifest["targets"]))
    for n in manifest.get("notes", []):
        print(f"note: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
