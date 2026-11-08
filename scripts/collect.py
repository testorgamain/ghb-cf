#!/usr/bin/env python3
"""Reduce completed benchmark runs to a comparison table.

Only measured runs are summarized. Nothing here estimates, extrapolates, or
fills a gap: a run that did not finish, or a warm run whose cache missed, is
dropped and counted in the output rather than quietly averaged in.
"""

import argparse
import json
import re
import statistics
import subprocess
import sys
from datetime import datetime

# Steps worth reporting on their own. The rest (checkout, corepack, the
# machine record) are small and stay folded into the job total.
STEPS = ["Restore dependency cache", "Install dependencies",
         "Run the upstream test suite"]


def gh(*args):
    out = subprocess.run(["gh", *args], capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"gh {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def seconds(a, b):
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).total_seconds()


def runs(repo, workflow, limit):
    # per_page in the path: `gh api -f` sends a body field, which turns this
    # GET into a 404.
    out = gh("api", f"repos/{repo}/actions/workflows/{workflow}/runs"
                    f"?per_page={min(limit, 100)}", "-q", ".workflow_runs")
    return json.loads(out)[:limit]


def job_of(repo, run_id):
    jobs = json.loads(gh("api", f"repos/{repo}/actions/runs/{run_id}/jobs",
                         "-q", ".jobs"))
    return jobs[0] if jobs else None


def facts(repo, job_id):
    """CPU model, core count and cache outcome, read from the job's own log."""
    try:
        text = gh("api", f"repos/{repo}/actions/jobs/{job_id}/logs")
    except SystemExit:
        return {}
    # The runner colours its log, so every value arrives with a trailing reset
    # sequence attached. Left in, `true` compares unequal to `true` and every
    # run is silently dropped as a cache miss.
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    found = {}
    for key in ("cache_mode", "cpu_model", "nproc", "mem_total_kb", "cache_hit"):
        # The log carries the command and then its output. Skipping any line
        # with a `$(` takes the resolved value rather than the echoed source,
        # which otherwise lands in the table as literal shell.
        for line in text.splitlines():
            if f"{key}=" in line and "$(" not in line:
                # Trailing quote included: a `${{ }}` expression is substituted
                # before the shell runs, so the echoed command in the log reads
                # `echo "cache_hit=true"` and is indistinguishable from output.
                found[key] = line.split(f"{key}=", 1)[1].strip().strip('"')
                break
    return found


def collect(repo, workflow, cache_mode, limit, since=None):
    rows, dropped = [], []
    for run in runs(repo, workflow, limit):
        # The runner image changes independently of this repository, so a
        # comparison has to be scoped to one version of it. Without a bound,
        # runs from either side of a rebuild get averaged together.
        if since and run["created_at"] < since:
            dropped.append((run["id"], f"created {run['created_at']} < {since}"))
            continue
        if run["status"] != "completed":
            dropped.append((run["id"], f"status={run['status']}"))
            continue
        if run["conclusion"] != "success":
            dropped.append((run["id"], f"conclusion={run['conclusion']}"))
            continue
        job = job_of(repo, run["id"])
        if not job or not job.get("completed_at"):
            dropped.append((run["id"], "no completed job"))
            continue

        f = facts(repo, job["id"])
        # Both modes dispatch the same workflow, so the run list carries both.
        # Without this the two get averaged together, which is the one thing
        # the methodology says never to do.
        if f.get("cache_mode") != cache_mode:
            dropped.append((run["id"], f"cache_mode={f.get('cache_mode')}"))
            continue
        # A warm run that missed its cache is a cold run wearing a warm label.
        # Counting it would understate the cache and is the exact mistake
        # actions/cache makes easy, since it downgrades a failed save to a
        # warning and still reports success at the step level.
        if cache_mode == "warm" and f.get("cache_hit") != "true":
            dropped.append((run["id"], f"warm run, cache_hit={f.get('cache_hit')}"))
            continue

        step = {}
        for s in job.get("steps", []):
            if s["name"] in STEPS and s.get("started_at") and s.get("completed_at"):
                step[s["name"]] = seconds(s["started_at"], s["completed_at"])
        rows.append({
            "run": run["id"],
            "job_s": seconds(job["started_at"], job["completed_at"]),
            "steps": step,
            **f,
        })
    return rows, dropped


def spread(values):
    v = sorted(values)
    return statistics.median(v), v[0], v[-1]


def report(name, rows):
    if not rows:
        return f"| {name} | n=0 | no measured runs | | |"
    med, lo, hi = spread([r["job_s"] for r in rows])
    cell = {}
    for s in STEPS:
        vals = [r["steps"][s] for r in rows if s in r["steps"]]
        cell[s] = f"{statistics.median(vals):.1f}" if vals else "-"
    cpus = sorted({r.get("cpu_model", "?") for r in rows})
    return (f"| {name} | n={len(rows)} | **{med:.1f}s** ({lo:.1f}-{hi:.1f}) | "
            f"{cell[STEPS[1]]}s | {cell[STEPS[2]]}s | {'; '.join(cpus)} |")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--cf-workflow", required=True)
    p.add_argument("--github-workflow", required=True)
    p.add_argument("--cache", choices=["cold", "warm"], required=True)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--since", help="ISO timestamp; ignore runs created before it")
    p.add_argument("--json", help="write the raw per-run rows here")
    a = p.parse_args()

    cf, cf_drop = collect(a.repo, a.cf_workflow, a.cache, a.limit, a.since)
    gh_, gh_drop = collect(a.repo, a.github_workflow, a.cache, a.limit, a.since)

    print(f"\n### prettier/prettier, {a.cache} cache\n")
    print("| runner | runs | job wall-clock, median (range) | install | test | CPU |")
    print("|---|---|---|---|---|---|")
    print(report("cf-container", cf))
    print(report("ubuntu-latest", gh_))

    if cf and gh_:
        c, g = statistics.median([r["job_s"] for r in cf]), statistics.median([r["job_s"] for r in gh_])
        faster = g / c
        verdict = f"{faster:.2f}x faster" if faster >= 1 else f"{1/faster:.2f}x SLOWER"
        print(f"\ncf-container is **{verdict}** than ubuntu-latest "
              f"on median job wall-clock ({c:.1f}s vs {g:.1f}s).")
    else:
        print("\nNo comparison: one side has no measured runs.")

    for label, d in (("cf", cf_drop), ("github", gh_drop)):
        if d:
            print(f"\nDropped ({label}): " + ", ".join(f"{i} {why}" for i, why in d))

    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"cache": a.cache, "cf": cf, "github": gh_}, fh, indent=2)
        print(f"\nRaw rows: {a.json}")


if __name__ == "__main__":
    sys.exit(main())
