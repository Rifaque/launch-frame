#!/usr/bin/env python3
"""Capture authentic Android screenshots from emulators (preferred) or devices.

Discovery (read-only):
  python capture_android.py avds                       # AVDs with size, density, form factor
  python capture_android.py devices                    # connected devices/emulators, form factor, Fire OS
Emulators:
  python capture_android.py boot Reflux_TV [--window] [--cold]   # prints the serial when booted
  python capture_android.py stop --serial emulator-5554          # emulators only
State (reversible; physical devices need --allow-physical):
  python capture_android.py prepare --serial S [--theme dark|light] [--orientation portrait|landscape]
  python capture_android.py restore --serial S
App and navigation (grounded in the live UI tree, never blind coordinates):
  python capture_android.py launch --serial S --package com.example [--activity .Main | --deeplink URL]
  python capture_android.py ui --serial S [--all]                # visible elements with bounds/focus
  python capture_android.py tap --serial S --text "Movies" [--exact] [--index N]
  python capture_android.py key --serial S down [--repeat 3]     # D-pad/TV: up down left right center back home
  python capture_android.py type --serial S "search words"
  python capture_android.py wait --serial S --text "Continue Watching" [--timeout 20]
Capture:
  python capture_android.py shot --serial S --out source-screenshots/phone-home.png --screen home \
      [--target google-play/phone] [--display ID]

`shot` uses `adb exec-out screencap -p` at the device's native resolution, rejects blank frames,
and records provenance in captures.json next to the image.
Requires: Python 3.9+, Pillow, Android SDK platform-tools (adb). Optional: emulator, Android CLI.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from captures import record  # noqa: E402

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover
    sys.stderr.write("Pillow is required: pip install Pillow\n")
    sys.exit(2)

KEYS = {"up": 19, "down": 20, "left": 21, "right": 22, "center": 23, "enter": 66, "back": 4, "home": 3,
        "menu": 82, "play_pause": 85, "tab": 61, "escape": 111}
STATE_DIR = Path(tempfile.gettempdir()) / "launchframe-device-state"


class AndroidError(RuntimeError):
    pass


# ---------------------------------------------------------------- tools
def sdk_roots() -> list[Path]:
    explicit = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT")]
    if any(explicit):  # an explicitly configured SDK wins; don't silently fall back to another one
        return [Path(r) for r in explicit if r and Path(r).is_dir()]
    roots = []
    home = Path.home()
    roots += [os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk"), str(home / "Library/Android/sdk"),
              str(home / "Android/Sdk"), str(home / "Android/sdk")]
    return [Path(r) for r in roots if r and "%" not in r and Path(r).is_dir()]


def find_tool(name: str, sub: str) -> str | None:
    exe = name + (".exe" if os.name == "nt" else "")
    for root in sdk_roots():
        cand = root / sub / exe
        if cand.is_file():
            return str(cand)
    return shutil.which(name)


def find_android_cli() -> str | None:
    """The modern Android CLI (`android`), not the removed legacy SDK `tools/android` script."""
    path = shutil.which("android")
    if not path and not (os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")):
        cand = Path(os.path.expandvars(r"%LOCALAPPDATA%\..\AndroidCLI\android.exe")) if os.name == "nt" else None
        path = str(cand) if cand and cand.is_file() else None
    if not path:
        return None
    try:
        out = subprocess.run([path, "emulator", "--help"], capture_output=True, text=True, timeout=30)
        return path if "emulator" in (out.stdout + out.stderr).lower() and out.returncode in (0, 255) else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def adb_path() -> str:
    path = find_tool("adb", "platform-tools")
    if not path:
        raise AndroidError("adb not found. Install Android SDK platform-tools or set ANDROID_HOME.")
    return path


def adb(serial: str | None, *args: str, binary=False, timeout=60, check=True):
    cmd = [adb_path()] + (["-s", serial] if serial else []) + list(args)
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout, text=not binary)
    if check and proc.returncode != 0:
        err = proc.stderr if not binary else proc.stderr.decode(errors="ignore")
        raise AndroidError(f"adb {' '.join(args)} failed: {err.strip()[:500]}")
    return proc.stdout


def sh(serial: str, command: str, timeout=60, check=True) -> str:
    return adb(serial, "shell", command, timeout=timeout, check=check).strip()


# ---------------------------------------------------------------- discovery
def read_ini(path: Path) -> dict:
    data = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    except OSError:
        pass
    return data


def classify_size(width: int, height: int, density: int) -> str:
    if not (width and height and density):
        return "unknown"
    sw = min(width, height) * 160 / density
    return "tablet" if sw >= 600 else "phone"


def list_avds() -> list[dict]:
    avd_home = Path(os.environ.get("ANDROID_AVD_HOME") or Path.home() / ".android" / "avd")
    out = []
    for ini in sorted(avd_home.glob("*.ini")):
        meta = read_ini(ini)
        cfg_dir = Path(meta.get("path", "")) if meta.get("path") else avd_home / (ini.stem + ".avd")
        if not cfg_dir.is_dir() and meta.get("path.rel"):
            cfg_dir = avd_home.parent / meta["path.rel"]
        cfg = read_ini(cfg_dir / "config.ini")
        w, h, d = (int(cfg.get(k, 0) or 0) for k in ("hw.lcd.width", "hw.lcd.height", "hw.lcd.density"))
        tag = (cfg.get("tag.id") or "").lower()
        device = (cfg.get("hw.device.name") or "").lower()
        if "tv" in tag or "tv" in device:
            kind = "tv"
        elif "wear" in tag:
            kind = "wear"
        elif "automotive" in tag:
            kind = "automotive"
        elif "desktop" in tag or "desktop" in device:
            kind = "desktop/chromebook"
        elif "xr" in tag:
            kind = "xr"
        elif "fold" in device:
            kind = "foldable"
        else:
            kind = classify_size(w, h, d)
        out.append({"name": ini.stem, "kind": kind, "width": w, "height": h, "density": d,
                    "device": cfg.get("hw.device.name"), "image": cfg.get("image.sysdir.1", "").strip("\\/"),
                    "tag": cfg.get("tag.id"), "config_found": bool(cfg)})
    return out


def device_info(serial: str) -> dict:
    props = {}
    for line in sh(serial, "getprop", check=False).splitlines():
        m = re.match(r"\[([^\]]+)\]: \[(.*)\]", line)
        if m:
            props[m.group(1)] = m.group(2)
    size = sh(serial, "wm size", check=False)
    dens = sh(serial, "wm density", check=False)
    sizes = re.findall(r"(\d+)x(\d+)", size)
    w, h = (int(x) for x in sizes[-1]) if sizes else (0, 0)
    dvals = re.findall(r"(\d+)", dens)
    density = int(dvals[-1]) if dvals else 0
    features = sh(serial, "pm list features", check=False)
    emulator = serial.startswith("emulator-") or props.get("ro.kernel.qemu") == "1" or \
        props.get("ro.boot.qemu") == "1"
    manufacturer = props.get("ro.product.manufacturer", "")
    chars = props.get("ro.build.characteristics", "")
    if "android.hardware.type.automotive" in features:
        kind = "automotive"
    elif "android.hardware.type.watch" in features or "watch" in chars:
        kind = "wear"
    elif "android.software.leanback" in features or "tv" in chars:
        kind = "tv"
    elif "android.hardware.type.pc" in features:
        kind = "desktop/chromebook"
    elif "tablet" in chars:
        kind = "tablet"
    else:
        kind = classify_size(w, h, density)
    fire_os = manufacturer.lower() == "amazon"
    avd = ""
    if emulator:
        avd_out = adb(serial, "emu", "avd", "name", check=False, timeout=15) or ""
        avd = avd_out.splitlines()[0].strip() if avd_out.strip() else ""
    return {"serial": serial, "model": props.get("ro.product.model", ""), "manufacturer": manufacturer,
            "kind": ("fire-" + kind) if fire_os and kind in ("tv", "tablet") else kind,
            "os": "Fire OS" if fire_os else "Android", "sdk": props.get("ro.build.version.sdk", ""),
            "emulator": emulator, "avd": avd, "width": w, "height": h, "density": density}


def list_devices() -> list[dict]:
    out = adb(None, "devices", "-l")
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            serial, state = parts[0], parts[1]
            if state == "device":
                try:
                    rows.append(device_info(serial))
                except (AndroidError, subprocess.TimeoutExpired) as exc:
                    rows.append({"serial": serial, "state": f"error: {exc}"})
            else:
                rows.append({"serial": serial, "state": state})
    return rows


def require_ok(serial: str, allow_physical: bool) -> dict:
    info = device_info(serial)
    if not info["emulator"] and os.environ.get("LAUNCHFRAME_DENY_PHYSICAL") == "1":
        raise AndroidError(f"{serial} is a physical device and LAUNCHFRAME_DENY_PHYSICAL=1 is set.")
    if not info["emulator"] and not allow_physical:
        raise AndroidError(f"{serial} is a physical device ({info['manufacturer']} {info['model']}). Prefer an "
                           "emulator; pass --allow-physical only if the user asked for this device or no "
                           "emulator can show the target.")
    return info


# ---------------------------------------------------------------- emulators
def boot(name: str, window: bool, cold: bool, timeout: int) -> str:
    names = {a["name"] for a in list_avds()}
    if name not in names:
        raise AndroidError(f"No AVD named {name}. Available: {', '.join(sorted(names)) or 'none'}")
    for d in list_devices():
        if d.get("emulator") and d.get("avd") == name:
            return d["serial"]
    # Always start detached and poll ourselves: `android emulator start` can stay attached for the emulator's
    # whole lifetime (observed with Android CLI 1.x), so waiting on it would hang until timeout.
    cli = find_android_cli()
    if cli:
        cmd = [cli, "emulator", "start"] + ([] if window else ["--headless"]) + (["--cold"] if cold else []) + [name]
    else:
        emu = find_tool("emulator", "emulator")
        if not emu:
            raise AndroidError("Neither the Android CLI nor the SDK emulator was found.")
        cmd = [emu, "-avd", name, "-no-boot-anim"] + ([] if window else ["-no-window"]) + \
              (["-no-snapshot-load"] if cold else [])
    flags = {"creationflags": 0x00000008} if os.name == "nt" else {"start_new_session": True}  # detached
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, **flags)
    deadline = time.time() + timeout
    while time.time() < deadline:
        for d in list_devices():
            if d.get("emulator") and d.get("avd") == name:
                if sh(d["serial"], "getprop sys.boot_completed", check=False) == "1":
                    return d["serial"]
        time.sleep(3)
    raise AndroidError(f"{name} did not finish booting within {timeout}s")


# ---------------------------------------------------------------- state
def state_file(serial: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / (re.sub(r"[^\w.-]", "_", serial) + ".json")


def prepare(serial: str, theme: str | None, orientation: str | None, demo: bool) -> list[str]:
    done = []
    sf = state_file(serial)
    if not sf.is_file():  # keep the ORIGINAL state if prepare runs more than once before restore
        saved = {"night": sh(serial, "cmd uimode night", check=False),
                 "accel": sh(serial, "settings get system accelerometer_rotation", check=False),
                 "user_rotation": sh(serial, "settings get system user_rotation", check=False)}
        sf.write_text(json.dumps(saved), encoding="utf-8")
    sh(serial, "input keyevent 224", check=False)  # wake
    sh(serial, "wm dismiss-keyguard", check=False)
    if demo:
        cmds = ["settings put global sysui_demo_allowed 1",
                "am broadcast -a com.android.systemui.demo -e command enter",
                "am broadcast -a com.android.systemui.demo -e command clock -e hhmm 0941",
                "am broadcast -a com.android.systemui.demo -e command battery -e level 100 -e plugged false",
                "am broadcast -a com.android.systemui.demo -e command network -e wifi show -e level 4 -e fully true",
                "am broadcast -a com.android.systemui.demo -e command network -e mobile hide",
                "am broadcast -a com.android.systemui.demo -e command status -e volume hide -e bluetooth hide "
                "-e location hide -e alarm hide -e zen hide -e sync hide -e tty hide -e eri hide -e mute hide "
                "-e speakerphone hide -e managed_profile hide -e vpn hide",
                "am broadcast -a com.android.systemui.demo -e command notifications -e visible false"]
        for c in cmds:
            sh(serial, c, check=False)
        done.append("status bar demo mode (09:41, full battery/signal, no notifications)")
    if theme:
        sh(serial, f"cmd uimode night {'yes' if theme == 'dark' else 'no'}", check=False)
        done.append(f"system theme {theme}")
    if orientation:
        # user_rotation is relative to the panel's NATURAL orientation (tablets/TVs are often natural landscape).
        sizes = re.findall(r"Physical size: (\d+)x(\d+)", sh(serial, "wm size", check=False))
        natural_landscape = bool(sizes) and int(sizes[0][0]) > int(sizes[0][1])
        want_landscape = orientation == "landscape"
        rot = "0" if want_landscape == natural_landscape else "1"
        sh(serial, "settings put system accelerometer_rotation 0", check=False)
        sh(serial, f"settings put system user_rotation {rot}", check=False)
        done.append(f"rotation locked {orientation}")
    return done


def restore(serial: str) -> list[str]:
    done = []
    sh(serial, "am broadcast -a com.android.systemui.demo -e command exit", check=False)
    done.append("demo mode off")
    sf = state_file(serial)
    if sf.is_file():
        saved = json.loads(sf.read_text(encoding="utf-8"))
        m = re.search(r"Night mode: (\w+)", saved.get("night", ""))
        if m:
            sh(serial, f"cmd uimode night {m.group(1)}", check=False)
            done.append(f"night mode {m.group(1)}")
        if saved.get("accel") in ("0", "1"):
            sh(serial, f"settings put system accelerometer_rotation {saved['accel']}", check=False)
        if saved.get("user_rotation", "").isdigit():
            sh(serial, f"settings put system user_rotation {saved['user_rotation']}", check=False)
        done.append("rotation settings restored")
        sf.unlink()
    return done


# ---------------------------------------------------------------- UI tree
BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def ui_elements(serial: str, include_all=False) -> list[dict]:
    remote = "/sdcard/launchframe-ui.xml"
    last = ""
    for _ in range(3):
        out = sh(serial, f"uiautomator dump {remote}", timeout=60, check=False)
        last = out
        if "dumped" in out.lower():
            break
        time.sleep(1.5)
    else:
        raise AndroidError(f"uiautomator dump failed: {last[:300]} (animations may keep the UI busy; "
                           "try again, or use `android layout --no-idle`)")
    xml = adb(serial, "exec-out", f"cat {remote}", binary=True)
    sh(serial, f"rm {remote}", check=False)
    root = ET.fromstring(xml)
    elements = []
    for node in root.iter("node"):
        m = BOUNDS.match(node.get("bounds", ""))
        if not m:
            continue
        l, t, r, b = (int(x) for x in m.groups())
        el = {"text": node.get("text", ""), "desc": node.get("content-desc", ""),
              "id": node.get("resource-id", ""), "class": node.get("class", "").split(".")[-1],
              "bounds": [l, t, r, b], "center": [(l + r) // 2, (t + b) // 2],
              "clickable": node.get("clickable") == "true", "focusable": node.get("focusable") == "true",
              "focused": node.get("focused") == "true", "selected": node.get("selected") == "true",
              "package": node.get("package", "")}
        if r - l <= 0 or b - t <= 0:
            continue
        if include_all or el["text"] or el["desc"] or el["focused"] or el["clickable"]:
            elements.append(el)
    return elements


def find(elements, text=None, desc=None, rid=None, exact=False) -> list[dict]:
    def match(val, want):
        if want is None:
            return True
        return val == want if exact else want.lower() in val.lower()
    return [e for e in elements if match(e["text"], text) and match(e["desc"], desc) and match(e["id"], rid)
            and (text or desc or rid)]


def resolve_target(elements, hits):
    """A label's own node may not be clickable; climb to the smallest clickable node containing it."""
    out = []
    for h in hits:
        if h["clickable"]:
            out.append(h)
            continue
        l, t, r, b = h["bounds"]
        parents = [e for e in elements if e["clickable"] and e["bounds"][0] <= l and e["bounds"][1] <= t
                   and e["bounds"][2] >= r and e["bounds"][3] >= b]
        out.append(min(parents, key=lambda e: (e["bounds"][2] - e["bounds"][0]) * (e["bounds"][3] - e["bounds"][1]))
                   if parents else h)
    uniq = []
    for e in out:
        if e not in uniq:
            uniq.append(e)
    return uniq


