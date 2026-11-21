# Release quality gate

Answer each item by looking at the actual exported files (contact sheets and full-size images), not
from memory of what you intended. Record failures and fixes; anything unresolved goes into the README's
"Known limitations".

## Review loop (mandatory)

1. Render the set. Build `previews/contact-sheet.png` and the store-scale sheet
   (`contact_sheet.py <release> --thumb-height 180 --out previews/store-scale.png --thumbnails previews/thumbnails`).
2. Open the sheets, then every image at full size. Write a critique in design-system.md under
   "Review log": one line per problem (shot, problem, fix). Look for: clipped or orphaned headlines,
   unreadable text at store scale, sliced UI text, duplicated elements, distortion, misalignment,
   uneven margins, weak hierarchy, repeated skeletons, unjustified decoration, poor contrast, device
   frames covering UI, the set not reading as one campaign.
3. Fix the compositions, re-render, and look again. At least one full cycle is required, and repeat
   while real problems remain.
4. If you cannot view images in this environment, say so in the README and the report. Never claim a
   visual review that didn't happen.

## Design
- [ ] Looks professionally designed: deliberate hierarchy, aligned edges, consistent margins.
- [ ] Clearly this app's brand: palette, type and shape come from design-system.md evidence.
- [ ] Nothing reads as default AI styling (see design-direction.md anti-generic checklist).
- [ ] Enough whitespace; nothing crowded against edges or safe areas.
- [ ] Typography is excellent: correct font, no orphans, balanced lines, consistent scale.
- [ ] Headlines readable at store-scale (`previews/store-scale.png`).
- [ ] Shot 1 communicates the core promise on its own.
- [ ] Set is cohesive with headlines hidden (same system).
- [ ] Each shot has its own composition; no two neighbors share a skeleton.
- [ ] Every effect/decoration has a stated reason.
- [ ] The real UI is the hero in every screenshot.
- [ ] No crop slices text mid-line; no UI element appears twice by accident.

## Authenticity
- [ ] Every UI pixel comes from a real capture in `source-screenshots/`.
- [ ] `captures.py verify` passes: every source registered, none edited; provenance stated in READMEs.
- [ ] Captures labelled with the right device class (Android TV vs Fire TV; emulator vs physical).
- [ ] Features shown exist in the current build; claims match project-profile.md evidence.
- [ ] UI text, numbers and icons unchanged; no stretching or recoloring.
- [ ] No invented UI, ratings, testimonials or rankings.
- [ ] No personal data, credentials, debug UI or private notifications.
- [ ] Media/content shown is owned or licensed for marketing.

## Technical compliance
- [ ] `validate_assets.py` reports no errors for every selected target.
- [ ] Warnings reviewed; each either fixed or justified in the README.
- [ ] Dimensions, aspect, format, file size, alpha correct (validator) — and device category correct (you).
- [ ] Order is 01, 02, 03 … matching the storyboard.
- [ ] Official requirements re-checked this session (or marked unverified with the profile date).
- [ ] Manual checks listed in the validation report reviewed.

## Deliverables
- [ ] Final images present for every selected target, nothing else in those folders but README.
- [ ] Editable sources preserved in `working/`.
- [ ] `previews/contact-sheet.png` (and store-scale sheet) current.
- [ ] Root README and every platform README complete, with accurate status.
- [ ] `validation-report.md` from the final run.
- [ ] No temp files, failed renders or stale exports left in the release folder.
