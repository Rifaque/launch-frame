# Discovery: what the app supports, and what this machine can capture

## Contents
- Run order
- Evidence model
- Reading the capability report
- Confirming Probable targets
- Choosing targets with the user
- Prior releases and existing assets

## Run order

```
python ${CLAUDE_SKILL_DIR}/scripts/discover_targets.py <repo>          # read-only, prints the report
python ${CLAUDE_SKILL_DIR}/scripts/check_env.py                        # read-only environment report
# after choosing targets (init_release.py saves capability-report.md + working/capability.json):
python ${CLAUDE_SKILL_DIR}/scripts/check_env.py --capability <release>/working/capability.json --markdown <release>/working/environment.md
```

Discovery and the environment check never write into the repo unless given an output path. Then read the files they cite (manifest, Gradle, Xcode settings, navigation code)
before relying on a row. Scripts find candidates; you confirm them.

## Evidence model

| Strength | Meaning | Examples |
|---|---|---|
| strong | The app's own build/manifest declares it | LAUNCHER / LEANBACK_LAUNCHER activity in an application module; `uses-feature …type.watch required=true`; `TARGETED_DEVICE_FAMILY` contains 2; `SDKROOT = appletvos`; `layout-sw600dp/`; Expo `supportsTablet: true`; Compose Desktop `application {}` |
| medium | Real code or config for the form factor, but not a declaration | width-adaptive layout code; an app form-factor enum with `TABLET`/`TV`; `uses-feature leanback required=false`; TV banner attribute |
| weak | Keywords only | a dependency on `androidx.tv` in a library module; docs/README mentions; `Package.swift` platforms |
| negative | Explicit exclusion | `leanback required=true` (TV-only → no phone/tablet); `supports-screens largeScreens=false`; `TARGETED_DEVICE_FAMILY = 1` (no iPad); `supportsTablet: false` |
| derived | Inferred from other rows | Fire TV = TV app + Amazon distribution evidence |

Statuses: **Confirmed** (any strong, no negative), **Probable** (medium only, or derived), **Unknown**
(weak or nothing), **Unsupported** (any negative). A keyword never confirms a target. A library module
never confirms a target; only application modules count. Marketing/docs websites (`website/`, `docs/`,
`landing/`) are not web-app targets.

Specific judgments:
- **Tablet**: every phone app installs on tablets, but a tablet *store set* needs a layout that works on
  tablets. Confirmed by large-screen resources or declarations; Probable by adaptive code. Look at a
  runtime capture before producing a tablet set.
- **Fire TV / Fire Tablet**: Fire OS runs Android apps. Technical support follows the Android TV/tablet
  row; distribution intent (Amazon flavor, Amazon release docs, `amazon.hardware.fire_tv`) decides
  whether it's a release target.
- **Chromebook**: Probable at most unless `android.hardware.type.pc` is declared; it needs a keyboard/
  mouse-friendly layout check at runtime.
- **Desktop / web**: no bundled store profile; they're "other platforms" with a custom profile.

## Reading the capability report

The report also lists app modules, package/bundle ids, build variants, launch activities, deep links,
existing screenshot/UI-test tooling (Paparazzi, Roborazzi, screengrab, fastlane snapshot, Maestro,
XCUITest, Playwright), existing screenshot folders, prior `store-assets/` releases, and capture
considerations (login screens). Use all of these for the capture plan.

`init_release.py` saves the report as `capability-report.md` in the new release folder. Append a
short "Decisions" section to it: what you selected, what you skipped and why.

## Confirming Probable targets

Prefer a runtime check: boot the matching emulator, launch the app, capture one screen, and look at
it. A layout that is just a stretched phone UI is not a tablet set. Record the result (Confirmed at
runtime / Rejected at runtime) in the Decisions section. If runtime is impossible, ask the user only
when the target materially changes the release.

## Choosing targets with the user

- Propose targets from Confirmed rows (plus runtime-confirmed Probable rows), mapped to store sets.
- "All supported platforms" means every Confirmed row's store sets for the stores the project
  distributes to (store intent in docs, Amazon flavor, existing listings). Don't ask the user to list
  them.
- Never create folders or AVDs for Unknown or Unsupported targets. Say briefly why they were skipped.
- Ask once, naturally, only when a genuinely ambiguous choice changes the release (e.g. "TV is
  supported. Should this release include the Google TV listing?").

## Prior releases and existing assets

If `store-assets/release-*` exists: read its README and design-system.md first. Reuse the campaign
system when the user wants continuity. Never write into a prior release folder. Create a new folder
for the new version, and ask before overwriting if the same version folder already exists.
