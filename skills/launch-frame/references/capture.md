# Capturing authentic screenshots

## Contents
- Priority and principles
- Capture plan
- Build and launch safely
- Android (emulators first)
- Android TV, Google TV and Fire TV
- Foldables, Chromebook, Wear OS, Automotive, XR
- Apple simulators
- Web and desktop
- Navigation
- The per-screenshot loop
- Fallback when capture is blocked
- Provenance

## Priority and principles

1. The project's own screenshot/UI-test automation (Paparazzi/Roborazzi captures of real screens,
   screengrab, fastlane snapshot, Maestro, XCUITest, Playwright). Run it rather than reinventing it.
2. Emulators / simulators: reproducible sizes, clean state, no personal data.
3. Physical devices: only when the user asks, or when no virtual device can show the target (e.g. real
   Fire OS). The scripts refuse physical devices without `--allow-physical`.
4. Existing authentic screenshots in the repo, then user-provided screenshots. Register both with
   `captures.py add`. Never call them auto-captured.

Capture the raw screen at the device's native resolution. Never resize a capture and present it as
coming from another device class. Design happens later, from these raw files.

Don't install SDKs, system images or simulator runtimes, or create AVDs, without the user's approval.
Say how much it will download. Use what exists first.

## Capture plan

Write `capture-plan.md` (template: `assets/templates/capture-plan.md`) before capturing:

| # | Target | Screen / feature | How to reach it | Device | Data/state needed | Status |
|---|---|---|---|---|---|---|

Status values: planned, captured, failed (reason), skipped (reason), provided-by-user, existing.
Plan from the storyboard: capture what the headlines need, plus one or two spare screens.

## Build and launch safely

- Read the project's build docs (README, BUILD.md, CONTRIBUTING, CLAUDE.md/AGENTS.md) and use its
  scripts (`./gradlew :app:installDebug`, `npm run ios`, `flutter run`, fastlane lanes).
- Use the debug/demo variant. Never touch release signing, production credentials, or release config.
- Don't modify app source to make capture easier unless the user approves (e.g. a demo flag).
- If the app is already installed on the emulator (check with `adb shell pm list packages`), confirm
  it's current enough. Ask before reinstalling over data the user may want.
- One failed build: read the error and fix the obvious environment issue (wrong JDK, missing SDK
  platform) if it's safe. Don't loop. Report the blocker and fall back.

## Android (emulators first)

```
python ${CLAUDE_SKILL_DIR}/scripts/capture_android.py avds          # kind, size, density per AVD
python ${CLAUDE_SKILL_DIR}/scripts/capture_android.py boot <AVD>    # headless; prints the serial
python ${CLAUDE_SKILL_DIR}/scripts/capture_android.py prepare --serial <S> --orientation portrait [--theme dark]
python ${CLAUDE_SKILL_DIR}/scripts/capture_android.py launch --serial <S> --package <id> [--deeplink URL]
python ${CLAUDE_SKILL_DIR}/scripts/capture_android.py ui --serial <S>
python ${CLAUDE_SKILL_DIR}/scripts/capture_android.py tap --serial <S> --text "Library"
python ${CLAUDE_SKILL_DIR}/scripts/capture_android.py wait --serial <S> --text "Continue Watching"
python ${CLAUDE_SKILL_DIR}/scripts/capture_android.py shot --serial <S> --out <release>/source-screenshots/phone-home.png --screen home --target google-play/phone
python ${CLAUDE_SKILL_DIR}/scripts/capture_android.py restore --serial <S>
python ${CLAUDE_SKILL_DIR}/scripts/capture_android.py stop --serial <S>   # only emulators you booted
```

The Android CLI (`android`) is an alternative when installed: `android emulator create --list-profiles`,
`android emulator create medium_tablet`, `android emulator start --headless <name>`,
`android layout --flat`, `android input tap "text=Library"`, `android screen capture -o out.png`
(never `--annotate` for store captures). Official guide:
https://developer.android.com/google/play/requirements/screenshots-android-cli

Status bar: `prepare` turns on SystemUI demo mode (09:41, full battery and Wi-Fi, no notifications).
Always look at the status bar in the first capture. Some system images still show icons. If they
persist, crop the status bar off in the composition (allowed and honest) rather than painting over it.

## Android TV, Google TV and Fire TV

- TV UIs are navigated with the D-pad: `key --serial <S> down --repeat 2`, `key … center`. After each
  move, `ui` shows which element is `focused`. Capture with the intended item focused, because focus
  rings are part of the real TV look.
