# prettier/prettier

Upstream pinned at `8f0c950` (3.9.6). Runner image: the one carrying a
pre-populated Node tool cache, live from 2026-08-19T23:19Z. Both sides
`actions/setup-node` at 24.19.0. n=5 per runner per cache state.

Reproduce with `scripts/collect.py --since 2026-08-19T23:19:00Z`.

## Cold cache

| runner | runs | job wall-clock, median (range) | install | test | CPU |
|---|---|---|---|---|---|
| cf-container | n=5 | **181.0s** (141.0-182.0) | 18.0s | 151.0s | AMD EPYC |
| ubuntu-latest | n=5 | **187.0s** (174.0-210.0) | 18.0s | 165.0s | EPYC 7763; Xeon Platinum 8573C |

Cloudflare is **1.07x faster** on the median.

## Warm cache

| runner | runs | job wall-clock, median (range) | install | test | CPU |
|---|---|---|---|---|---|
| cf-container | n=5 | **159.0s** (139.0-186.0) | 11.0s | 136.0s | AMD EPYC |
| ubuntu-latest | n=5 | **177.0s** (136.0-197.0) | 12.0s | 154.0s | EPYC 7763; EPYC 9V74; Xeon 6973P-C |

Cloudflare is **1.11x faster** on the median.

## Read this honestly

**The ranges overlap.** Cold spans 141-182s against 174-210s; warm spans
139-186s against 136-197s. At n=5 a 7-11% median difference is real but it is
the same size as the run-to-run spread, so the defensible claim is *parity with
a small edge*, not a speedup. Anyone wanting a stronger claim should raise n.

**GitHub's fleet is the larger variable.** Across these runs `ubuntu-latest`
drew four CPU models: EPYC 7763, EPYC 9V74, Xeon Platinum 8573C, and Xeon
6973P-C. Its test step moved 154-165s between batches on identical work. The
Cloudflare side reports a single generic `AMD EPYC` and was steadier. Which
machine a hosted job lands on affects the result more than the platform does.

**The install step is a tie**, at 18s cold and 11-12s warm on both. prettier
uses yarn PnP, so the cache is a 51.6 MiB set of zips rather than a large
`node_modules`. This case study therefore tests CPU and does **not** meaningfully
test cache throughput. A workload with a large dependency tree is needed for
that, and no such claim is made from this data.

## What this benchmark already caught

The first cold run had Cloudflare **1.08x slower**, at 194s against 179s. The
per-step breakdown put 8 of those 15 seconds in `Set up Node`: 9.0s against 1.0s,
because `actions/setup-node` re-downloaded a version the image already shipped
while `ubuntu-latest` resolved it from a populated tool cache. The runner image
now ships `/opt/hostedtoolcache/node/24.19.0/x64`, the step fell to 1.0s, and
the numbers above are from after that change.

Worth stating plainly: most of the original gap was a missing directory, and
none of it was the machine.
