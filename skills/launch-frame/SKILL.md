---
name: launch-frame
description: Designs and produces store-ready app screenshots and listing graphics from an app's real UI. Discovers which targets the repo actually supports (phone, tablet, foldable, Chromebook, Android TV/Google TV, Wear OS, Automotive, XR, Fire TV/Fire Tablet, iPhone, iPad, Apple TV, Watch, Vision Pro, Mac), checks available emulators/simulators/devices, captures authentic screenshots automatically, and turns them into brand-matched compositions for Google Play, the Apple App Store and the Amazon Appstore. Validates exports against current store specs, builds an in-repo release folder with per-store upload READMEs, and uploads only when explicitly asked. Use it for ANY task about Play Store, App Store or Amazon Appstore screenshots, listing graphics, feature graphics, TV banners or store release assets, including planning-only requests, visual direction, capture, validation and uploads. Its scripts enforce target, provenance and safety checks that ad-hoc work skips.
---

# LaunchFrame

You act as design director, capture operator, technical validator and release assistant for a real
app. The output is a release folder inside the app's repository that someone can upload from without
asking you anything. Raw captures are source material. The deliverables are designed compositions.

## Non-negotiables

1. **Evidence before assumptions.** Targets come from repository and runtime evidence, never from
   keywords alone or from what stores offer. Skip unsupported targets and say why.
2. **Real UI only.** Every UI pixel comes from a genuine capture (auto-captured, existing, or
   user-provided, recorded in `captures.json`). Never generate, redraw, recolor or stretch UI, or edit
   its text, numbers or icons.
3. **No invented features or claims.** Every headline must be provable from code or a capture.
4. **The app's identity drives the design.** Derive color, type and shape from evidence. No generic
   LaunchFrame look, no default purple gradients, glass, glow, blobs, or one layout repeated.
5. **Specs are perishable.** `assets/platform-profiles.json` is a dated snapshot. Re-check official
   sources each release. Label ambiguities and LaunchFrame defaults as such.
6. **Safe by default.** Emulators before physical devices. No SDK/system-image downloads, app-source
   edits, signing/config changes, or overwriting prior releases without approval. Restore device state.
7. **Never pretend.** No claimed capture, visual review, validation, save or upload that didn't happen.
   README statuses match reality.
8. **No LaunchFrame or RSX branding** in generated assets unless the app itself carries it.

## Workflow

Pick the mode: **full release** (default), **partial set**, **validate only** (step 10), or
**upload** ([references/upload.md](references/upload.md)). With "go straight to production", skip optional
checkpoints, state assumptions, and continue. Other skills (e.g. a platform build skill) may be active.
Use them for building and running; LaunchFrame owns the store assets.

All scripts live in `${CLAUDE_SKILL_DIR}/scripts/` and are **run**, not read (`--help` on each).
References are **read** when their step comes up.

### 1. Discover the project → `capability-report.md`, `project-profile.md`
- `python ${CLAUDE_SKILL_DIR}/scripts/discover_targets.py <repo>` (read-only; prints the report).
- Read what it cites (manifests, Gradle, Xcode settings, navigation, README/build docs) and record app
  purpose, audience and evidenced features ([template](assets/templates/project-profile.md)).
  Evidence rules and edge cases: [references/discovery.md](references/discovery.md).

### 2. Discover the environment
- `python ${CLAUDE_SKILL_DIR}/scripts/check_env.py` lists SDKs, AVDs, simulators and devices.
  After step 3, add `--capability <release>/working/capability.json` for the per-target capture matrix.

### 3. Select targets → create the release folder (one command)
- Choose Confirmed targets (and Probable ones you confirmed at runtime). "All supported platforms" means
  all of those for the stores the project distributes to. Don't make the user enumerate them. Ask once
  only if an ambiguous choice changes the release.
- Create the folder **only** with:
  `python ${CLAUDE_SKILL_DIR}/scripts/init_release.py <repo> --release 1.0.0 --targets google-play/phone,google-play/tv [--reuse google-play/feature-graphic="current listing graphic"] [--expected google-play/phone=5]`
  It re-runs discovery, refuses unknown keys and unsupported targets, adds required companions (or
  records `--reuse`), never touches an existing release, and writes `release.json`,
  `capability-report.md` and `working/capability.json`. If it refuses, fix the input; don't make
  folders by hand.
- Valid keys: `google-play/phone`, `google-play/tv`, `google-play/tablet-10-inch`, `amazon-appstore/fire-tv`,
  `amazon-appstore/fire-tablet`, `apple-app-store/iphone` (full list: `validate_assets.py --list-targets`).
  Invalid (invented): `google-play/android-tv`, `amazon-appstore/phone`, `apple-tv/screenshots`.
- Per-store notes: [Google Play](references/platforms/google-play.md), [Apple](references/platforms/apple-app-store.md),
  [Amazon](references/platforms/amazon-appstore.md), [other stores](references/platforms/other-stores.md).

### 4. Verify current specs
- Open each selected platform's `sources` URLs. If anything differs, write
  `working/profiles-override.json` (same schema) and pass `--profiles` to the validator. Tell the user so
  the bundled profile can be updated. Offline: mark specs "unverified since <checked date>".

### 5. Story first
- Rank evidenced features and draft the storyboard (which screen proves which headline; shots 1–3
  carry the listing). Read [references/copywriting.md](references/copywriting.md).
- Never storyboard empty, login, onboarding, loading or error states as store shots, not even as
  "candidates", unless the user asks or that state is the product's distinctive feature.

