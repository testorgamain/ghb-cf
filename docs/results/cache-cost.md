# What a CI cache costs

Regenerate every table here with `scripts/cache-cost.py`. Every rate is from the
provider's own documentation, linked below, and verified 2026-08.

## The rates

| provider | at rest, per GB-month | included | transfer |
|---|---|---|---|
| **This project** (R2) | **$0.015** | 10 GB account-wide | restore free, **save billed** |
| [GitHub Actions cache][gh] | $0.07 | 10 GB per repo | free |
| [Blacksmith cache][bs] | n/a, free | 25 GB per repo per week | free |
| [Blacksmith sticky disk][bsd] | $0.50 | none | free |
| [Namespace cache volume][ns] | $0.144 ($0.0048/GB-day) | 3,000 GB-day on Team | plus snapshot, below |
| [Namespace registry, Turborepo, Gradle][ns] | $0.20 | none | free |
| [WarpBuild cache][wb] | $0.20 | none | $0.0001 per operation |

Two of these are not object caches. A Namespace cache volume and a Blacksmith
sticky disk are persistent block devices, which do more and are priced on the
volume's whole size whether or not it is full. Namespace also bills *snapshot
usage*, the volume size multiplied by the attached instance's lifetime, at
$0.002/GB-hour; their documentation says it "typically dominates the cost of a
cache volume".

## Storage is the axis this project wins

At $0.015/GB-month, R2 is **4.7x** cheaper than GitHub's overage rate, **9.6x**
cheaper than a Namespace cache volume at rest, **13x** cheaper than WarpBuild,
and **33x** cheaper than a Blacksmith sticky disk. There is also no cap, where
GitHub defaults to 10 GB per repository and evicts against it.

## Transfer is the axis it loses

Everyone else includes cache transfer. This project does not: a save leaves the
container and is billed as egress at $0.025/GB past 1 TB a month. A restore
arrives and is free.

So the bill is set by **saves per month times cache size**, and it is free while
that product stays under 1 TB.

| cache size | free saves per month | each save after that |
|---|---|---|
| 1 GB | 1,000 | $0.03 |
| 10 GB | 100 | $0.25 |
| 50 GB | 20 | $1.25 |
| 100 GB | 10 | $2.50 |

## Worked comparison

1,000 jobs a month, three minutes each, at three miss rates. Bold marks the
cheapest real option in each column.

**1% of jobs miss and save**

| provider | 1 GB | 10 GB | 50 GB |
|---|---|---|---|
| **This project** | **$0.00** | **$0.00** | **$0.60** |
| GitHub Actions cache | $0.00 | $0.00 | $2.80 |
| Blacksmith cache | $0.00 | $0.00 | over its allowance |
| Namespace cache volume | $0.24 | $2.44 | $12.20 |
| WarpBuild cache | $0.30 | $2.10 | $10.10 |

**5% miss**

| provider | 1 GB | 10 GB | 50 GB |
|---|---|---|---|
| This project | $0.00 | $0.00 | $38.10 |
| GitHub Actions cache | $0.00 | $0.00 | **$2.80** |
| Namespace cache volume | $0.24 | $2.44 | $12.20 |
| WarpBuild cache | $0.31 | $2.10 | $10.11 |

**20% miss**

| provider | 1 GB | 10 GB | 50 GB |
|---|---|---|---|
| This project | $0.00 | $25.00 | $225.60 |
| GitHub Actions cache | $0.00 | **$0.00** | **$2.80** |
| Namespace cache volume | $0.24 | $2.44 | $12.20 |
| WarpBuild cache | $0.32 | $2.12 | $10.12 |

## Read this honestly

**A large cache rewritten often is the worst case for this design, by a wide
margin.** At a 20% miss rate on a 50 GB cache it costs $225.60 a month against
GitHub's $2.80. That is not a rounding difference and no amount of restore speed
compensates for it.

**Below roughly 10 GB, or with a stable cache key, it is free and the others are
not.** A 50 GB cache saved ten times a month costs $0.60 here, $12.20 on a
Namespace cache volume, and $10.10 on WarpBuild.

**Blacksmith's free 25 GB per repository per week is the best plain deal for a
small cache**, and GitHub's 10 GB is free too. Neither is beaten on price at
that size; the argument there is restore speed and the absence of a cap, not
cost.

**The lever is save volume, not restore speed.** All of this project's cache
engineering so far, side-load, squashfs, and lazy hydration, makes restores fast.
Restores are the free direction. Cutting the bytes a save writes, by storing
deltas or content-addressed chunks rather than a whole image each time, is the
change that would move this table, and it has not been built.

[gh]: https://docs.github.com/en/billing/concepts/product-billing/github-actions
[bs]: https://docs.blacksmith.sh/blacksmith-caching/dependencies-actions
[bsd]: https://docs.blacksmith.sh/blacksmith-caching/dependencies-sticky-disks
[ns]: https://namespace.so/pricing
[wb]: https://warpbuild.com/pricing