# ---------------------------------------------------------------- capture
def screenshot(serial: str, display: str | None) -> Image.Image:
    args = ["exec-out", "screencap", "-p"] + (["-d", display] if display else [])
    data = adb(serial, *args, binary=True, timeout=60)
    if not data.startswith(b"\x89PNG"):
        raise AndroidError("screencap did not return a PNG (device locked or display id wrong?)")
    im = Image.open(io.BytesIO(data))
    im.load()
    return im


def is_blank(im: Image.Image) -> bool:
    stat = ImageStat.Stat(im.convert("L").resize((64, 64)))
    return stat.stddev[0] < 2.0


def cmd_shot(args) -> int:
    info = require_ok(args.serial, args.allow_physical)
    im = screenshot(args.serial, args.display)
    if is_blank(im):
        raise AndroidError("Captured frame is blank/uniform: screen off, still loading, or the app sets "
                           "FLAG_SECURE. Not saved.")
    w, h = im.size
    if info["width"] and {w, h} != {info["width"], info["height"]} and not args.display:
        print(f"note: capture {w}x{h} differs from wm size {info['width']}x{info['height']}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() != ".png":
        raise AndroidError("--out must be a .png path (raw captures are stored losslessly)")
    im.save(out, "PNG")
    method = "adb exec-out screencap -p" + (f" -d {args.display}" if args.display else "")
    device = {k: info[k] for k in ("model", "manufacturer", "kind", "os", "sdk", "emulator", "avd", "density")}
    device["serial"] = args.serial
    entry = record(out.parent, out, "auto-captured", args.screen, method, device, args.target, note=args.note)
    print(f"Captured {out} {entry['width']}x{entry['height']} from "
          f"{'emulator ' + info['avd'] if info['emulator'] else 'physical ' + info['model']} ({info['kind']})")
    return 0


# ---------------------------------------------------------------- commands
def cmd_avds(args) -> int:
    avds = list_avds()
    if args.json:
        print(json.dumps(avds, indent=2))
        return 0
    if not avds:
        print("No AVDs found.")
        return 0
    print("| AVD | Kind | Size | Density | Device | Image |\n|---|---|---|---|---|---|")
    for a in avds:
        print(f"| {a['name']} | {a['kind']} | {a['width']}x{a['height']} | {a['density']} | {a['device']} | {a['image']} |")
    return 0


def cmd_devices(args) -> int:
    devs = list_devices()
    if args.json:
        print(json.dumps(devs, indent=2))
        return 0
    if not devs:
        print("No devices connected.")
        return 0
    print("| Serial | Type | Kind | OS | Model | Size | Density |\n|---|---|---|---|---|---|---|")
    for d in devs:
        if "state" in d:
            print(f"| {d['serial']} | - | - | - | {d['state']} | - | - |")
            continue
        typ = f"emulator ({d['avd']})" if d["emulator"] else "physical"
        print(f"| {d['serial']} | {typ} | {d['kind']} | {d['os']} {d['sdk']} | {d['manufacturer']} {d['model']} "
              f"| {d['width']}x{d['height']} | {d['density']} |")
    return 0


def cmd_boot(args) -> int:
    serial = boot(args.name, args.window, args.cold, args.timeout)
    print(serial)
    return 0


def cmd_stop(args) -> int:
    info = device_info(args.serial)
    if not info["emulator"]:
        raise AndroidError("stop only shuts down emulators")
    adb(args.serial, "emu", "kill", check=False)
    print(f"Stopped {args.serial}")
    return 0


def cmd_prepare(args) -> int:
    require_ok(args.serial, args.allow_physical)
    for line in prepare(args.serial, args.theme, args.orientation, not args.no_demo):
        print(f"- {line}")
    print("Run `restore` when capture is finished.")
    return 0


def cmd_restore(args) -> int:
    require_ok(args.serial, args.allow_physical)
    for line in restore(args.serial):
        print(f"- {line}")
    return 0


def cmd_launch(args) -> int:
    info = require_ok(args.serial, args.allow_physical)
    if not sh(args.serial, f"pm path {args.package}", check=False):
        raise AndroidError(f"{args.package} is not installed on {args.serial}. Build/install the debug or demo "
                           "variant first (see the project's build instructions).")
    if args.deeplink:
        out = sh(args.serial, f"am start -W -a android.intent.action.VIEW -d '{args.deeplink}' {args.package}")
    else:
        component = args.activity
        if component and component.startswith("."):
            component = args.package + "/" + component
        elif component and "/" not in component:
            component = args.package + "/" + component
        if not component:
            category = "android.intent.category.LEANBACK_LAUNCHER" if info["kind"].endswith("tv") \
                else "android.intent.category.LAUNCHER"
            res = sh(args.serial, f"cmd package resolve-activity --brief -c {category} {args.package}", check=False)
            comps = [ln for ln in res.splitlines() if "/" in ln]
            if not comps and category.endswith("LEANBACK_LAUNCHER"):
                res = sh(args.serial, f"cmd package resolve-activity --brief -c android.intent.category.LAUNCHER "
                                      f"{args.package}", check=False)
                comps = [ln for ln in res.splitlines() if "/" in ln]
            if not comps:
                raise AndroidError(f"Could not resolve a launcher activity for {args.package}; pass --activity")
            component = comps[-1].strip()
        out = sh(args.serial, f"am start -W -n {component}")
    if "Error" in out:
        raise AndroidError(out)
    # Verify the app actually stayed in front: `am start` reports success even if the app crashes at once.
    for _ in range(6):
        time.sleep(1.5)
        top = sh(args.serial, "dumpsys activity activities | grep -E 'topResumedActivity|ResumedActivity'",
                 check=False)
        if args.package + "/" in top:
            print(f"{args.package} is in the foreground")
            return 0
    crash = sh(args.serial, "logcat -d -b crash -t 60", check=False)
    lines = [ln.split("AndroidRuntime: ", 1)[-1] for ln in crash.splitlines()
             if args.package in crash and ("Exception" in ln or "Caused by" in ln or "FATAL" in ln)]
    detail = ("\n  " + "\n  ".join(lines[-4:])) if lines else " (no crash in the crash buffer; it may have "\
             "been sent to the background or blocked by a dialog)"
    raise AndroidError(f"{args.package} did not stay in the foreground.{detail}\nDo not capture; report the blocker.")


def cmd_ui(args) -> int:
    elements = ui_elements(args.serial, args.all)
    if args.json:
        print(json.dumps(elements, indent=2))
        return 0
    print("| # | Text | Desc | Id | Class | Bounds | Flags |\n|---|---|---|---|---|---|---|")
    for i, e in enumerate(elements):
        flags = ",".join(k for k in ("clickable", "focusable", "focused", "selected") if e[k])
        rid = e["id"].split("/")[-1]
        print(f"| {i} | {e['text'][:40]} | {e['desc'][:40]} | {rid} | {e['class']} | {e['bounds']} | {flags} |")
    return 0


def cmd_tap(args) -> int:
    require_ok(args.serial, args.allow_physical)
    # Keyboards and transitions move things: only tap once the target's bounds are stable across two reads.
    previous = None
    for _ in range(5):
        elements = ui_elements(args.serial, include_all=True)
        hits = find(elements, args.text, args.desc, args.id, args.exact)
        targets = resolve_target(elements, hits)
        bounds = [t["bounds"] for t in targets]
        if bounds and bounds == previous:
            break
        previous = bounds
        time.sleep(0.8)
    if not targets:
        raise AndroidError("No element matches. Run `ui` to see what is on screen.")
    if len(targets) > 1 and args.index is None:
        listing = "\n".join(f"  [{i}] text={t['text']!r} desc={t['desc']!r} bounds={t['bounds']}"
                            for i, t in enumerate(targets))
        raise AndroidError(f"{len(targets)} elements match; pass --index N or --exact:\n{listing}")
    t = targets[args.index or 0]
    x, y = t["center"]
    sh(args.serial, f"input tap {x} {y}")
    label = args.text or args.desc or args.id
    via = "" if (t["text"] or t["desc"]) else " via its clickable container"
    print(f"Tapped {label!r}{via} at {x},{y} (bounds {t['bounds']})")
    return 0


def cmd_key(args) -> int:
    require_ok(args.serial, args.allow_physical)
    code = KEYS.get(args.key.lower(), args.key)
    for _ in range(args.repeat):
        sh(args.serial, f"input keyevent {code}")
        time.sleep(args.delay)
    print(f"Sent {args.key} x{args.repeat}")
    return 0


def cmd_type(args) -> int:
    require_ok(args.serial, args.allow_physical)
    if args.clear:  # move to the end and delete, so a field never keeps stale text
        sh(args.serial, "input keyevent KEYCODE_MOVE_END " + " ".join(["KEYCODE_DEL"] * 80))
    escaped = re.sub(r"([\\\"'()&<>|;$`])", r"\\\1", args.value).replace(" ", "%s")
    sh(args.serial, f"input text \"{escaped}\"")
    # Verify the text landed in the focused field (an IME or focus change can route it elsewhere).
    focused = [e for e in ui_elements(args.serial, include_all=True) if e["focused"] and e["class"] == "EditText"]
    if focused:
        got = focused[0]["text"]
        masked = bool(got) and set(got) <= {"•", "*", "•"}
        if not masked and args.value not in got:
            raise AndroidError(f"typed text did not reach the focused field (it shows {got!r}). On TV the keyboard "
                               "can cover fields: move focus with `key tab` / D-pad instead of tapping.")
    print("Typed text (field cleared first)" if args.clear else "Typed text")
    return 0


def cmd_wait(args) -> int:
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        try:
            if find(ui_elements(args.serial, include_all=True), args.text, args.desc, args.id, args.exact):
                print("Visible")
                return 0
        except AndroidError:
            pass
        time.sleep(1.5)
    raise AndroidError(f"Not visible after {args.timeout}s - the expected screen is not showing")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, serial=True, physical=False):
        p = sub.add_parser(name)
        if serial:
            p.add_argument("--serial", required=True, help="adb serial (see `devices`)")
        if physical:
            p.add_argument("--allow-physical", action="store_true",
                           help="permit this action on a physical device (only when requested/necessary)")
        p.set_defaults(fn=fn)
        return p

    for name, fn in (("avds", cmd_avds), ("devices", cmd_devices)):
        add(name, fn, serial=False).add_argument("--json", action="store_true")
    p = add("boot", cmd_boot, serial=False)
    p.add_argument("name")
    p.add_argument("--window", action="store_true", help="show the emulator window (default headless)")
    p.add_argument("--cold", action="store_true", help="cold boot (ignore snapshot)")
    p.add_argument("--timeout", type=int, default=300)
    add("stop", cmd_stop)
    p = add("prepare", cmd_prepare, physical=True)
    p.add_argument("--theme", choices=["dark", "light"])
    p.add_argument("--orientation", choices=["portrait", "landscape"])
    p.add_argument("--no-demo", action="store_true", help="leave the status bar alone")
    add("restore", cmd_restore, physical=True)
    p = add("launch", cmd_launch, physical=True)
    p.add_argument("--package", required=True)
    p.add_argument("--activity")
    p.add_argument("--deeplink")
    p = add("ui", cmd_ui)
    p.add_argument("--all", action="store_true", help="include non-interactive, unlabeled nodes")
    p.add_argument("--json", action="store_true")
    for name, fn in (("tap", cmd_tap), ("wait", cmd_wait)):
        p = add(name, fn, physical=(name == "tap"))
        p.add_argument("--text")
        p.add_argument("--desc")
        p.add_argument("--id")
        p.add_argument("--exact", action="store_true")
        if name == "tap":
            p.add_argument("--index", type=int)
        else:
            p.add_argument("--timeout", type=int, default=20)
    p = add("key", cmd_key, physical=True)
    p.add_argument("key", help="up down left right center enter back home menu play_pause, or a keycode")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--delay", type=float, default=0.35)
    p = add("type", cmd_type, physical=True)
    p.add_argument("value")
    p.add_argument("--clear", action="store_true", help="empty the focused field before typing")
    p = add("shot", cmd_shot, physical=True)
    p.add_argument("--out", required=True)
    p.add_argument("--screen", required=True)
    p.add_argument("--target")
    p.add_argument("--display", help="display id for multi-display devices (foldables)")
    p.add_argument("--note")
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except AndroidError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    except subprocess.TimeoutExpired as exc:
        sys.stderr.write(f"error: timed out: {exc.cmd}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
