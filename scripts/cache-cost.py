#!/usr/bin/env python3
"""What a CI cache costs per month, across providers.

Every rate is from the provider's own documentation, cited in
docs/results/cache-cost.md. Nothing here is a quote, an estimate, or a
list price inferred from a neighbouring tier.

The providers do not sell the same shape of thing. GitHub, Blacksmith and this
project sell an object cache: you pay for what is stored. Namespace cache
volumes and Blacksmith sticky disks are persistent block devices, which are more
capable and priced on the volume's full size whether or not it is full. Both are
modelled, and the difference is the point.
"""
import argparse

GB_MONTH = {                      # $/GB-month at rest
    "cloudflare-r2":       0.015,
    "github-actions":      0.07,
    "namespace-registry":  0.20,   # also Turborepo, Gradle, Artifacts
    "warpbuild":           0.20,
    "blacksmith-sticky":   0.50,   # Docker layer cache and git mirrors too
}
FREE_GB = {                       # included at rest, per repo unless noted
    "cloudflare-r2":  10,          # account-wide R2 free tier
    "github-actions": 10,
    "blacksmith-dep": 25,          # per repo per week
}


def cloudflare(size, jobs, mins, saves):
    store = max(0, size - FREE_GB["cloudflare-r2"]) * GB_MONTH["cloudflare-r2"]
    # A restore is ingress and unmetered. Only saves leave the container.
    egress_gb = saves * size
    egress = max(0, egress_gb - 1000) * 0.025      # 1 TB included, NA/EU
    return store + egress, f"{egress_gb:.0f} GB out, 1 TB free"


def github(size, jobs, mins, saves):
    # Billed on peak usage per hour above 10 GB. Cache transfer is not billed.
    return max(0, size - FREE_GB["github-actions"]) * GB_MONTH["github-actions"], \
        ("within the 10 GB cap" if size <= 10 else
         f"{size - 10:.0f} GB over the cap, and only if the limit was raised")


def blacksmith_dep(size, jobs, mins, saves):
    if size <= FREE_GB["blacksmith-dep"]:
        return 0.0, "free, 25 GB per repo per week"
    return None, "over the 25 GB allowance; evicted rather than billed"


def blacksmith_sticky(size, jobs, mins, saves):
    return size * GB_MONTH["blacksmith-sticky"], "persistent disk, full size"


def namespace_volume(size, jobs, mins, saves):
    # Their docs: snapshot usage is volume size x instance lifetime, and
    # "typically dominates the cost of a cache volume".
    snap = size * (jobs * mins / 60) * 0.002
    store = size * 30 * 0.0048
    return snap + store, f"snapshot ${snap:.2f} + at rest ${store:.2f}"


def warpbuild(size, jobs, mins, saves):
    ops = (jobs + saves) * 0.0001
    return size * GB_MONTH["warpbuild"] + ops, f"storage + {jobs + saves:,} ops"


PROVIDERS = [
    ("this project (R2)",        cloudflare),
    ("GitHub Actions cache",     github),
    ("Blacksmith cache",         blacksmith_dep),
    ("Blacksmith sticky disk",   blacksmith_sticky),
    ("Namespace cache volume",   namespace_volume),
    ("WarpBuild cache",          warpbuild),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--jobs", type=int, default=1000, help="jobs per month")
    p.add_argument("--minutes", type=float, default=3.0, help="minutes per job")
    p.add_argument("--save-rate", type=float, default=0.05,
                   help="fraction of jobs that miss and therefore save")
    p.add_argument("--sizes", default="1,10,50,200",
                   help="cache sizes in GB")
    a = p.parse_args()

    saves = int(a.jobs * a.save_rate)
    print(f"{a.jobs:,} jobs/month, {a.minutes:g} min each, "
          f"{saves:,} saves ({a.save_rate*100:g}% miss rate)\n")
    sizes = [float(s) for s in a.sizes.split(",")]
    w = max(len(n) for n, _ in PROVIDERS) + 1
    print(f"{'':{w}}" + "".join(f"{str(int(s))+' GB':>12}" for s in sizes))
    print("-" * (w + 12 * len(sizes)))
    for name, fn in PROVIDERS:
        cells = []
        for s in sizes:
            cost, _ = fn(s, a.jobs, a.minutes, saves)
            cells.append("capped" if cost is None else f"${cost:,.2f}")
        print(f"{name:{w}}" + "".join(f"{c:>12}" for c in cells))

    print("\nNotes at each size:")
    for s in sizes:
        print(f"\n  {int(s)} GB cache:")
        for name, fn in PROVIDERS:
            cost, note = fn(s, a.jobs, a.minutes, saves)
            amt = "capped" if cost is None else f"${cost:,.2f}"
            print(f"    {name:<26} {amt:>10}   {note}")


if __name__ == "__main__":
    main()
