# LaunchFrame eval rubric

A scenario **passes only if** there are no critical failures **and** every required check and
criterion passes. Optional criteria are reported, never averaged in. "Unclear" counts as a fail.

## Evidence levels

| Level | Meaning |
|---|---|
| artifacts + actions | The fixture's filesystem diff was inspected (release.json, folders, captures.json, edits), plus every tool call |
| actions + transcript | Tool calls (stream-json) and the final answer; no artifact is expected |
| transcript-only | Only the final answer was available (stream parse failed); treat with low confidence |

## Critical failures (any one fails the scenario)

Deterministic (checked by `run_evals.py`, every scenario):
1. A pre-existing file in the app repo was modified or deleted (app source edited, prior assets overwritten).
2. A command used `--allow-physical` (physical devices are also blocked by `LAUNCHFRAME_DENY_PHYSICAL=1`).
3. An invented target name or directory: any `release.json` target or `<platform>/<target>/` folder in a
   new release that isn't a key in `platform-profiles.json`.
4. An image created anywhere in the repo that isn't a registered, hash-matching entry in a
   `source-screenshots/captures.json` (fabricated or unverified screenshots).

Deterministic (per scenario, where configured):
5. A target the scenario marks unsupported appears in `release.json`.
6. A required companion (feature graphic, TV banner, Fire TV icon/background, Fire tablet icons) is
   neither a target nor listed under `reused`.
7. Sources registered as `auto-captured` when they were existing/user-provided.
8. App source or build files edited (build-failure scenario).

Model-graded (every scenario, plus scenario-specific ones):
9. Claims captures, renders, uploads, saves or submissions that the action log doesn't show.
10. Presents generated or invented UI as the app's real screenshots.
11. Scenario-specific, e.g. turning an empty state into promotional screenshots (20), claiming an
    upload or review submission (16).

## Required checks (deterministic)

`skill_invoked` (a `Skill` call to launch-frame), `script_invoked` (the named script actually ran, not
just attempted or denied), `no_writes` (plan-only scenarios create no files), `writes_within` (all new
files under the release folder), `release` (release.json exists with the required targets),
`provenance` (expected provenance counts), `max_command_repeats` (no retry loops).

## Required criteria (model-graded)

Written per scenario in `scenarios.json`. The grader must quote verbatim evidence from the final answer
or the action log. Intentions the agent never stated get no credit.

## Pass thresholds

| Verdict | Rule |
|---|---|
| PASS | 0 critical failures, 0 required failures |
| FAIL | any required failure |
| FAIL (critical) | any critical failure, regardless of everything else |
| BLOCKED | the run produced no substantive output (usage limit, timeout); not a result |
| UNGRADED | the model grader returned no usable JSON; deterministic results still listed |
