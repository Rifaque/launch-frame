#!/usr/bin/env python3
"""Report what this machine can capture, and how, for each supported app target.

  python check_env.py                                   # environment report
  python check_env.py --capability capability.json      # + per-target capture matrix
                                                        #   (capability.json from discover_targets.py --json)
  python check_env.py --json env.json

Read-only. Connected physical devices are queried with getprop/wm/pm (no changes).
Never installs anything; it says what setup a target would need so the user can approve it.
Requires: Python 3.9+. Pillow/Playwright detection is optional.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_android as ca  # noqa: E402
import capture_apple as capl  # noqa: E402
from render_html import find_browser  # noqa: E402

# Target -> device kinds that genuinely show that target's UI.
KIND_FOR = {
    "android-phone": ["phone"], "android-tablet": ["tablet"], "android-foldable": ["foldable"],
    "chromebook": ["desktop/chromebook"], "android-tv": ["tv"], "wear-os": ["wear"],
    "android-automotive": ["automotive"], "android-xr": ["xr"], "fire-tv": ["fire-tv"],
    "fire-tablet": ["fire-tablet"],
}
CLI_PROFILE = {"android-phone": "medium_phone", "android-tablet": "medium_tablet",
               "android-foldable": "foldable_1_1 / foldable_4_3 (Android CLI with emulator >= 37.3.10)",
               "chromebook": "large_desktop (start as desktop_large)"}


def module_ok(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def gather() -> dict:
    env = {"host": f"{platform.system()} {platform.version()}", "python": platform.python_version(),
           "pillow": module_ok("PIL"), "playwright": module_ok("playwright"), "browser": find_browser(None)}
    roots = ca.sdk_roots()
    env["android"] = {"sdk": str(roots[0]) if roots else None, "adb": ca.find_tool("adb", "platform-tools"),
                      "emulator": ca.find_tool("emulator", "emulator"), "android_cli": ca.find_android_cli(),
                      "system_images": [], "avds": [], "devices": [], "errors": []}
    a = env["android"]
    if roots and (roots[0] / "system-images").is_dir():
        a["system_images"] = sorted(str(p.relative_to(roots[0] / "system-images")).replace("\\", "/")
                                    for p in (roots[0] / "system-images").glob("*/*/*") if p.is_dir())
    try:
        a["avds"] = ca.list_avds()
    except Exception as exc:  # noqa: BLE001
        a["errors"].append(f"avds: {exc}")
    if a["adb"]:
        try:
            a["devices"] = ca.list_devices()
        except Exception as exc:  # noqa: BLE001
            a["errors"].append(f"devices: {exc}")
    reason = capl.available()
    env["apple"] = {"available": reason is None, "reason": reason, "simulators": []}
    if reason is None:
        try:
            env["apple"]["simulators"] = capl.parse_devices(json.loads(capl.simctl("list", "devices", "available",
                                                                                     "-j")))
        except Exception as exc:  # noqa: BLE001
            env["apple"]["reason"] = f"simctl failed: {exc}"
    return env


def plan_for(target: str, env: dict) -> dict:
    a = env["android"]
    if target in KIND_FOR:
        kinds = KIND_FOR[target]
        avds = [x for x in a["avds"] if x["kind"] in kinds]
        app = re.sub(r"[^a-z0-9]", "", str(env.get("app_name", "")).lower())
        if app:  # an AVD named after the app (e.g. Reflux_Phone) is the one the team prepared
            avds.sort(key=lambda x: app not in re.sub(r"[^a-z0-9]", "", x["name"].lower()))
        emus = [d for d in a["devices"] if d.get("emulator") and d.get("kind") in kinds]
        phys = [d for d in a["devices"] if not d.get("emulator") and d.get("kind") in kinds]
        if not a["adb"]:
            return {"env": "none", "method": "-", "auto": "no", "setup": "Android SDK platform-tools (adb)",
                    "help": "install SDK or provide screenshots"}
        if emus or avds:
            name = (emus[0].get("avd") if emus else avds[0]["name"])
            state = "running" if emus else "installed"
            return {"env": f"emulator {name} ({state})", "method": "capture_android.py (adb screencap)",
                    "auto": "yes", "setup": "none" if emus else f"boot {name}", "help": "no"}
        if phys:
            d = phys[0]
            fire_note = " (real Fire OS)" if d["kind"].startswith("fire") else ""
            return {"env": f"physical {d['manufacturer']} {d['model']}{fire_note}",
                    "method": "capture_android.py --allow-physical", "auto": "yes, with user approval",
                    "setup": "none", "help": "approve use of the physical device"}
        if target in ("fire-tv", "fire-tablet"):
            analog = "tv" if target == "fire-tv" else "tablet"
            near = [x for x in a["avds"] if x["kind"] == analog]
            alt = (f"Android {analog} emulator {near[0]['name']} shows the app's Android UI but is not Fire OS"
                   if near else f"no Android {analog} emulator either")
            device = "Fire TV" if target == "fire-tv" else "Fire tablet"
            return {"env": "no Fire OS device or Fire OS emulator found", "method": "-", "auto": "partial",
                    "setup": f"connect a {device} via ADB", "help": f"{alt}; label such captures honestly"}
        profile = CLI_PROFILE.get(target)
        setup = (f"create AVD: android emulator create {profile}" if profile and a["android_cli"]
                 else "create an AVD for this form factor (SDK system image download; ask first)")
        return {"env": "none", "method": "capture_android.py after setup", "auto": "after setup", "setup": setup,
                "help": "approve download/creation"}
    if target in ("iphone", "ipad", "apple-tv", "apple-watch", "vision-pro", "mac"):
        ap = env["apple"]
        if not ap["available"]:
            return {"env": "unavailable", "method": "-", "auto": "no", "setup": ap["reason"],
                    "help": "run on a Mac, use project CI screenshots, or provide captures"}
        want = {"iphone": "iphone", "ipad": "ipad", "apple-tv": "apple-tv", "apple-watch": "apple-watch",
                "vision-pro": "vision-pro"}.get(target)
        sims = [s for s in ap["simulators"] if s["kind"] == want]
        if target == "mac":
            return {"env": "this Mac", "method": "screencapture -l<windowid> or the app's UI tests", "auto": "partial",
                    "setup": "none", "help": "may need window selection"}
        if sims:
            return {"env": f"simulator {sims[0]['name']}", "method": "capture_apple.py", "auto": "yes",
                    "setup": "build/install the app into the simulator", "help": "no"}
        return {"env": "no simulator", "method": "-", "auto": "after setup", "setup": "install the simulator runtime",
                "help": "approve download"}
    if target == "web":
        ok = env["playwright"] or env["browser"]
        return {"env": "Playwright" if env["playwright"] else (env["browser"] or "none"),
                "method": "capture_web.py against the running dev server", "auto": "yes" if ok else "no",
                "setup": "start the app's dev server" if ok else "install Playwright or Chrome", "help": "no"}
    if target == "desktop":
        return {"env": env["host"], "method": "run the app; OS window capture or its UI-test harness",
                "auto": "partial", "setup": "build/run the desktop app", "help": "may need window focus"}
    return {"env": "?", "method": "-", "auto": "no", "setup": "-", "help": "-"}


def to_markdown(env: dict, matrix: list[dict] | None) -> str:
    a = env["android"]
    out = ["# Environment capability report", "",
           f"- Host: {env['host']}, Python {env['python']}, Pillow {'yes' if env['pillow'] else 'NO'}",
           f"- Playwright: {'yes' if env['playwright'] else 'no'}; browser: {env['browser'] or 'none found'}",
           f"- Android SDK: {a['sdk'] or 'not found'}; adb: {'yes' if a['adb'] else 'no'}; "
           f"emulator: {'yes' if a['emulator'] else 'no'}; Android CLI: {'yes' if a['android_cli'] else 'no'}",
           f"- System images: {', '.join(a['system_images']) or 'none'}",
           f"- Apple simulators: {'available' if env['apple']['available'] else env['apple']['reason']}", ""]
    if a["avds"]:
        out += ["## AVDs", "", "| AVD | Kind | Size | Density |", "|---|---|---|---|"]
        out += [f"| {x['name']} | {x['kind']} | {x['width']}x{x['height']} | {x['density']} |" for x in a["avds"]]
        out.append("")
    if a["devices"]:
        out += ["## Connected Android devices", "", "| Serial | Type | Kind | OS | Model |", "|---|---|---|---|---|"]
        for d in a["devices"]:
            if "state" in d:
                out.append(f"| {d['serial']} | - | - | - | {d['state']} |")
            else:
                typ = f"emulator ({d['avd']})" if d["emulator"] else "physical"
                out.append(f"| {d['serial']} | {typ} | {d['kind']} | {d['os']} {d['sdk']} | "
                           f"{d['manufacturer']} {d['model']} |")
        out.append("")
    if env["apple"]["simulators"]:
        out += ["## Apple simulators", ""] + [f"- {s['name']} ({s['platform']} {s['version']}, {s['state']})"
                                               for s in env["apple"]["simulators"][:20]] + [""]
    if matrix is not None:
        out += ["## Capture matrix (Confirmed/Probable targets)", "",
                "| Target | Status | Capture environment | Method | Automated | Setup needed | User assistance |",
                "|---|---|---|---|---|---|---|"]
        for m in matrix:
            p = m["plan"]
            out.append(f"| {m['label']} | {m['status']} | {p['env']} | {p['method']} | {p['auto']} | "
                       f"{p['setup']} | {p['help']} |")
        out += ["", "Prefer emulators/simulators. Physical devices only when requested or when no virtual "
                    "device can show the target. Ask before downloading system images or creating AVDs."]
    for e in a["errors"]:
        out.append(f"- note: {e}")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capability", help="capability JSON from discover_targets.py --json")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--markdown", dest="md_out")
    args = ap.parse_args(argv)
    env = gather()
    matrix = None
    if args.capability:
        cap = json.loads(Path(args.capability).read_text(encoding="utf-8"))
        env["app_name"] = Path(cap.get("repo", "")).name
        matrix = [{"target": t["target"], "label": t["label"], "status": t["status"], "plan": plan_for(t["target"], env)}
                  for t in cap["targets"] if t["status"] in ("Confirmed", "Probable")]
        env["matrix"] = matrix
    md = to_markdown(env, matrix)
    if args.md_out:
        Path(args.md_out).write_text(md, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(env, indent=2), encoding="utf-8")
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
