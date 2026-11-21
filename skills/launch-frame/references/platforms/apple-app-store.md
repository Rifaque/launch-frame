# Apple App Store (App Store Connect)

Machine-readable rules: `assets/platform-profiles.json` → `apple-app-store`. Verify against:
- https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications
- https://developer.apple.com/help/app-store-connect/manage-app-information/upload-app-previews-and-screenshots
- https://developer.apple.com/help/app-store-connect/reference/app-information/app-preview-specifications

Apple TV, Mac, Vision Pro and Watch assets all live in App Store Connect, under the matching platform
version of the app record.

## Global rules (snapshot, checked 2026-11-20)

- 1–10 screenshots per device size and localization; `.png`, `.jpg`, `.jpeg`.
- **No alpha channels or transparency.**
- Exact pixel sizes only (listed per class). Apple scales the largest required class down for smaller
  devices if you don't supply them.
- No published file-size limit for screenshots (the validator does not check one).

## Targets

| Folder | Class | Accepted sizes (portrait; landscape = rotated) | Notes |
|---|---|---|---|
| `iphone/` | Large iPhone (6.9"/6.7"/6.5" class) | 1320×2868, 1290×2796, 1260×2736, 1284×2778, 1242×2688 | Required if the app runs on iPhone. Default 1320×2868 |
| `iphone-6.1/` | Medium iPhone | 1206×2622, 1179×2556, 1170×2532, 1125×2436, 1080×2340 | Optional; scaled from large otherwise |
| `iphone-duo-outer/` / `iphone-duo-inner/` | iPhone Duo | 1398×2034 / 2007×2853 | Stated as required from April 2027 for iOS 27.1 SDK builds; verify |
| `ipad/` | 13" iPad | 2064×2752, 2048×2732 | Required if the app runs on iPad |
| `mac/` | Mac | 1280×800, 1440×900, 2560×1600, 2880×1800 (16:10) | Required for Mac apps |
| `apple-tv/` | Apple TV | 1920×1080, 3840×2160 | Required for tvOS apps |
| `vision-pro/` | Apple Vision Pro | 3840×2160 | Required for visionOS apps |
| `apple-watch/` | Apple Watch | 422×514, 410×502, 416×496, 396×484, 368×448, 312×390 | One size consistently across localizations |

Older iPhone/iPad classes (5.5", 4.7", 12.9", 11", 10.5", 9.7") are optional and scaled; add a profile
override only if the user needs them.

## App previews (video, optional)

Up to 3 per device size and language, 15–30 s, ≤ 500 MB, H.264/ProRes, ≤ 30 fps. LaunchFrame does not
produce video; note it as a possible next step.

## Design notes

- Apple product bezels from Apple's design resources may be used only under Apple's terms (marketing
  Apple-platform apps). A frameless or simple neutral-frame treatment avoids the question.
- Apple guidelines reject screenshots that misrepresent the app; keep UI authentic.

## Upload location

App Store Connect → Apps → app → platform version in the sidebar (choose localization top-right) →
App Previews and Screenshots → device tab (View All Sizes in Media Manager for others) → upload/drag →
reorder → Save. Editable states include Prepare for Submission, Rejected, Metadata Rejected, Developer
Rejected. Submitting for review is the user's decision. See `references/upload.md`.
