#!/usr/bin/env python3
"""Capture authentic screenshots from Apple simulators (iPhone, iPad, Apple TV, Watch, Vision Pro).

macOS with Xcode only. On other hosts every command exits with code 3 and says so.
Syntax follows `xcrun simctl help`; verify on the host with `xcrun simctl help io` if a flag fails.

  python capture_apple.py devices [--json]                 # available simulators by platform
  python capture_apple.py boot --udid UDID                 # boot and wait (simctl bootstatus)
  python capture_apple.py prepare --udid UDID [--appearance dark|light]   # 9:41, full bars/battery
  python capture_apple.py restore --udid UDID              # clear status bar override
  python capture_apple.py launch --udid UDID --bundle com.example.app [--url myapp://route]
  python capture_apple.py shot --udid UDID --out source-screenshots/iphone-home.png --screen home \
      [--target apple-app-store/iphone]

Navigation inside iOS apps is best driven by the project's XCUITests / fastlane snapshot or by
deep links (`--url`); simctl has no tap command.
Requires: Python 3.9+, Pillow, Xcode command line tools.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from captures import record  # noqa: E402

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover
    sys.stderr.write("Pillow is required: pip install Pillow\n")
    sys.exit(2)

UNAVAILABLE = 3
PLATFORM_KIND = {"iOS": "iphone/ipad", "tvOS": "apple-tv", "watchOS": "apple-watch", "xrOS": "vision-pro",
                 "visionOS": "vision-pro"}


class AppleError(RuntimeError):
    pass


def available() -> str | None:
    if platform.system() != "Darwin":
        return f"Apple simulators need macOS with Xcode; this host is {platform.system()}."
    if not shutil.which("xcrun"):
        return "xcrun not found; install Xcode and run `xcode-select --install`."
    return None


def simctl(*args: str, timeout=120) -> str:
    proc = subprocess.run(["xcrun", "simctl", *args], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise AppleError(f"simctl {' '.join(args)} failed: {proc.stderr.strip()[:500]}")
    return proc.stdout


def parse_devices(data: dict) -> list[dict]:
    rows = []
    for runtime, devices in data.get("devices", {}).items():
        # runtime ids look like com.apple.CoreSimulator.SimRuntime.iOS-18-2
        tail = runtime.rsplit(".", 1)[-1]
        plat, _, ver = tail.partition("-")
        for d in devices:
            if not d.get("isAvailable", True):
                continue
            name = d.get("name", "")
            kind = PLATFORM_KIND.get(plat, plat)
            if plat == "iOS":
                kind = "ipad" if "iPad" in name else "iphone"
            rows.append({"udid": d.get("udid"), "name": name, "platform": plat, "version": ver.replace("-", "."),
                         "state": d.get("state"), "kind": kind})
    return rows


def device_by_udid(udid: str) -> dict:
    for d in parse_devices(json.loads(simctl("list", "devices", "available", "-j"))):
        if d["udid"] == udid:
            return d
    raise AppleError(f"No available simulator with UDID {udid}")


def cmd_devices(args) -> int:
    rows = parse_devices(json.loads(simctl("list", "devices", "available", "-j")))
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    print("| UDID | Name | Platform | Kind | State |\n|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['udid']} | {r['name']} | {r['platform']} {r['version']} | {r['kind']} | {r['state']} |")
    return 0


def cmd_boot(args) -> int:
    d = device_by_udid(args.udid)
    if d["state"] != "Booted":
        simctl("boot", args.udid)
    simctl("bootstatus", args.udid, "-b", timeout=600)
    print(f"Booted {d['name']}")
    return 0


def cmd_prepare(args) -> int:
    d = device_by_udid(args.udid)
    if d["platform"] in ("iOS",):
        simctl("status_bar", args.udid, "override", "--time", "9:41", "--batteryState", "charged",
               "--batteryLevel", "100", "--wifiBars", "3", "--cellularBars", "4", "--dataNetwork", "wifi")
        print("- status bar override (9:41, full battery and bars)")
    if args.appearance:
        simctl("ui", args.udid, "appearance", args.appearance)
        print(f"- appearance {args.appearance}")
    return 0


def cmd_restore(args) -> int:
    d = device_by_udid(args.udid)
    if d["platform"] == "iOS":
        simctl("status_bar", args.udid, "clear")
    print("- status bar override cleared")
    return 0


def cmd_launch(args) -> int:
    if args.url:
        simctl("openurl", args.udid, args.url)
        print(f"Opened {args.url}")
    else:
        simctl("launch", args.udid, args.bundle)
        print(f"Launched {args.bundle}")
    return 0


def cmd_shot(args) -> int:
    d = device_by_udid(args.udid)
    out = Path(args.out)
    if out.suffix.lower() != ".png":
        raise AppleError("--out must be a .png path")
    out.parent.mkdir(parents=True, exist_ok=True)
    simctl("io", args.udid, "screenshot", "--type=png", str(out))
    with Image.open(out) as im:
        if ImageStat.Stat(im.convert("L").resize((64, 64))).stddev[0] < 2.0:
            out.unlink()
            raise AppleError("Captured frame is blank/uniform; not saved.")
    device = {"model": d["name"], "kind": d["kind"], "os": f"{d['platform']} {d['version']}", "simulator": True,
              "udid": d["udid"]}
    entry = record(out.parent, out, "auto-captured", args.screen, "xcrun simctl io screenshot", device, args.target)
    print(f"Captured {out} {entry['width']}x{entry['height']} from {d['name']} simulator")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("devices")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_devices)
    for name, fn in (("boot", cmd_boot), ("restore", cmd_restore)):
        p = sub.add_parser(name)
        p.add_argument("--udid", required=True)
        p.set_defaults(fn=fn)
    p = sub.add_parser("prepare")
    p.add_argument("--udid", required=True)
    p.add_argument("--appearance", choices=["dark", "light"])
    p.set_defaults(fn=cmd_prepare)
    p = sub.add_parser("launch")
    p.add_argument("--udid", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--bundle")
    g.add_argument("--url")
    p.set_defaults(fn=cmd_launch)
    p = sub.add_parser("shot")
    p.add_argument("--udid", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--screen", required=True)
    p.add_argument("--target")
    p.set_defaults(fn=cmd_shot)
    args = ap.parse_args(argv)
    reason = available()
    if reason:
        sys.stderr.write(f"unavailable: {reason}\n")
        return UNAVAILABLE
    try:
        return args.fn(args)
    except (AppleError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
