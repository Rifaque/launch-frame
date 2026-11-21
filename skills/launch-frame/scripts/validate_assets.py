#!/usr/bin/env python3
"""LaunchFrame store asset validator.

Checks exported store assets against the platform profiles in
assets/platform-profiles.json (or an override file) and writes a readable
report that separates errors (official requirements) from warnings
(recommendations, hygiene) and lists what was NOT checked automatically.

Layout convention: <release>/<platform>/<target>/01.png, 02.png, ...
where <platform> and <target> are keys in the profile file
(e.g. google-play/phone, apple-app-store/iphone, amazon-appstore/fire-tv).

Usage:
  python validate_assets.py RELEASE_DIR
  python validate_assets.py RELEASE_DIR --target google-play/phone --target google-play/feature-graphic
  python validate_assets.py RELEASE_DIR --report RELEASE_DIR/validation-report.md --json out.json
  python validate_assets.py --list-targets

Exit code: 0 = no errors, 1 = errors found, 2 = usage/setup problem.
Requires: Python 3.9+, Pillow (pip install Pillow).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.stderr.write("Pillow is required: pip install Pillow\n")
    sys.exit(2)

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROFILES = SKILL_DIR / "assets" / "platform-profiles.json"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic"}
DOC_EXTS = {".md", ".txt", ".json"}
EXT_FORMAT = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}
NUMBERED = re.compile(r"^(\d{2,3})(?:[-_][A-Za-z0-9-_]+)?$")
# Top-level release folders that never hold final exports.
NON_EXPORT_DIRS = {"source-screenshots", "previews", "working", "other-platforms"}


# ---------------------------------------------------------------- profiles
def load_profiles(extra: list[str]) -> dict:
    with open(DEFAULT_PROFILES, encoding="utf-8") as fh:
        data = json.load(fh)
    for path in extra:
        with open(path, encoding="utf-8") as fh:
            override = json.load(fh)
        for pkey, pval in override.get("platforms", {}).items():
            base = data["platforms"].setdefault(pkey, {"name": pkey, "sources": [], "targets": {}})
            for k, v in pval.items():
                if k == "targets":
                    base.setdefault("targets", {}).update(v)
                else:
                    base[k] = v
        if "checked" in override:
            data["override_checked"] = override["checked"]
    return data


def parse_aspect(text: str) -> tuple[int, int]:
    a, b = text.split(":")
    return int(a), int(b)


def matches_aspect(w: int, h: int, aspect: str) -> bool:
    aw, ah = parse_aspect(aspect)
    # Exact ratio within one pixel of rounding on the dependent side.
    return abs(round(w * ah / aw) - h) <= 1


# ---------------------------------------------------------------- per file
def inspect_file(path: Path) -> dict:
    info: dict = {"file": path.name, "bytes": path.stat().st_size}
    data = path.read_bytes()
    info["sha256"] = hashlib.sha256(data).hexdigest()
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            im.load()
            info["format"] = (im.format or "").lower()
            info["width"], info["height"] = im.size
            info["mode"] = im.mode
            info["icc"] = bool(im.info.get("icc_profile"))
            has_alpha_channel = im.mode in ("RGBA", "LA", "PA", "RGBa", "La") or (
                im.mode == "P" and "transparency" in im.info)
            info["alpha_channel"] = has_alpha_channel
            transparent = False
            if has_alpha_channel:
                lo, _ = im.convert("RGBA").getchannel("A").getextrema()
                transparent = lo < 255
            info["transparent_pixels"] = transparent
    except Exception as exc:  # noqa: BLE001 - report any decode failure
        info["open_error"] = f"{type(exc).__name__}: {exc}"
    return info


def check_file(info: dict, spec: dict, ext: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if "open_error" in info:
        return [f"cannot be opened as an image ({info['open_error']})"], []
    info.setdefault("info", [])
    if info.get("icc"):
        info["info"].append("embedded ICC color profile (fine; stores display sRGB)")

    fmt = info["format"]
    if fmt == "jpg":
        fmt = "jpeg"
    ext_fmt = EXT_FORMAT.get(ext)
    if ext_fmt is None:
        errors.append(f"extension '{ext}' is not an accepted upload type")
    elif ext_fmt != fmt:
        errors.append(f"file content is {fmt.upper()} but extension is '{ext}'")
    allowed = spec.get("formats", [])
    if allowed and fmt not in allowed:
        errors.append(f"format {fmt.upper()} not accepted (allowed: {', '.join(a.upper() for a in allowed)})")

    w, h = info["width"], info["height"]
    short, long_ = min(w, h), max(w, h)
    if spec.get("sizes") and [w, h] not in spec["sizes"]:
        listed = ", ".join(f"{a}x{b}" for a, b in spec["sizes"])
        errors.append(f"{w}x{h} is not an accepted size (accepted: {listed})")
    if "min_side" in spec and short < spec["min_side"]:
        errors.append(f"shortest side {short}px is below minimum {spec['min_side']}px")
    if "max_side" in spec and long_ > spec["max_side"]:
        errors.append(f"longest side {long_}px exceeds maximum {spec['max_side']}px")
    if "min_size" in spec:
        mw, mh = sorted(spec["min_size"])
        if short < mw or long_ < mh:
            errors.append(f"{w}x{h} is below minimum {spec['min_size'][0]}x{spec['min_size'][1]}")
    if "max_ratio" in spec and long_ / short > spec["max_ratio"] + 1e-9:
        errors.append(f"long side is {long_ / short:.2f}x the short side (max {spec['max_ratio']}x)")
    if spec.get("aspects") and not any(matches_aspect(w, h, a) for a in spec["aspects"]):
        errors.append(f"aspect ratio {w}:{h} is not one of {', '.join(spec['aspects'])}")

    if "max_bytes" in spec and info["bytes"] > spec["max_bytes"]:
        errors.append(f"file is {info['bytes'] / 1048576:.2f} MB (max {spec['max_bytes'] / 1048576:.2f} MB)")

    alpha_rule = spec.get("alpha", "unspecified")
    if info["alpha_channel"]:
        detail = "has transparent pixels" if info["transparent_pixels"] else "has an alpha channel (fully opaque)"
        if alpha_rule == "forbidden":
            errors.append(f"{detail}; this asset must not contain alpha - flatten to RGB")
        elif alpha_rule in ("discouraged", "unspecified"):
            warnings.append(f"{detail}; export opaque RGB to be safe")

    mode = info["mode"]
    if mode == "CMYK":
        errors.append("CMYK color mode; stores expect RGB")
    elif mode in ("I;16", "I;16B", "I;16L", "I", "F"):
        warnings.append(f"high-bit-depth mode {mode}; export 8-bit RGB")
    elif mode in ("L", "1"):
        warnings.append(f"grayscale mode {mode}; export as 24-bit RGB")
    elif mode == "P" and not info["alpha_channel"]:
        warnings.append("palette (indexed) PNG; Google Play asks for 24-bit PNG - export RGB")

    rec = spec.get("recommended", {})
    if rec.get("aspects") and not any(matches_aspect(w, h, a) for a in rec["aspects"]):
        warnings.append(f"recommended aspect is {' or '.join(rec['aspects'])}")
    if rec.get("min_short_side") and short < rec["min_short_side"]:
        warnings.append(f"recommended minimum is {rec['min_short_side']}px on the short side")
    if rec.get("sizes") and [w, h] not in rec["sizes"] and not errors:
        listed = ", ".join(f"{a}x{b}" for a, b in rec["sizes"])
        warnings.append(f"not a recommended size ({listed})")
    return errors, warnings


# ---------------------------------------------------------------- per target
def validate_target(tdir: Path, key: str, spec: dict, expected: int | None = None) -> dict:
    result = {"target": key, "label": spec.get("label", key), "dir": str(tdir), "files": [],
              "errors": [], "warnings": [], "info": [], "ignored": []}
    if not tdir.is_dir():
        result["errors"].append("directory is missing")
        return result
    assets = []
    for p in sorted(tdir.iterdir(), key=lambda q: q.name.lower()):
        if p.is_dir():
            result["warnings"].append(f"subfolder '{p.name}/' inside an export folder (not validated)")
            continue
        ext = p.suffix.lower()
        if ext in IMAGE_EXTS:
            assets.append(p)
        elif ext in DOC_EXTS or p.name.startswith("."):
            result["ignored"].append(p.name)
        else:
            result["warnings"].append(f"unexpected non-image file '{p.name}' in export folder")

    seen: dict[str, str] = {}
    for p in assets:
        info = inspect_file(p)
        errs, warns = check_file(info, spec, p.suffix.lower())
        stem = p.stem
        if not NUMBERED.match(stem):
            warns.append("name is not numbered (use 01.png, 02.png ... to fix upload order)")
        if info.get("sha256") in seen:
            warns.append(f"identical to {seen[info['sha256']]}")
        elif "sha256" in info:
            seen[info["sha256"]] = p.name
        info["errors"], info["warnings"] = errs, warns
        result["files"].append(info)

    n = len(assets)
    count = spec.get("count", {})
    if n == 0:
        result["errors"].append("no image assets found")
    else:
        if "min" in count and n < count["min"]:
            result["errors"].append(f"{n} asset(s); at least {count['min']} required")
        if "max" in count and n > count["max"]:
            result["errors"].append(f"{n} assets; at most {count['max']} allowed")
    if expected is not None and n and n != expected:
        result["warnings"].append(f"{n} asset(s) but release.json expects {expected} (storyboard/capture plan)")
    rec_min = spec.get("recommended", {}).get("min_count")
    if rec_min and 0 < n < rec_min:
        result["warnings"].append(f"{n} asset(s); {rec_min}+ recommended ({spec['recommended'].get('why', 'store guidance')})")

    nums = []
    for p in assets:
        m = NUMBERED.match(p.stem)
        if m:
            nums.append(int(m.group(1)))
    if nums and sorted(nums) != list(range(1, len(nums) + 1)):
        result["warnings"].append(f"numbering is not contiguous from 01 (found {sorted(nums)})")

    opened = [f for f in result["files"] if "width" in f]
    if spec.get("uniform_size") and len({(f["width"], f["height"]) for f in opened}) > 1:
        result["warnings"].append("mixed pixel sizes in one device set; use one size per set")
    if spec.get("min_per_orientation") and opened:
        need = spec["min_per_orientation"]
        portrait = sum(1 for f in opened if f["height"] > f["width"])
        landscape = sum(1 for f in opened if f["width"] > f["height"])
        if portrait < need or landscape < need:
            result["errors"].append(
                f"needs at least {need} portrait and {need} landscape (found {portrait} portrait, {landscape} landscape)")
    return result


def discover_targets(release: Path, profiles: dict) -> tuple[list[str], list[str]]:
    found, unknown = [], []
    for pdir in sorted(p for p in release.iterdir() if p.is_dir()):
        if pdir.name in NON_EXPORT_DIRS or pdir.name.startswith("."):
            continue
        platform = profiles["platforms"].get(pdir.name)
        for tdir in sorted(t for t in pdir.iterdir() if t.is_dir()):
            key = f"{pdir.name}/{tdir.name}"
            if platform and tdir.name in platform["targets"]:
                found.append(key)
            else:
                unknown.append(key)
    return found, unknown


# ---------------------------------------------------------------- report
def check_companions(profiles: dict, targets: list[str], reused: dict) -> list[dict]:
    """Required companion assets (e.g. Google Play feature graphic) for the selected targets."""
    out = []
    selected = set(targets)
    for key in targets:
        pk, tk = key.split("/", 1)
        comp = profiles["platforms"].get(pk, {}).get("companions", {})
        for need in comp.get("*", []) + comp.get(tk, []):
            ckey = f"{pk}/{need}"
            if ckey in selected or ckey == key or any(c["companion"] == ckey for c in out):
                continue
            if ckey in reused:
                out.append({"companion": ckey, "for": key, "level": "INFO",
                            "message": f"{ckey} reused, not in this release: {reused[ckey]}"})
            else:
                out.append({"companion": ckey, "for": key, "level": "WARN",
                            "message": f"{ckey} is required alongside {key} but is neither in this release nor "
                                       f"listed under release.json 'reused'"})
    return out


def provenance_checks(release: Path) -> list[dict]:
    src = release / "source-screenshots"
    imgs = [p for p in src.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}] if src.is_dir() else []
    if not imgs:
        return []
    mf = src / "captures.json"
    if not mf.is_file():
        return [{"level": "WARN", "message": "source-screenshots/ has no captures.json: provenance of the sources "
                                             "is not recorded (capture scripts or captures.py add)"}]
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [{"level": "ERROR", "message": "source-screenshots/captures.json is not valid JSON"}]
    out = []
    known = {}
    for c in data.get("captures", []):
        known[c["file"]] = c
        p = src / c["file"]
        if not p.is_file():
            out.append({"level": "ERROR", "message": f"source {c['file']} is registered but missing"})
        elif hashlib.sha256(p.read_bytes()).hexdigest() != c.get("sha256"):
            out.append({"level": "ERROR", "message": f"source {c['file']} changed after capture (sources must stay "
                                                     "untouched)"})
    for p in imgs:
        if p.name not in known:
            out.append({"level": "WARN", "message": f"source {p.name} has no provenance entry"})
    counts = {}
    for c in known.values():
        counts[c.get("provenance", "?")] = counts.get(c.get("provenance", "?"), 0) + 1
    out.append({"level": "INFO", "message": "sources by provenance: " +
                ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))})
    return out


def handoff_checks(release: Path, targets: list[str]) -> list[dict]:
    out = []
    need = [("README.md", "root README"), ("design-system.md", "design notes"),
            ("previews/contact-sheet.png", "contact sheet")]
    for rel, label in need:
        if not (release / rel).is_file():
            out.append({"level": "ERROR", "message": f"{label} missing ({rel})"})
    for platform in sorted({t.split("/")[0] for t in targets}):
        if not (release / platform / "README.md").is_file():
            out.append({"level": "ERROR", "message": f"{platform}/README.md missing (per-store upload guide)"})
    return out


def render_markdown(release: Path, profiles: dict, results: list[dict], unknown: list[str],
                    target_source: str, companions: list[dict] | None = None, checks: list[dict] | None = None) -> str:
    companions = companions or []
    checks = checks or []
    total_e = sum(len(r["errors"]) + sum(len(f["errors"]) for f in r["files"]) for r in results)
    total_w = sum(len(r["warnings"]) + sum(len(f["warnings"]) for f in r["files"]) for r in results)
    total_w += sum(1 for c in companions + checks if c["level"] == "WARN")
    total_e += sum(1 for c in companions + checks if c["level"] == "ERROR")
    checked = profiles.get("override_checked") or profiles.get("checked", "unknown")
    lines = [
        "# Validation report",
        "",
        f"- Release folder: `{release.name}`",
        f"- Run date: {date.today().isoformat()}",
        f"- Platform profile checked against official docs on: **{checked}**",
        f"- Targets from: {target_source}",
        f"- Result: **{'FAIL' if total_e else 'PASS'}** - {total_e} error(s), {total_w} warning(s)",
        "",
        "Errors are official requirements that failed. Warnings are recommendations or hygiene issues.",
        "PASS means only that the automatic checks listed below passed; see 'Not checked automatically'.",
        "",
    ]
    for r in results:
        platform_key = r["target"].split("/")[0]
        platform = profiles["platforms"].get(platform_key, {})
        spec = platform.get("targets", {}).get(r["target"].split("/")[1], {})
        n_err = len(r["errors"]) + sum(len(f["errors"]) for f in r["files"])
        status = "FAIL" if n_err else "PASS"
        lines += [f"## {platform.get('name', platform_key)} - {r['label']} (`{r['target']}`): {status}", ""]
        if r["files"]:
            lines += ["| File | Size (px) | Format | Mode | KB | Result |", "|---|---|---|---|---|---|"]
            for f in r["files"]:
                dims = f"{f.get('width', '?')}x{f.get('height', '?')}"
                res = "error" if f["errors"] else ("warning" if f["warnings"] else "ok")
                lines.append(f"| {f['file']} | {dims} | {f.get('format', '?').upper()} | {f.get('mode', '?')} "
                             f"| {f['bytes'] // 1024} | {res} |")
            lines.append("")
        issues = [("ERROR", e) for e in r["errors"]] + [("WARN", w) for w in r["warnings"]]
        issues += [("INFO", i) for i in r.get("info", [])]
        for f in r["files"]:
            issues += [("ERROR", f"{f['file']}: {e}") for e in f["errors"]]
            issues += [("WARN", f"{f['file']}: {w}") for w in f["warnings"]]
            issues += [("INFO", f"{f['file']}: {i}") for i in f.get("info", [])]
        if issues:
            lines += [f"- **{lvl}** {msg}" for lvl, msg in issues] + [""]
        rules = []
        if spec.get("formats"):
            rules.append("format " + "/".join(x.upper() for x in spec["formats"]))
        if spec.get("sizes"):
            rules.append("exact size list")
        if "min_side" in spec or "max_side" in spec:
            rules.append(f"sides {spec.get('min_side', '-')}-{spec.get('max_side', '-')}px")
        if spec.get("aspects"):
            rules.append("aspect " + "/".join(spec["aspects"]))
        if "max_ratio" in spec:
            rules.append(f"ratio <= {spec['max_ratio']}")
        if "max_bytes" in spec:
            rules.append(f"<= {spec['max_bytes'] // 1048576} MB")
        rules.append(f"alpha {spec.get('alpha', 'unspecified')}")
        if spec.get("count"):
            rules.append(f"count {spec['count'].get('min', 0)}-{spec['count'].get('max', 'n')}")
        lines += [f"Checked: {', '.join(rules)}, file type vs extension, color mode, naming, duplicates.", ""]
        if spec.get("notes"):
            lines += [f"Note: {spec['notes']}", ""]
        if spec.get("manual_checks"):
            lines += ["Not checked automatically (review by eye):"] + [f"- [ ] {m}" for m in spec["manual_checks"]] + [""]
    if companions:
        lines += ["## Companion assets", ""] + [f"- **{c['level']}** {c['message']}" for c in companions] + [""]
    if checks:
        lines += ["## Release checks", ""] + [f"- **{c['level']}** {c['message']}" for c in checks] + [""]
    if unknown:
        lines += ["## Not validated", "", "Folders with no matching platform profile (nothing was checked):", ""]
        lines += [f"- `{u}`" for u in unknown] + [""]
    lines += [
        "## Not checked automatically (all targets)",
        "",
        "- Visual quality, legibility at store thumbnail size, brand fit.",
        "- Truthfulness of headlines and that UI is authentic and unaltered.",
        "- Store content policies (claims, trademarks, personal data in screenshots).",
        "- Whether the official requirements changed after the profile date above.",
        "",
        "Sources:",
    ]
    used = sorted({r["target"].split("/")[0] for r in results})
    for pk in used:
        for src in profiles["platforms"].get(pk, {}).get("sources", []):
            lines.append(f"- {src}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("release", nargs="?", help="release folder, e.g. store-assets/release-1.0.0")
    ap.add_argument("--target", action="append", default=[], help="platform/target to validate (repeatable)")
    ap.add_argument("--profiles", action="append", default=[], help="extra/override profile JSON (repeatable)")
    ap.add_argument("--report", help="write the markdown report to this path")
    ap.add_argument("--json", dest="json_out", help="write machine-readable results to this path")
    ap.add_argument("--list-targets", action="store_true", help="print known platform/target keys and exit")
    ap.add_argument("--final", action="store_true",
                    help="pre-handoff gate: missing companions, READMEs, contact sheet or design notes become errors")
    args = ap.parse_args(argv)

    try:
        profiles = load_profiles(args.profiles)
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"Could not load profiles: {exc}\n")
        return 2

    if args.list_targets:
        print(f"Profiles checked: {profiles.get('checked')}")
        for pk, pv in profiles["platforms"].items():
            for tk, tv in pv["targets"].items():
                print(f"{pk}/{tk}\t{tv.get('label', '')}")
        return 0
    if not args.release:
        ap.error("release folder is required")
    release = Path(args.release).resolve()
    if not release.is_dir():
        sys.stderr.write(f"Not a directory: {release}\n")
        return 2

    unknown: list[str] = []
    manifest: dict = {}
    if (release / "release.json").is_file():
        try:
            manifest = json.loads((release / "release.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"release.json is not valid JSON: {exc}\n")
            return 2
    if args.target:
        targets, source = args.target, "--target arguments"
    elif manifest:
        targets, source = manifest.get("targets", []), "release.json"
        found, unknown = discover_targets(release, profiles)
        extra = [t for t in found if t not in targets]
        unknown += [f"{t} (folder exists but is not listed in release.json)" for t in extra]
    else:
        targets, unknown = discover_targets(release, profiles)
        source = "folder discovery (no release.json)"
    if not targets:
        sys.stderr.write("No targets found. Use <platform>/<target> folders, release.json, or --target.\n")
        return 2

    results = []
    checks: list[dict] = []  # release-level checks: {"level", "message"}
    for key in targets:
        if "/" not in key:
            sys.stderr.write(f"Target must be platform/target: {key}\n")
            return 2
        pk, tk = key.split("/", 1)
        spec = profiles["platforms"].get(pk, {}).get("targets", {}).get(tk)
        if spec is None:
            checks.append({"level": "ERROR", "message": f"`{key}` is not a known target key (invented name?). "
                                                        "Use validate_assets.py --list-targets / init_release.py."})
            continue
        results.append(validate_target(release / pk / tk, key, spec, manifest.get("expected", {}).get(key)))
    if manifest and not args.target:
        for u in unknown:
            checks.append({"level": "ERROR", "message": f"folder `{u.split(' ')[0]}` is not a target in release.json "
                                                        "(remove it or add it with a valid key)"})
        unknown = []
    checks += provenance_checks(release)
    if args.final:
        checks += handoff_checks(release, [r["target"] for r in results])

    companions = check_companions(profiles, [r["target"] for r in results], manifest.get("reused", {}))
    if args.final:
        for c in companions:
            if c["level"] == "WARN":
                c["level"] = "ERROR"
    report = render_markdown(release, profiles, results, unknown, source, companions, checks)
    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({"profiles_checked": profiles.get("checked"),
                                                   "results": results, "companions": companions,
                                                   "release_checks": checks, "not_validated": unknown}, indent=2),
                                       encoding="utf-8")
    sys.stdout.write(report)
    has_errors = any(r["errors"] or any(f["errors"] for f in r["files"]) for r in results)
    has_errors = has_errors or any(c["level"] == "ERROR" for c in checks + companions)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
