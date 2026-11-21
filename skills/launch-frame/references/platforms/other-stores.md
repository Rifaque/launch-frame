# Other storefronts

LaunchFrame v1 ships **no verified profile** for these. Do not guess sizes from memory.

## Procedure for any additional store

1. Find the store's official developer documentation for listing images (screenshots, icons,
   promotional/feature graphics). Prefer the store's own domain.
2. Write an override profile, e.g. `working/profiles-<store>.json`:
   ```json
   {
     "checked": "YYYY-MM-DD",
     "platforms": {
       "samsung-galaxy-store": {
         "name": "Samsung Galaxy Store",
         "sources": ["<official URL>"],
         "targets": {
           "phone": {"label": "Screenshots", "kind": "screenshot", "formats": ["png", "jpeg"],
                     "alpha": "forbidden", "count": {"min": 4, "max": 8}, "min_side": 320, "max_side": 3840}
         }
       }
     }
   }
   ```
   (Values above illustrate the schema only — replace every number with what the docs say.)
3. Validate with `validate_assets.py <release> --profiles working/profiles-<store>.json`.
4. Record the source URLs and check date in the platform README.
5. If the user will reuse it, offer to add the profile to the skill's `assets/platform-profiles.json`.

## Profile keys

Target fields understood by the validator: `label`, `kind`, `formats` (`png`, `jpeg`), `alpha`
(`forbidden` | `discouraged` | `allowed`), `max_bytes`, `count.min/max`, `sizes` (exact list of
`[w, h]`), `min_side`, `max_side`, `min_size` `[w, h]`, `max_ratio`, `aspects` (e.g. `"16:9"`),
`uniform_size`, `min_per_orientation`, `recommended` (`aspects`, `min_short_side`, `min_count`, `sizes`,
`why`), `notes`, `manual_checks`.

## Candidates to research when asked

- Samsung Galaxy Store (Seller Portal)
- Huawei AppGallery (AppGallery Connect)
- Xiaomi GetApps, OPPO/vivo stores (region-specific)
- Microsoft Store (Partner Center) for Windows/PWA apps
- Mac App Store is covered by `apple-app-store/mac`
- Steam, Meta Horizon Store, and similar have their own capsule/screenshot systems; treat as custom
