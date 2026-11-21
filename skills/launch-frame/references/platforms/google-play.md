# Google Play

Machine-readable rules: `assets/platform-profiles.json` → `google-play`. Verify against:
- https://support.google.com/googleplay/android-developer/answer/9866151 (preview assets)
- https://developer.android.com/google/play/requirements/screenshots-android-cli (large screens)
- https://developer.android.com/docs/quality-guidelines/tv-app-quality (TV quality, TV-G4)

Google TV / Android TV, Wear OS, Automotive, XR, Chromebook and tablets are **device-specific sections
of the same Google Play listing**, not separate stores.

## Targets (snapshot, checked 2026-11-20)

| Folder | Asset | Requirements | Recommended / LaunchFrame default |
|---|---|---|---|
| `phone/` | Phone screenshots | 2–8; PNG/JPEG; no alpha; ≤ 8 MB; sides 320–3840; long ≤ 2.3× short | 4+ at 1080×1920 (9:16) or 1920×1080 for promotion eligibility |
| `tablet-7-inch/` | 7" tablet | ≤ 8; PNG/JPEG; no alpha; sides 1080–7680 | 4+; 16:9 or 9:16, 1920×1080 / 1080×1920 |
| `tablet-10-inch/` | 10" tablet | as 7" | as 7" |
| `chromebook/` | Chromebook | 4–8; exactly 16:9 or 9:16; 1080–7680 | 1920×1080 or 3840×2160 |
| `foldable/` | Foldable | 3–8; 1:1 or 4:3 inner, 10:16 outer; 960–3840 | — |
| `tv/` | TV screenshots | ≥ 1 (required for TV apps); generic rules | 1920×1080 (16:9). Official TV dimensions were not stated; verify |
| `tv-banner/` | TV banner | 1280×720; PNG/JPEG; no alpha | Required for TV apps |
| `wear-os/` | Wear OS | ≥ 1; 1:1; ≥ 384×384; no alpha | Plain UI only: no frame, text, background or mask |
| `automotive/` | Automotive OS | If provided: ≥ 2 portrait 800×1280 and ≥ 2 landscape 1024×768 | Generic system UI only |
| `xr/` | Android XR | 4–8; 8:5; ≥ 1920×1200 | 3840×2400 |
| `feature-graphic/` | Feature graphic | 1024×500; PNG/JPEG; no alpha; required to publish | Centered content; avoid white/black/dark-gray ground |
| `app-icon/` | Hi-res icon | 512×512 PNG (32-bit, alpha allowed); ≤ 1024 KB | Usually already exists; only include if the release changes it |

Large-screen note: the help article gives both 1,080–7,680 px (large screens) and 3,840 px max (general).
1920×1080 / 1080×1920 satisfies both.

## Content guidance (recommendations, but follow them)

- First three screenshots should show the actual app UI and its core value.
- Text ≤ ~20% of the image; no "Best", "#1", "New", "Free", "Sale", or CTAs like "Download now".
- Clean status bars; no device-holding hands; sharp, correctly oriented images.
- Alt text ≤ 140 chars per image (entered in the console). Put proposed alt text in the platform README.
- Localize text in graphics per listing language.

## Upload location

Play Console → app → Grow (users) → Store presence → Main store listing (or Custom store listings) →
Graphics. TV/Wear/Automotive sections appear after the form factor is added under Release → Setup →
Advanced settings → Form factors. Details and boundaries: `references/upload.md`.