- A Google TV / Android TV emulator capture is an **Android TV** capture. Label it Fire TV only if it
  ran on Fire OS (Fire TV device, or a Fire OS emulator). If the UI is identical and only an Android TV
  capture exists, you may use it for Amazon, and the README must say so.
- Google's TV quality guideline asks for at least one unaltered TV screenshot. Keep one raw capture in
  the set.

## Foldables, Chromebook, Wear OS, Automotive, XR

- Foldables: Android CLI profiles `foldable_1_1` / `foldable_4_3` (emulator ≥ 37.3.10), `adb emu fold`
  / `adb emu unfold`, and `adb shell screencap -d <display-id>` (`shot --display <id>`). IDs come from
  `adb shell dumpsys SurfaceFlinger --display-id`.
- Chromebook / desktop: `android emulator create large_desktop`, started as `desktop_large`. Capture at
  1920×1080 or 3840×2160.
- Wear OS: Wear emulator; deliver square, unframed, with no added text.
- Automotive: the generic Automotive emulator profiles (1024p landscape and portrait), 2+ of each.
- XR: Android XR emulator where available. Otherwise mark it blocked.

## Apple simulators

macOS with Xcode only. `capture_apple.py` exits with code 3 elsewhere. Report that, and offer
alternatives (a Mac/CI run of the project's UI tests, existing captures, or user captures).

```
python ${CLAUDE_SKILL_DIR}/scripts/capture_apple.py devices
python ${CLAUDE_SKILL_DIR}/scripts/capture_apple.py boot --udid <U>
python ${CLAUDE_SKILL_DIR}/scripts/capture_apple.py prepare --udid <U> [--appearance dark]
python ${CLAUDE_SKILL_DIR}/scripts/capture_apple.py launch --udid <U> --bundle <id>     # or --url myapp://route
python ${CLAUDE_SKILL_DIR}/scripts/capture_apple.py shot --udid <U> --out <release>/source-screenshots/iphone-home.png --screen home
```

simctl cannot tap. Navigate with deep links, the project's XCUITests / fastlane snapshot, or launch
arguments the app already supports. Pick simulators whose native size matches the store class (e.g.
a 6.9" iPhone for 1320×2868, a 13" iPad for 2064×2752, Apple TV 4K for 3840×2160).

## Web and desktop

- Web: run the project's dev server (its own script), then
  `capture_web.py <url> --viewport 1440x900 --out … --screen … --wait-for "text=Library"`. Choose
  viewports from the project's breakpoints (Tailwind config, CSS media queries).
- Desktop: run the app with its own command and capture the window with OS tools or the app's UI-test
  harness. Register the result with `captures.py add --provenance existing` and a note saying how it
  was taken. Don't call it auto-captured unless a script did it.

## Navigation

Use the most reliable method available:
1. Existing UI tests / screenshot tests that already reach the screen.
2. Deep links from the capability report (`launch --deeplink`).
3. Debug/demo entry points the app already has.
4. Accessibility-grounded taps: `ui` → `tap --text/--desc/--id`. The script resolves labels to their
   clickable container and refuses ambiguous matches.
5. D-pad/key navigation for TV, checking `focused` after each step.
6. Raw coordinates only from bounds that `ui` just reported, never guessed.

## The per-screenshot loop

1. Navigate. 2. `wait` for an element that proves the right screen. 3. Dismiss transient UI (toasts,
keyboards, permission prompts) through the UI, not by force-stopping. 4. `shot`. 5. **Open the
image and look at it**: right screen, loaded, honest data, nothing private, status bar clean. 6. If
wrong, fix and recapture; don't edit pixels.

Handle first-run onboarding, permissions and empty states through normal UI. If the app needs a server,
account or media to look meaningful, stop and ask for safe demo data or a test account. Never use the
user's personal accounts or production data without consent, and never capture an empty state as if
it were the product.

## Fallback when capture is blocked

1. Name the blocker exactly (no AVD for TV, build fails with X, login required, not macOS).
2. Look for existing authentic screenshots, only in relevant places (the capability report's
   screenshot folders, fastlane metadata, docs/design folders, previous releases).
3. Judge them: resolution, recency against current UI, privacy, consistency.
4. Ask for the minimum: "Two phone captures exist; I need the Downloads and Search screens. Can you
   capture them, or allow me to use the connected tablet?"
5. Continue with the targets that work, and report partial success plainly.

## Provenance

Every file in `source-screenshots/` must be registered in `captures.json` (`shot` does this; use
`captures.py add` for existing/user files). `captures.py verify` flags edited or unregistered sources.
READMEs state provenance per screenshot.
