# Amazon Appstore

Machine-readable rules: `assets/platform-profiles.json` → `amazon-appstore`. Verify against:
- https://developer.amazon.com/docs/app-submission/add-store-listing-information.html#image-asset-guidelines
  (Assets section, tabs "Fire Tablet" and "Fire TV")

## Fire Tablet (snapshot, checked 2026-11-20)

| Folder | Asset | Rules |
|---|---|---|
| `fire-tablet/` | Screenshots (required) | 3–10; PNG/JPEG; landscape or portrait; one of 800×480, 1024×600, 1280×720, 1280×800, 1920×1080, 1920×1200, 2560×1600 (or rotated). No alpha rule or size limit stated; export opaque |
| `fire-tablet-icons/` | Icons (required) | 114×114 and 512×512 PNG (transparency allowed). Export each size from source; don't upscale |
| `fire-tablet-promo/` | Promotional image (optional) | 1024×500 PNG/JPEG, landscape; not a screenshot; legible at 300×146; text ≥ 50 px from edges |

Recommended screenshot size: 1920×1200 or 2560×1600 landscape (matches modern Fire tablets) unless the
captures come from a 16:9 device.

## Fire TV (Fire OS and Vega OS)

| Folder | Asset | Rules |
|---|---|---|
| `fire-tv/` | Screenshots (required) | 3–10; exactly 1920×1080; JPG or 24-bit PNG, no transparency |
| `fire-tv-icon/` | App icon (required) | 1280×720 PNG, no transparency; subject within central 882×448 |
| `fire-tv-background/` | Background (required) | 1920×1080 JPG/24-bit PNG, no transparency; subject inside 1214×830, preferably right; no logos or titles |

If required Fire TV assets are missing, Fire TV applies a default scaled treatment — avoid that.
Feature Rotator art is an advertising placement, not a listing asset.

Google Play TV and Fire TV screenshots are both 1920×1080: one design can serve both, but export into
both folders and validate each set separately. Fire TV UI should be captured on Fire TV (or the
interface verified identical) — say which in the README.

## Upload location

Amazon Developer Console → Apps & Games → the app → store listing for the language → assets/images
section with "Fire Tablet" and "Fire TV" tabs. Save. Submission (and the release date setting) is the
user's decision. See `references/upload.md`.
