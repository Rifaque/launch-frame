# Production

## Contents
- Choosing a rendering approach
- HTML/CSS compositions (recommended)
- Exporting
- Pillow and SVG alternatives
- Generated imagery
- Working files

## Choosing a rendering approach

| Approach | Use when | Notes |
|---|---|---|
| HTML/CSS + `render_html.py` | Default. Real typography, web fonts, precise layout | Needs Playwright or Chrome/Edge/Chromium |
| Pillow script | No browser available; simple compositions | Weaker text layout; set fonts by file path |
| SVG | Editable vector source wanted (Figma/Illustrator) | Render via the browser (wrap in HTML) for consistent fonts |
| Image generation tool | Backgrounds/textures only | Never UI, never text |

Use whatever the environment supports; don't install heavy tooling without telling the user.

## HTML/CSS compositions

Start from `assets/templates/composition-starter.html`. It only sets up mechanics: exact canvas,
tokens, local fonts, and a non-distorting screenshot element. Design each shot yourself.

Mechanics that matter:
- `html, body { width: Wpx; height: Hpx; margin: 0; overflow: hidden; }` — the canvas **is** the viewport.
- Use absolute pixel units on a fixed canvas (or CSS variables derived from the canvas size). Avoid
  viewport-relative tricks that change with zoom.
- Screenshots: `<img>` with only `width` *or* `height` set (the other `auto`), or `object-fit: cover`
  inside a box for an intentional crop. Never set both width and height on an `<img>` without
  `object-fit` — that distorts.
- Reference images with paths relative to the HTML file (`../../../source-screenshots/home.png`).
- Fonts: `@font-face { font-family: "AppFont"; src: url("../../fonts/AppFont-Bold.ttf"); font-weight: 700; }`.
  Keep font files in `working/fonts/` with their license. The renderer waits for fonts to load.
- Device corners: if you mask a capture with `border-radius`, match the device's real corner radius
  roughly (≈ 5–6% of screen width on modern phones). No mask is also fine.
- Shadows: only if the app's own UI uses elevation, and keep them soft and subtle.
- Text: use `text-wrap: balance` for headlines; set explicit `line-height`; check no line has a single
  orphan word.
- Keep a consistent safe margin (≈ 6–8% of the short side on phones; ~5% title-safe on TV).

Render:
```
python ${CLAUDE_SKILL_DIR}/scripts/render_html.py "working/google-play/phone/*.html" --outdir google-play/phone --size 1080x1920
```
One render call per target size. Each HTML file name (`01.html`) becomes the export name (`01.png`).

## Exporting

- Exact pixel size per target (see `platform-profiles.json`). The renderer refuses mismatched sizes.
- Opaque RGB. The renderer flattens alpha; store icons that allow alpha are the exception.
- PNG by default. Use `--format jpeg --quality 90-95` only if a file exceeds a size limit (Google Play: 8 MB)
  or the user prefers JPEG.
- sRGB. If source captures are Display P3 (iOS), browsers convert to sRGB; this is normal.
- One size per device set (don't mix 1320×2868 and 1290×2796 in one iPhone folder).
- Reuse across stores only when sizes and rules genuinely match (e.g. Google Play TV 1920×1080 and Fire TV
  1920×1080 can share a design but should be separate files in each folder; verify each set separately).

## Pillow alternative

When no browser is available, write a small script in `working/` that opens the capture, scales it
uniformly with `Image.LANCZOS`, pastes it onto an RGB canvas, and draws text with `ImageFont.truetype`
using the app's font file. Keep the script in `working/` as the editable source.

## Generated imagery

Allowed for backgrounds and atmosphere. Generate at or above canvas size, without text, without UI,
consistent across the set. Save the prompts and outputs in `working/generated/` and list them in
design-system.md.

## Working files

`working/<platform>/<target>/NN.html` per shot, plus shared CSS (`working/campaign.css`), fonts,
backgrounds and crops. Final folders contain only final images and the README. Remove scratch renders
and failed experiments from final folders before delivery (keep useful explorations in `previews/`).
