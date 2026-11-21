# Visual DNA

Establish what the app actually looks like before designing anything around it. The marketing set
should feel like it was made by the app's own design team.

## Evidence, in priority order

1. **Design tokens and theme code** — Compose `Color.kt`/`Theme.kt`/`Type.kt`, `res/values/colors.xml`,
   `themes.xml`, SwiftUI `Color`/asset-catalog `.colorset`, Flutter `ThemeData`, Tailwind config, CSS
   custom properties, design-token JSON.
2. **Typography definitions** — font families, weights, sizes, letter-spacing, line-height.
3. **Bundled font files** (`res/font`, `assets/fonts`, `public/fonts`, `.xcassets`/Info.plist `UIAppFonts`).
4. **Icons, logos, wordmarks, illustrations** in the repo.
5. **Real screenshots** of the running app (measure them; code can disagree with what ships).
6. **Website and brand docs** (brand README, style guides, existing store listing).
7. **User-provided references** — borrow hierarchy and density only, never another brand's palette or type.

`scan_brand.py` surfaces candidates for 1–4 and platform hints. `extract_palette.py` measures 5.
Always open the files it points to: a hex value in a theme file can be unused, and the dominant
color on screen may come from content (artwork, photos) rather than the brand.

## What to document (design-system.md)

| Area | Record |
|---|---|
| Color | Primary, secondary, accent(s), background, surface(s), on-colors, semantic colors; hex + where defined + where seen |
| Theme | Light, dark, or both; which one ships by default; what each screen uses |
| Typography | Exact families, weights used, heading/body scale, case, tracking, numerals |
| Shape | Corner radii (cards, buttons, sheets), stroke weights, pill vs. square |
| Cards & surfaces | Fill vs. outline, borders, elevation/shadow style (or none) |
| Spacing & density | Tight/airy, grid, typical margins |
| Iconography | Outline/filled, stroke weight, rounded/sharp, icon set (Material Symbols, SF Symbols, custom) |
| Imagery | Photography, poster art, illustration, data viz, none |
| Motion cues | Only if they shape static design (e.g. a signature transition or gradient sweep) |
| Personality | 3–5 adjectives backed by observations, not wishes |
| Signatures | 2–4 elements unique to this app (a specific control, chart, card, color pairing) |
| Avoid | Things that would feel off-brand for this app |

Cite evidence for each item (`file:line` or screenshot name). Mark guesses as guesses.

## Fonts

1. If the app bundles or loads a font, use that exact family for headlines unless it is unsuitable for
   display sizes; then use the app's own heavier weight or its documented companion face.
2. Check the license before using it in marketing images. Fonts under SIL OFL, Apache 2.0 or Ubuntu
   Font License permit this. Platform/system fonts carry their own terms: SF Pro is licensed for
   designing for Apple platforms; Roboto is Apache 2.0; check the current license of Google's brand
   fonts (Google Sans family) before using them. When the terms are unclear, ask the user.
3. Load fonts locally with `@font-face` from the repo or a downloaded copy kept in `working/fonts/`.
   Record the source and license in design-system.md.
4. If the real font is unavailable, choose a substitute by matching characteristics: classification
   (geometric/grotesque/humanist sans, transitional/didone serif, slab, mono), x-height, width,
   terminal shape, contrast, and weight range. State the reasoning. Do not default to whichever font is
   popular.

## Color decisions for marketing

- The campaign palette is a subset of the app palette, plus at most one derived tint/shade.
- Background choices follow the app's dominant theme *and* the store context: a dark app often reads
  well on deep grounds, but test a light or mid-tone ground if the brand has one; a light app should
  rarely be shown on near-black.
- Check headline contrast: `extract_palette.py contrast "#FFFFFF" "#0E1A2B"`. Aim for ≥ 4.5:1; large
  display text ≥ 3:1 is the floor.
- Google Play feature graphics should avoid pure white, black or dark-gray grounds.

## Typical mistakes

- Treating poster/album/photo content colors as brand colors.
- Picking a font "close enough" without checking the code.
- Using the same accent color for every headline highlight plus every decorative element.
- Copying a reference app's palette because the user said they liked its screenshots.
