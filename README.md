# AI-Assisted Python Trading Engine

A public-safe reconstruction of a real, contract-led Python automation project. It formalised an existing manual trading workflow into a deterministic, auditable engine while deliberately withholding the proprietary decision criteria that created the trading edge.

This is an engineering case study—not investment advice, a trading signal, or a claim about future performance.

## Project Objectives

This project had three equal objectives:

1. **Python and software engineering** — build a non-trivial modular system with explicit ownership, deterministic state, configuration integrity, data validation, logging and independent verification.
2. **AI prompting and AI-assisted engineering** — practise turning natural-language requirements into contracts, using AI for implementation support and debugging, then validating outputs rather than trusting them by default.
3. **Automation of an existing manual workflow** — formalise a pre-existing process into deterministic software, with the strategy logic intentionally separated from the public infrastructure.

AI was an engineering assistant during development, not a runtime decision-maker. The engine has no LLM dependency.

## System Architecture

The public repository preserves the real orchestration, configuration, data, state, audit and verification structure. Strategy decision providers retain their genuine contracts and lifecycle positions, but their production predicates are intentionally withheld.

![Engine architecture](https://github.com/RootFM786/ai-assisted-python-trading-engine/raw/5906aba9e65757a992070d931c49a62e2e259b59/assets/04-engine-architecture.png)

See [architecture documentation](docs/architecture.md) and the [public contract index](docs/contracts/public-contract-index.md).

## Engineering Highlights

- Contract-led design across 17 numbered components covering orchestration, time, configuration, data, state, strategy boundaries, outcomes and logging.
- Immutable configuration snapshots, canonical JSON and SHA-256 run identity for reproducibility and auditability.
- UTC-first candle semantics, CSV OHLC validation and normalised data-adapter boundaries.
- Deterministic, forward-only state advancement with explicit lifecycle and component ownership.
- Separate mandatory audit sinks and optional diagnostic sinks, keeping observability from silently changing execution.
- Independent realised-R and candle-outcome verification utilities using public synthetic fixtures.
- A credential-free MT5 integration experiment that retains connectivity, rates and account-query engineering while omitting public order submission.

## AI-Assisted Development & Prompt Engineering

AI support was used to extract requirements, challenge ambiguities, draft/refine module contracts, support implementation, investigate failures and review deterministic outputs. Human review, frozen contracts, audit output and repeatable checks remained the control layer.

![AI-assisted development workflow](https://github.com/RootFM786/ai-assisted-python-trading-engine/raw/5906aba9e65757a992070d931c49a62e2e259b59/assets/05-ai-assisted-development-workflow.png)

Read the [AI-assisted development workflow](docs/ai-assisted-development.md) and [AI prompting and engineering notes](docs/ai-prompt-engineering.md).

## Public Strategy Boundary

The repository intentionally shows the real engine around the strategy without exposing enough information to recreate the private Barakat decision process.

Retained: architecture, contracts, state machine, run harness, time handling, configuration, CSV adaptation, audit/logging, verification and selected MT5 framework code.

Withheld: exact qualification predicates, parameters, thresholds, entry timing, stop/target selection, private combinations of rules, private data/configurations, live order submission and real trade logs.

See [strategy boundary](docs/strategy-boundary.md) for the precise public/private split.

## Validation & Reproducibility

Run the public test suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Run the synthetic harness:

```bash
PYTHONPATH=src python -m barakat_engine.run_backtest --config config/examples/public_backtest.example.json
```

Run the public verification tools:

```bash
PYTHONPATH=src python tools/verify_realised_r.py examples/sample-output/verification_trade_log.synthetic.csv
PYTHONPATH=src python tools/verify_outcomes_against_m5.py examples/sample-output/outcome_verification_log.synthetic.csv examples/data/synthetic_m5.csv
```

![Public test suite passing](https://github.com/RootFM786/ai-assisted-python-trading-engine/raw/5906aba9e65757a992070d931c49a62e2e259b59/assets/01-tests-passing.png)

![Synthetic engine run](https://github.com/RootFM786/ai-assisted-python-trading-engine/raw/5906aba9e65757a992070d931c49a62e2e259b59/assets/02-synthetic-engine-run.png)

![Synthetic verification output](https://github.com/RootFM786/ai-assisted-python-trading-engine/raw/5906aba9e65757a992070d931c49a62e2e259b59/assets/03-verification-output.png)

The examples use synthetic market data and representative output only. See [validation documentation](docs/validation.md).

## Historical Development Evidence

These selected and redacted captures are historical implementation evidence from the development process. They are not performance promises, investment advice or a basis for reproducing the private strategy.

![Historical backtest summary](https://github.com/RootFM786/ai-assisted-python-trading-engine/raw/5906aba9e65757a992070d931c49a62e2e259b59/assets/historical/historical-backtest-summary.jpg)

*Historical aggregated backtest output from iterative engine validation. Historical development evidence only; not indicative of future performance.*

![Historical multi-year validation](https://github.com/RootFM786/ai-assisted-python-trading-engine/raw/5906aba9e65757a992070d931c49a62e2e259b59/assets/historical/historical-multiyear-validation.jpg)

*Multi-year historical test summary used to assess consistency across annual samples. Historical development evidence only; not indicative of future performance.*

![Historical MT5 runtime](https://github.com/RootFM786/ai-assisted-python-trading-engine/raw/5906aba9e65757a992070d931c49a62e2e259b59/assets/historical/historical-mt5-runtime.jpg)

*MT5-connected runner processing market data during multi-instrument development testing. Historical development evidence only; not indicative of future performance.*

![Historical AI research](https://github.com/RootFM786/ai-assisted-python-trading-engine/raw/5906aba9e65757a992070d931c49a62e2e259b59/assets/historical/historical-ai-research.jpg)

*AI-assisted requirements research for external-data integration and backtest/forward-run consistency. Historical development evidence only; not indicative of future performance.*

Additional redacted material is indexed in [supporting evidence](evidence/README.md).

## Development Evolution

The preserved archive shows an evolution from requirements/specification work, through a contract-led V1 implementation, to verification tooling, research branches and a later MT5 integration layer. The public repository deliberately selects the mature engineering spine rather than presenting every experiment as one finished product.

See [development history](docs/development-history.md) and [design-process artefacts](docs/design-process/README.md).

## MT5 Integration

The `experiments/mt5-integration/` folder is a bounded, later integration branch. It demonstrates terminal initialisation, market-data access, metadata/account-query abstractions and error handling. It does **not** include credentials, terminal paths, broker/account identifiers, order placement or position-sizing logic.

See [MT5 integration notes](experiments/mt5-integration/README.md).

## Repository Structure

```text
assets/                       Clean technical visuals and redacted historical evidence
config/                       Public-safe presets and example configuration
docs/                         Architecture, contracts, validation and development history
evidence/                     Redacted supplementary historical captures
examples/                     Synthetic data and representative verification output
experiments/mt5-integration/  Credential-free MT5 connectivity/data experiment
src/barakat_engine/           Contract-led engine modules and public strategy boundary
tests/                        Deterministic public tests
tools/                        Configuration, outcome and realised-R verification utilities
```

## Skills Demonstrated

- Python packaging, modules, types and testable interfaces
- Contract-driven design and modular architecture
- Deterministic state management and time semantics
- Configuration canonicalisation, hashing and auditability
- CSV/data validation and adapter design
- Logging, diagnostics and independent verification
- Backtesting/replay infrastructure using synthetic fixtures
- Safe integration design for MT5 connectivity and market data
- AI prompting, requirements engineering, code review and validation discipline
- Iterative debugging and portfolio-safe technical communication

## Scope & Limitations

- This is a public-safe engineering reconstruction, not the full live/private system.
- It intentionally cannot reproduce private Barakat entries or exact historical trades.
- Historical screenshots are selected evidence, not complete performance reporting.
- Synthetic fixtures demonstrate deterministic mechanics; they do not represent live-market performance.
- No live trading, credentials, broker/account identifiers, private paths, raw market datasets or generated run artefacts are included.
