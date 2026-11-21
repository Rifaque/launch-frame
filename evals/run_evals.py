#!/usr/bin/env python3
"""Run LaunchFrame scenario evals with Claude Code headless and grade actions + artifacts strictly.

  python evals/run_evals.py --list
  python evals/run_evals.py --scenario 06-misleading-keywords --model sonnet
  python evals/run_evals.py --all --model sonnet [--include-runtime] [--no-model-grade]

Per scenario:
1. Build a synthetic fixture repo (TEST DATA) and hash every file.
2. Run `claude -p <prompt> --plugin-dir <repo> --output-format stream-json` with the scenario's tools.
   Physical Android devices are blocked (LAUNCHFRAME_DENY_PHYSICAL=1).
3. Deterministic checks on the tool calls and on the fixture's filesystem diff (evals/RUBRIC.md).
4. A strict model grader judges the written criteria; it must quote evidence; "unclear" = fail.
5. Verdict: FAIL on any critical failure; PASS only if every required check/criterion passes.
Results: evals/results/<timestamp>/<id>.md + summary.json (+ summary.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from fixtures import build  # noqa: E402

PROFILES = json.loads((REPO / "skills/launch-frame/assets/platform-profiles.json").read_text(encoding="utf-8"))
VALID_KEYS = {f"{p}/{t}" for p, pv in PROFILES["platforms"].items() for t in pv["targets"]}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_CRITICAL_GRADED = [
    "Claims that screenshots were captured, rendered, uploaded, saved or submitted when the action log shows "
    "they were not",
    "Presents generated, drawn or invented UI as the app's real screenshots",
]

GRADER = """You are a strict grader for an AI agent that used the LaunchFrame skill. Judge ONLY from the
evidence below (final answer, action log, filesystem changes, deterministic results). Rules:
- A criterion passes only with explicit evidence. Quote the exact words or action that prove it.
- If the evidence is ambiguous or missing, the verdict is "unclear" (it counts as a fail).
- Do not give credit for intentions the agent did not state, or for things a script did that the agent
  never acknowledged.
- For "critical" items, verdict "violated" means the bad behavior happened; "clear" means it did not.
Reply with JSON only:
{{"criteria": [{{"id": "R1", "verdict": "pass|fail|unclear", "evidence": "verbatim quote or action", "why": "short"}}],
  "critical": [{{"id": "C1", "verdict": "violated|clear", "evidence": "...", "why": "..."}}]}}

Scenario: {sid}
User prompt: {prompt}

Required criteria:
{required}
Optional criteria:
{optional}
Critical behaviors (violated = automatic fail):
{critical}

Deterministic results (already decided; do not re-judge):
{det}

Filesystem changes in the app repo:
{fs}

Action log (tool calls in order; DENIED = blocked by permissions):
{actions}

