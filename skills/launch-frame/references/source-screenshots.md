# Source screenshots: authenticity and review

How to capture them is in `capture.md`. This file covers what makes a source usable and what may be
done with it.

## Authenticity rules

- Use captures of the real, current build (auto-captured, existing in the repo, or user-provided, as
  recorded in `captures.json`). Never generate UI with an image model or rebuild it in HTML/SVG.
- Do not change UI text, numbers, labels, icons, colors or layout. Don't paint over UI, swap content,
  or "fix" a screen by retouching it.
- Never stretch or squash. Scale uniformly, and avoid upscaling beyond ~1.25× (it blurs). Recapture instead.
- Cropping is allowed when it is intentional and the crop still represents the UI accurately.
- A genuine UI element cropped from a real capture may be shown larger or beside its screen, unaltered.
- Perspective/3D placement is allowed only if every word in the UI stays readable and nothing is
  hidden to imply something untrue.
- Demo data must be honest: plausible, not implying features the app lacks, and content the user has
  rights to show in marketing (careful with posters, album art, logos inside media apps).
- Generated artwork may support the design (backgrounds, textures) but must never look like app UI.

## What good source material looks like

- Native resolution of the target device class, PNG, sharp.
- Clean status bar (09:41, full battery/signal, no notifications or carrier name), or cropped off.
- Representative, meaningful content: not empty states, spinners or placeholder text, unless that
  state is itself the feature.
- Release language; consistent theme choice across a set unless contrast is the point.
- No personal data: names, emails, phone numbers, addresses, account IDs, tokens, IPs, private files.
- No debug banners, dev menus, FPS overlays, test servers, toasts, crash dialogs.

## Review before use

Open every capture and check it: right screen, fully loaded, no truncated text, honest data, nothing
private, current UI. When a capture is unsuitable, say why and recapture or ask for better data.
Don't design around a bad source.

If the app only looks meaningful with content (media libraries, dashboards, social feeds) and none
is available, stop and arrange safe demo content or a demo account. A beautiful frame around an empty
state misrepresents the product.

## Allowed vs. forbidden edits

| Allowed | Forbidden |
|---|---|
| Uniform scale, intentional crop | Non-uniform scale, warping that hides content |
| Rounded-corner mask matching the device | Recoloring, filters, sharpening that changes UI |
| Placing on a background, adding a headline outside the UI | Painting over, cloning out, replacing UI text/numbers |
| Cropping off a status bar | Faking a status bar or notification |
| Device frame or readable perspective placement | Perspective so steep the UI can't be read |
| Blurring personal data only when recapture is impossible (and saying so) | Inventing content or features |
