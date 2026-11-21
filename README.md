# LaunchFrame

An Agent Skill for Claude Code that turns an app's real screenshots into store-ready listing assets:
designed to match the app, sized and validated for each store, and handed off in a release folder
that someone else (or another agent) can upload from.

How a release works:
1. It inspects the repository to work out which targets the app really supports. Each target is graded
   Confirmed, Probable, Unknown or Unsupported, based on manifests, build files and Xcode settings, not
   keywords.
2. It checks what this machine can capture with: SDKs, emulators, simulators and connected devices.
3. It captures authentic screenshots automatically, preferring emulators and simulators. It navigates
   via deep links or taps grounded in the live UI tree, and records where every source came from.
4. It reads the app's design evidence: theme code, tokens, fonts, icons, brand docs and the captures.
5. It plans a story from features it can prove and composes each image individually around the real UI.
6. It renders exact-size files, reviews them visually, fixes problems, and validates them against a dated
   profile of official store requirements.
7. It writes upload instructions per store. When you ask, it can also do the console upload through
   browser tools.

## Supported stores

| Store | Device sets |
|---|---|
| Google Play | Phone, 7" and 10" tablet, Chromebook, foldable, Android TV / Google TV, Wear OS, Automotive OS, Android XR, feature graphic, TV banner, hi-res icon |
| Apple App Store | iPhone (large and 6.1" classes, Duo), iPad 13", Mac, Apple TV, Vision Pro, Apple Watch |
| Amazon Appstore | Fire Tablet (screenshots, icons, promo image), Fire TV (screenshots, icon, background) |
| Others | Samsung Galaxy Store, Huawei AppGallery, Microsoft Store, etc. via a profile override written from their official docs at release time (none bundled) |

The store rules live in `skills/launch-frame/assets/platform-profiles.json`, checked against official
documentation on the date in that file. Store rules change, so the skill re-checks the official pages at
the start of each release when it has web access.

## Install

Requirements: Python 3.9+ with Pillow (`pip install Pillow`). For rendering, either
`pip install playwright` or an installed Chrome, Edge or Chromium. For automatic capture, whichever
platform tooling you already have: Android SDK platform-tools (adb) plus emulator/AVDs (the Android CLI
is used when present), Xcode simulators on macOS, and Playwright/Chrome for web. Optional: Claude in Chrome (or
another browser tool) for upload assistance.

**As a plugin (Claude Code)**
```
/plugin marketplace add Rifaque/launch-frame
/plugin install launch-frame@launch-frame
```

**As a personal skill** (clone, then link the skill folder):
```
git clone https://github.com/Rifaque/launch-frame.git
# macOS / Linux
ln -s "$PWD/launch-frame/skills/launch-frame" ~/.claude/skills/launch-frame
# Windows (PowerShell)
New-Item -ItemType Junction -Path "$HOME\.claude\skills\launch-frame" -Target "$PWD\launch-frame\skills\launch-frame"
```
Copying the folder instead of linking also works. Run `/reload-skills` (or restart) if it doesn't appear.

## Use

From the app's repository, ask in plain language, or invoke it directly (`/launch-frame`, or
`/launch-frame:launch-frame` when installed as a plugin):

- "Prepare Google Play phone and TV screenshots for 1.2.0."
- "Make App Store screenshots for iPhone and iPad, go straight to production."
- "Validate the assets in store-assets/release-2.0.0."
- "Upload the Fire TV screenshots from the 1.0.0 release to the Amazon console and save."

The skill infers the target stores from the project when it can, and asks once when it can't. It
offers design directions for the first three shots unless you ask it to go straight to production.

## Output