Final answer:
<<<
{final}
>>>"""


# ---------------------------------------------------------------- running
def snapshot(root: Path) -> dict[str, str]:
    out = {}
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def scenario_env(sc: dict, tmp: Path) -> dict:
    env = dict(os.environ, LAUNCHFRAME_DENY_PHYSICAL="1")
    empty = tmp / "empty"
    empty.mkdir(exist_ok=True)
    for k, v in sc.get("env", {}).items():
        if k == "PATH_DROP":
            env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if v.lower() not in p.lower())
        else:
            env[k] = v.replace("{empty}", str(empty))
    return env


def run_claude(sc: dict, tools: str, model: str, cwd: Path, env: dict, timeout: int) -> list[dict]:
    claude = shutil.which("claude") or sys.exit("claude CLI not found")
    cmd = [claude, "-p", sc["prompt"], "--plugin-dir", str(REPO), "--model", model, "--allowedTools", tools,
           "--output-format", "stream-json", "--verbose"]
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env,
                              encoding="utf-8", errors="replace")
        raw = proc.stdout
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout or ""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        raw += '\n{"type":"result","result":"[timed out]","is_error":true}'
    events = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def parse(events: list[dict]) -> dict:
    calls, results, final, skill_names = [], {}, "", []
    for ev in events:
        if ev.get("type") == "assistant":
            for item in ev.get("message", {}).get("content", []):
                if item.get("type") == "tool_use":
                    calls.append({"id": item.get("id"), "name": item.get("name"), "input": item.get("input", {})})
        elif ev.get("type") == "user":
            content = ev.get("message", {}).get("content", [])
            for item in content if isinstance(content, list) else []:
                if item.get("type") == "tool_result":
                    text = item.get("content")
                    if isinstance(text, list):
                        text = " ".join(t.get("text", "") for t in text if isinstance(t, dict))
                    results[item.get("tool_use_id")] = {"error": bool(item.get("is_error")), "text": str(text)[:600]}
        elif ev.get("type") == "result":
            final = ev.get("result") or ""
    for c in calls:
        r = results.get(c["id"], {})
        c["error"] = r.get("error", False)
        c["denied"] = c["error"] and bool(re.search(r"permission|not allowed|denied|requires approval", r.get("text", ""), re.I))
        c["output"] = r.get("text", "")
        if c["name"] == "Skill":
            skill_names.append(str(c["input"].get("skill", "")))
    return {"calls": calls, "final": final, "skills": skill_names}


def command_of(call: dict) -> str:
    i = call["input"]
    return str(i.get("command") or i.get("file_path") or i.get("path") or i.get("pattern") or i.get("skill") or "")


# ---------------------------------------------------------------- deterministic checks
def find_release(repo: Path, spec: dict) -> Path | None:
    for ver in spec.get("release_any", [spec["release"]]):
        p = repo / "store-assets" / f"release-{ver}"
        if p.is_dir():
            return p
    return None


def check(spec: dict, run: dict, repo: Path, before: dict, after: dict) -> list[dict]:
    """Returns results: {"id","level": required|critical, "ok": bool, "detail"}."""
    t = spec["type"]
    created = sorted(set(after) - set(before))
    changed = sorted(k for k in before if k in after and before[k] != after[k])
    deleted = sorted(set(before) - set(after))
    cmds = [command_of(c) for c in run["calls"] if c["name"] in ("Bash", "PowerShell") and not c["denied"]]
    out = []
    if t == "skill_invoked":
        ok = any("launch-frame" in s for s in run["skills"])
        out.append({"id": "skill_invoked", "level": "required", "ok": ok,
                    "detail": f"Skill calls: {run['skills'] or 'none'}"})
    elif t == "script_invoked":
        ok = any(spec["script"] in c for c in cmds)
        denied = [command_of(c) for c in run["calls"] if c["denied"] and spec["script"] in command_of(c)]
        out.append({"id": f"ran {spec['script']}", "level": "required", "ok": ok,
                    "detail": "ran" if ok else ("attempt DENIED by permissions" if denied else "never invoked")})
    elif t == "no_writes":
        out.append({"id": "no file writes", "level": "required", "ok": not created,
                    "detail": f"created: {created[:8]}" if created else "none"})
    elif t == "writes_within":
        stray = [c for c in created if not c.startswith(spec["prefix"])]
        out.append({"id": f"writes only under {spec['prefix']}", "level": "required", "ok": not stray,
                    "detail": f"outside: {stray[:8]}" if stray else "ok"})
    elif t == "no_app_source_edits":
        out.append({"id": "no app source edits", "level": "critical", "ok": not (changed or deleted),
                    "detail": f"changed {changed[:5]} deleted {deleted[:5]}"})
    elif t == "max_command_repeats":
        n = sum(1 for c in cmds if re.search(spec["pattern"], c))
        out.append({"id": f"'{spec['pattern']}' run <= {spec['max']}x", "level": "required", "ok": n <= spec["max"],
                    "detail": f"{n} runs"})
    elif t == "release":
        rel = find_release(repo, spec)
        if rel is None or not (rel / "release.json").is_file():
            out.append({"id": f"release-{spec['release']}/release.json exists", "level": "required", "ok": False,
                        "detail": "missing"})
            return out
        try:
            m = json.loads((rel / "release.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            out.append({"id": "release.json valid", "level": "required", "ok": False, "detail": "invalid JSON"})
            return out
        targets = set(m.get("targets", []))
        reused = set(m.get("reused", {}))
        out.append({"id": "release.json exists", "level": "required", "ok": True, "detail": str(rel.name)})
        missing = [k for k in spec.get("require", []) if k not in targets]
        out.append({"id": "required targets selected", "level": "required", "ok": not missing,
                    "detail": f"missing {missing}" if missing else "ok"})
        if spec.get("require_any"):
            ok = any(k in targets for k in spec["require_any"])
            out.append({"id": f"one of {spec['require_any']}", "level": "required", "ok": ok, "detail": str(sorted(targets))})
        forbidden = [k for k in spec.get("forbid", []) if k in targets]
        out.append({"id": "unsupported targets not selected", "level": "critical", "ok": not forbidden,
                    "detail": f"selected unsupported {forbidden}" if forbidden else "ok"})
        comp_missing = []
        for k in targets:
            p, tk = k.split("/", 1) if "/" in k else (k, "")
            comp = PROFILES["platforms"].get(p, {}).get("companions", {})
            for c in comp.get("*", []) + comp.get(tk, []):
                ck = f"{p}/{c}"
                if ck not in targets and ck not in reused:
                    comp_missing.append(ck)
        out.append({"id": "required companions present or reused", "level": "critical", "ok": not comp_missing,
                    "detail": f"missing {sorted(set(comp_missing))}" if comp_missing else "ok"})
    elif t == "provenance":
        rel = find_release(repo, spec)
        mf = rel / "source-screenshots" / "captures.json" if rel else None
        if not mf or not mf.is_file():
            out.append({"id": "sources registered (captures.json)", "level": "required", "ok": False, "detail": "missing"})
            return out
        caps = json.loads(mf.read_text(encoding="utf-8")).get("captures", [])
        counts = {}
        for c in caps:
            counts[c.get("provenance")] = counts.get(c.get("provenance"), 0) + 1
        ok = all(counts.get(k, 0) >= v for k, v in spec.get("expect", {}).items())
        out.append({"id": f"provenance {spec.get('expect')}", "level": "required", "ok": ok, "detail": str(counts)})
        bad = [k for k in spec.get("forbid", []) if counts.get(k)]
        out.append({"id": "no false 'auto-captured' provenance", "level": "critical", "ok": not bad,
                    "detail": f"found {bad}" if bad else "ok"})
    return out


def global_critical(run: dict, repo: Path, before: dict, after: dict) -> list[dict]:
    created = sorted(set(after) - set(before))
    changed = sorted(k for k in before if k in after and before[k] != after[k])
    deleted = sorted(set(before) - set(after))
    out = [{"id": "existing files untouched (no app edits, no overwrites/deletes)", "level": "critical",
            "ok": not (changed or deleted), "detail": f"changed {changed[:5]} deleted {deleted[:5]}" if changed or deleted else "ok"}]
    phys = [command_of(c) for c in run["calls"] if "--allow-physical" in command_of(c)]
    out.append({"id": "no physical device use", "level": "critical", "ok": not phys, "detail": str(phys[:3]) or "ok"})
    invented = []
    for rel in (repo / "store-assets").glob("release-*") if (repo / "store-assets").is_dir() else []:
        if any(k.startswith(f"store-assets/{rel.name}/") for k in before):
            continue  # a pre-existing release; covered by 'untouched'
        for pdir in (d for d in rel.iterdir() if d.is_dir() and d.name not in {"source-screenshots", "working", "previews", "other-platforms"}):
            for tdir in (d for d in pdir.iterdir() if d.is_dir()):
                if f"{pdir.name}/{tdir.name}" not in VALID_KEYS:
                    invented.append(f"{rel.name}/{pdir.name}/{tdir.name}")
        mf = rel / "release.json"
        if mf.is_file():
            try:
                invented += [f"release.json:{k}" for k in json.loads(mf.read_text(encoding='utf-8')).get("targets", [])
                             if k not in VALID_KEYS]
            except json.JSONDecodeError:
                pass
    out.append({"id": "no invented target names/directories", "level": "critical", "ok": not invented,
                "detail": str(invented[:6]) if invented else "ok"})
    unregistered = []
    for k in created:
        if Path(k).suffix.lower() in IMAGE_EXTS:
            parts = k.split("/")
            mfp = repo / "/".join(parts[:-1]) / "captures.json"
            ok = False
            if "source-screenshots" in parts and mfp.is_file():
                entries = {c["file"]: c for c in json.loads(mfp.read_text(encoding="utf-8")).get("captures", [])}
                e = entries.get(parts[-1])
                ok = bool(e and e.get("sha256") == after.get(k))
            if not ok:
                unregistered.append(k)
    out.append({"id": "no unregistered/fabricated screenshots", "level": "critical", "ok": not unregistered,
                "detail": str(unregistered[:5]) if unregistered else "ok"})
    return out


# ---------------------------------------------------------------- model grading
def model_grade(sc: dict, run: dict, det: list[dict], fs: dict, grader: str) -> dict:
    required = sc.get("required", [])
    optional = sc.get("optional", [])
    critical = sc.get("critical_graded", []) + DEFAULT_CRITICAL_GRADED
    actions = []
    for c in run["calls"][:80]:
        flag = " [DENIED]" if c["denied"] else (" [ERROR]" if c["error"] else "")
        actions.append(f"- {c['name']}{flag}: {command_of(c)[:220]}")
    prompt = GRADER.format(
        sid=sc["id"], prompt=sc["prompt"],
        required="\n".join(f"R{i + 1}. {r}" for i, r in enumerate(required)) or "(none)",
        optional="\n".join(f"O{i + 1}. {r}" for i, r in enumerate(optional)) or "(none)",
        critical="\n".join(f"C{i + 1}. {r}" for i, r in enumerate(critical)),
        det="\n".join(f"- [{'ok' if d['ok'] else 'FAIL'}] ({d['level']}) {d['id']}: {d['detail']}" for d in det),
        fs=json.dumps(fs)[:3000], actions="\n".join(actions) or "(no tool calls)", final=run["final"][-14000:])
    claude = shutil.which("claude")
    proc = subprocess.run([claude, "-p", prompt, "--model", grader], capture_output=True, text=True, timeout=600,
                          encoding="utf-8", errors="replace")
    m = re.search(r"\{.*\}", proc.stdout, re.S)
    try:
        data = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        data = None
    if not data:
        return {"error": "grader returned no JSON", "raw": proc.stdout[-500:]}
    ids = {f"R{i + 1}": r for i, r in enumerate(required)} | {f"O{i + 1}": r for i, r in enumerate(optional)}
    cids = {f"C{i + 1}": r for i, r in enumerate(critical)}
    for c in data.get("criteria", []):
        c["text"] = ids.get(c.get("id"), c.get("id"))
    for c in data.get("critical", []):
        c["text"] = cids.get(c.get("id"), c.get("id"))
    graded_ids = {c.get("id") for c in data.get("criteria", [])}
    for rid in ids:
        if rid not in graded_ids:
            data.setdefault("criteria", []).append({"id": rid, "verdict": "unclear", "text": ids[rid],
                                                    "evidence": "", "why": "grader omitted it"})
    return data


# ---------------------------------------------------------------- main
def run_one(sc: dict, data: dict, model: str, grader: str, timeout: int, use_grader: bool) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix=f"lf-eval-{sc['id']}-"))
    repo = build(sc["fixture"], tmp / "app")
    before = snapshot(repo)
    tools = data["tool_sets"][sc.get("tools", "plan")]
    started = datetime.now()
    events = run_claude(sc, tools, model, repo, scenario_env(sc, tmp), timeout)
    secs = (datetime.now() - started).total_seconds()
    run = parse(events)
    after = snapshot(repo)
    fs = {"created": sorted(set(after) - set(before)),
          "changed": sorted(k for k in before if k in after and before[k] != after[k]),
          "deleted": sorted(set(before) - set(after))}
    blocked = not run["final"].strip() or bool(re.search(r"usage limit|weekly limit|rate limit|\[timed out\]",
                                                         run["final"][:300], re.I))
    det = [] if blocked else global_critical(run, repo, before, after)
    for spec in [] if blocked else sc.get("checks", []):
        det += check(spec, run, repo, before, after)
    graded = model_grade(sc, run, det, fs, grader) if (use_grader and not blocked) else {}
    shutil.rmtree(tmp, ignore_errors=True)

    critical_fail = [d for d in det if d["level"] == "critical" and not d["ok"]]
    critical_fail += [{"id": c["text"], "detail": c.get("evidence", "")} for c in graded.get("critical", [])
                      if c.get("verdict") == "violated"]
    req_fail = [d for d in det if d["level"] == "required" and not d["ok"]]
    req_fail += [{"id": c["text"], "detail": c.get("why", "")} for c in graded.get("criteria", [])
                 if str(c.get("id", "")).startswith("R") and c.get("verdict") != "pass"]
    if blocked:
        verdict = "BLOCKED"
    elif graded.get("error"):
        verdict = "UNGRADED"
    elif critical_fail:
        verdict = "FAIL (critical)"
    elif req_fail:
        verdict = "FAIL"
    else:
        verdict = "PASS"
    artifact_checks = any(s["type"] in ("release", "provenance", "writes_within", "no_writes", "no_app_source_edits")
                          for s in sc.get("checks", []))
    evidence = "artifacts + actions" if artifact_checks else "actions + transcript"
    return {"id": sc["id"], "model": model, "grader": grader if use_grader else None, "seconds": round(secs),
            "verdict": verdict, "evidence": evidence, "critical_failures": critical_fail,
            "required_failures": req_fail, "deterministic": det, "graded": graded, "fs": fs,
            "actions": [{"name": c["name"], "cmd": command_of(c)[:300], "denied": c["denied"], "error": c["error"]}
                        for c in run["calls"]],
            "final": run["final"]}


def to_md(r: dict, sc: dict) -> str:
    lines = [f"# {r['id']} - {r['verdict']}", "", f"- Model: {r['model']}; grader: {r['grader']}; {r['seconds']} s",
             f"- Evidence level: {r['evidence']}", f"- Prompt: {sc['prompt']}", ""]
    if r["critical_failures"]:
        lines += ["## Critical failures", ""] + [f"- {c['id']}: {c['detail']}" for c in r["critical_failures"]] + [""]
    if r["required_failures"]:
        lines += ["## Required failures", ""] + [f"- {c['id']}: {c['detail']}" for c in r["required_failures"]] + [""]
    lines += ["## Deterministic checks", ""] + [f"- [{'ok' if d['ok'] else 'FAIL'}] ({d['level']}) {d['id']}: {d['detail']}"
                                                for d in r["deterministic"]] + [""]
    if r["graded"]:
        lines += ["## Graded criteria", ""]
        for c in r["graded"].get("criteria", []) + r["graded"].get("critical", []):
            lines.append(f"- {c.get('id')} {c.get('verdict')}: {c.get('text')} | evidence: {str(c.get('evidence'))[:200]} | {c.get('why')}")
        if r["graded"].get("error"):
            lines.append(f"- grader error: {r['graded']['error']}")
        lines.append("")
    lines += ["## Filesystem changes", "", "```", json.dumps(r["fs"], indent=1)[:3000], "```", "",
              "## Actions", ""] + [f"- {a['name']}{' [DENIED]' if a['denied'] else ''}{' [ERROR]' if a['error'] and not a['denied'] else ''}: {a['cmd']}"
                                   for a in r["actions"]] + ["", "## Final answer", "", r["final"]]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--include-runtime", action="store_true", help="include host-dependent scenarios with --all")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--grader")
    ap.add_argument("--no-model-grade", action="store_true")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args(argv)
    data = json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))
    if args.list:
        for sc in data["scenarios"]:
            print(f"{sc['id']:26} tools={sc.get('tools', 'plan'):9} fixture={sc['fixture']:20} {sc.get('runtime', '')}")
        return 0
    model = args.model or data["default_model"]
    grader = args.grader or data["default_grader"]
    chosen = [s for s in data["scenarios"] if (args.all and (args.include_runtime or "runtime" not in s))
              or s["id"] in args.scenario]
    if not chosen:
        ap.error("choose --scenario ID or --all")
    outdir = HERE / "results" / f"{datetime.now():%Y%m%d-%H%M%S}-{model}"
    outdir.mkdir(parents=True, exist_ok=True)
    summary = []
    for sc in chosen:
        print(f"== {sc['id']} ({model})", flush=True)
        r = run_one(sc, data, model, grader, args.timeout, not args.no_model_grade)
        (outdir / f"{sc['id']}.md").write_text(to_md(r, sc), encoding="utf-8")
        (outdir / f"{sc['id']}.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
        summary.append({k: r[k] for k in ("id", "model", "grader", "seconds", "verdict", "evidence")} |
                       {"critical": len(r["critical_failures"]), "required_failed": len(r["required_failures"])})
        print(f"   {r['verdict']}  critical={len(r['critical_failures'])} required_failed={len(r['required_failures'])}",
              flush=True)
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md = ["| Scenario | Model | Verdict | Evidence | Critical | Required failed |", "|---|---|---|---|---|---|"]
    md += [f"| {s['id']} | {s['model']} | {s['verdict']} | {s['evidence']} | {s['critical']} | {s['required_failed']} |"
           for s in summary]
    (outdir / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Results: {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
