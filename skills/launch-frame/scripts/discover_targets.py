#!/usr/bin/env python3
"""Discover which app targets a repository really supports, with graded evidence.

Reads build files, manifests, Xcode projects, package manifests and docs, then
classifies every relevant device target as:
  Confirmed   - strong, direct declaration in the app's own build/manifest config
  Probable    - meaningful evidence that still needs runtime or user confirmation
  Unknown     - only keywords/docs, or nothing (never enough to produce assets)
  Unsupported - explicit evidence the target is excluded
It also reports app modules, package ids, variants, launch activities, deep
links, existing screenshot/UI-test infrastructure, existing store assets and
capture considerations (login, network).

Usage:
  python discover_targets.py [REPO] [--json capability.json] [--markdown capability-report.md]

Requires: Python 3.9+ (standard library only). Read-only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "build", "dist", "out", ".next", ".gradle", ".idea", "Pods", "DerivedData",
             ".venv", "venv", "__pycache__", ".dart_tool", ".expo", "coverage", "vendor", "target", ".turbo",
             ".cache", "intermediates", ".kotlin", ".cxx", "Carthage", ".build", ".svelte-kit"}
A = "{http://schemas.android.com/apk/res/android}"
MAX_TEXT = 800_000

# target key -> (label, store target keys)
TARGETS = {
    "android-phone": ("Android phone", ["google-play/phone"]),
    "android-tablet": ("Android tablet", ["google-play/tablet-7-inch", "google-play/tablet-10-inch"]),
    "android-foldable": ("Android foldable", ["google-play/foldable"]),
    "chromebook": ("Chromebook", ["google-play/chromebook"]),
    "android-tv": ("Android TV / Google TV", ["google-play/tv", "google-play/tv-banner"]),
    "wear-os": ("Wear OS", ["google-play/wear-os"]),
    "android-automotive": ("Android Automotive OS", ["google-play/automotive"]),
    "android-xr": ("Android XR", ["google-play/xr"]),
    "fire-tv": ("Amazon Fire TV", ["amazon-appstore/fire-tv", "amazon-appstore/fire-tv-icon",
                                   "amazon-appstore/fire-tv-background"]),
    "fire-tablet": ("Amazon Fire Tablet", ["amazon-appstore/fire-tablet", "amazon-appstore/fire-tablet-icons"]),
    "iphone": ("iPhone", ["apple-app-store/iphone"]),
    "ipad": ("iPad", ["apple-app-store/ipad"]),
    "apple-tv": ("Apple TV", ["apple-app-store/apple-tv"]),
    "apple-watch": ("Apple Watch", ["apple-app-store/apple-watch"]),
    "vision-pro": ("Apple Vision Pro", ["apple-app-store/vision-pro"]),
    "mac": ("Mac", ["apple-app-store/mac"]),
    "desktop": ("Desktop (Windows/Linux/macOS app)", []),
    "web": ("Web app", []),
}
ECOSYSTEM = {
    "android": ["android-phone", "android-tablet", "android-foldable", "chromebook", "android-tv", "wear-os",
                "android-automotive", "android-xr", "fire-tv", "fire-tablet"],
    "apple": ["iphone", "ipad", "apple-tv", "apple-watch", "vision-pro", "mac"],
    "desktop": ["desktop"],
    "web": ["web"],
}

DOC_PATTERNS = {
    "android-tv": r"\b(android tv|google tv)\b",
    "wear-os": r"\bwear ?os\b",
    "android-tablet": r"\btablets?\b",
    "chromebook": r"\bchromebooks?\b",
    "android-automotive": r"\b(android automotive|automotive os)\b",
    "android-xr": r"\bandroid xr\b",
    "fire-tv": r"\bfire ?tv\b",
    "fire-tablet": r"\bfire (hd |max )?tablets?\b",
    "ipad": r"\bipad\b",
    "apple-tv": r"\b(apple tv|tvos)\b",
    "apple-watch": r"\b(apple watch|watchos)\b",
    "vision-pro": r"\b(vision pro|visionos)\b",
}
SCREENSHOT_TOOLS = [
    (r"app\.cash\.paparazzi", "Paparazzi screenshot tests"),
    (r"roborazzi", "Roborazzi screenshot tests"),
    (r"com\.karumi\.shot", "Shot screenshot tests"),
    (r"com\.android\.compose\.screenshot", "Compose Preview Screenshot Testing"),
    (r"tools\.fastlane:screengrab|Screengrab", "fastlane screengrab"),
    (r"SnapshotHelper|snapshot\(\"", "fastlane snapshot (iOS)"),
    (r"androidx\.test\.espresso", "Espresso UI tests"),
    (r"androidx\.compose\.ui:ui-test", "Compose UI tests"),
    (r"androidx\.test\.uiautomator", "UI Automator tests"),
    (r"XCUIApplication\(\)", "XCUITest UI tests"),
    (r"\"detox\"", "Detox"),
    (r"@playwright/test|playwright\.config", "Playwright"),
]
LOGIN_HINTS = re.compile(r"\b(sign[ _-]?in|log[ _-]?in|login|authenticate|password)\b", re.I)


class Findings:
    def __init__(self):
        self.signals: dict[str, list[tuple[str, str]]] = defaultdict(list)  # target -> [(strength, evidence)]
        self.ecosystems: set[str] = set()
        self.facts: dict[str, list] = defaultdict(list)

    def add(self, target: str, strength: str, evidence: str):
        item = (strength, evidence)
        if item not in self.signals[target] and len(self.signals[target]) < 12:
            self.signals[target].append(item)

    def fact(self, key: str, value):
        if value not in self.facts[key] and len(self.facts[key]) < 40:
            self.facts[key].append(value)


def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not (d.startswith(".") and d != ".maestro")]
        yield Path(dirpath), dirnames, filenames


def read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_TEXT:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def is_test_path(rel: str) -> bool:
    return bool(re.search(r"(^|/)(test|tests|androidTest|commonTest|jvmTest|testFixtures|__tests__|"
                          r"\w+UITests|\w+Tests|fixtures?|samples?|examples?)(/|$)", rel))


# ---------------------------------------------------------------- Android
def gradle_info(text: str) -> dict:
    plugin_lines = [ln for ln in text.splitlines() if not re.search(r"apply\s*\(?\s*false", ln)]
    applied = "\n".join(plugin_lines)
    info = {"application": bool(re.search(
        r"com\.android\.application|android\.application\b|id\s*\(?\s*[\"']com\.android\.application", applied)),
        "library": "com.android.library" in text or "android.library" in text}
    m = re.search(r"applicationId\s*=?\s*[\"']([\w.]+)[\"']", text)
    info["applicationId"] = m.group(1) if m else None
    info["flavors"] = block_names(text, "productFlavors")
    info["buildTypes"] = block_names(text, "buildTypes")
    info["compose_desktop"] = bool(re.search(r"compose\.desktop\s*\{", text)) and "application" in text
    deps = {
        "androidx.tv": "android-tv", "androidx.leanback": "android-tv", "androidx.wear": "wear-os",
        "androidx.car.app": "android-automotive", "androidx.xr": "android-xr", "androidx.window": "android-foldable",
        "material3.adaptive": "android-tablet", "material3-adaptive": "android-tablet",
        "material3-window-size-class": "android-tablet", "com.amazon.device": "fire-tv",
    }
    info["deps"] = sorted({t for k, t in deps.items() if k in text})
    return info


def block_names(text: str, block: str) -> list[str]:
    m = re.search(block + r"\s*\{", text)
    if not m:
        return []
    depth, i, start = 1, m.end(), m.end()
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    body = text[start:i - 1]
    names, depth = [], 0
    for tok in re.finditer(r"([{}])|(?:create|register|maybeCreate|getByName)\(\s*\"(\w+)\"\s*\)|^\s*(\w+)\s*\{",
                           body, re.M):
        if tok.group(1) == "{":
            depth += 1
        elif tok.group(1) == "}":
            depth -= 1
        name = tok.group(2) or tok.group(3)
        if name and depth == 0 and name not in names:
            names.append(name)
        if tok.group(3):
            depth += 1  # the "{" was consumed by the name alternative
    return names


def parse_manifest(path: Path, rel: str, f: Findings, module_is_app: bool):
    text = read(path)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return
    pkg = root.get("package")
    if pkg:
        f.fact("manifest_packages", pkg)
    features = {}
    for uf in root.iter("uses-feature"):
        name = uf.get(A + "name") or ""
        req = (uf.get(A + "required") or "true").lower() != "false"
        features[name] = req
    for sc in root.iter("supports-screens"):
        if (sc.get(A + "largeScreens") or "").lower() == "false" and module_is_app:
            f.add("android-tablet", "negative", f"{rel}: supports-screens largeScreens=false")
    app = root.find("application")
    launcher = leanback = False
    if app is not None:
        if app.get(A + "banner") and module_is_app:
            f.add("android-tv", "medium", f"{rel}: application android:banner set")
        for meta in app.iter("meta-data"):
            n = meta.get(A + "name") or ""
            if n == "com.google.android.gms.car.application" and module_is_app:
                f.add("android-automotive", "strong", f"{rel}: car application meta-data")
            if n == "com.google.android.wearable.standalone" and module_is_app:
                f.add("wear-os", "strong", f"{rel}: wearable.standalone meta-data")
        for act in list(app.iter("activity")) + list(app.iter("activity-alias")):
            aname = act.get(A + "name") or "?"
            for flt in act.iter("intent-filter"):
                cats = {c.get(A + "name") for c in flt.iter("category")}
                actions = {a.get(A + "name") for a in flt.iter("action")}
                if "android.intent.action.MAIN" in actions:
                    if "android.intent.category.LAUNCHER" in cats:
                        launcher = True
                        f.fact("launch_activities", f"{aname} (LAUNCHER) [{rel}]")
                    if "android.intent.category.LEANBACK_LAUNCHER" in cats:
                        leanback = True
                        f.fact("launch_activities", f"{aname} (LEANBACK_LAUNCHER) [{rel}]")
                if "android.intent.action.VIEW" in actions:
                    for d in flt.iter("data"):
                        scheme, host = d.get(A + "scheme"), d.get(A + "host")
                        if scheme:
                            path = d.get(A + "pathPrefix") or d.get(A + "path") or d.get(A + "pathPattern") or ""
                            f.fact("deep_links", f"{scheme}://{host or ''}{path}  [{aname}]")
    if not module_is_app:
        feat_names = {"android.software.leanback": "android-tv", "android.hardware.type.watch": "wear-os",
                      "android.hardware.type.automotive": "android-automotive"}
        for name in features:
            if name in feat_names:
                f.add(feat_names[name], "weak", f"{rel}: {name} in a library module (not the app; ignored)")
        return
    if launcher:
        f.add("android-phone", "strong", f"{rel}: MAIN/LAUNCHER activity")
    if leanback:
        f.add("android-tv", "strong", f"{rel}: LEANBACK_LAUNCHER activity")
    feat_map = {
        "android.software.leanback": "android-tv", "android.hardware.type.watch": "wear-os",
        "android.hardware.type.automotive": "android-automotive", "android.hardware.type.pc": "chromebook",
        "android.software.xr.api.spatial": "android-xr", "android.software.xr.immersive": "android-xr",
        "android.software.xr.api.openxr": "android-xr", "amazon.hardware.fire_tv": "fire-tv",
    }
    for name, req in features.items():
        t = feat_map.get(name)
        if t:
            strength = "strong" if (req or t in ("fire-tv", "android-xr", "chromebook")) else "medium"
            f.add(t, strength, f"{rel}: uses-feature {name} required={str(req).lower()}")
    if features.get("android.software.leanback") is True:
        f.add("android-phone", "negative", f"{rel}: leanback required=true (TV-only distribution)")
        f.add("android-tablet", "negative", f"{rel}: leanback required=true (TV-only distribution)")
    if features.get("android.hardware.type.watch") is True:
        f.add("android-phone", "negative", f"{rel}: hardware.type.watch required=true (watch-only)")
    if features.get("android.hardware.touchscreen") is False:
        f.add("chromebook", "weak", f"{rel}: touchscreen not required")


# ---------------------------------------------------------------- Apple
def parse_pbxproj(path: Path, rel: str, f: Findings):
    text = read(path)
    for block in re.findall(r"buildSettings\s*=\s*\{(.*?)\};", text, re.S):
        bundle = re.search(r"PRODUCT_BUNDLE_IDENTIFIER\s*=\s*\"?([^\";]+)", block)
        if not bundle or re.search(r"tests?\b|UITests", bundle.group(1), re.I):
            continue
        bid = bundle.group(1).strip()
        f.fact("bundle_ids", bid)
        sdk = (re.search(r"SDKROOT\s*=\s*\"?(\w+)", block) or [None, ""])[1]
        fam = (re.search(r"TARGETED_DEVICE_FAMILY\s*=\s*\"?([\d,]+)", block) or [None, ""])[1]
        plats = (re.search(r"SUPPORTED_PLATFORMS\s*=\s*\"([^\"]+)\"", block) or [None, ""])[1]
        platforms = set(plats.split()) | {sdk}
        fams = set(fam.split(",")) if fam else set()
        ev = f"{rel}: {bid}"
        if "iphoneos" in platforms:
            if not fams or "1" in fams:
                f.add("iphone", "strong", f"{ev} SDK iphoneos, device family {fam or 'default'}")
            if "2" in fams:
                f.add("ipad", "strong", f"{ev} device family includes 2 (iPad)")
            elif fams == {"1"}:
                f.add("ipad", "negative", f"{ev} TARGETED_DEVICE_FAMILY = 1 (iPhone only)")
        if "appletvos" in platforms or "3" in fams:
            f.add("apple-tv", "strong", f"{ev} tvOS")
        if "watchos" in platforms or "4" in fams:
            f.add("apple-watch", "strong", f"{ev} watchOS")
        if "xros" in platforms or "7" in fams:
            f.add("vision-pro", "strong", f"{ev} visionOS")
        if "macosx" in platforms:
            f.add("mac", "strong", f"{ev} macOS")
        if re.search(r"SUPPORTS_MACCATALYST\s*=\s*YES", block):
            f.add("mac", "medium", f"{ev} Mac Catalyst")


# ---------------------------------------------------------------- main scan
def scan(root: Path) -> Findings:
    f = Findings()
    gradle_dirs: dict[Path, dict] = {}
    manifests: list[Path] = []
    docs: list[Path] = []
    sources_checked = 0
    for d, dirnames, files in walk(root):
        rel_d = d.relative_to(root).as_posix()
        rel_d = "" if rel_d == "." else rel_d
        if rel_d.startswith("store-assets"):
            continue
        if d.name == "store-assets":
            continue
        if "store-assets" in dirnames:
            for r in sorted((d / "store-assets").glob("release-*")):
                f.fact("existing_store_assets", r.relative_to(root).as_posix())
        if d.name == ".maestro" or any(n.endswith(".maestro") for n in [d.name]):
            f.fact("capture_infrastructure", f"Maestro flows in {rel_d}")
        if re.search(r"(^|/)(layout|values)-(sw[6-9]\d\ddp|large|xlarge|w[6-9]\d\ddp)(-|$)", rel_d) \
                and "/src/main/res/" in "/" + rel_d + "/" and not is_test_path(rel_d):
            f.add("android-tablet", "strong", f"{rel_d}: large-screen resources")
        if re.search(r"fastlane/metadata/android/.+/images/(phone|sevenInch|tenInch|tv|wear)Screenshots$", rel_d) \
                or re.search(r"(^|/)screenshots?$", rel_d):
            imgs = [x for x in files if x.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
            if imgs:
                f.fact("existing_screenshots", f"{rel_d}/ ({len(imgs)} images)")
        for name in files:
            p = d / name
            rel = (rel_d + "/" + name).lstrip("/")
            low = name.lower()
            if name in ("build.gradle", "build.gradle.kts", "libs.versions.toml"):
                gtext = read(p)
                if name != "libs.versions.toml":
                    gradle_dirs[d] = gradle_info(gtext)
                for pat, label in SCREENSHOT_TOOLS:
                    if re.search(pat, gtext):
                        f.fact("capture_infrastructure", f"{label} ({rel})")
            elif name == "AndroidManifest.xml" and not is_test_path(rel):
                manifests.append(p)
            elif name == "project.pbxproj":
                f.ecosystems.add("apple")
                parse_pbxproj(p, rel, f)
            elif name in ("Snapfile", "Screengrabfile"):
                f.fact("capture_infrastructure", f"fastlane {name} ({rel})")
            elif name == "package.json":
                parse_package_json(p, rel, f)
            elif name == "pubspec.yaml" and re.search(r"^\s*flutter:\s*$", read(p), re.M):
                for plat, tgt in (("ios", "iphone"), ("macos", "mac"), ("web", "web"),
                                  ("windows", "desktop"), ("linux", "desktop")):
                    if (d / plat).is_dir():
                        f.add(tgt, "medium", f"{rel}: Flutter platform folder {plat}/")
                        f.ecosystems.add({"iphone": "apple", "mac": "apple"}.get(tgt, tgt))
            elif name in ("app.json", "app.config.js", "app.config.ts"):
                parse_expo(p, rel, f)
            elif name == "Package.swift":
                t = read(p)
                for k, tgt in ((".iOS(", "iphone"), (".tvOS(", "apple-tv"), (".watchOS(", "apple-watch"),
                               (".visionOS(", "vision-pro"), (".macOS(", "mac")):
                    if k in t:
                        f.add(tgt, "weak", f"{rel}: Swift package platform {k[1:-1]} (package, not app target)")
            elif name == "tauri.conf.json":
                f.ecosystems.add("desktop")
                f.add("desktop", "strong", f"{rel}: Tauri app")
            elif low.endswith(".csproj") and re.search(r"<(UseWPF|UseWinUI|UseWindowsForms)>true", read(p)):
                f.ecosystems.add("desktop")
                f.add("desktop", "strong", f"{rel}: Windows desktop project")
            elif low.endswith(".md") and (rel_d == "" or re.match(r"(docs?|release|metadata|store)(/|$)", rel_d)):
                docs.append(p)
            elif low.endswith((".kt", ".java", ".swift", ".dart", ".ts", ".tsx", ".js", ".xml", ".yaml", ".yml")) \
                    and sources_checked < 6000:
                sources_checked += 1
                scan_source(p, rel, f)

    # Gradle modules and manifests
    app_modules = {d for d, info in gradle_dirs.items() if info["application"]}
    for d, info in gradle_dirs.items():
        rel = d.relative_to(root).as_posix() or "."
        if info["application"]:
            f.ecosystems.add("android")
            f.fact("android_app_modules", f"{rel} (applicationId {info['applicationId'] or 'not set in this file'})")
            for fl in info["flavors"]:
                f.fact("build_variants", f"{rel}: flavor {fl}")
                if "amazon" in fl.lower() or "fire" in fl.lower():
                    f.fact("amazon_intent", f"{rel}: product flavor '{fl}'")
            for bt in info["buildTypes"]:
                f.fact("build_variants", f"{rel}: buildType {bt}")
            for t in info["deps"]:
                f.add(t, "weak", f"{rel}/build.gradle*: dependency for {TARGETS[t][0]}")
        if info["library"] and not info["application"]:
            for t in info["deps"]:
                f.add(t, "weak", f"{rel}/build.gradle*: {TARGETS[t][0]} dependency in library module {rel} "
                                 "(not the app; ignored)")
        if info["compose_desktop"]:
            f.ecosystems.add("desktop")
            f.add("desktop", "strong", f"{rel}/build.gradle*: Compose Desktop application")
        if (d / "gradlew").exists() or (d / "gradlew.bat").exists():
            f.fact("build_entry_points", f"{rel}/gradlew")
    for m in manifests:
        rel = m.relative_to(root).as_posix()
        module = next((d for d in app_modules if d in m.parents), None)
        parse_manifest(m, rel, f, module_is_app=module is not None)

    # Docs: weak mentions + distribution intent
    for p in docs:
        text = read(p)
        rel = p.relative_to(root).as_posix()
        for tgt, pat in DOC_PATTERNS.items():
            if re.search(pat, text, re.I):
                f.add(tgt, "weak", f"{rel}: mentions {TARGETS[tgt][0]}")
        if re.search(r"amazon app ?store", text, re.I):
            f.fact("amazon_intent", f"{rel}: mentions Amazon Appstore")
        if re.search(r"(google play|play console)", text, re.I):
            f.fact("store_intent", f"{rel}: Google Play")
        if re.search(r"app store connect|apple app store", text, re.I):
            f.fact("store_intent", f"{rel}: Apple App Store")
    return f


def parse_package_json(p: Path, rel: str, f: Findings):
    try:
        data = json.loads(read(p) or "{}")
    except json.JSONDecodeError:
        return
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    if "react-native" in deps:
        f.fact("frameworks", f"React Native ({rel})")
        return
    if "electron" in deps:
        f.ecosystems.add("desktop")
        f.add("desktop", "strong", f"{rel}: Electron app")
    web = [k for k in ("next", "vite", "react-scripts", "@angular/core", "nuxt", "@sveltejs/kit", "astro", "vue")
           if k in deps]
    if web and "react-native" not in deps:
        scripts = data.get("scripts", {})
        parent = Path(rel).parent.name.lower()
        if re.fullmatch(r"(website|site|www|docs?|landing|marketing|homepage|blog|storybook)", parent):
            f.add("web", "weak", f"{rel}: {', '.join(web)} project looks like a website/docs site, not the app")
            return
        strength = "strong" if ("build" in scripts or "dev" in scripts) else "medium"
        f.ecosystems.add("web")
        f.add("web", strength, f"{rel}: web framework {', '.join(web)}")
    for pat, label in SCREENSHOT_TOOLS:
        if re.search(pat, json.dumps(deps)):
            f.fact("capture_infrastructure", f"{label} ({rel})")


def parse_expo(p: Path, rel: str, f: Findings):
    text = read(p)
    if "expo" not in text and '"ios"' not in text:
        return
    f.fact("frameworks", f"Expo / React Native config ({rel})")
    if re.search(r"[\"']?ios[\"']?\s*:\s*\{", text):
        f.ecosystems.add("apple")
        if re.search(r"bundleIdentifier", text):
            f.add("iphone", "strong", f"{rel}: ios.bundleIdentifier")
        else:
            f.add("iphone", "medium", f"{rel}: ios config")
        if re.search(r"supportsTablet[\"']?\s*:\s*true", text):
            f.add("ipad", "strong", f"{rel}: ios.supportsTablet true")
        elif re.search(r"supportsTablet[\"']?\s*:\s*false", text):
            f.add("ipad", "negative", f"{rel}: ios.supportsTablet false")
    if re.search(r"[\"']?android[\"']?\s*:\s*\{", text) and re.search(r"package[\"']?\s*:", text):
        f.ecosystems.add("android")
        f.add("android-phone", "strong", f"{rel}: android.package")
    if re.search(r"isTV|react-native-tvos", text):
        f.add("android-tv", "medium", f"{rel}: TV config")


FORM_FACTOR_ENUM = re.compile(r"enum\s+(?:class\s+)?\w*(?:FormFactor|DeviceType|DeviceClass|ScreenClass|LayoutClass)\w*"
                              r"\s*(?:\([^)]*\))?\s*(?::\s*[\w<>]+)?\s*\{([^}]*)\}")
ENUM_ENTRIES = {"TABLET": "android-tablet", "TV": "android-tv", "TELEVISION": "android-tv", "WATCH": "wear-os",
                "WEAR": "wear-os", "FOLD": "android-foldable", "FOLDABLE": "android-foldable", "CAR": "android-automotive",
                "AUTOMOTIVE": "android-automotive", "DESKTOP": "desktop", "XR": "android-xr"}

ADAPTIVE = [
    (r"\bscreenWidthDp\b|maxWidth\s*[<>]=?\s*\d{3}\.dp", "android-tablet", "medium", "width-adaptive layout code"),
    (r"\b(calculateWindowSizeClass|currentWindowAdaptiveInfo|WindowSizeClass|NavigationSuiteScaffold|"
     r"ListDetailPaneScaffold|SupportingPaneScaffold)\b", "android-tablet", "medium", "adaptive layout API"),
    (r"\b(WindowInfoTracker|FoldingFeature)\b", "android-foldable", "strong", "fold-aware code"),
    (r"\bandroidx\.tv\.material3\b|\bandroidx\.tv\.foundation\b", "android-tv", "medium", "TV Compose UI code"),
    (r"\bUIDevice\.current\.userInterfaceIdiom\s*==\s*\.pad\b|horizontalSizeClass", "ipad", "medium",
     "iPad-specific layout code"),
]


def scan_source(p: Path, rel: str, f: Findings):
    text = read(p)
    if not text:
        return
    test = is_test_path(rel)
    for pat, label in SCREENSHOT_TOOLS:
        if re.search(pat, text):
            f.fact("capture_infrastructure", f"{label} ({rel})")
    if test:
        return
    for pat, tgt, strength, label in ADAPTIVE:
        if re.search(pat, text):
            f.add(tgt, strength, f"{rel}: {label}")
    for body in FORM_FACTOR_ENUM.findall(text):
        for entry in re.findall(r"\b([A-Z][A-Z_]+)\b", body):
            tgt = ENUM_ENTRIES.get(entry)
            if tgt:
                f.add(tgt, "medium", f"{rel}: app form-factor enum has {entry}")
    if rel.endswith(".xml") and "/res/values" in rel and "strings" in p.name and LOGIN_HINTS.search(text):
        f.fact("capture_considerations", f"login/auth strings present ({rel}) - plan demo account or demo mode")
    if re.search(r"(^|/)(login|signin|sign_in|auth)[\w-]*\.(kt|swift|dart|tsx?|jsx?)$", rel, re.I):
        f.fact("capture_considerations", f"auth screen in code ({rel}) - capture may need a test account")


def classify(f: Findings) -> list[dict]:
    rows = []
    # Fire TV / Fire Tablet: technical support + distribution intent
    amazon = f.facts.get("amazon_intent", [])
    for t in ECOSYSTEM["android"] + ECOSYSTEM["apple"] + ECOSYSTEM["desktop"] + ECOSYSTEM["web"]:
        sig = f.signals.get(t, [])
        strengths = {s for s, _ in sig}
        if "negative" in strengths:
            status = "Unsupported"
        elif "strong" in strengths:
            status = "Confirmed"
        elif "medium" in strengths:
            status = "Probable"
        else:
            status = "Unknown"
        rows.append({"target": t, "label": TARGETS[t][0], "status": status, "evidence": sig,
                     "store_targets": TARGETS[t][1]})
    by = {r["target"]: r for r in rows}
    tv, phone = by["android-tv"], by["android-phone"]
    if by["fire-tv"]["status"] in ("Unknown", "Probable") and tv["status"] == "Confirmed" and amazon:
        by["fire-tv"]["status"] = "Confirmed" if any("product flavor" in a or "Amazon Appstore" in a
                                                       for a in amazon) else "Probable"
        by["fire-tv"]["evidence"] = by["fire-tv"]["evidence"] + [
            ("derived", "TV app (LEANBACK_LAUNCHER) runs on Fire TV"), ("derived", "; ".join(amazon[:3]))]
    # Fire Tablet is never lifted by doc mentions (docs often say "Fire TV only"); it needs real evidence
    # (e.g. a Fire-tablet flavor or device targeting) or a runtime/user confirmation via init_release --force-target.
    # Tablet: a phone app installs on tablets, but a store set needs real tablet layout evidence.
    # Docs mentions alone never lift it; only layout code/resources (medium/strong) do.
    for r in rows:
        r["evidence"].sort(key=lambda e: ["negative", "strong", "medium", "derived", "weak"].index(e[0]))
    return rows


def action_for(row: dict) -> str:
    return {"Confirmed": "Capture", "Probable": "Confirm (runtime check or ask)",
            "Unknown": "Skip", "Unsupported": "Skip (unsupported)"}[row["status"]]


def relevant_rows(rows: list[dict], f: Findings) -> list[dict]:
    keep = []
    for r in rows:
        eco = next(e for e, ts in ECOSYSTEM.items() if r["target"] in ts)
        if eco in f.ecosystems or r["status"] != "Unknown":
            keep.append(r)
    return keep


def to_markdown(root: Path, rows: list[dict], f: Findings) -> str:
    out = [f"# Capability report: {root.name}", "",
           "Generated by discover_targets.py from repository evidence. Statuses: Confirmed (direct declaration), "
           "Probable (needs runtime/user confirmation), Unknown (keywords or nothing), Unsupported (explicitly "
           "excluded). Keyword mentions alone never confirm a target.", "",
           "| Target | Status | Evidence | Action | Store sets |", "|---|---|---|---|---|"]
    for r in rows:
        ev = "; ".join(f"{e} ({s})" for s, e in r["evidence"][:4]) or "no evidence found"
        out.append(f"| {r['label']} | {r['status']} | {ev} | {action_for(r)} | "
                   f"{', '.join(r['store_targets']) or 'n/a (custom store)'} |")
    out.append("")
    sections = [("android_app_modules", "Android app modules"), ("bundle_ids", "Apple bundle identifiers"),
                ("manifest_packages", "Manifest packages"), ("build_variants", "Build variants"),
                ("launch_activities", "Launch activities"), ("deep_links", "Deep links"),
                ("build_entry_points", "Build entry points"), ("frameworks", "Frameworks"),
                ("capture_infrastructure", "Existing capture / UI-test infrastructure"),
                ("existing_screenshots", "Existing screenshot folders"),
                ("existing_store_assets", "Existing store-assets releases (do not overwrite)"),
                ("capture_considerations", "Capture considerations"),
                ("amazon_intent", "Amazon distribution evidence"), ("store_intent", "Other store intent")]
    always = {"capture_infrastructure", "existing_screenshots", "existing_store_assets"}
    for key, title in sections:
        if not f.facts.get(key) and key in always:
            out += [f"## {title}", "", "- none found", ""]
            continue
        if f.facts.get(key):
            vals = f.facts[key]
            out += [f"## {title}", ""] + [f"- {v}" for v in vals[:8]]
            out += ([f"- ... and {len(vals) - 8} more"] if len(vals) > 8 else []) + [""]
    out += ["Next: confirm Probable targets at runtime (emulator/device) or with the user; run check_env.py "
            "to see which targets can be captured here."]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--markdown", dest="md_out")
    ap.add_argument("--all", action="store_true", help="list every known target, not only relevant ecosystems")
    args = ap.parse_args(argv)
    root = Path(args.repo).resolve()
    if not root.is_dir():
        sys.stderr.write(f"Not a directory: {root}\n")
        return 2
    f = scan(root)
    rows = classify(f)
    shown = rows if args.all else relevant_rows(rows, f)
    md = to_markdown(root, shown, f)
    if args.md_out:
        Path(args.md_out).write_text(md, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "repo": str(root), "ecosystems": sorted(f.ecosystems),
            "targets": [{**r, "action": action_for(r), "evidence": [{"strength": s, "detail": e}
                                                                     for s, e in r["evidence"]]} for r in rows],
            "facts": f.facts}, indent=2), encoding="utf-8")
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
