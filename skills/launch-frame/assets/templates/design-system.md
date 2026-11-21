<!-- LaunchFrame template: design-system.md. Cite evidence; mark guesses. Keep decisions short and reasoned. -->
# Design system — {{App name}} {{release}}

## Evidence reviewed
- {{path/to/Theme.kt — color scheme}}
- {{source-screenshots/home.png — measured palette (extract_palette.py)}}

## Visual DNA
| Area | Finding | Evidence | Confidence |
|---|---|---|---|
| Theme | {{dark by default, no light theme}} | {{…}} | {{high: tokens + captures agree}} |
| Primary / accent | {{#hex name}} | {{…}} | {{…}} |
| Background / surfaces | {{#hex, #hex}} | {{…}} | {{…}} |
| Typography | {{family, weights, scale}} | {{…}} | {{…}} |
| Shape | {{radii}} | {{…}} | {{…}} |
| Spacing / density | {{…}} | {{…}} | {{…}} |
| Elevation | {{…}} | {{…}} | {{…}} |
| Iconography | {{…}} | {{…}} | {{…}} |
| Imagery / marketing art | {{…}} | {{…}} | {{…}} |
| Personality | {{3–5 adjectives with reasons}} | | {{…}} |
| Signatures | {{2–4 unique elements}} | | {{…}} |
| Avoid | {{…}} | | |

## Typography for marketing
- Headline: {{family weight size/line-height}} — {{source + license}}
- Sub-line: {{…}}
- Substitutions: {{none / X because Y}}

## Campaign system
- Ground: {{…}} — reason: {{…}}
- Emphasis device: {{…}}
- Motif: {{none / … derived from …}}
- Device treatment: {{frameless crops / flat neutral bezel / none}}
- Margins & safe areas: {{…}}
- Generated imagery: {{none / list}}

## Directions considered
| Direction | Concept | Chosen? | Why |
|---|---|---|---|
| {{A}} | {{…}} | {{yes}} | {{…}} |

## Storyboard
| # | Target / size | Source capture | Feature | Headline | Supporting line | Composition | Background | Device treatment | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| 01 | {{google-play/phone 1080x1920}} | {{phone-home.png}} | {{…}} | {{…}} | {{…}} | {{full-bleed, headline top}} | {{graphite ground}} | {{direct UI}} | {{file/screen}} |

## Per-platform adaptations
- {{Tablet: landscape split layout using tablet captures}}
- {{TV: near-full-bleed, lower-third headline; 01 is an unaltered capture (TV-G4)}}

## Review log
| Round | Shot | Problem seen in the render | Fix |
|---|---|---|---|
| 1 | {{phone/02}} | {{Version card appears twice}} | {{crop base screen above the card}} |

## Decisions & assumptions
- {{…}}
