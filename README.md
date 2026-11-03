# BubbleBuster · What did the system know on January 6?

A data-centre operator corrects its annual capital expenditure from $12 million to $15 million. Which figure belongs in an analysis run before the correction? This small PostgreSQL case study follows the source bytes, the review decision and the financial fact all the way to a dollar-denominated what-if result.

> This repository is a curated engineering snapshot of a larger, actively developed private project. It demonstrates selected backend, temporal-data and simulation mechanisms using synthetic data. It is not the complete research platform.

An excerpt from the executable demonstration:

```text
Jan 06: 12 USD_MILLION | fact b276c465-43e9-542e-95ad-3f355ebacf27
Jan 12: 15 USD_MILLION | fact c7e24669-0e6e-592d-a1b5-42e3c1a64646
Jan 06 replay: 12 USD_MILLION | fact b276c465-43e9-542e-95ad-3f355ebacf27
2031-01-06 | baseline * (1 + CAPEX_PERCENT / 100) | +10% | 12000000 -> 13200000.0 USD | input b276c465-43e9-542e-95ad-3f355ebacf27
Blocked scenario: REVENUE baseline is unavailable at the cutoff
Supplier effect withheld: UNKNOWN_EXPOSURE_VALUE
```

```text
Source bytes → SHA-256 archive → cited proposal → analyst approval
                                                     ↓
                    PostgreSQL financial fact with a knowledge interval
                                   ├── cutoff → scenario, shock and output
                                   └── cutoff → immutable input manifest
```

**Three decisions to inspect.** The archive lets a reviewer verify the exact statement that supplied a number. Corrections close the old fact's half-open knowledge interval, so an earlier query can still select its original evidence. A percentage shock requires a compatible baseline. Missing revenue and unknown supplier exposure each produce an explicit refusal.

## Run locally

From this checkout, with Docker and Docker Compose v2 or later:

```sh
docker compose build
docker compose run --rm app
docker compose run --rm app pytest -q
```

The demo applies the showcase baseline automatically. To inspect that step alone, run `docker compose run --rm app python -m database`. Running the demo again reuses the same evidence and frozen input while recording new scenario runs. Both services run with networking disabled. PostgreSQL uses a project-local Unix socket and generates its own local-only startup password. Compose manages three project volumes. To remove just this checkout's default showcase resources, run `docker compose down -v` here.

## What to inspect

- [Guided walkthrough and schema](docs/walkthrough.md) follows the two statements and the saved input manifest.
- [Code tour and scope](docs/code-tour.md) separates retained services, adaptations and fixture code, with links to the constraints and negative tests.

The executable includes local storage, reviewed synthetic capex, system-known history, financial shocks and a frozen input contract. A narrow supplier-rule example demonstrates a refusal. Public-time replay, a live exposure graph, private analytical rules, forecast admission and outcome evaluation are outside this slice. A future forecasting method could consume the cutoff-specific manifest before separately recording an outcome. No forecast or accuracy score is produced here.