```
store-assets/release-<version>/
├── README.md               status, what's where, re-render commands
├── release.json            selected targets
├── project-profile.md      app purpose, audience, evidenced features
├── capability-report.md    supported targets with evidence and selection decisions
├── capture-plan.md         every source screenshot: screen, device, method, status
├── design-system.md        visual DNA evidence, campaign system, storyboard
├── validation-report.md
├── source-screenshots/     untouched captures + captures.json (provenance)
├── working/                editable HTML/CSS compositions, fonts
├── previews/               contact-sheet.png, store-scale.png, thumbnails/
└── google-play/ | apple-app-store/ | amazon-appstore/
    ├── README.md           upload location, order, alt text, status
    └── <device>/01.png …
```

Only selected stores and devices get folders.

## Scripts

All in `skills/launch-frame/scripts/`, Python, cross-platform, `--help` on each.

| Script | Does |
|---|---|
| `discover_targets.py` | Grades every device target from repo evidence. Also finds modules, package ids, variants, deep links, existing screenshot/UI-test tooling and prior releases |
| `init_release.py` | The one way to create a release folder: validates target names against the store profiles, refuses unsupported targets, adds required companions, never touches an existing release; `--out` writes outside a read-only repo |
| `check_env.py` | Reports SDKs, AVDs, simulators and devices, plus a per-target capture matrix: method, automated or not, setup needed |
| `capture_android.py` | Boots emulators, cleans the status bar, launches the app, reads the UI tree, does grounded taps and D-pad navigation, and captures at native resolution. Refuses physical devices unless allowed |
| `capture_apple.py` | Captures from Apple simulators via simctl (macOS only; exits 3 elsewhere) |
| `capture_web.py` | Captures a running web UI at an exact viewport |
| `captures.py` | Keeps the provenance manifest (auto-captured, existing or user-provided) and verifies sources stay unedited |
| `scan_brand.py` | Finds fonts, color tokens, icons and logos in a repo |
| `extract_palette.py` | Measures colors and light/dark tone from screenshots; WCAG contrast check |
| `render_html.py` | Renders HTML/CSS compositions to exact-size opaque PNG/JPEG (Playwright or headless Chrome/Edge) |
| `validate_assets.py` | Checks exports against store profiles: type, size, aspect, file size, alpha, color mode, count, order, duplicates, missing sets. Writes a report that separates errors from warnings and lists what it did not check |
| `contact_sheet.py` | Builds review sheets of every set, a store-scale sheet and per-asset thumbnails |

## Store uploads

The skill uploads only when you explicitly ask. It works through browser tools in a session where
you're already signed in, never handles passwords, and asks before replacing existing assets. It
never submits for review or publishes. It updates the platform README only with what it actually
confirmed. Without browser control, it gives you the steps instead.

## Limitations

- It needs real captures of the app and won't invent UI. If it can't run the app (no emulator, broken
  build, login or demo data needed), it says exactly what's blocking and asks for the minimum help.
- Apple capture needs macOS with Xcode. LaunchFrame has no Fire OS emulator path, so Fire TV/Fire tablet
  captures come from a real device (with your approval) or are labelled as Android captures.
- Android demo mode doesn't clean every status-bar icon on every system image; the skill checks, and
  crops the status bar when needed.
- The bundled store rules are a dated snapshot. Google doesn't publish TV screenshot dimensions, so
  1920×1080 is a default there.
- No device frame artwork is bundled (licensing); frames, if used, are simple CSS.
- No app preview video production.
- Design quality depends on the model's judgment plus its review of the rendered images. The
  validator checks the technical rules, not taste.

## Development

```
python -m unittest discover -s tests -v
LAUNCHFRAME_LIVE_SERIAL=emulator-5554 python -m unittest discover -s tests   # + live emulator test
python evals/run_evals.py --list                                             # 20 behavior scenarios
python evals/run_evals.py --scenario 06-misleading-keywords --model sonnet   # strict grading: evals/RUBRIC.md
```
Tests and evals use synthetic fixture repositories and images labelled TEST DATA. Renderer tests are
skipped when no browser is available. Physical devices are blocked during evals.

---

<sub>Maintained by RSX Develops.</sub>
