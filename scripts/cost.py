#!/usr/bin/env python3
"""Cost per CI job, from published rates.

Cloudflare bills memory and disk on the instance's whole wall-clock life and
CPU on active use only, every 10ms. GitHub rounds each job up to a whole
minute. Both of those change the answer more than the headline rate does, so
both are modelled rather than assumed away.

Rates: developers.cloudflare.com/containers/pricing (2026-04-21) and
docs.github.com/billing/reference/actions-runner-pricing.
"""
import argparse

# Cloudflare, per second, beyond the Workers Paid included allotment.
CF_MEM_GIB_S = 0.0000025
CF_CPU_VCPU_S = 0.000020
CF_DISK_GB_S = 0.00000007
# standard-4, which is what this project runs.
VCPU, MEM_GIB, DISK_GB = 4, 12, 20

# Competitors at FOUR vCPU, which is the shape this project runs. Quoting a
# 2-vCPU price against a 4-vCPU instance is the easiest way to make either side
# look good, so it is avoided here.
#
# Blacksmith bills higher tiers proportionally: "a job taking 10 minutes on a
# 4vCPU runner would consume the equivalent of 20 2vCPU minutes", so 4 vCPU is
# 2x the $0.004 headline. Namespace publishes 4x16 directly.
#
# `round_up` is the billing granularity in seconds. Cloudflare bills every 10ms;
# GitHub "rounds the minutes and partial minutes each job uses up to the nearest
# whole minute"; Namespace has a one-minute minimum and bills 150s as 3 minutes.
PER_MIN = {
    "GitHub 4-core larger runner":      (0.012, 4, 60),
    "Blacksmith 4 vCPU / 16 GB":        (0.008, 4, 60),
    "Namespace 4x16 (prepaid)":         (0.008, 4, 60),
    "Namespace 4x16 (overage)":         (0.012, 4, 60),
}


def cf_per_min(util):
    fixed = (MEM_GIB * CF_MEM_GIB_S + DISK_GB * CF_DISK_GB_S) * 60
    cpu = util * VCPU * CF_CPU_VCPU_S * 60
    return fixed + cpu, fixed, cpu


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--util", type=float, default=0.89,
                   help="mean CPU utilisation, 0-1. The default is measured: a "
                        "prettier job reports 87.7-90.5%% busy from /proc/stat, "
                        "so jest keeps all four cores fed and this sits near the "
                        "ceiling rather than at a typical idle-ish CI average.")
    p.add_argument("--job-seconds", type=float,
                   help="measured Cloudflare job duration, to price one job")
    p.add_argument("--other-seconds", type=float,
                   help="measured duration on the per-minute runners; defaults "
                        "to --job-seconds when they are not being compared")
    a = p.parse_args()

    print("Cloudflare standard-4 (4 vCPU / 12 GiB / 20 GB), $/minute\n")
    print("| CPU utilisation | memory+disk | CPU | total |")
    print("|---|---|---|---|")
    for u in sorted({0.0, 0.193, 0.5, 1.0, a.util}):
        t, f, c = cf_per_min(u)
        tag = " (measured)" if abs(u - a.util) < 1e-9 else ""
        print(f"| {u*100:.0f}%{tag} | ${f:.5f} | ${c:.5f} | **${t:.5f}** |")

    total, _, _ = cf_per_min(a.util)
    worst, _, _ = cf_per_min(1.0)
    print(f"\nAgainst per-minute pricing. Cloudflare is shown at {a.util*100:.0f}% CPU "
          f"and again with all four cores pinned, which is the ceiling and needs "
          f"no assumption about utilisation.\n")
    print("| runner | vCPU | $/min | $/vCPU-min | vs CF (worst case) |")
    print("|---|---|---|---|---|")
    print(f"| **Cloudflare standard-4**, {a.util*100:.0f}% CPU | {VCPU} | "
          f"**${total:.5f}** | ${total/VCPU:.5f} | - |")
    print(f"| **Cloudflare standard-4**, 100% CPU | {VCPU} | "
          f"**${worst:.5f}** | ${worst/VCPU:.5f} | - |")
    for name, (rate, cores, _) in PER_MIN.items():
        print(f"| {name} | {cores} | ${rate:.4f} | ${rate/cores:.5f} | "
              f"{(rate/cores)/(worst/VCPU):.2f}x per core |")

    if a.job_seconds:
        s = a.job_seconds
        cf_cost = cf_per_min(a.util)[0] * s / 60
        print(f"\nOne {s:.0f}s job:\n")
        print("| runner | billed | cost |")
        print("|---|---|---|")
        print(f"| **Cloudflare standard-4** | {s:.1f}s (per 10ms) | **${cf_cost:.5f}** |")
        for name, (rate, _, gran) in PER_MIN.items():
            # Their own measured duration, not ours: the two runners do not take
            # the same time, and pricing their side at our wall-clock would be
            # a comparison of rate cards rather than of bills.
            other = a.other_seconds or s
            billed = -(-other // gran)
            print(f"| {name} | {other:.0f}s -> {billed:.0f} min | ${rate*billed:.5f} |")
        print("\nRounding is not a footnote. A job just over a minute boundary "
              "bills the whole next minute on a per-minute runner and nothing "
              "extra on Cloudflare.")


if __name__ == "__main__":
    main()
