# Cost

Rates from [Cloudflare](https://developers.cloudflare.com/containers/pricing/)
(2026-04-21), [GitHub](https://docs.github.com/en/billing/reference/actions-runner-pricing),
[Blacksmith](https://docs.blacksmith.sh/blacksmith-runners/overview), and
[Namespace](https://namespace.so/pricing). Regenerate with `scripts/cost.py`.

## What is measured and what is not

Only Cloudflare and GitHub were **run**. Blacksmith and Namespace appear at
their published rates, priced at GitHub's measured duration because their
runners were not benchmarked here. Their hardware scores higher on single-thread
CPU, so they would likely finish sooner and cost less than the row shows. Treat
those two rows as a rate-card comparison, not a result.

## Why duration alone does not give the cost

Cloudflare bills memory and disk on the instance's whole wall-clock life but
**CPU on active use only**, every 10ms. So the bill depends on how busy the job
kept the cores, which this benchmark measures from `/proc/stat` rather than
assumes: a prettier job runs at **87.7-90.5% busy**. jest keeps all four cores
fed, so these figures sit near the ceiling. An I/O-bound job costs materially
less on Cloudflare and exactly the same everywhere else.

## Per minute, at four vCPU

| runner | vCPU | RAM | $/min | $/vCPU-min |
|---|---|---|---|---|
| **Cloudflare standard-4**, 89% CPU (measured) | 4 | 12 GiB | **$0.00616** | $0.00154 |
| **Cloudflare standard-4**, 100% CPU (ceiling) | 4 | 12 GiB | **$0.00668** | $0.00167 |
| Blacksmith 4 vCPU | 4 | 16 GB | $0.0080 | $0.00200 |
| Namespace 4x16, prepaid | 4 | 16 GB | $0.0080 | $0.00200 |
| GitHub 4-core larger runner | 4 | 16 GB | $0.0120 | $0.00300 |
| Namespace 4x16, overage | 4 | 16 GB | $0.0120 | $0.00300 |

Even with all four cores pinned, which needs no assumption at all, Cloudflare is
**1.2x** cheaper per core-minute than Blacksmith or prepaid Namespace and
**1.8x** cheaper than GitHub's 4-core runner.

The 2-vCPU headline rate these vendors advertise, $0.004/min, is not comparable
to a 4-vCPU instance. Blacksmith states the scaling directly: "a job taking 10
minutes on a 4vCPU runner would consume the equivalent of 20 2vCPU minutes".

## One prettier job

Each runner is priced at its own measured duration. Cloudflare's warm median is
159s; `ubuntu-latest` is 177s.

| runner | duration | billed as | cost |
|---|---|---|---|
| **Cloudflare standard-4** | 159s | 159s, per 10ms | **$0.01631** |
| Blacksmith 4 vCPU | 177s (not measured) | 3 min | $0.02400 |
| Namespace 4x16, prepaid | 177s (not measured) | 3 min | $0.02400 |
| GitHub 4-core larger runner | 177s | 3 min | $0.03600 |

**2.2x cheaper than GitHub** for the same job, and faster.

## Rounding is a real line item

Cloudflare bills every 10ms. GitHub "rounds the minutes and partial minutes each
job uses up to the nearest whole minute". Namespace has a one-minute minimum and
bills 150 seconds as 3 minutes.

A 159-second job is 2.65 minutes of work and 3 billed minutes on a per-minute
runner: a 13% surcharge for finishing just past a boundary. Short jobs pay this
worst. A 20-second lint job bills a full minute there and 20 seconds here.

## Where this gets more expensive, not less

- **Egress, and only egress.** The 1 TB monthly allowance for North America and
  Europe covers bytes leaving a container. Bytes arriving are not metered at
  all: the billable dataset,
  `containersUsageAdaptiveGroups`, sums `allocatedDisk`, `allocatedMemory`,
  `cpuTimeSec`, and `txBytes`, and **has no `rxBytes` field**. The
  observability dataset next to it, `containersMetricsAdaptiveGroups`, does
  carry `rxBytes`, so the asymmetry is a billing decision rather than a gap in
  instrumentation.

  Measured on this account for the current period:

  | direction | volume | billed |
  |---|---|---|
  | `rxBytes`, into containers | 624.31 GB | no |
  | `txBytes`, out of containers | 223.89 GB | yes, against the 1 TB |

  The billed figure agrees with the dashboard's 223.86 GB, which is what
  confirms `txBytes` is the metered quantity.

  A restore is a download into the container and costs nothing, so the
  side-load, squashfs, and lazy-hydration work that makes restores fast carries
  no bandwidth bill. A **save** is the one CI operation that moves a large
  object outward, and it is billed.

  The prettier case study is a poor guide to this. Across 41 container instances
  in that session the split was 7,232.7 MB in against 32.5 MB out, a ratio of
  222x, which makes egress look like a rounding error. It is not representative:
  the cold arm has no cache step at all, and the warm arm hit its cache, so
  almost nothing was saved. Its cache is 51.6 MiB regardless.

  The account-level figure shows the real shape. All 223.89 GB is attributable
  by `applicationId` to a single container application, and it lands in the
  hours that ran cache benchmarks: 43.79 GB in one hour, 33.73 GB in another.

  | cache saved per job | jobs before 1 TB | egress cost per job past it |
  |---|---|---|
  | 100 MB | 10,000 | $0.0025 |
  | 500 MB | 2,000 | $0.0125 |
  | 1 GB | 1,000 | $0.0250 |
  | 2.5 GB | 400 | $0.0625 |

  The job measured here costs $0.0163 of compute. **Past the included terabyte,
  saving a cache of 1 GB or more costs more than running the job.**

  A save happens on a miss, not on every run, which is what keeps that
  uncommon. A workload whose cache key changes every run inverts it.
- **Memory and disk bill on wall-clock, not on use.** A container that sits idle
  still accrues $0.00188/min. Runners are one-job-per-container and exit when the
  job does, which is what keeps the fixed portion small, but a leak here is a
  standing charge rather than a spike.
- **The free allotment is not modelled.** The Workers Paid plan includes 25
  GiB-hours of memory, 375 vCPU-minutes, and 200 GB-hours of disk per month.
  Every figure above is the marginal rate beyond it, which is the right basis for
  "what does one more job cost" and understates how cheap the first few are.
