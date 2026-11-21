<!--
LaunchFrame template: release root README. Replace every {{...}} with real values from this release.
Delete sections that do not apply. Never leave a placeholder or claim a status that was not reached.
Status words: generated -> validated -> uploaded -> verified (verified = seen live/persisted in the console).
-->
# {{App name}} — store assets for {{release}}

Prepared {{YYYY-MM-DD}}. Store specifications last verified against official docs on {{date}} ({{how: fetched official pages / not verified, using profile dated X}}).

## Status

| Store | Device / asset | Folder | Count | Size (px) | Status |
|---|---|---|---|---|---|
| {{Google Play}} | {{Phone screenshots}} | `{{google-play/phone}}` | {{4}} | {{1080x1920}} | {{validated}} |

Validation: `validation-report.md` — {{PASS/FAIL}}, {{n}} errors, {{n}} warnings ({{short note on warnings}}).

## What's here

- `project-profile.md` — what the app does, audience, evidenced feature list.
- `capability-report.md` — supported targets with evidence (Confirmed/Probable/Unknown/Unsupported) and selection decisions.
- `capture-plan.md` — how each source screenshot was obtained, on which device, and what failed.
- `design-system.md` — visual DNA evidence, campaign system, storyboard, decisions.
- `source-screenshots/` — original captures with provenance in `captures.json` ({{n}} auto-captured on {{emulator names}}, {{n}} existing, {{n}} user-provided). Not for upload.
- `working/` — editable compositions ({{HTML/CSS}}), fonts, backgrounds. Re-render with the commands below.
- `previews/` — `contact-sheet.png`, `store-scale.png`{{, direction previews}}.
- Platform folders, each with its own README and upload steps:
  - {{`google-play/README.md`}}

## Screenshot story

| # | Headline | Shows | Feature evidence |
|---|---|---|---|
| 01 | {{headline}} | {{screen}} | {{file or screen}} |

## Re-rendering

```
python <launch-frame>/scripts/render_html.py "working/{{platform}}/{{target}}/*.html" --outdir {{platform}}/{{target}} --size {{WxH}}
python <launch-frame>/scripts/validate_assets.py . --report validation-report.md
python <launch-frame>/scripts/contact_sheet.py .
```

## Assumptions

- {{e.g. Release name taken from versionName 1.0.0 in app/build.gradle.kts}}

## Known limitations

- {{e.g. Fire TV screenshots reuse Google TV captures; interface verified identical on {{date}}}}

## Remaining tasks

- [ ] {{Upload to Google Play phone section (user)}}
- [ ] {{Enter alt text}}
