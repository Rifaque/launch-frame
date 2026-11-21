# Design direction and composition

## Contents
- Campaign system vs. per-shot composition
- Matching the app's theme
- Composition vocabulary
- Device classes (phone, tablet, TV, watch, desktop, XR)
- Feature graphic, TV banner, Fire TV art
- Anti-generic checklist
- Presenting directions

## Campaign system vs. per-shot composition

Hold constant across the set (the *system*):
- Background family (one ground color or a tight range; one texture/image family if any).
- Headline typeface, weight, size scale and case.
- One emphasis device (e.g. accent color on a key word, an underline, a weight change) — not several.
- Margins and safe areas.
- Device treatment (frameless crop, a flat generic bezel, or none) — pick one.
- At most one graphic motif, derived from the app (a shape from its UI, its icon geometry, a grid).

Vary per shot (the *composition*):
- Where the UI sits (centered, offset, bleeding off an edge, split).
- Scale (full screen vs. a cropped detail that proves one feature).
- How many UI pieces (one screen, two related screens, a screen plus an extracted element).
- Headline position (top, bottom, side on landscape) and length.
- What is biggest: the UI, a detail, or the words.

Neighbors should not look like copies. Read the contact sheet left to right: if three in a row share
the same skeleton, change at least one.

## Matching the app's theme

| App character | Tends to suit | Watch out for |
|---|---|---|
| Dark media / cinema | Deep grounds from the app's own surface color, artwork-led crops, restrained type | Every shot near-black with one neon accent |
| Light productivity | Bright or paper grounds, structured grid, crisp headline | Over-decoration; pastel gradients by default |
| Playful / consumer | Bolder type, app's own shapes as motifs, more color from its palette | Random blobs, emoji spam |
| Finance / health | Calm grounds, high legibility, data-forward crops | Invented numbers, fear/guarantee claims |
| Minimal / utility | Lots of space, one clear idea per shot | Burying a simple UI under effects |
| Games | Real gameplay, in-game art as background | Fake renders presented as gameplay |

Dark backgrounds are not automatic for dark apps; light backgrounds are not automatic for light apps.
Decide from the brand evidence and how the UI reads against the ground.

## Composition vocabulary (mix, don't template)

- **Full-bleed screen**: the capture fills most of the canvas, headline in a band. Strong for shot 1
  when the main screen is self-explanatory.
- **Detail crop**: a large crop of one region (a control, a card, a chart) that proves the headline.
  Keep it unaltered and sharp — never upscale beyond ~1.25×.
- **Pair**: two related screens (before/after, list/detail) at different scales or offsets.
- **Offset bleed**: the screen runs off one edge, leaving room for a longer headline.
- **Element lift**: one genuine UI element shown larger beside its screen. Only if the element is
  cropped from a real capture, not redrawn. End the base screen's crop before that element so it
  doesn't appear twice — a visible duplicate reads as a rendering glitch.
- **Typographic lead**: words dominate, UI is smaller but still readable — use sparingly (at most once).
- **Landscape split** (tablet/TV/desktop): text column + UI, or UI full-bleed with a lower-third headline.
- **Layered screens**: two or three real screens overlapping at different depths, each still readable;
  good for "one library, many sources" or flow stories. Keep overlap off the content that proves the point.
- **Cross-device**: phone + TV (or tablet) together when multi-device support *is* the feature, and
  both captures are real.

Crops must never slice text mid-line or mid-word; widen the crop or end it on a whole block.

## Device treatment

Decide per shot, and record why. Options, from least to most decorated:

| Treatment | Use when | Avoid when |
|---|---|---|
| Direct UI (frameless, maybe rounded mask) | The UI is the story; most shots | — |
| Cropped detail | One control/card proves the headline | Crop would slice text |
| Flat device frame (`assets/templates/device-frames.css`) | Form factor matters (TV/tablet/laptop context), or the brand is hardware-adjacent | Every shot; Wear OS (frames not allowed) |
| Floating / tilted device (≤ ~12°, `.lf-tilt-*`) | Once per set for depth when it adds meaning | Text becomes hard to read; more than ~2 shots |
| Multiple devices | Cross-device continuity is a real feature | The devices show different, unrelated UI |

Rules: frames are generic and license-free (don't imitate Apple/Google hardware; Apple's own bezels
are only for Apple-platform marketing under Apple's terms). No device-holding hands on Google Play.
No device mockups in the Google Play feature graphic. No frames, text or backgrounds on Wear OS
screenshots. A device must never cover or distort the UI it holds.

## Per-image spec

For every image, the storyboard records: feature, headline, supporting line, raw source file,
composition, background, typography, device treatment, target size, and the reason for each effect.

## Device classes

- **Phone portrait (9:16 or taller)**: headline in top ~20–25%; keep text ≥ ~4.5% of canvas height
  for primary lines so it survives the small store thumbnail.
- **Tablet / Chromebook (16:9 or 9:16, 4:3 on iPad)**: use the width — side-by-side text and UI, or
  multi-pane captures. Don't just center a phone layout on a wide canvas.
- **TV (16:9, 10-foot UI)**: TV screenshots are viewed on a TV. Prefer near-full-bleed real TV UI with a
  short lower-third or upper-left headline; keep inside a ~5% title-safe margin. Google's TV-G4 asks for
  at least one unaltered screenshot — make one shot pure capture.
- **Watch**: Wear OS screenshots must be plain app UI, 1:1, no frame/text/background. Apple Watch
  screenshots are plain captures at the exact watch size.
- **Desktop (Mac)**: real window captures; a neutral desktop-like ground is fine, avoid fake menu bars.
- **XR / Vision Pro**: real captures of the spatial UI; landscape.

## Feature graphic, TV banner, Fire TV art

- **Google Play feature graphic (1024×500)**: one idea, brand-led. Keep important content in the center
  and away from edges (it is cropped in places). Avoid pure white/black/dark-gray grounds, device mockups
  and store badges. App name and a short line, or a strong crop of signature UI/art.
- **Google Play TV banner (1280×720)**: app name/logo large and legible from a distance; no small text.
- **Amazon Fire TV icon (1280×720)**: subject within the central 882×448 safe zone.
- **Amazon Fire TV background (1920×1080)**: atmospheric, subject on the right within 1214×830, no
  logos or titles.
- **Amazon promotional image (1024×500)**: not a screenshot; legible at 300×146; text ≥ 50 px from edges.

## Anti-generic checklist

Every effect needs a reason you can state in one line in design-system.md ("the app's player uses a
blurred-artwork backdrop, so shot 3 does too"). Reject by default:
- Purple/blue gradients, mesh gradients, glow, neon edges, glassmorphism.
- Floating 3D phones, perspective tilts, drop shadows on everything.
- Random blobs, confetti, sparkles, abstract swooshes.
- More than one emphasis style per headline.
- Rounded-rectangle frames around everything.
- Identical layouts with the screenshot swapped.
- Generic slogans that could describe any app.

## Presenting directions

When showing options, make them differ in idea, not just color. For each direction give: name, one-line
concept, why it fits the evidence, and the risk. Recommend one. Render shots 1–3 per direction; do not
render the full set until a direction is chosen (unless the user asked for direct production).

## Image generation

Generated imagery may provide backgrounds, textures or atmosphere when it fits the brand. It must never
depict app UI, and it must not contain text. Note in design-system.md which elements are generated.
