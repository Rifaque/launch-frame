# Store upload assistance

Only when the user explicitly asks to upload or finish listing work. Screenshot production never
implies permission to touch a store console.

## Boundaries

Allowed when requested: navigating the console, uploading the generated assets into the matching
device sections, reordering them, filling alt text, viewing previews, and saving the listing draft
(only if saving was within the request — ask if unclear).

Never without explicit, specific permission: submitting for review, publishing or rolling out a
release, sending changes for review on Google Play, deleting existing screenshots or graphics,
changing pricing, availability, content rating, or anything outside the store listing graphics.
If an action would replace existing assets, list what will be removed and ask first.

## Procedure

1. Confirm store, app, listing language(s), and scope (upload only / upload and save).
2. Read the release `README.md` and the platform `README.md`; re-run `validate_assets.py` for the
   targets you will upload. Don't upload a failing set.
3. Open the console with the available browser tools (e.g. Claude in Chrome). The user must already be
   signed in; never ask for or type passwords, 2FA codes, or recovery codes. If a sign-in page appears,
   stop and ask the user to sign in.
4. Navigate to the app and listing section (paths in the platform reference files). Take a screenshot or
   read the page to confirm you are in the right app and locale before changing anything.
5. Upload each set into its device section, in order 01, 02, 03 …. Use the browser tool's file-upload
   capability with absolute paths to the exported files.
6. Arrange order to match the README; add alt text if the store supports it.
7. Inspect the console's preview of every uploaded set; check count, order and crop.
8. Save only if in scope. Then reload the page and confirm the assets persisted.
9. Update the platform README status (`uploaded`, then `verified` after the reload check), with date and
   what was done. Record anything you could not do.
10. Report: what was uploaded where, what was saved, what remains (e.g. "Send for review" is for the user).

## When browser control is unavailable

Say so plainly. Give the user step-by-step instructions from the platform README (section, buttons,
file order). Never claim an upload happened.

## Console locations (verify; consoles change)

- **Google Play Console**: app → Grow (users) → Store presence → Main store listing (or a custom store
  listing) → Graphics: App icon, Feature graphic, Phone / 7-inch tablet / 10-inch tablet / Chromebook /
  Android XR screenshots. TV, Wear OS and Automotive screenshots and the TV banner appear only after the
  form factor is added (Release → Setup → Advanced settings → Form factors) — that is a release-config
  change, so ask before adding a form factor. Saved listing changes go live through Publishing overview /
  review — leave sending for review to the user.
- **App Store Connect**: Apps → app → platform version (iOS/macOS/tvOS/visionOS) in the sidebar →
  Product Page Information / App Previews and Screenshots → device tab (View All Sizes in Media Manager
  for others) → upload or drag files → reorder → Save. Uploading is allowed while the version is in an
  editable state (e.g. Prepare for Submission). Submitting for review is the user's call.
- **Amazon Developer Console**: Apps & Games → app → Appstore Details / store listing for the language →
  Images & Multimedia (assets): Fire Tablet tab (icons, screenshots, promotional image) and Fire TV tab
  (icon, screenshots, background). Save. Submission is separate.
