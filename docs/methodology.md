# Methodology

Nobody has to trust a claim on the front page. The projects, the workflows, and
the rules below are public, and the script that turns runs into a table refuses
to report anything it did not measure.

## One variable

Each case study runs a real open-source project's own test command on both
runners. The upstream code is fetched at a pinned commit when the pipeline runs.
What lives in this repository is two thin callers and one reusable workflow
holding every measured step. Because the steps exist once, the only difference
between the two sides is the `runner` input.

## Shape parity

| | vCPU | RAM | Disk | Platform |
|---|---|---|---|---|
| `ubuntu-latest` | 4 | 16 GB | 14 GB | Azure VM |
| `cf-container` | 4 | 12 GiB | 20 GB | Cloudflare, Firecracker microVM |

Core count is equal, which is the dimension that decides a jest run. Memory is
**lower** on the Cloudflare side: Cloudflare requires 3 GiB per vCPU for the
first four vCPUs, so 4 vCPU forces 12 GiB and 16 GiB is not selectable at this
shape. Disk is higher, and irrelevant to a case study that never approaches
14 GB.

A private repository gets a 2 CPU / 8 GB `ubuntu-latest`. This repository is
public so that the comparison is four cores against four.

## What is measured

The job's wall-clock on the runner: `started_at` to `completed_at` from the
Actions jobs API.

Run-level timing is deliberately not used. It also counts the run record being
created and the job being assigned, which is platform overhead that differs
between a hosted runner and a container this project starts on demand. Queue
time is excluded on both sides, because `started_at` is post-assignment.

Excluding queue time costs the Cloudflare side nothing and is the conservative
choice: a container has to boot before it can claim a job, and a hosted runner
is drawn from a warm pool.

Per-step timings for install and test are reported alongside the total, so a
difference can be attributed rather than just observed.

## Median of at least three runs

One CI run is noise: scheduling, network, and neighbors all move it. Every
published number is the median of at least three runs of the same workflow on
the same runner, and the run count appears next to it. The median rather than
the mean, so a single outlier cannot carry the result.

## The CPU model is recorded per run

`ubuntu-latest` is not one machine. Across a 20-run burst on this project's
sibling repository it drew four different CPU models. The first step of every
job records `/proc/cpuinfo`, core count, and memory, and the collector prints
every distinct model behind a number. A median that spans several CPUs is
disclosed as such.

## Cold and warm are never blended

Dependency resolution dominates many CI runs, and a cache changes the picture
completely. The two states are reported separately:

- **Cold**: no dependency cache. Everything is fetched.
- **Warm**: `actions/cache` restores a populated cache.

Warm requires two runs: the first populates, the second measures. The first is
never counted. A "speedup" always states which state it refers to; comparing a
warm Cloudflare run against a cold GitHub one is not a valid comparison and is
not published.

The cache action is byte-identical on both sides. On `ubuntu-latest` it talks to
GitHub's cache service; inside a container the same requests are answered from
R2. Substituting a vendor-specific cache action would change what is being
compared, so the standard action is used throughout.

`actions/cache` reports a save that entirely failed as a `##[warning]` and still
prints `Cache saved with key: ...`, so a warm run that missed looks like a warm
run at the step level. The job records the restore outcome and the collector
drops any warm run whose cache did not hit, then says how many it dropped.

## Node is installed, not inherited

Both sides install Node with `actions/setup-node` at the same pinned version,
rather than using whatever each image ships, which differs and is not the
variable under test.

This is a small handicap to the Cloudflare side, disclosed rather than hidden:
the hosted image carries a populated tool cache and can resolve that version
locally, while the container downloads it. The install step's time is reported
separately, so the cost is visible.

## Point-in-time

Each case study pins an upstream commit. Published results record the ref and
the date. When upstream moves, update the pin and re-run; runs against different
refs are never blended.

## What is not controlled

Disclosed, because comparing two platforms cannot eliminate them:

- Network path and bandwidth to package registries differ. That difference is
  part of what a cold run measures, which is why cold and warm are separate.
- Background load on shared infrastructure, on both sides. Median-of-N dampens
  this; it cannot remove it.
- The CPU model behind each shape, which is why every run records it.

## Fork-PR safety

The case-study workflows are `workflow_dispatch` only. There is no
`pull_request` trigger, so a fork cannot cause code to run on a self-hosted
runner. Every run is a deliberate action.