### 6. Capture → `capture-plan.md`, `source-screenshots/`
- Plan every capture ([template](assets/templates/capture-plan.md)), then capture with the best available
  method: the project's own screenshot automation, then emulators/simulators (`capture_android.py`,
  `capture_apple.py`, `capture_web.py`), then devices with approval, then existing or user captures
  (`captures.py add`). Navigate with deep links or UI-tree-grounded taps, never guessed coordinates.
  Open every capture and check it. Details, fallbacks and safety: [references/capture.md](references/capture.md).
- What makes a source usable: [references/source-screenshots.md](references/source-screenshots.md).
  If the app can't look meaningful without demo data or an account, stop and arrange it.

### 7. Visual DNA → `design-system.md`
- `scan_brand.py <repo>` (fonts, tokens, icons) and `extract_palette.py source-screenshots/*.png`.
  Confirm roles in code. Use the real font if licensed. Method: [references/visual-dna.md](references/visual-dna.md);
  [template](assets/templates/design-system.md).

### 8. Direction and compositions → `working/`, final folders
- Read [references/design-direction.md](references/design-direction.md). Unless told to go straight to
  production, render shots 1–3 in two genuinely different directions to `previews/`, show them, and
  recommend one.
- Compose each shot individually in HTML/CSS ([references/production.md](references/production.md);
  [starter](assets/templates/composition-starter.html); optional [device frames](assets/templates/device-frames.css)), then
  `render_html.py "working/<platform>/<target>/*.html" --outdir <platform>/<target> --size WxH`.
  Final names `01.png …` in upload order.

### 9. Review loop (mandatory)
- `contact_sheet.py <release>` and `contact_sheet.py <release> --thumb-height 180 --out <release>/previews/store-scale.png --thumbnails <release>/previews/thumbnails`.
- Look at the sheets and every full-size image, log problems in design-system.md, fix, re-render, look
  again. At least one full cycle. Checklist: [references/quality-gate.md](references/quality-gate.md).

### 10. Validate
- `validate_assets.py <release> --report <release>/validation-report.md` (errors = requirements,
  warnings = recommendations/companions/expected counts, info). `captures.py verify --dir <release>/source-screenshots`.
  Fix errors. Explain remaining warnings.

### 11. Handoff READMEs and the final gate
- Root README ([template](assets/templates/release-README.md)) and one per platform folder
  ([template](assets/templates/platform-README.md)), written from the actual files, reports and actions.
- Before you call the release done, all of these must be true:
  1. `validate_assets.py <release> --final --report <release>/validation-report.md` exits 0 (it fails on
     spec errors, unknown targets, missing companions, edited/unregistered sources, missing READMEs,
     design notes or contact sheet).
  2. You opened every final image and the contact sheets, and the review log has at least one round.
  3. Every headline is backed by evidence in design-system.md.
  4. READMEs say "generated/validated", never "uploaded", unless an upload was actually observed.

### 12. Report, and upload only if asked
- Summarize what was produced, how sources were captured, validation and review results, assumptions,
  skipped targets, and what remains. Uploading: [references/upload.md](references/upload.md). Never submit,
  publish or delete listing assets without explicit permission.

## Release folder

```
store-assets/release-<version>/
├── README.md  release.json  validation-report.md
├── project-profile.md  capability-report.md  capture-plan.md  design-system.md
├── source-screenshots/        # raw captures + captures.json (provenance); never edited
├── working/                   # capability.json, HTML/CSS compositions, fonts, overrides
├── previews/                  # contact-sheet.png, store-scale.png, thumbnails/, direction previews
└── <platform>/README.md + <target>/01.png …   # google-play | apple-app-store | amazon-appstore | other-platforms
```

Only selected targets get folders. Never write into an existing `release-*` folder of another version.

## Scripts (Python 3.9+ and Pillow; run with `python` or `python3`)

| Script | Purpose |
|---|---|
| `discover_targets.py [repo]` | Evidence-graded target support, modules, variants, deep links, test/capture tooling |
| `init_release.py repo --release V --targets …` | The only way to create a release folder: exact keys, companions, discovery saved |
| `check_env.py [--capability json]` | SDKs, AVDs, simulators, devices; per-target capture matrix |
| `capture_android.py <cmd>` | avds, devices, boot, prepare/restore, launch, ui, tap, key, type, wait, shot |
| `capture_apple.py <cmd>` | simctl devices, boot, prepare, launch/openurl, shot (macOS only) |
| `capture_web.py url …` | Exact-viewport capture of a running web UI |
| `captures.py add/list/verify` | Provenance manifest for source screenshots |
| `scan_brand.py [repo]` | Fonts, color tokens, icons (brand evidence) |
| `extract_palette.py imgs…` / `contrast FG BG` | Measured palette and tone; WCAG contrast |
| `render_html.py html… --size WxH` | Exact-size opaque PNG/JPEG via Playwright or headless Chrome/Edge |
| `validate_assets.py release [--final]` | Store-spec + release checks; `--final` is the handoff gate; exit 1 on errors |
| `contact_sheet.py release` | Review sheets and store-scale thumbnails |

## Stop conditions

Stop the affected target and report the blocker (don't work around it) when:
- the app can't be built or launched after one attempt to fix an obvious environment issue;
- the app only shows empty, login or placeholder states and no safe demo data/account exists;
- the only way to capture is a physical device, a download, or an app-source change you weren't approved for;
- the only available sources are unverified or private-data screenshots;
- `init_release.py` or `validate_assets.py --final` fails and the fix would mean bending the rules.
Continue with targets that aren't blocked, and report partial results plainly.

## When to ask vs. proceed

Ask only for: ambiguous target choices that change the release, approvals (physical devices, downloads,
app-source changes, overwrites), demo data or test accounts you can't create safely, and anything that
saves or publishes in a store console. Otherwise decide, note it in the release docs, and continue.
