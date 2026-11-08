# prettier/prettier

| | |
|---|---|
| Upstream | <https://github.com/prettier/prettier> |
| Pinned ref | `8f0c95057cc91d5836409466cd9d9af3bb901e84` (3.9.6) |
| Package manager | yarn 4.18.0, through corepack |
| Install | `yarn install --immutable` |
| Test | `yarn test` (jest) |
| Node | 24.19.0, installed by `actions/setup-node` on both sides |
| License | MIT |

## Why this project

- **Hermetic.** Formatting is a pure function of its input. The suite touches no
  database, no network, and no service, so a failure is a real failure and a
  number is not measuring somebody else's uptime.
- **Parallel.** jest spreads across cores, so a 4-vCPU shape is actually used.
- **Large dependency tree.** 59 direct devDependencies and a committed
  lockfile, which is what makes the install step worth measuring.
- **Recognizable.** 52k stars. The test command is upstream's own, unmodified.

## What is run

One Linux leg. Upstream's own matrix also covers macOS, Windows, and a second
Node version; those are excluded because the point is to race one identical job
per runner, not two different matrices.
