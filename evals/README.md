# LaunchFrame evals

Scenario evaluations of the skill's *behavior* (discovery, capture decisions, safety, honesty), on
synthetic fixture repositories built by `fixtures.py`. All fixture content is TEST DATA.

```
python evals/run_evals.py --list
python evals/run_evals.py --scenario 06-misleading-keywords --model sonnet
python evals/run_evals.py --all --model sonnet                 # non-runtime scenarios
python evals/run_evals.py --all --include-runtime --model sonnet # also host-dependent scenarios
```

- `plan` scenarios ask the agent to plan without writing files; they're cheap and safe.
- `runtime` scenarios depend on the host (emulators present or absent, macOS or not). Their `setup`
  field says what the host must look like.
- Physical Android devices are blocked during evals (`LAUNCHFRAME_DENY_PHYSICAL=1`).
- Grading: deterministic checks on actions and files plus a strict model grader (see `RUBRIC.md`); read the results in `evals/results/`
  (git-ignored).

The deterministic parts (target classification on every fixture) are also covered by
`tests/test_launchframe.py`.
