# cf-runner-benchmark

Head-to-head CI benchmarks: GitHub Actions jobs on
[Cloudflare Containers](https://github.com/emirb/cf-runner-poc) against
GitHub-hosted runners.

One real open-source project, its own test command, one variable: `runs-on`.
The upstream code is fetched at a pinned commit when the pipeline runs; nothing
is vendored here. Every workflow, every number, and the script that produces
them is public, so anyone can reproduce or challenge the result.

## Results

prettier/prettier at `8f0c950`, n=5 per runner per cache state.

| cache | cf-container | ubuntu-latest | |
|---|---|---|---|
| cold | **181.0s** (141-182) | 187.0s (174-210) | 1.07x faster |
| warm | **159.0s** (139-186) | 177.0s (136-197) | 1.11x faster |

**The ranges overlap, so read this as parity with a small edge, not a speedup.**
At n=5 the median difference is the same size as the run-to-run spread. Across
these runs `ubuntu-latest` drew four different CPU models and its test step
moved 154-165s on identical work; which machine a hosted job lands on affects
the result more than the platform does.

Cost, at the measured 89% CPU busy, priced per runner at its own duration:

| runner | one job | per vCPU-minute |
|---|---|---|
| **Cloudflare standard-4** | **$0.01631** | $0.00154 |
| Blacksmith 4 vCPU / Namespace 4x16 | $0.02400 | $0.00200 |
| GitHub 4-core larger runner | $0.03600 | $0.00300 |

**2.2x cheaper than GitHub** for the same job, and faster. Only Cloudflare and
GitHub were run; the middle row is a rate card, not a measurement.

Egress is billed in one direction. Bytes arriving at a container are not metered,
so a cache restore is free; a cache **save** is egress, at $0.025/GB past 1 TB a
month. Every other provider includes cache transfer, so this is the one axis
where this design is the expensive option:

| 1,000 jobs/month, 50 GB cache | 1% miss | 20% miss |
|---|---|---|
| this project | **$0.60** | $225.60 |
| GitHub Actions cache | $2.80 | **$2.80** |
| Namespace cache volume | $12.20 | $12.20 |

Cheapest at rest by 4.7x to 33x, and worst by a wide margin for a large cache
that is rewritten often. Rates, citations, and the break-even:
[`docs/results/cache-cost.md`](docs/results/cache-cost.md).

Full numbers, caveats, and what this does *not* show:
[`docs/results/prettier.md`](docs/results/prettier.md) and
[`docs/results/cost.md`](docs/results/cost.md).

## How it works

Three files per case study. The measured steps live in the reusable workflow
and exist exactly once, so the two sides cannot drift apart.

```
casestudy-prettier.yml              reusable: checkout upstream @pin -> yarn install -> yarn test
   |- casestudy-prettier-cf.yml     runs-on: cf-container
   |- casestudy-prettier-github.yml runs-on: ubuntu-latest
```

The callers differ in the runner label and nothing else:

```console
$ diff .github/workflows/casestudy-prettier-{cf,github}.yml
<       runner: cf-container
>       runner: ubuntu-latest
```

## Shape parity

| | vCPU | RAM | Disk |
|---|---|---|---|
| `ubuntu-latest` (public repo) | 4 | 16 GB | 14 GB |
| `cf-container` | 4 | 12 GiB | 20 GB |

Core count matches. Cloudflare bills 3 GiB per vCPU for the first four, so a
4-vCPU instance is 12 GiB and the Cloudflare side runs with **less memory**,
not more. This repository is public deliberately: on a private repository
`ubuntu-latest` is 2 CPU / 8 GB, and racing four cores against two measures the
billing tier rather than the runner.

## Case studies

| Upstream | Pinned ref | Test command | Why this project |
|---|---|---|---|
| [prettier/prettier](https://github.com/prettier/prettier) | 3.9.6 (`8f0c950`) | `yarn test` (jest) | Formatting is a pure function, so the suite needs no database, no network, and no service. It parallelizes across cores and has a large dependency tree. |

Details in [`case-studies/projects/`](case-studies/projects/).

## Reproduce

```bash
# Dispatch each caller at least three times per cache mode, then:
python3 scripts/collect.py \
    --repo emirb/cf-runner-benchmark \
    --cf-workflow casestudy-prettier-cf.yml \
    --github-workflow casestudy-prettier-github.yml \
    --cache cold
```

The collector drops any run that did not complete, and any warm run whose cache
missed. It reports what it dropped and why.

## Methodology

[`docs/methodology.md`](docs/methodology.md) covers what is controlled, what
isn't, the median-of-N rule, and why cold and warm runs are never blended.

## License

[Apache-2.0](LICENSE).
